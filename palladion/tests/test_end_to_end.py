"""Real local Qdrant/HTTP integration, explicitly enabled and temporary synthetic state."""
from __future__ import annotations

import os
import subprocess
import sys
import uuid
from contextlib import closing
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from evidence_agent.core.bootstrap import seed
from evidence_agent.core.errors import DependencyUnavailable
from evidence_agent.main import create_app
from evidence_agent.retrieval.rerank import FastEmbedReranker
from evidence_agent.storage.catalog import Catalog
from evidence_agent.storage.originals import OriginalStore
from evidence_agent.storage.qdrant import QdrantIndex
from evidence_agent.storage.registry import Registry
from evidence_agent.storage.sqlite import Database
from evidence_agent.telemetry.audit import AuditLog

APP = Path(__file__).resolve().parents[1]
URL = os.environ.get("PALLADION_TEST_QDRANT_URL")
pytestmark = pytest.mark.skipif(not URL, reason="Explicit local Qdrant integration enablement required")
TOKENS = {"test-admin-a": "admin-a", "test-upload-a": "uploader-a",
          "test-reader-a": "reader-a", "test-limited-a": "reader-a-limited",
          "test-reader-b": "reader-b"}


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def runtime(tmp_path: Path):
    assert URL and URL.startswith("http://127.0.0.1:"), "Tests require an explicitly local server"
    index = QdrantIndex(url=URL, collection_name="p02_test_" + uuid.uuid4().hex,
                       model_cache_dir=APP / "runtime/model_cache")
    try:
        index.ensure_collection()
        root = tmp_path / "runtime"
        revisions = seed(root, APP, index)
        yield root, index, revisions
    finally:
        try:
            with closing(QdrantClient(url=URL, timeout=30)) as client:
                client.delete_collection(index.collection_name, timeout=30)
        finally:
            index.close()


def test_actual_upload_approval_search_citation_and_revocation(runtime) -> None:
    root, index, _ = runtime
    with TestClient(create_app(root, index, TOKENS)) as client:
        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 200
        body = {"case_id": "case-42", "family_id": "INTEGRATION.ONLY", "filename": "test.md",
                "mime_type": "text/markdown", "owner_id": "admin-a",
                "content": "# Synthetic citation\n\n[CLAUSE: TEST-ONLY]\nA violet demonstration requires a settlement recheck.\n"}
        assert client.post("/sources", json={**body, "sha256": "0" * 64},
                           headers=auth("test-upload-a")).status_code == 400
        uploaded = client.post("/sources", json=body, headers=auth("test-upload-a"))
        assert uploaded.status_code == 201, uploaded.text
        revision = uploaded.json()["revision_id"]
        assert client.post(f"/sources/{revision}/approve", headers=auth("test-upload-a")).status_code == 403
        approved = client.post(f"/sources/{revision}/approve", headers=auth("test-admin-a"))
        assert approved.status_code == 200, approved.text
        result = client.post("/search", json={"case_id": "case-42", "query": "violet demonstration settlement"},
                             headers=auth("test-reader-a"))
        assert result.status_code == 200, result.text
        passages = [p for p in result.json()["passages"] if p["revision_id"] == revision]
        assert passages
        for passage in passages:
            citation = client.get(f"/evidence/{passage['citation_id']}", params={"case_id": "case-42"},
                                  headers=auth("test-reader-a"))
            assert citation.status_code == 200, citation.text
            actual = citation.json()
            assert actual["text"].encode() == body["content"].encode()[actual["start_byte"]:actual["end_byte"]]
            assert client.get(f"/evidence/{passage['citation_id']}", params={"case_id": "case-42"},
                              headers=auth("test-reader-b")).status_code == 403
        assert client.post(f"/sources/{revision}/revoke", headers=auth("test-reader-a")).status_code == 403
        assert client.post(f"/sources/{revision}/revoke", headers=auth("test-admin-a")).status_code == 200
        assert client.get(f"/evidence/{passages[0]['citation_id']}", params={"case_id": "case-42"},
                          headers=auth("test-reader-a")).status_code == 403
        after = client.post("/search", json={"case_id": "case-42", "query": "violet demonstration settlement"},
                            headers=auth("test-reader-a"))
        assert after.status_code == 200
        assert all(p["revision_id"] != revision for p in after.json()["passages"])
        assert client.post("/sources", json=body, headers=auth("admin-a")).status_code == 403
        assert client.post("/search", json={"case_id": "case-42", "query": "x", "principal_id": "admin-a"},
                           headers=auth("test-reader-a")).status_code == 422
        assert client.post("/sources", content=b"x" * 131073, headers=auth("test-upload-a")).status_code == 413


def test_seed_reconcile_exact_scope_and_source_acl(runtime) -> None:
    root, index, revisions = runtime
    assert seed(root, APP, index) == revisions
    with Database(root / "registry.sqlite") as database:
        registry = Registry(database, OriginalStore(root / "originals"))
        catalog = Catalog(registry)
        admin = registry.access.authenticate("admin-a")
        chunk = next(c for c in catalog.chunks_for_revision(admin, revisions["SOP-2026-B"])
                     if "S26-REVERSAL" in c.text)
        catalog.add_alias(admin, "POL-71", revisions["SOP-2026-B"], chunk.chunk_id)
    with TestClient(create_app(root, index, TOKENS)) as client:
        found = client.post("/search", json={"case_id": "case-42", "query": "SOP-2026-B"},
                            headers=auth("test-reader-a"))
        assert found.status_code == 200, found.text
        assert found.json()["passages"]
        known = client.post("/search", json={"case_id": "case-42", "query": "POL-71"},
                            headers=auth("test-reader-a"))
        assert known.json()["passages"]
        wrong = client.post("/search", json={"case_id": "case-42", "query": "POL-17"},
                            headers=auth("test-reader-a"))
        assert not wrong.json()["passages"]
        restricted = client.post("/search", json={"case_id": "case-42", "query": "EX-2026-04"},
                                 headers=auth("test-limited-a"))
        assert restricted.status_code == 200, restricted.text
        assert not restricted.json()["passages"]
        assert "EX-SETTLEMENT-DELAY" not in restricted.text
        assert client.post(f"/sources/{revisions['EX-2026-04']}/revoke", headers=auth("test-admin-a")).status_code == 200
        assert seed(root, APP, index) == revisions
        denied_after_seed = client.post("/search", json={"case_id": "case-42", "query": "EX-2026-04"},
                                       headers=auth("test-reader-a"))
        assert denied_after_seed.json()["passages"] == []
    with Database(root / "registry.sqlite") as database:
        registry = Registry(database, OriginalStore(root / "originals"))
        catalog = Catalog(registry)
        admin = registry.access.authenticate("admin-a")
        metadata = catalog.generation_for_revision(admin, revisions["SOP-2026-B"])
        assert metadata and metadata["state"] == "READY"
        assert metadata["fingerprint"] == index.fingerprint


def test_real_missing_point_health_and_correlated_audit_reopen(runtime) -> None:
    root, index, revisions = runtime
    with TestClient(create_app(root, index, TOKENS)) as client:
        result = client.post("/search", json={"case_id": "case-42", "query": "historical reversal review"},
                             headers=auth("test-reader-a"))
        assert result.status_code == 200, result.text
        report = result.json()
        assert report["passages"]
        assert all(p["revision_id"] not in {revisions["SOP-2025-A"], revisions["MEMO-DRAFT-1"]}
                   for p in report["passages"])
        with closing(QdrantClient(url=URL)) as raw:
            points, _ = raw.scroll(index.collection_name, limit=100, with_payload=True)
            point = next(p for p in points if p.payload and p.payload["revision_id"] == revisions["SOP-2026-B"])
            raw.delete(index.collection_name, points_selector=[point.id], wait=True)
        health = client.get("/index-health", params={"case_id": "case-42"}, headers=auth("test-reader-a"))
        assert health.status_code == 200, health.text
        assert health.json()["index_coverage"] is False
        assert "INDEX_MANIFEST_MISMATCH" in health.json()["warnings"]
    with Database(root / "registry.sqlite") as database:
        log = AuditLog(Registry(database, OriginalStore(root / "originals")))
        records = log.read(report["trace_id"])
        assert len(records) == 1
        assert records[0]["returned_count"] == len(report["passages"])
        assert "historical reversal review" not in str(records)
        assert "EX-SETTLEMENT-DELAY" not in str(records)


def test_discovery_failure_keeps_exact_evidence_and_honest_scope(runtime, monkeypatch) -> None:
    root, index, _ = runtime

    def unavailable(*args, **kwargs):
        raise DependencyUnavailable

    monkeypatch.setattr(index, "query", unavailable)
    with TestClient(create_app(root, index, TOKENS)) as client:
        exact = client.post("/search", json={"case_id": "case-42", "query": "SOP-2026-B"},
                            headers=auth("test-reader-a"))
        assert exact.status_code == 200, exact.text
        assert exact.json()["status"] == "DEGRADED"
        assert exact.json()["passages"]
        assert "INDEX_UNAVAILABLE" in exact.json()["warnings"]
        assert exact.json()["coverage"]["inventory_attested"] is False
        no_exact = client.post("/search", json={"case_id": "case-42", "query": "unknown settlement explanation"},
                               headers=auth("test-reader-a"))
        assert no_exact.json()["status"] == "UNAVAILABLE"
        assert no_exact.json()["passages"] == []
        assert no_exact.json()["coverage"]["requirements_assessed"] is False


def test_reranked_http_request_bounds_more_than_thirty_candidates(runtime) -> None:
    root, index, _ = runtime
    ranker = FastEmbedReranker(enabled=True, cache_dir=APP / "runtime/model_cache")
    with TestClient(create_app(root, index, TOKENS, ranker)) as client:
        content = "# Many synthetic sections\n" + "".join(
            f"\n## Section {i}\n\nSettlement reversal investigation requires verification for synthetic item {i}.\n"
            for i in range(40))
        upload = client.post("/sources", json={"case_id": "case-42", "family_id": "MANY.SECTIONS",
            "filename": "many.md", "mime_type": "text/markdown", "owner_id": "admin-a",
            "content": content}, headers=auth("test-upload-a"))
        assert upload.status_code == 201, upload.text
        approved = client.post(f"/sources/{upload.json()['revision_id']}/approve", headers=auth("test-admin-a"))
        assert approved.status_code == 200, approved.text
        response = client.post("/search", json={"case_id": "case-42", "query": "settlement reversal investigation",
                                                "mode": "reranked"}, headers=auth("test-reader-a"))
        assert response.status_code == 200, response.text
        counts = response.json()["stage_counts"]
        assert counts["resolved"] > 30
        assert counts["reranked"] == 30
        assert len(response.json()["passages"]) <= 12


@pytest.mark.parametrize("failure", ["load", "inference"])
def test_reranker_asset_failure_degrades_actual_http_consumer(runtime, monkeypatch, failure) -> None:
    root, index, _ = runtime
    ranker = FastEmbedReranker(enabled=True, cache_dir=APP / "runtime/model_cache")

    def unavailable(**kwargs):
        raise OSError("synthetic unavailable model cache")

    if failure == "load":
        monkeypatch.setattr("evidence_agent.retrieval.rerank.snapshot_download", unavailable)
    else:
        class BrokenModel:
            def rerank(self, *args, **kwargs):
                raise RuntimeError("synthetic inference failure")
        monkeypatch.setattr(ranker, "_load", lambda: BrokenModel())
    with TestClient(create_app(root, index, TOKENS, ranker=ranker)) as client:
        response = client.post("/search", headers=auth("test-reader-a"),
                               json={"case_id": "case-42", "query": "settlement reversal investigation",
                                     "mode": "reranked"})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["status"] == "DEGRADED"
        assert "RERANK_UNAVAILABLE" in result["warnings"]
        assert result["passages"]


def test_reconcile_cli_reads_active_generation_after_profile_rollback(runtime) -> None:
    root, index, _ = runtime
    alternate = QdrantIndex(url=URL, collection_name=index.collection_name,
                            model_cache_dir=APP / "runtime/model_cache", bm25_profile="no_stemming")
    try:
        seed(root, APP, alternate)
    finally:
        alternate.close()
    seed(root, APP, index)
    completed = subprocess.run(
        [sys.executable, "scripts/reconcile.py", "--root", str(root), "--url", str(URL),
         "--collection", index.collection_name], cwd=APP, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert '"all_match": true' in completed.stdout
