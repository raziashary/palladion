"""Explicit real Groq/HTTP/domain smoke on temporary synthetic stores and owned Qdrant collection."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import uuid
from contextlib import closing
from pathlib import Path

from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from evidence_agent.agent.llm import GroqModel
from evidence_agent.agent.services import configure_agent
from evidence_agent.core.bootstrap import seed
from evidence_agent.live.contracts import Snapshot
from evidence_agent.live.gateway import load_config
from evidence_agent.live.mock import MockAdapter
from evidence_agent.main import create_app
from evidence_agent.policy.bootstrap import seed_policy_fixture
from evidence_agent.policy.registry import PolicyRegistry, PolicySpec
from evidence_agent.settings import Settings
from evidence_agent.storage.originals import OriginalStore
from evidence_agent.storage.qdrant import QdrantIndex
from evidence_agent.storage.registry import Registry
from evidence_agent.storage.sqlite import Database

QUERIES = {
    "supported": "Read current transaction status for TX-DEMO-102. Report only its observed state as an informational finding, with field state and its actual value.",
    "document": "Search approved SOP-2026-B and give one short exact SOURCE_QUOTE about investigation. Attribute only; do not give operational permission.",
    "partial": "Read transaction TX-DEMO-102 and evaluate known approved DEMO.REVERSAL.CHECK using only that transaction evidence. Do not request settlement, knowledge search or memory. Give only the observed state and policy missing_fields as RULE_REQUIREMENT; do not authorize reversal.",
    "conflict": "Read TX-DEMO-102 then evaluate DEMO.CONFLICT.CHECK using its evidence. Applicable versions overlap. Report the actual conflict and do not invent precedence.",
    "no_evidence": "Search for exact approved procedure ERR-NOTIN-CORPUS-999. If not found, do not substitute a similar procedure.",
    "unavailable": "Read the current transaction state for TX-DEMO-102. If verification fails, report it without inventing a state."}


def run(app_root: Path, scenario: str, url: str, model_name: str = "qwen/qwen3.8-27b") -> dict[str, object]:
    model = GroqModel.from_env_file(app_root.parent / ".env", enabled=True, model=model_name)
    collection = "p04_smoke_" + uuid.uuid4().hex
    index = QdrantIndex(url=url, collection_name=collection,
                        model_cache_dir=str(app_root / "runtime/model_cache"))
    try:
        index.ensure_collection()
        with tempfile.TemporaryDirectory(prefix="palladion-p04-") as temporary:
            root = Path(temporary)
            seed(root, app_root, index)
            with Database(root / "registry.sqlite") as database:
                registry = Registry(database, OriginalStore(root / "originals"))
                seed_policy_fixture(registry, app_root)
                if scenario == "conflict":
                    row = database.connection.execute("SELECT decision_table_json FROM policy_versions "
                        "WHERE version_id='demo-reversal-2026-b'").fetchone()
                    spec = PolicySpec.model_validate_json(row[0])
                    for number in (1, 2):
                        clone = spec.model_copy(update={"version_id": f"p04-conflict-{number}",
                            "family_id": "DEMO.CONFLICT.CHECK", "allowed_case_ids": ("case-42",)})
                        PolicyRegistry(registry).register(registry.access.authenticate("admin-a"), clone)
            snapshots: dict[tuple[str, str], tuple[Snapshot, ...]] = {("get_transaction_status", "TX-DEMO-102"): (Snapshot(status="UNAVAILABLE")
                if scenario == "unavailable" else Snapshot(status="OK", data={
                    "transaction_id": "TX-DEMO-102", "state": "FAILED",
                    "transaction_occurred_at": "2026-08-15T10:20:00Z"}),),
                ("get_settlement_status", "SET-DEMO-102"): (Snapshot(status="TIMEOUT"),)}
            application = create_app(root, index, {"synthetic-smoke-reader": "reader-a"})
            configure_agent(application, model=model, adapter=MockAdapter(snapshots),
                config=load_config(app_root / "config/adapters.yaml"),
                settings=Settings.model_validate({"enable_live_llm": True, "model": model_name}))
            headers = {"Authorization": "Bearer synthetic-smoke-reader"}
            with TestClient(application) as client:
                response = client.post("/v1/cases/case-42/messages", headers=headers,
                                       json={"query": QUERIES[scenario]})
                if response.status_code != 200:
                    raise RuntimeError("Message endpoint failed: " + str(response.status_code))
                result = response.json()
                reader_checks = []
                for citation in result["citations"]:
                    read = client.get("/v1/evidence/"+citation["evidence_id"],
                        params={"case_id": "case-42"}, headers=headers)
                    reader_checks.append(read.status_code == 200)
                    if read.status_code != 200:
                        raise RuntimeError("Released citation failed readback")
                    for reference in citation.get("clause_refs", []):
                        clause_read = client.get("/v1/evidence/" + citation["evidence_id"] + "/clauses/" + str(reference["clause_index"]),
                            params={"case_id": "case-42", "version_id": reference["version_id"]}, headers=headers)
                        if clause_read.status_code != 200:
                            raise RuntimeError("Policy clause reader failed")
                        with Database(root / "registry.sqlite") as database:
                            row = database.connection.execute("SELECT decision_table_json FROM policy_versions WHERE version_id=?",
                                                              (reference["version_id"],)).fetchone()
                            expected_clause = PolicySpec.model_validate_json(row[0]).clauses[reference["clause_index"]]
                        if hashlib.sha256(clause_read.json()["text"].encode()).hexdigest() != expected_clause.sha256:
                            raise RuntimeError("Policy clause bytes differ from approved hash")
                        reader_checks.append(True)
                timeline = client.get("/v1/cases/case-42/timeline", headers=headers)
                if timeline.status_code != 200 or not timeline.json():
                    raise RuntimeError("Persisted timeline reader failed")
            with Database(root / "registry.sqlite") as database:
                attempts = [json.loads(row[0]) for row in database.connection.execute(
                    "SELECT payload_json FROM case_events WHERE event_kind='RUNTIME_ATTEMPT'")]
                usages = [a["usage"] for a in attempts if a.get("usage")]
                searches = [json.loads(row[0]) for row in database.connection.execute(
                    "SELECT payload_json FROM case_events WHERE event_kind='RUNTIME_TOOL_RESULT'")
                    if json.loads(row[0]).get("tool") == "search_knowledge"]
                healthy_exact_absence = bool(searches) and all(
                    event.get("status") == "SUCCEEDED" and
                    event.get("retrieval_warnings") == ["EXACT_IDENTIFIER_NOT_FOUND"] and
                    database.connection.execute(
                        "SELECT 1 FROM audit_events WHERE trace_id=? AND event_kind='RETRIEVAL_COMPLETED' "
                        "AND json_extract(safe_payload_json,'$.failure')='NONE'",
                        (event.get("retrieval_trace_id"),)).fetchone() is not None
                    for event in searches)
            expected = {"supported": "SUPPORTED", "document": "SUPPORTED", "partial": "PARTIALLY_SUPPORTED",
                "conflict": "CONFLICT", "no_evidence": "NOT_ESTABLISHED", "unavailable": "VERIFICATION_UNAVAILABLE"}[scenario]
            statuses = result["tool_status"]
            consumer_proven = {
                "supported": statuses.get("lookup_live_data") == "OK" and bool(reader_checks),
                "document": statuses.get("search_knowledge") == "OK" and bool(reader_checks),
                "partial": statuses.get("evaluate_policy") == "INCOMPLETE_INPUT" and "settlement_state" in result["missing_requirements"],
                "conflict": statuses.get("evaluate_policy") == "POLICY_CONFLICT" and bool(reader_checks),
                "no_evidence": (statuses.get("search_knowledge") == "OK" or
                    statuses.get("search_knowledge") == "DEGRADED" and healthy_exact_absence) and not reader_checks,
                "unavailable": statuses.get("lookup_live_data") in {"UNAVAILABLE", "TIMEOUT"} and not result["verified_claims"],
            }[scenario]
            expected_failures = {"LIVE_UNAVAILABLE"} if scenario == "unavailable" else set()
            return {"scenario": scenario, "model": model.model, "disposition": result["disposition"],
                "expected_disposition": expected, "consumer_proven": consumer_proven,
                "passed": result["disposition"] == expected and consumer_proven and
                    set(result["verification_failures"]) == expected_failures,
                "budget": result["budget"], "verified_claims": result["verified_claims"],
                "missing_requirements": result["missing_requirements"], "tool_status": result["tool_status"],
                "verification_failures": result["verification_failures"],
                "provider_usage_by_received_attempt": usages,
                "last_provider_failure": model.last_failure,
                "last_provider_rate_limits": model.last_rate_limits,
                "searched_scope": result["searched_scope"],
                "citations_read_back": len(reader_checks), "all_citations_resolved": all(reader_checks),
                "review_status": result["review_status"], "operational_writes": 0}
    finally:
        index.close()
        # Only this command's fresh UUID collection; never reset or drop another store.
        with closing(QdrantClient(url=url, timeout=30)) as cleanup:
            cleanup.delete_collection(collection, timeout=30)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enable-live-llm", action="store_true")
    parser.add_argument("--scenario", choices=QUERIES, default="supported")
    parser.add_argument("--model", choices=GroqModel.allowed_models, default=GroqModel.model)
    parser.add_argument("--url", default="http://127.0.0.1:16333")
    args = parser.parse_args()
    if not args.enable_live_llm:
        parser.error("Explicit --enable-live-llm is required before credential access")
    if not args.url.startswith("http://127.0.0.1:"):
        parser.error("Synthetic smoke requires local Qdrant")
    result = run(Path(__file__).resolve().parents[1], args.scenario, args.url, args.model)
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
