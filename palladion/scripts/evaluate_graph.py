"""P07 frozen synthetic B2/B3 and automatic-memory consumer pilot, not P08 accuracy."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import tempfile
import time
import uuid
from collections.abc import Callable
from contextlib import closing
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from evidence_agent.agent.llm import GroqModel, ModelTurn
from evidence_agent.agent.search_worker import search as worker_search
from evidence_agent.agent.services import configure_agent, fixture_adapter
from evidence_agent.core.bootstrap import seed
from evidence_agent.graph.relations import TraversalLimits
from evidence_agent.live.gateway import load_config
from evidence_agent.main import create_app
from evidence_agent.memory.packet import build_packet
from evidence_agent.memory.store import CaseStore
from evidence_agent.policy.bootstrap import seed_policy_fixture
from evidence_agent.retrieval.graph_expand import GraphExpansion
from evidence_agent.retrieval.hybrid import HybridSearch
from evidence_agent.retrieval.rerank import FastEmbedReranker
from evidence_agent.settings import Settings
from evidence_agent.storage.catalog import Catalog
from evidence_agent.storage.neo4j import Neo4jIndex
from evidence_agent.storage.originals import OriginalStore
from evidence_agent.storage.qdrant import QdrantIndex
from evidence_agent.storage.registry import Registry
from evidence_agent.storage.sqlite import Database

APP = Path(__file__).resolve().parents[1]
QUERIES = (
    ("S26-REVERSAL", "EX-SETTLEMENT-DELAY"),
    ("settlement timeout investigation", "EX-SETTLEMENT-DELAY"),
    ("ERR-NOTIN-CORPUS-999", None),
    ("duplicate capture verification", None),
)


class ObservedModel:
    """Forwards real calls; records input-consumption booleans, never credentials/prompts."""

    def __init__(self, model: GroqModel) -> None:
        self.model = model
        self.observations: list[dict[str, Any]] = []

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        final: bool = False,
        before_send: Callable[[], None] | None = None,
    ) -> ModelTurn:
        encoded = json.dumps(messages)
        observed: dict[str, Any] = {
            "final": final,
            "preference_present": "I prefer concise answers." in encoded,
            "old_episode_present": "P07_OLD_SESSION_CANARY" in encoded,
            "received": False,
        }
        self.observations.append(observed)
        turn = await self.model.complete(messages, tools, final=final, before_send=before_send)
        observed.update(received=True, usage=turn.usage)
        return turn


def run(url: str, *, live: bool = False, model_name: str = "openai/gpt-oss-20b") -> dict[str, Any]:
    run_id = "p07_" + uuid.uuid4().hex
    destination = APP / "runtime/evaluation" / (run_id + ".json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "run_id": run_id,
        "scope": "frozen synthetic development pilot",
        "queries_sha256": hashlib.sha256(json.dumps(QUERIES).encode()).hexdigest(),
        "graph_default": "DISABLED",
        "graph_timeout_seconds": 10,
        "top_k": 4,
        "pairs": [],
        "provider_calls": None if live else 0,
        "failures": [],
        "semantic_accuracy": "UNKNOWN",
        "runtime": None,
    }

    def save() -> None:
        destination.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    collection = run_id
    partition = run_id
    index = QdrantIndex(
        url=url, collection_name=collection, model_cache_dir=str(APP / "runtime/model_cache")
    )
    backend = Neo4jIndex(partition=partition, timeout_seconds=10)
    graph = GraphExpansion(backend, TraversalLimits(timeout_seconds=10))
    try:
        with tempfile.TemporaryDirectory(prefix="palladion-p07-") as temporary:
            root = Path(temporary)
            seed(root, APP, index, backend)
            with Database(root / "registry.sqlite") as database:
                registry = Registry(database, OriginalStore(root / "originals"))
                seed_policy_fixture(registry, APP)
                catalog = Catalog(registry)
                principal = registry.access.authenticate("reader-a")
                ranker = FastEmbedReranker(enabled=True, cache_dir=APP / "runtime/model_cache")
                b2 = HybridSearch(catalog, index, ranker)
                b3 = HybridSearch(catalog, index, ranker, graph)
                report["representation"] = index.representation_manifest
                report["reranker"] = ranker.manifest
                # Frozen paired input/scope; retain timings without a throughput claim.
                for query, expected in QUERIES:
                    reference = (
                        set(catalog.lookup_alias(principal, "case-42", expected))
                        if expected
                        else set()
                    )
                    pair: dict[str, Any] = {
                        "query": query,
                        "reference_ids": sorted(reference),
                        "conditions": {},
                    }
                    report["pairs"].append(pair)
                    for label, reader in (("B2", b2), ("B3", b3)):
                        started = time.perf_counter()
                        try:
                            result = reader.search(
                                principal, "case-42", query, mode="reranked", limit=4
                            )
                            ids = [p.citation_id for p in result.passages]
                            pair["conditions"][label] = {
                                "ids": ids,
                                "status": result.status,
                                "warnings": list(result.warnings),
                                "elapsed_ms": (time.perf_counter() - started) * 1000,
                                "expected_recovered": bool(reference.intersection(ids))
                                if reference
                                else None,
                                "path_count": len(result.graph_paths),
                                "stage_counts": result.stage_counts,
                            }
                        except Exception as error:
                            pair["conditions"][label] = {
                                "status": "FAILED",
                                "error_type": type(error).__name__,
                            }
                            report["failures"].append(
                                {"stage": label, "query": query, "error_type": type(error).__name__}
                            )
                        save()
                started = time.perf_counter()

                async def owned_search() -> Any:
                    async with asyncio.timeout(60):
                        return await worker_search(
                            b3, "reader-a", "case-42", "S26-REVERSAL", "hybrid", 2
                        )

                worker = asyncio.run(owned_search())
                report["worker"] = {
                    "status": worker.status,
                    "path_count": len(worker.graph_paths),
                    "warnings": list(worker.warnings),
                    "elapsed_ms": (time.perf_counter() - started) * 1000,
                    "citation_readback": all(
                        b3.resolver.resolve(principal, "case-42", p.citation_id).text == p.text
                        for p in worker.passages
                    ),
                }
                report["graph_records"] = {
                    table: database.connection.execute("SELECT count(*) FROM " + table).fetchone()[
                        0
                    ]
                    for table in (
                        "graph_entity_attestations",
                        "graph_relations",
                        "graph_relation_reviews",
                        "graph_merge_decisions",
                    )
                }
                report["identity_review_effort"] = (
                    "synthetic registered structural links; no independent human adjudication"
                )
                gains = sum(
                    p["conditions"].get("B3", {}).get("expected_recovered") is True
                    and p["conditions"].get("B2", {}).get("expected_recovered") is False
                    for p in report["pairs"]
                )
                report["incremental_exception_recoveries"] = gains
                report["retention_decision"] = (
                    "DISABLED: small development fixture does not justify default graph cost"
                )
                report["selected_miss_limit"] = (
                    "Registered exception is already B2 context-linked; no fabricated novel recovery. Two-hop controlled-anchor recovery is a separate integration control."
                )
            observed = (
                ObservedModel(
                    GroqModel.from_env_file(
                        APP.parent / ".env",
                        enabled=True,
                        model=model_name,
                        call_interval_seconds=10,
                    )
                )
                if live
                else None
            )
            application = create_app(
                root, index, {"p07-reader": "reader-a", "p07-admin": "admin-a"}, ranker, graph
            )
            configure_agent(
                application,
                model=observed,
                adapter=fixture_adapter(APP),
                config=load_config(APP / "config/adapters.yaml"),
                settings=Settings.model_validate({"enable_live_llm":live,"model":model_name,
                    "graph_enabled":True,"graph_timeout_seconds":10.0}),
            )
            headers = {"Authorization": "Bearer p07-reader"}
            with TestClient(application) as client:
                response = client.post(
                    "/search",
                    headers=headers,
                    json={"case_id": "case-42", "query": "S26-REVERSAL", "limit": 2},
                )
                report["api_graph"] = {
                    "http_status": response.status_code,
                    "paths": len(response.json().get("graph_paths", [])),
                }
                if live:
                    # First actual message automatically stores the preference through CaseStore.
                    first = client.post(
                        "/v1/cases/case-42/messages",
                        headers=headers,
                        json={"query": "I prefer concise answers."},
                    )
                    if first.status_code != 200:
                        raise RuntimeError("First real memory message failed")
                    first_data = first.json()
                    with Database(root / "registry.sqlite") as database:
                        registry = Registry(database, OriginalStore(root / "originals"))
                        store = CaseStore(
                            registry,
                            registry.access.authenticate("reader-a"),
                            "case-42",
                            first_data["session_id"],
                        )
                        store.append("REQUEST", "p07-episode", {"query": "P07_OLD_SESSION_CANARY"})
                    session = client.post("/v1/cases/case-42/sessions", headers=headers).json()[
                        "session_id"
                    ]
                    assert observed is not None
                    boundary = len(observed.observations)
                    second = client.post(
                        "/v1/cases/case-42/messages",
                        headers=headers,
                        json={
                            "session_id": session,
                            "query": "Search approved S26-REVERSAL with limit 2 and quote a short exact source passage. No operational permission.",
                        },
                    )
                    output = second.json()
                    citation_reads=[client.get("/v1/evidence/"+citation["evidence_id"],
                        params={"case_id":"case-42"},headers=headers).status_code==200
                        for citation in output.get("citations",[])]
                    with Database(root / "registry.sqlite") as database:
                        registry = Registry(database, OriginalStore(root / "originals"))
                        store = CaseStore(
                            registry, registry.access.authenticate("reader-a"), "case-42", session
                        )
                        packet = build_packet(store, "follow up")
                        report["runtime"] = {
                            "http_status": second.status_code,
                            "model": model_name,
                            "second_turn_attempts": observed.observations[boundary:],
                            "first_budget": first_data["budget"],
                            "second_budget": output.get("budget"),
                            "tool_status": output.get("tool_status"),
                            "verification_failures": output.get("verification_failures"),
                            "disposition": output.get("disposition"),
                            "citation_count":len(citation_reads),
                            "all_citations_read_back":bool(citation_reads) and all(citation_reads),
                            "original_preference_read_back": any(
                                f.statement == "I prefer concise answers."
                                for f in packet.reported_facts
                            ),
                            "old_episode_absent": "P07_OLD_SESSION_CANARY"
                            not in packet.model_dump_json(),
                            "provider_failure": observed.model.last_failure,
                            "rate_limits": observed.model.last_rate_limits,
                        }
                save()
                if observed is not None:
                    report["model_invocations"] = len(observed.observations)
                    report["received_model_responses"] = sum(
                        o["received"] for o in observed.observations
                    )
            report["completed"] = True
    except Exception as error:
        report["failures"].append({"stage": "pilot", "error_type": type(error).__name__})
        raise
    finally:
        save()
        index.close()
        # Only this command's newly created synthetic UUID resources are removed.
        try:
            with closing(QdrantClient(url=url, timeout=30)) as cleanup:
                if cleanup.collection_exists(collection):
                    cleanup.delete_collection(collection)
            cleanup_graph = Neo4jIndex(partition=partition, timeout_seconds=10)
            try:
                cleanup_graph._run("MATCH(n) WHERE n.partition=$partition DETACH DELETE n")
            finally:
                cleanup_graph.close()
        finally:
            backend.close()
    return {
        "report": str(destination),
        "completed": report.get("completed", False),
        "incremental_exception_recoveries": report.get("incremental_exception_recoveries"),
        "runtime": report["runtime"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", required=True)
    parser.add_argument("--url", default="http://127.0.0.1:16333")
    parser.add_argument("--enable-live-llm", action="store_true")
    parser.add_argument("--model", choices=GroqModel.allowed_models, default="openai/gpt-oss-20b")
    args = parser.parse_args()
    print(json.dumps(run(args.url, live=args.enable_live_llm, model_name=args.model), indent=2))


if __name__ == "__main__":
    main()
