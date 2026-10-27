"""Run the explicitly enabled, retrieval-only P02 synthetic pilot."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import statistics
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from qdrant_client import QdrantClient

from evidence_agent.core.bootstrap import seed
from evidence_agent.core.errors import PermissionDenied, ResourceConflict
from evidence_agent.core.evaluation import macro_average, score_ranked_references
from evidence_agent.core.fixtures import load_fixtures
from evidence_agent.core.models import Principal
from evidence_agent.retrieval.hybrid import HybridSearch
from evidence_agent.retrieval.rerank import FastEmbedReranker
from evidence_agent.storage.applicability import Applicability
from evidence_agent.storage.catalog import Catalog
from evidence_agent.storage.originals import OriginalStore
from evidence_agent.storage.qdrant import QdrantIndex
from evidence_agent.storage.registry import Registry
from evidence_agent.storage.sqlite import Database

APP_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = APP_ROOT / "data" / "demo"
REPORT_PATH = APP_ROOT / "runtime" / "evaluation" / "p02-pilot.json"
PILOT_PATH = DATA_ROOT / "retrieval_pilot.json"
Bm25Profile = Literal["english", "no_stemming"]
IndexMode = Literal["lexical", "dense", "hybrid"]
SearchMode = Literal["hybrid", "reranked"]
BM25_PROFILES: tuple[Bm25Profile, ...] = ("english", "no_stemming")
TOP_K = 20


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonicalize(
    search: HybridSearch,
    principal: Principal,
    case_id: str,
    hits: tuple[Any, ...],
    as_of: datetime | None,
) -> tuple[list[str], int]:
    ids: list[str] = []
    excluded = 0
    for hit in hits:
        try:
            search.resolver.resolve(principal, case_id, hit.chunk_id, generation=hit.generation,
                                    applicability=Applicability.at(as_of) if as_of else None)
        except (PermissionDenied, ResourceConflict):
            excluded += 1
            continue
        if hit.chunk_id not in ids:
            ids.append(hit.chunk_id)
    return ids, excluded


def _reference_ids(
    references: list[dict[str, str]], catalog: Catalog, admin: Principal, case_id: str
) -> list[str]:
    ids: list[str] = []
    for reference in references:
        ids.extend(hit.chunk_id for hit in catalog.alias_hits(admin, case_id, reference["clause_id"]))
    return list(dict.fromkeys(ids))


class _ObservedRanker:
    def __init__(self, ranker: FastEmbedReranker) -> None:
        self.ranker = ranker
        self.last: dict[str, Any] | None = None

    @property
    def max_candidates(self) -> int:
        return self.ranker.max_candidates

    def rank(self, query: str, chunks: Any) -> tuple[Any, ...]:
        started = time.perf_counter()
        ordered = self.ranker.rank(query, chunks)
        elapsed_ms = (time.perf_counter() - started) * 1000
        self.last = {
            "input_ids": [chunk.chunk_id for chunk in chunks],
            "ranked_ids": [chunk.chunk_id for chunk in ordered],
            "candidate_count": len(chunks),
            "elapsed_ms": elapsed_ms,
        }
        return ordered


def _failed_stage(error: Exception) -> dict[str, Any]:
    return {"status": "ERROR", "error_type": type(error).__name__, "error": str(error),
            "raw_ids": [], "ranked_ids": [], "candidate_count": None,
            "canonical_excluded_count": None, "elapsed_ms": None}


def _score_or_missing(expected: list[str], ranked: list[str], failed: bool) -> dict[str, float | None]:
    if failed:
        return {key: None for key in score_ranked_references(expected, ())}
    return score_ranked_references(expected, ranked)


def _pilot_case(
    case: dict[str, Any],
    *,
    profile: Bm25Profile,
    index: QdrantIndex,
    catalog: Catalog,
    principals: dict[str, Principal],
    expected_lookup: dict[str, list[str]],
    ranker: _ObservedRanker,
    expected_clause_texts: dict[str, str],
) -> dict[str, Any]:
    principal = principals[case["principal_id"]]
    case_id = case["case_id"]
    as_of = datetime.fromisoformat(case["as_of"]) if case.get("as_of") else None
    gold_ids = expected_lookup[case["query_id"]]
    result: dict[str, Any] = {
        "query_id": case["query_id"], "case_id": case_id,
        "principal_id": principal.principal_id, "language": case["language"],
        "query": case["query"], "as_of": case.get("as_of"), "slice": case["slice"],
        "expected_clause_refs": case["expected"], "expected_chunk_ids": gold_ids,
        "stages": {}, "metrics": {},
    }
    service = HybridSearch(catalog, index)
    reranked_service = HybridSearch(catalog, index, ranker)
    stage_specs: tuple[tuple[str, IndexMode, bool], ...] = (
        ("lexical", "lexical", False),
        ("dense_ann", "dense", False),
        ("dense_exact", "dense", True),
        ("hybrid", "hybrid", False),
    )
    for name, index_mode, exact in stage_specs:
        started = time.perf_counter()
        try:
            hits = index.query(case["query"], principal, case_id, mode=index_mode,
                               limit=TOP_K, exact=exact)
            elapsed_ms = (time.perf_counter() - started) * 1000
            canonical_ids, excluded = _canonicalize(service, principal, case_id, hits, as_of)
            result["stages"][name] = {
                "status": "OK", "raw_ids": [hit.chunk_id for hit in hits],
                "ranked_ids": canonical_ids, "candidate_count": len(hits),
                "canonical_excluded_count": excluded, "elapsed_ms": elapsed_ms,
            }
        except Exception as error:  # retain the failure as a measurement outcome
            result["stages"][name] = _failed_stage(error)
        result["metrics"][name] = _score_or_missing(
            gold_ids, result["stages"][name]["ranked_ids"],
            result["stages"][name]["status"] != "OK")

    service_specs: tuple[tuple[str, SearchMode, HybridSearch], ...] = (
        ("hybrid_exact_union", "hybrid", service),
        ("expanded", "reranked", reranked_service),
    )
    for name, search_mode, target_service in service_specs:
        if search_mode == "reranked":
            ranker.last = None
        started = time.perf_counter()
        try:
            search_result = target_service.search(
                principal, case_id, case["query"], mode=search_mode, limit=12, as_of=as_of)
            result["stages"][name] = {
                "status": search_result.status,
                "warnings": list(search_result.warnings),
                "ranked_ids": [passage.citation_id for passage in search_result.passages],
                "passages": [passage.model_dump(mode="json") for passage in search_result.passages],
                "stage_counts": search_result.stage_counts,
                "candidate_count": search_result.stage_counts.get("discovered"),
                "canonical_excluded_count": None,
                "elapsed_ms": (time.perf_counter() - started) * 1000,
            }
            if search_mode == "reranked":
                reranker_result = ranker.last
                result["stages"]["reranked"] = {
                    "status": search_result.status,
                    "ranked_ids": (reranker_result["ranked_ids"]
                                   if reranker_result is not None else []),
                    "input_ids": (reranker_result["input_ids"]
                                  if reranker_result is not None else []),
                    "candidate_count": (reranker_result["candidate_count"]
                                        if reranker_result is not None else None),
                    "elapsed_ms": (reranker_result["elapsed_ms"]
                                   if reranker_result is not None else None),
                    "failure": "RERANK_RESULT_UNAVAILABLE" if reranker_result is None else None,
                }
                result["stages"][name]["service"] = {
                    "stage_counts": search_result.stage_counts,
                    "warnings": list(search_result.warnings),
                }
            result["metrics"][name] = _score_or_missing(
                gold_ids, result["stages"][name]["ranked_ids"],
                result["stages"][name]["status"] == "ERROR")
            if search_mode == "reranked":
                result["metrics"]["reranked"] = _score_or_missing(
                    gold_ids, result["stages"]["reranked"]["ranked_ids"],
                    result["stages"]["reranked"]["status"] == "ERROR")
        except Exception as error:
            result["stages"][name] = _failed_stage(error)
            result["stages"][name]["reranker"] = ranker.last
            if search_mode == "reranked":
                reranker_result = ranker.last
                result["stages"]["reranked"] = (
                    {"status": "ERROR", "error_type": "RERANK_FAILURE",
                     "ranked_ids": [], "candidate_count": None, "elapsed_ms": None}
                    if reranker_result is None else
                    {"status": "OK", **reranker_result})
                result["metrics"]["reranked"] = _score_or_missing(gold_ids, [],
                                                                      reranker_result is None)
            result["metrics"][name] = _score_or_missing(gold_ids, [], True)

    for name, metrics in result["metrics"].items():
        if ("exception" in case["slice"] and gold_ids
                and result["stages"][name]["status"] != "ERROR"):
            metrics["exception_recall"] = metrics["recall_at_20"]
        else:
            metrics["exception_recall"] = None

    ann = result["stages"]["dense_ann"]
    exact = result["stages"]["dense_exact"]
    if ann["status"] == "OK" and exact["status"] == "OK":
        exact_ids = set(exact["ranked_ids"])
        overlap = (len(set(ann["ranked_ids"]) & exact_ids) / len(exact_ids)
                   if exact_ids else None)
    else:
        overlap = None
    result["dense_ann_vs_exact_overlap_at_20"] = {
        "value": overlap, "ann_count": len(ann["ranked_ids"]),
        "exact_count": len(exact["ranked_ids"]),
        "denominator": len(exact["ranked_ids"]),
    }

    if case.get("exact_identifier"):
        hybrid = result["stages"]["hybrid_exact_union"]
        expected_behavior = case["exact_expected"]
        if expected_behavior == "hit":
            success = bool(set(gold_ids) & set(hybrid["ranked_ids"]))
        elif expected_behavior == "unknown":
            success = ("EXACT_IDENTIFIER_NOT_FOUND" in hybrid.get("warnings", [])
                       and not hybrid["ranked_ids"])
        else:
            restricted = case["restricted_reference"]
            restricted_id = expected_lookup[f"restricted:{restricted['clause_id']}"]
            success = not set(restricted_id) & set(hybrid["ranked_ids"])
            restricted_text = expected_clause_texts[restricted["clause_id"]]
            result["restricted_text_leak"] = any(
                restricted_text.casefold() in passage["text"].casefold()
                for passage in hybrid.get("passages", [])
            )
            success = success and not result["restricted_text_leak"]
        result["exact_identifier_result"] = {
            "identifier": case["exact_identifier"], "expected": expected_behavior,
            "success": success,
        }
    else:
        result["exact_identifier_result"] = None
    return result


def _run_profile(url: str, profile: Bm25Profile, pilot: dict[str, Any], bundle: Any,
                 expected_clause_texts: dict[str, str]) -> dict[str, Any]:
    collection = f"p02_eval_{profile}_{uuid.uuid4().hex}"
    index_client = QdrantClient(url=url, timeout=10)
    cleanup_client = QdrantClient(url=url, timeout=10)
    created = False
    index = QdrantIndex(url=url, collection_name=collection, bm25_profile=profile,
                        client=index_client)
    try:
        if cleanup_client.collection_exists(collection):
            raise RuntimeError(f"generated collection name already exists: {collection}")
        index.ensure_collection()
        created = True
        with tempfile.TemporaryDirectory(prefix="p02-eval-") as temporary:
            runtime_root = Path(temporary)
            seed(runtime_root, APP_ROOT, index)
            if not cleanup_client.collection_exists(collection):
                raise RuntimeError("seed removed the evaluator-owned Qdrant collection")
            with (runtime_root / "registry.sqlite").open("rb") as stream:
                sqlite_sha256 = hashlib.sha256(stream.read()).hexdigest()
            with Database(runtime_root / "registry.sqlite") as database:
                registry = Registry(database, OriginalStore(runtime_root / "originals"))
                catalog = Catalog(registry)
                principals = {
                    principal.principal_id: registry.access.authenticate(principal.principal_id)
                    for principal in bundle.principals
                }
                admin = principals["admin-a"]
                expected_lookup: dict[str, list[str]] = {}
                for case in pilot["queries"]:
                    expected_lookup[case["query_id"]] = _reference_ids(
                        case["expected"], catalog, admin, case["case_id"])
                    if case.get("restricted_reference"):
                        reference = case["restricted_reference"]
                        expected_lookup[f"restricted:{reference['clause_id']}"] = _reference_ids(
                            [reference], catalog, admin, case["case_id"])
                ranker = _ObservedRanker(FastEmbedReranker(enabled=True))
                before = index.health()
                cases = [
                    _pilot_case(
                        case, profile=profile, index=index, catalog=catalog,
                        principals=principals, expected_lookup=expected_lookup,
                        ranker=ranker, expected_clause_texts=expected_clause_texts)
                    for case in pilot["queries"]
                ]
                after = index.health()
                exact_id_rows = [case for case in cases if case["exact_identifier_result"] is not None]
                per_stage = {}
                stage_names = tuple(cases[0]["metrics"])
                for stage in stage_names:
                    per_stage[stage] = {
                        "overall": macro_average(case["metrics"][stage] for case in cases),
                        "language": {
                            language: macro_average(case["metrics"][stage] for case in cases
                                                    if case["language"] == language)
                            for language in sorted({case["language"] for case in cases})
                        },
                        "slices": {
                            label: macro_average(case["metrics"][stage] for case in cases
                                                 if label in case["slice"])
                            for label in sorted({label for case in cases for label in case["slice"]})
                        },
                        "scored_case_count": sum(
                            case["metrics"][stage]["mrr"] is not None for case in cases),
                        "pilot_case_count": len(cases),
                    }
                timings = [case["stages"][stage]["elapsed_ms"] for case in cases
                           for stage in case["stages"]
                           if case["stages"][stage]["elapsed_ms"] is not None]
                return {
                    "collection": collection,
                    "bm25_profile": profile,
                    "representation": index.representation_manifest,
                    "fingerprint": index.fingerprint,
                    "sqlite_sha256": sqlite_sha256,
                    "index_health_before": before,
                    "index_health_after": after,
                    "indexed_vectors_count_disclosure": {
                        "value": after.get("indexed_vectors_count"),
                        "points_count": after.get("points_count"),
                        "small_collection_note": (
                            "Qdrant may scan a small collection without a built HNSW segment; "
                            "the reported health value is retained and no ANN speed/recall "
                            "claim is made from this tiny pilot."),
                    },
                    "reranker": ranker.ranker.manifest,
                    "metric_definitions": {
                        "relevance": "Every expected canonical chunk has binary gain 1; all others 0.",
                        "recall_at_k": "Unique expected chunk IDs found in the first K unique canonical results / expected chunk IDs.",
                        "mrr": "Reciprocal rank of first expected canonical chunk; zero when an applicable query has no hit.",
                        "ndcg_at_k": "DCG with binary relevance / ideal DCG; duplicate ranked IDs are removed before scoring.",
                        "empty_expected_set": "Metrics are null and excluded from macro averages, not treated as zero.",
                        "exact_id_success": "Known ID resolves to expected canonical chunk; unknown ID is explicitly rejected; restricted ID returns no restricted passage or full clause text.",
                        "ann_overlap_at_20": "Canonical, time-eligible ANN dense top 20 intersection with exact dense top 20 / exact eligible top-20 count; null for an empty exact set.",
                        "aggregation": "Unweighted macro mean over cases with a non-empty gold denominator; pilot only.",
                        "exception_recall": "Recall@20 on the source-clause-anchored exception query only; null on other cases.",
                    },
                    "exact_identifier_cases": {
                        "success_count": sum(row["exact_identifier_result"]["success"] for row in exact_id_rows),
                        "denominator": len(exact_id_rows),
                        "results": [row["exact_identifier_result"] for row in exact_id_rows],
                    },
                    "timing_summary_ms": {
                        "observation_count": len(timings),
                        "mean": statistics.fmean(timings) if timings else None,
                        "p50": statistics.median(timings) if timings else None,
                        "max": max(timings) if timings else None,
                        "scope": "Per-query component calls; includes canonicalized direct stages and service calls; local synthetic CPU/Qdrant only.",
                    },
                    "metrics_by_stage": per_stage,
                    "observed_misses": [
                        {"query_id": case["query_id"], "stage": stage,
                         "missing_expected_chunk_ids": sorted(
                             set(case["expected_chunk_ids"]) - set(case["stages"][stage]["ranked_ids"]))}
                        for case in cases for stage in case["stages"]
                        if case["expected_chunk_ids"]
                        and case["stages"][stage]["status"] != "ERROR"
                        and set(case["expected_chunk_ids"]) - set(case["stages"][stage]["ranked_ids"])
                    ],
                    "cases": cases,
                }
    finally:
        try:
            if created and cleanup_client.collection_exists(collection):
                cleanup_client.delete_collection(collection_name=collection)
        finally:
            index.close()
            cleanup_client.close()


def _safe_run_profile(url: str, profile: Bm25Profile, pilot: dict[str, Any], bundle: Any,
                      expected_clause_texts: dict[str, str]) -> dict[str, Any]:
    try:
        return _run_profile(url, profile, pilot, bundle, expected_clause_texts)
    except Exception as error:
        return {"bm25_profile": profile, "status": "ERROR",
                "error_type": type(error).__name__, "error": str(error),
                "measurements": None}


def run(url: str) -> dict[str, Any]:
    pilot = json.loads(PILOT_PATH.read_text(encoding="utf-8"))
    if pilot.get("schema_version") != 1 or pilot.get("annotation_status") != "PILOT":
        raise ValueError("retrieval pilot must declare schema version 1 and PILOT annotation status")
    bundle = load_fixtures(APP_ROOT)
    source_by_id = bundle.source_map()
    for case in pilot["queries"]:
        if case["principal_id"] not in bundle.principal_map():
            raise ValueError(f"unknown pilot principal in {case['query_id']}")
        if case["case_id"] not in bundle.case_map():
            raise ValueError(f"unknown pilot case in {case['query_id']}")
        for reference in case.get("expected", []) + ([case["restricted_reference"]]
                                                        if case.get("restricted_reference") else []):
            source = source_by_id[reference["source_id"]]
            if reference["clause_id"] not in source.clauses:
                raise ValueError(f"unknown source clause in {case['query_id']}: {reference}")
            if source.approval_state != "APPROVED":
                raise ValueError(f"pilot gold must name an approved source: {case['query_id']}")
    expected_clause_texts = {
        reference["clause_id"]: source_by_id[reference["source_id"]].clauses[
            reference["clause_id"]].text
        for case in pilot["queries"] if case.get("restricted_reference")
        for reference in [case["restricted_reference"]]
    }
    sources = [source for source in bundle.sources if source.approval_state == "APPROVED"]
    corpus_paths = [APP_ROOT / "data" / "demo" / source.path.removeprefix("data/demo/")
                    for source in sources]
    corpus_digest = hashlib.sha256("".join(
        f"{path.name}:{_sha256(path)}\n" for path in sorted(corpus_paths)
    ).encode("utf-8")).hexdigest()
    run_id = f"p02-pilot-{uuid.uuid4().hex}"
    profiles = [_safe_run_profile(url, profile, pilot, bundle, expected_clause_texts)
                for profile in BM25_PROFILES]
    return {
        "schema_version": 1,
        "run_id": run_id,
        "run_label": "retrieval-substrate-pilot",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PILOT_ONLY" if all(
            item.get("status") != "ERROR"
            and all(stage["status"] != "ERROR" for case in item.get("cases", [])
                    for stage in case["stages"].values())
            and all(case["exact_identifier_result"] is None or case["exact_identifier_result"]["success"]
                    for case in item.get("cases", []))
            for item in profiles)
        else "INCOMPLETE_FAILURE_RECORDED",
        "scope": "Retrieval-only lexical/hybrid/reranked-context substrate. No generative model, answer arms, graph, production data, or held-out claim.",
        "limitations": [
            "Synthetic fixture labels are PILOT and lack independent human adjudication.",
            "Indonesian queries target English source documents; this does not measure Indonesian-document retrieval.",
            "The eight bounded queries do not establish generalized language, temporal, security, or retrieval quality.",
            "Small collection state may not exercise HNSW; actual index-health counts are reported per profile.",
            "BM25 profile comparison is descriptive development evidence only; no generalized winner is claimed.",
        ],
        "environment": {
            "python": platform.python_version(),
            "qdrant_client": importlib.metadata.version("qdrant-client"),
            "qdrant_server_url": url,
            "app_version": "0.1.0",
        },
        "corpus": {
            "approved_source_ids": [source.source_id for source in sources],
            "approved_source_count": len(sources),
            "source_hashes": {source.source_id: source.sha256 for source in sources},
            "approved_source_files_sha256": corpus_digest,
            "pilot_definition_sha256": _sha256(PILOT_PATH),
            "fixture_catalog_sha256": _sha256(DATA_ROOT / "sample_cases.json"),
            "settings_sha256": _sha256(APP_ROOT / "config" / "settings.yaml"),
            "evaluator_sha256": _sha256(Path(__file__).resolve()),
            "metric_module_sha256": _sha256(APP_ROOT / "src" / "evidence_agent" / "core"
                                               / "evaluation.py"),
            "annotation_status": bundle.annotation_status,
            "pilot_query_count": len(pilot["queries"]),
            "query_languages": dict((language, sum(case["language"] == language
                                                     for case in pilot["queries"]))
                                    for language in sorted({case["language"]
                                                            for case in pilot["queries"]})),
            "query_scope": sorted({case["case_id"] for case in pilot["queries"]}),
        },
        "profiles": profiles,
    }


def run_memory(url: str, model_name: str, call_interval_seconds: float = 0) -> dict[str, Any]:
    """Fixed pilot: identical saved history, sources and live state; only memory varies."""
    import shutil
    import sqlite3
    from contextlib import closing

    from fastapi.testclient import TestClient

    from evidence_agent.agent.llm import GroqModel
    from evidence_agent.agent.preflight import preflight
    from evidence_agent.agent.services import configure_agent
    from evidence_agent.core.evaluation import score_continuation
    from evidence_agent.live.contracts import Snapshot
    from evidence_agent.live.gateway import load_config
    from evidence_agent.live.mock import MockAdapter
    from evidence_agent.main import create_app
    from evidence_agent.memory.store import CaseStore, MemorySpec
    from evidence_agent.policy.bootstrap import seed_policy_fixture
    from evidence_agent.settings import Settings

    if not url.startswith("http://127.0.0.1:"):
        raise ValueError("Memory pilot requires an explicitly local Qdrant")
    pilot = json.loads(PILOT_PATH.read_text(encoding="utf-8"))["continuity_pilot"]
    run_id = "p05-" + uuid.uuid4().hex
    destination = APP_ROOT / "runtime/evaluation" / (run_id + ".json")
    report: dict[str, Any] = {"run_id": run_id, "status": "PILOT_ONLY",
        "model_call_interval_seconds": call_interval_seconds, "model": model_name, "provider": "groq", "parent": "B2+policy (reranker enabled; graph off)",
        "corpus_sha256": _sha256(PILOT_PATH), "script_sha256": _sha256(Path(__file__)),
        "annotation_status": "PILOT_NOT_HUMAN_ADJUDICATED", "critic": True, "vector_memory": False,
        "review_comparison": "Current mandatory critic held constant across continuity arms",
        "conditions": [], "provider_tokenizer_revision": None,
        "limitations": ["One fixed synthetic continuation, no quality/improvement inference",
                        "No retry or selective rerun; failures remain in the denominator",
                        "Packets measured before request using the same preflight producer",
                        "Character bounds are not provider tokenizer counts"]}
    destination.parent.mkdir(parents=True, exist_ok=True)
    collection = "p05_pilot_" + uuid.uuid4().hex
    index = QdrantIndex(url=url, collection_name=collection, model_cache_dir=str(APP_ROOT / "runtime/model_cache"))
    config = load_config(APP_ROOT / "config/adapters.yaml")
    headers = {"Authorization": "Bearer synthetic-memory-reader"}
    first_query = ("Read current transaction TX-DEMO-102, then evaluate DEMO.REVERSAL.CHECK "
        "with that live ID only. Do not look up settlement. Return draft JSON containing only "
        "its OBSERVED_FACT state and actual policy missing fields as RULE_REQUIREMENT. No action permission.")
    follow_up = ("Follow up the previous investigation. Read current TX-DEMO-102 again, then evaluate "
        "DEMO.REVERSAL.CHECK with that new live ID only. Do not look up settlement. Report the current "
        "OBSERVED_FACT state and actual missing fields as RULE_REQUIREMENT, without operational permission.")

    def app_for(root: Path, model: GroqModel, settings: Settings, value: str) -> Any:
        app = create_app(root, index, {"synthetic-memory-reader": "reader-a"}, FastEmbedReranker(enabled=True))
        adapter = MockAdapter({("get_transaction_status", "TX-DEMO-102"): (Snapshot(status="OK",
            data={"transaction_id": "TX-DEMO-102", "state": value,
                  "transaction_occurred_at": "2026-08-15T10:20:00Z"}),)})
        configure_agent(app, model=model, adapter=adapter, config=config, settings=settings)
        return app

    try:
        index.ensure_collection()
        with tempfile.TemporaryDirectory(prefix="palladion-p05-") as temp:
            base = Path(temp) / "base"
            seed(base, APP_ROOT, index)
            with Database(base / "registry.sqlite") as database:
                registry = Registry(database, OriginalStore(base / "originals"))
                seed_policy_fixture(registry, APP_ROOT)
            model = GroqModel.from_env_file(APP_ROOT.parent / ".env", enabled=True, model=model_name, call_interval_seconds=call_interval_seconds)
            settings = Settings.model_validate({"enable_live_llm": True, "model": model_name})
            initial_started = time.perf_counter()
            with TestClient(app_for(base, model, settings, pilot["stale_state"])) as client:
                first = client.post("/v1/cases/case-42/messages", headers=headers, json={"query": first_query})
                first.raise_for_status()
                report["initial_response"] = first.json()
            report["initial_elapsed_seconds"] = time.perf_counter()-initial_started
            report["initial_provider_failure"] = model.last_failure
            report["setup_critical_gap_present"] = "settlement_state" in first.json()["missing_requirements"]
            with Database(base / "registry.sqlite") as database:
                registry = Registry(database, OriginalStore(base / "originals"))
                store = CaseStore(registry, registry.access.authenticate("reader-a"), "case-42")
                report["initial_received_usage"] = [json.loads(r[0])["usage"] for r in database.connection.execute(
                    "SELECT payload_json FROM case_events WHERE event_kind='RUNTIME_ATTEMPT'")
                    if json.loads(r[0]).get("usage")]
                report["initial_attempts"] = [{k:v for k,v in json.loads(r[0]).items() if k in {
                    "role", "stage", "status", "attempt", "usage", "error_code"}}
                    for r in database.connection.execute(
                        "SELECT payload_json FROM case_events WHERE event_kind='RUNTIME_ATTEMPT'")]
                store.memory().write(MemorySpec(scope_id="reader-a", content="Operator reports customer debit; unverified."))
                for number in range(pilot["chatter_turns"]):
                    store.append("REQUEST", "long-session-"+str(number), {"query": "Synthetic unrelated discussion "*20})
                    store.append("ATTEMPT", "long-session-"+str(number), {"status": "FAILED", "attempt": number})
            for condition in pilot["conditions"]:
                arm, enabled, bound = condition["arm"], condition["memory"], condition["packet_max_chars"]
                # Deliberate inter-condition pacing; not an in-request retry.
                time.sleep(45)
                root = Path(temp) / arm
                root.mkdir()
                with closing(sqlite3.connect(base / "registry.sqlite")) as source, closing(sqlite3.connect(root / "registry.sqlite")) as target:
                    source.backup(target)
                shutil.copytree(base / "originals", root / "originals")  # Synthetic immutable bytes only.
                settings = settings.model_copy(update={"continuity_enabled": enabled, "packet_max_chars": bound})
                model = GroqModel.from_env_file(APP_ROOT.parent / ".env", enabled=True, model=model_name, call_interval_seconds=call_interval_seconds)
                row: dict[str, Any] = {"arm": arm, "memory_enabled": enabled, "packet_max_chars": bound}
                with Database(root / "registry.sqlite") as database:
                    registry = Registry(database, OriginalStore(root / "originals"))
                    store = CaseStore(registry, registry.access.authenticate("reader-a"), "case-42")
                    packet = preflight(follow_up, store, include_memory=enabled, packet_max_chars=bound)["packet"]
                    row["packet"] = packet
                    row["packet_characters"] = len(json.dumps(packet))
                started = time.perf_counter()
                with TestClient(app_for(root, model, settings, pilot["current_state"])) as client:
                    response = client.post("/v1/cases/case-42/messages", headers=headers, json={"query": follow_up})
                    row["http_status"] = response.status_code
                    if response.status_code == 200:
                        output = response.json()
                        row["response"] = output
                        row["score"] = score_continuation(output, packet, required_gaps=pilot["required_gaps"],
                            current_value=pilot["current_state"], stale_value=pilot["stale_state"])
                        row["citations_resolved"] = all(client.get("/v1/evidence/"+c["evidence_id"],
                            params={"case_id": "case-42"}, headers=headers).status_code == 200 for c in output["citations"])
                        with Database(root / "registry.sqlite") as database:
                            received = [json.loads(r[0]) for r in database.connection.execute(
                                "SELECT payload_json FROM case_events WHERE event_kind='RUNTIME_ATTEMPT' "
                                "AND json_extract(payload_json,'$.trace_id')=?", (output["trace_id"],))]
                            row["received_usage"] = [r["usage"] for r in received if r.get("usage")]
                            row["attempts"] = [{k:v for k,v in r.items() if k in {
                                "role", "stage", "status", "attempt", "usage", "error_code"}} for r in received]
                row["elapsed_seconds"] = time.perf_counter()-started
                row["last_provider_failure"] = model.last_failure
                row["last_rate_limits"] = model.last_rate_limits
                report["conditions"].append(row)
                destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
        report["all_conditions_observed"] = len(report["conditions"]) == 3
    finally:
        index.close()
        with closing(QdrantClient(url=url, timeout=30)) as cleanup:
            cleanup.delete_collection(collection, timeout=30)  # Only the command's fresh UUID.
        destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {"report": str(destination), **report}


def run_critic(url: str, model_name: str, call_interval_seconds: float = 0) -> dict[str, Any]:
    """Frozen controlled drafts, actual reviews/finalization, then separate HTTP runtime."""
    import asyncio
    import shutil
    import sqlite3
    import subprocess
    from contextlib import closing

    from fastapi.testclient import TestClient

    from evidence_agent.agent.critic import CRITIC_INSTRUCTIONS, evidence_digest
    from evidence_agent.agent.draft import (
        DRAFT_INSTRUCTIONS,
        FINALIZATION_INSTRUCTIONS,
        Claim,
        Draft,
    )
    from evidence_agent.agent.gate import release
    from evidence_agent.agent.llm import GroqModel
    from evidence_agent.agent.services import AgentServices, configure_agent
    from evidence_agent.core.clock import utc_clock
    from evidence_agent.core.evaluation import score_critic_output
    from evidence_agent.ingest.pipeline import IngestPipeline
    from evidence_agent.live.contracts import CaseScope, Snapshot
    from evidence_agent.live.gateway import load_config, register_scope
    from evidence_agent.live.mock import MockAdapter
    from evidence_agent.main import create_app
    from evidence_agent.policy.bootstrap import seed_policy_fixture
    from evidence_agent.settings import Settings

    if not url.startswith("http://127.0.0.1:"):
        raise ValueError("Critic pilot requires explicit local Qdrant")
    config = json.loads(PILOT_PATH.read_text(encoding="utf-8"))["critic_pilot"]
    settings = Settings.model_validate({"enable_live_llm": True, "model": model_name})
    run_id = "p06-" + uuid.uuid4().hex
    destination = APP_ROOT / "runtime/evaluation" / (run_id + ".json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_paths = sorted((APP_ROOT / "src").rglob("*.py")) + sorted((APP_ROOT / "scripts").glob("*.py"))
    source_paths += sorted((APP_ROOT / "src").rglob("*.sql"))
    source_paths += sorted((APP_ROOT / "data/demo").glob("*"))
    source_paths += sorted((APP_ROOT / "config").rglob("*.yaml")) + sorted((APP_ROOT / "config").rglob("*.json"))
    source_paths += [APP_ROOT / "pyproject.toml", APP_ROOT / "uv.lock"]
    source_paths = [p for p in source_paths if p.is_file()]
    snapshot_root = destination.with_suffix("")
    for source_path in source_paths:
        copied = snapshot_root / source_path.relative_to(APP_ROOT)
        copied.parent.mkdir(parents=True, exist_ok=True)
        copied.write_bytes(source_path.read_bytes())
    patch = subprocess.check_output(["git", "diff", "HEAD", "--", "AGENTS.md", "README.md", "palladion"], cwd=APP_ROOT.parent)
    (snapshot_root / "scoped.patch").write_bytes(patch)
    report: dict[str, Any] = {"schema_version": "2.0", "run_id": run_id,
        "provider": "groq", "model": model_name, "status": config["status"], "model_call_interval_seconds": call_interval_seconds,
        "controlled_initial_drafts": True, "critic_prompt_sha256": hashlib.sha256(CRITIC_INSTRUCTIONS.encode()).hexdigest(),
        "main_prompt_sha256": hashlib.sha256(DRAFT_INSTRUCTIONS.encode()).hexdigest(),
        "finalization_prompt_sha256": hashlib.sha256(FINALIZATION_INSTRUCTIONS.encode()).hexdigest(),
        "fixture_sha256": _sha256(PILOT_PATH), "script_sha256": _sha256(Path(__file__)),
        "git_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=APP_ROOT.parent, text=True).strip(),
        "dirty_scoped_patch_sha256": hashlib.sha256(patch).hexdigest(),
        "source_hashes": {str(p.relative_to(APP_ROOT)): _sha256(p) for p in source_paths},
        "provider_tokenizer_revision": None, "python": platform.python_version(),
        "settings": settings.model_dump(mode="json"),
        "cases": [], "runtime": None, "all_conditions_observed": False,
        "limitations": ["Mechanical controlled pilot, not adjudicated semantic accuracy",
            "Synthetic initial mistakes are not a measured main-model error rate",
            "Same-provider separate contexts are not independent truth",
            "Unknown failed-request token usage is not zero", "No selective retry inside a condition"]}
    adapter_config = load_config(APP_ROOT / "config/adapters.yaml")
    bundle = load_fixtures(APP_ROOT)
    sop = bundle.source_map()["SOP-2026-B"]
    exception = bundle.source_map()["EX-2026-04"].clauses["EX-SETTLEMENT-DELAY"]
    headers = {"Authorization": "Bearer synthetic-critic-reader"}

    def save() -> None:
        destination.write_text(json.dumps(report, indent=2), encoding="utf-8")

    def adapter() -> MockAdapter:
        return MockAdapter({("get_transaction_status", "TX-DEMO-102"): (Snapshot(status="OK",
            data={"transaction_id": "TX-DEMO-102", "state": "FAILED",
                "transaction_occurred_at": "2026-08-15T10:20:00Z"}),)})

    def seed_withheld(root: Path, index: QdrantIndex) -> dict[str, str]:
        # Supply only one approved SOP; appendix is never registered or indexed in this case.
        with Database(root / "registry.sqlite") as db:
            registry = Registry(db, OriginalStore(root / "originals"))
            for principal in bundle.principals:
                registry.bootstrap_principal(principal)
            case = bundle.case_map()["case-42"]
            registry.bootstrap_case(case.tenant_id, case.case_id)
            for identifier in case.allowed_principal_ids:
                registry.bootstrap_membership(registry.access.authenticate(identifier), case.case_id)
            admin = registry.access.authenticate("admin-a")
            register_scope(registry, admin, case.case_id, CaseScope(product=case.product,
                transaction_class=case.transaction_class, targets={"get_transaction_status": case.transaction_id}), utc_clock())
            revision = registry.register_source(registry.access.authenticate("uploader-a"),
                tenant_id=sop.tenant_id, case_id=case.case_id, family_id=sop.family_id,
                content=(APP_ROOT / sop.path).read_bytes(), source_path=sop.path,
                owner_id="admin-a", allowed_principal_ids=sop.allowed_principal_ids)
            registry.approve_source(admin, revision)
            IngestPipeline(Catalog(registry), index).index(admin, revision)
            return {sop.source_id: revision}

    try:
        with tempfile.TemporaryDirectory(prefix="palladion-p06-") as temporary:
            workspace = Path(temporary)
            for case_name in config["cases"]:
                collection = "p06_pilot_" + uuid.uuid4().hex
                index = QdrantIndex(url=url, collection_name=collection,
                    model_cache_dir=str(APP_ROOT / "runtime/model_cache"))
                case_report: dict[str, Any] = {"case": case_name, "conditions": []}
                report["cases"].append(case_report)
                try:
                    index.ensure_collection()
                    case_report["representation_manifest"] = index.representation_manifest
                    base = workspace / case_name / "base"
                    base.mkdir(parents=True)
                    if case_name == "withheld_appendix":
                        revisions = seed_withheld(base, index)
                    else:
                        revisions = seed(base, APP_ROOT, index)
                        with Database(base / "registry.sqlite") as db:
                            seed_policy_fixture(Registry(db, OriginalStore(base / "originals")), APP_ROOT)
                    services = AgentServices(base, index, None, adapter(), adapter_config, settings)
                    try:
                        runtime = services.begin("reader-a", "case-42")
                        registry = runtime.store.registry
                        chunks = Catalog(registry).chunks_for_revision(runtime.store.principal, revisions[sop.source_id])
                        clause = sop.clauses["S26-REVERSAL"]
                        chunk = next(c for c in chunks if c.start_byte <= clause.span_start and c.end_byte >= clause.span_end)
                        runtime.ledger.add(chunk.chunk_id)
                        live = asyncio.run(runtime.tools.execute("lookup_live_data", json.dumps({
                            "operation": "get_transaction_status", "target_id": "TX-DEMO-102"})))
                        live_id = live["data"]["evidence_id"]
                        if case_name == "missing_inputs":
                            asyncio.run(runtime.tools.execute("evaluate_policy", json.dumps({
                                "family_id": "DEMO.REVERSAL.CHECK", "evidence_ids": [live_id]})))
                        draft = Draft(claims=(Claim(id="C1", type="OBSERVED_FACT", text="Observed state",
                            evidence_ids=(live_id,), field="state", value="FAILED"),
                            Claim(id="C2", type="SOURCE_QUOTE", evidence_ids=(chunk.chunk_id,),
                                text=clause.text if case_name == "correct_fact" else
                                "A settlement timeout proves UNSETTLED and permits reversal.")))
                        question = ("Report the verified current transaction state and the actual missing policy fields; do not assume a missing input is false."
                            if case_name == "missing_inputs" else config["question"])
                        frozen = {"schema_version": "2.0", "question": question,
                            "draft": draft.model_dump(mode="json"), "initial_ledger": runtime.ledger.records,
                            "collection": collection, "source_revisions": revisions,
                            "missing_slots": [s for r in runtime.ledger.records.values() for s in r.get("missing_fields", [])]}
                        case_report["frozen_input"] = frozen
                        case_report["frozen_sha256"] = evidence_digest(frozen)
                        case_report["appendix_supplied"] = "EX-2026-04" in revisions
                        assert case_report["appendix_supplied"] == (case_name != "withheld_appendix")
                        save()
                    finally:
                        services.close()
                    off_retained: bool | None = None
                    for condition in config["conditions"]:
                        time.sleep(config["pacing_seconds"])
                        root = workspace / case_name / condition["arm"]
                        root.mkdir()
                        with closing(sqlite3.connect(base / "registry.sqlite")) as source, closing(sqlite3.connect(root / "registry.sqlite")) as target:
                            source.backup(target)
                        shutil.copytree(base / "originals", root / "originals")
                        row: dict[str, Any] = {"arm": condition["arm"], "status": "STARTED"}
                        case_report["conditions"].append(row)
                        model = GroqModel.from_env_file(APP_ROOT.parent / ".env", enabled=True, model=model_name, call_interval_seconds=call_interval_seconds)
                        services = AgentServices(root, index, model, adapter(), adapter_config, settings)
                        started = time.perf_counter()
                        runtime_created = False
                        try:
                            runtime = services.begin("reader-a", "case-42")
                            runtime_created = True
                            # Consume the persisted frozen envelope, not a regenerated draft/retrieval.
                            consumed = json.loads(destination.read_text(encoding="utf-8"))["cases"][-1]["frozen_input"]
                            consumed_hash = evidence_digest(consumed)
                            if consumed_hash != case_report["frozen_sha256"]:
                                raise ValueError("Frozen inputs changed")
                            initial = Draft.model_validate_json(json.dumps(consumed["draft"]))
                            for identifier in consumed["initial_ledger"]:
                                runtime.ledger.add(identifier)
                            if evidence_digest(runtime.ledger.records) != evidence_digest(consumed["initial_ledger"]):
                                raise ValueError("Canonical initial ledger changed")
                            async def execute() -> dict[str, Any]:
                                async with asyncio.timeout(settings.request_timeout_seconds):
                                    if condition["review"]:
                                        runtime.review = await runtime.critic.run(consumed["question"], {}, initial,
                                            allow_search=condition["search"], blind_requirements=condition["blind"])
                                    final = await runtime._finalize(consumed["question"], initial)
                                    output = release(final, runtime.ledger, review=runtime.review if condition["review"] else None)
                                    output.pop("_blocked_claim_ids")
                                    output["verification_failures"] = sorted(set(runtime.ledger.failures))
                                    return output
                            output = asyncio.run(execute())
                            row.update(status="OBSERVED", response=output,
                                reviews=[r.model_dump(mode="json") for r in runtime.critic.reviews],
                                consumed_sha256=consumed_hash,
                                initial_evidence_ids=list(consumed["initial_ledger"]), final_evidence_ids=list(runtime.ledger.records),
                                main_calls=runtime.budget.main_used, critic_calls=runtime.budget.critic_used,
                                counter_searches=runtime.budget.critic_search_used, tools_used=runtime.budget.tools_used)
                            row["final_ledger"] = runtime.ledger.records
                            row["score"] = score_critic_output(output, frozen_hash=case_report["frozen_sha256"],
                                consumed_hash=consumed_hash, expected_quote=exception.text if case_name == "exception" else None,
                                known_fact_id=live_id, initial_ids=list(consumed["initial_ledger"]),
                                final_ids=list(runtime.ledger.records), initial_fact_retained=off_retained,
                                reviews=row["reviews"], known_valid_claim_ids=("C1", "C2") if case_name == "correct_fact" else ("C1",),
                                known_invalid_claim_ids=() if case_name == "correct_fact" else ("C2",))
                            if condition["arm"] == "off":
                                off_retained = bool(row["score"]["known_fact_retained"])
                            with TestClient(create_app(root, index, {"synthetic-critic-reader": "reader-a"})) as client:
                                row["citations_resolved"] = all(client.get("/v1/evidence/"+c["evidence_id"],
                                    params={"case_id": "case-42"}, headers=headers).status_code == 200 for c in output["citations"])
                            row["received_usage"] = [json.loads(r[0])["usage"] for r in runtime.store.registry.database.connection.execute(
                                "SELECT payload_json FROM case_events WHERE event_kind='RUNTIME_ATTEMPT' AND json_extract(payload_json,'$.trace_id')=?",
                                (runtime.ledger.trace_id,)) if json.loads(r[0]).get("usage")]
                        except Exception as exc:
                            row.update(status="FAILED", failure_type=type(exc).__name__)
                        finally:
                            if runtime_created:
                                row.update(main_calls=runtime.budget.main_used, critic_calls=runtime.budget.critic_used,
                                    counter_searches=runtime.budget.critic_search_used, tools_used=runtime.budget.tools_used)
                                row["attempts"] = [{k: value for k, value in json.loads(r[0]).items() if k in {
                                    "role", "stage", "status", "attempt", "usage", "error_code"}} for r in runtime.store.registry.database.connection.execute(
                                    "SELECT payload_json FROM case_events WHERE event_kind='RUNTIME_ATTEMPT' AND json_extract(payload_json,'$.trace_id')=?",
                                    (runtime.ledger.trace_id,))]
                            row.update(elapsed_seconds=time.perf_counter()-started,
                                provider_failure=model.last_failure, rate_limits=model.last_rate_limits)
                            services.close()
                            save()
                        print(json.dumps({"case": case_name, "arm": row["arm"], "status": row["status"]}), flush=True)
                    if case_name == "exception":
                        time.sleep(config["pacing_seconds"])
                        model = GroqModel.from_env_file(APP_ROOT.parent / ".env", enabled=True, model=model_name, call_interval_seconds=call_interval_seconds)
                        app = create_app(base, index, {"synthetic-critic-reader": "reader-a"})
                        configure_agent(app, model=model, adapter=adapter(), config=adapter_config, settings=settings)
                        with TestClient(app) as client:
                            query = ("Use search_knowledge once for SOP-2026-B, then immediately return a draft quoting its reversal prerequisites. "
                                "Leave the approved settlement-delay appendix check to independent review. "
                                "Does a timeout establish UNSETTLED? Report exact source attributions, no payment permission.")
                            response = client.post("/v1/cases/case-42/messages", headers=headers, json={"query": query})
                            report["runtime"] = {"http_status": response.status_code}
                            if response.status_code == 200:
                                output = response.json()
                                report["runtime"].update(response=output,
                                    citations_resolved=all(client.get("/v1/evidence/"+c["evidence_id"], params={"case_id": "case-42"},
                                        headers=headers).status_code == 200 for c in output["citations"]),
                                    timeline=client.get("/v1/cases/case-42/timeline", headers=headers).json())
                                report["runtime"]["exception_quote_released"] = any(exception.text in c["text"] for c in output["verified_claims"])
                                with Database(base / "registry.sqlite") as db:
                                    report["runtime"]["attempts"] = [{k: value for k, value in json.loads(r[0]).items()
                                        if k in {"role", "stage", "status", "attempt", "usage", "error_code"}}
                                        for r in db.connection.execute("SELECT payload_json FROM case_events WHERE event_kind='RUNTIME_ATTEMPT' "
                                            "AND json_extract(payload_json,'$.trace_id')=?", (output["trace_id"],))]
                            report["runtime"].update(provider_failure=model.last_failure, rate_limits=model.last_rate_limits)
                        save()
                finally:
                    index.close()
                    with closing(QdrantClient(url=url, timeout=30)) as cleanup:
                        cleanup.delete_collection(collection, timeout=30)
            report["all_conditions_observed"] = (len(report["cases"]) == len(config["cases"]) and
                all(len(c["conditions"]) == len(config["conditions"]) for c in report["cases"]))
    finally:
        save()
    return {"report": str(destination), "all_conditions_observed": report["all_conditions_observed"],
        "conditions": sum(len(c["conditions"]) for c in report["cases"]), "runtime_observed": report["runtime"] is not None}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:16333")
    parser.add_argument("--capabilities", action="store_true", help="Read-only isolated evaluator capability matrix")
    parser.add_argument("--critic", action="store_true", help="Explicit P06 real-Groq frozen critic pilot")
    parser.add_argument("--memory", action="store_true", help="Explicit P05 actual-Groq continuity pilot")
    parser.add_argument("--enable-live-llm", action="store_true")
    parser.add_argument("--study",choices=("development","evaluation"),help="Explicit P08 study phase")
    parser.add_argument("--protocol",type=Path,help="Frozen approved P08 evaluation protocol")
    parser.add_argument("--replay-study",type=Path,help="Replay saved study outputs without provider calls")
    parser.add_argument("--model", choices=("qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"))
    parser.add_argument("--run", action="store_true",
                        help="explicitly seed/query/delete only unique p02_eval_* collections")
    parser.add_argument("--model-call-interval", type=float, default=0, help="Opt-in live Groq dispatch interval within unchanged deadlines")
    args = parser.parse_args(argv)
    if args.capabilities:
        if args.run or args.enable_live_llm or args.study or args.critic or args.memory or args.replay_study:
            parser.error("Capability inspection cannot combine with execution or replay")
        from evidence_agent.agent.experiments import evaluator_capabilities
        print(json.dumps(evaluator_capabilities(), indent=2))
        return 0
    if args.replay_study:
        if args.run or args.enable_live_llm or args.study or args.critic or args.memory:
            parser.error("Replay is read-only and cannot combine with execution flags")
        from evidence_agent.evaluation.study import replay_study
        print(json.dumps(replay_study(args.replay_study),indent=2))
        return 0
    if args.study:
        if not args.run or not args.enable_live_llm or args.critic or args.memory:
            parser.error("Study requires --run --enable-live-llm and cannot combine other pilots")
        if args.model is not None or args.model_call_interval:
            parser.error("Study model and spacing come from the frozen study config; CLI overrides are not allowed")
        from evidence_agent.evaluation.study import run_study
        print(json.dumps(run_study(args.url,phase=args.study,enabled=True,protocol=args.protocol,app=APP_ROOT),indent=2))
        return 0
    if args.model_call_interval and not (args.critic or args.memory):
        parser.error("Model call spacing requires an explicit live critic or memory pilot")
    if not args.run:
        parser.error("--run is required before the pilot creates temporary SQLite data and Qdrant collections")
    if args.critic:
        if not args.enable_live_llm or args.memory:
            parser.error("Critic pilot requires --enable-live-llm and cannot combine with --memory")
        result = run_critic(args.url, args.model or "qwen/qwen3.8-27b", args.model_call_interval)
        print(json.dumps(result, indent=2))
        return 0 if result.get("all_conditions_observed") else 1
    if args.memory:
        if not args.enable_live_llm:
            parser.error("Memory pilot requires --enable-live-llm before credentials are read")
        result = run_memory(args.url, args.model or "qwen/qwen3.8-27b", args.model_call_interval)
        print(json.dumps(result, indent=2))
        return 0 if result.get("all_conditions_observed") else 1
    report = run(args.url)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if REPORT_PATH.exists():
        prior = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        history = REPORT_PATH.with_name(prior["run_id"] + ".json")
        if not history.exists():
            history.write_bytes(REPORT_PATH.read_bytes())
    encoded = json.dumps(report, sort_keys=True, indent=2) + "\n"
    REPORT_PATH.with_name(report["run_id"] + ".json").write_text(encoded, encoding="utf-8")
    REPORT_PATH.write_text(encoded, encoding="utf-8")
    print(json.dumps({"report": str(REPORT_PATH), "run_id": report["run_id"],
                      "status": report["status"],
                      "profiles": [{"bm25_profile": item["bm25_profile"],
                                    "collection": item["collection"],
                                    "index_health": item["index_health_after"],
                                    "exact_identifier_cases": item["exact_identifier_cases"]}
                                   if item.get("status") != "ERROR" else item
                                   for item in report["profiles"]]}, indent=2))
    return 0 if report["status"] == "PILOT_ONLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
