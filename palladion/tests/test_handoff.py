"""Part B consumers using real HTTP/canonical storage and isolated index transport."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from evidence_agent.core.retrieval import Candidate
from evidence_agent.main import create_app
from evidence_agent.retrieval.embeddings import PassageTokenizer

from .test_pipeline import MemoryIndex


class HandoffIndex(MemoryIndex):
    audit_cache_identity = "isolated-handoff-test-backend"
    model_cache_dir = Path(__file__).resolve().parents[1]/"runtime/model_cache"
    def __init__(self):
        super().__init__()
        self.fingerprint = "a" * 64
        self.batches = 0

    def upsert(self, chunks, generation, allowed_principal_ids):
        # Discovery is deliberately untrusted here; canonical readers must apply ACLs.
        if chunks:
            self.points.setdefault((chunks[0].revision_id,generation), {}).update(
                {chunk.chunk_id:chunk.content_sha256 for chunk in chunks})

    def query(self, *args, **kwargs):
        return tuple(Candidate(chunk_id=chunk, generation=generation, score=1, channel="guard")
            for (_, generation), chunks in self.points.items() for chunk in chunks)[:40]

    def readback_many(self, tenant_id, revisions):
        self.batches += 1
        return {(revision, generation): self.readback(tenant_id, revision, generation)
            for revision, generation in revisions.items()}


@pytest.fixture
def handoff(p03):
    index = HandoffIndex()
    root = p03.registry.originals.root.parent
    app = create_app(root, index, {"uploader": "uploader-a", "admin": "admin-a", "reader": "reader-a"})
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, index=index, p03=p03)


def upload_approved(handoff, *, family="HANDOFF-SOP", content="# HANDOFF-SOP\n\nUse scoped evidence.", **times):
    client = handoff.client
    response = client.post("/sources", headers={"Authorization": "Bearer uploader"}, json={
        "case_id": "case-42", "family_id": family, "filename": family+".md", "mime_type": "text/markdown",
        "content": content, "owner_id": "uploader-a", **times})
    assert response.status_code == 201, response.text
    revision = response.json()["revision_id"]
    response = client.post(f"/sources/{revision}/approve", headers={"Authorization": "Bearer admin"})
    assert response.status_code == 200, response.text
    return revision


def test_approved_upload_exact_alias_and_unknown_code(handoff):
    revision = upload_approved(handoff, content="# HANDOFF-SOP\n\nMS-1954 requires scoped evidence.")
    headers = {"Authorization": "Bearer reader"}
    response = handoff.client.post("/search", headers=headers,
        json={"case_id": "case-42", "query": "HANDOFF-SOP"})
    assert response.status_code == 200, response.text
    passage = response.json()["passages"][0]
    assert passage["revision_id"] == revision
    citation = handoff.client.get("/evidence/"+passage["citation_id"], headers=headers, params={"case_id":"case-42"})
    assert citation.status_code == 200 and citation.json()["text"] == passage["text"]
    for query in ("what status does MS-1954 return", revision):
        hit = handoff.client.post("/search", headers=headers,
            json={"case_id":"case-42", "query":query}).json()
        assert hit["passages"] and hit["passages"][0]["revision_id"] == revision
    unknown = handoff.client.post("/search", headers=headers,
        json={"case_id":"case-42", "query":"HANDOFF-NONEXISTENT"}).json()
    assert unknown["passages"] == [] and "EXACT_IDENTIFIER_NOT_FOUND" in unknown["warnings"]


def test_historical_cutoff_and_citation_keep_current_revocation(handoff):
    revision = upload_approved(handoff, valid_from="2020-01-01T00:00:00Z", valid_to="2024-01-01T00:00:00Z")
    newer = upload_approved(handoff, content="# HANDOFF-SOP\n\nNew scoped evidence.", valid_from="2024-01-01T00:00:00Z")
    headers = {"Authorization":"Bearer reader"}
    body = {"case_id":"case-42", "query":"HANDOFF-SOP"}
    current = handoff.client.post("/search", headers=headers, json=body).json()["passages"]
    assert current and all(p["revision_id"] == newer for p in current)
    body["as_of"] = "2023-01-01T00:00:00Z"
    result = handoff.client.post("/search", headers=headers, json=body)
    assert result.status_code == 200, result.text
    passage = result.json()["passages"][0]
    route = "/evidence/"+passage["citation_id"]
    params = {"case_id":"case-42", "as_of":body["as_of"]}
    assert handoff.client.get(route, headers=headers, params=params).status_code == 200
    assert handoff.client.get(route, headers=headers, params={"case_id":"case-42"}).status_code == 403
    assert handoff.client.post("/search", headers=headers,
        json={**body, "as_of":"2023-01-01T00:00:00"}).status_code == 422
    assert handoff.client.post(f"/sources/{revision}/revoke", headers={"Authorization":"Bearer admin"}).status_code == 200
    assert handoff.client.post("/search", headers=headers, json=body).json()["passages"] == []
    assert handoff.client.get(route, headers=headers, params=params).status_code == 403


def test_http_applicability_instants_return_the_older_version_and_its_citation(handoff):
    older = upload_approved(handoff, valid_from="2020-01-01T00:00:00Z", valid_to="2024-01-01T00:00:00Z")
    newer = upload_approved(handoff, content="# HANDOFF-SOP\n\nNew scoped evidence.", valid_from="2024-01-01T00:00:00Z")
    headers = {"Authorization":"Bearer reader"}
    body = {"case_id":"case-42", "query":"HANDOFF-SOP"}
    now_only = handoff.client.post("/search", headers=headers, json=body).json()["passages"]
    assert {p["revision_id"] for p in now_only} == {newer}
    instant = "2023-01-01T00:00:00Z"
    both = handoff.client.post("/search", headers=headers, json={**body, "applicability_instants":[instant]})
    assert both.status_code == 200, both.text
    passages = both.json()["passages"]
    assert {p["revision_id"] for p in passages} == {older, newer}
    old = next(p for p in passages if p["revision_id"] == older)
    route = "/evidence/"+old["citation_id"]
    assert handoff.client.get(route, headers=headers, params={"case_id":"case-42"}).status_code == 403
    assert handoff.client.get(route, headers=headers,
        params={"case_id":"case-42", "applicability_instants":[instant]}).status_code == 200
    assert handoff.client.post("/search", headers=headers,
        json={**body, "applicability_instants":["2023-01-01T00:00:00"]}).status_code == 422
    assert handoff.client.post("/search", headers=headers,
        json={**body, "applicability_instants":[f"2023-01-0{day}T00:00:00Z" for day in range(1, 9)]}).status_code == 422


def test_http_whole_passage_budget_preserves_bytes_and_discloses_tokenizer(handoff):
    upload_approved(handoff, content="# HANDOFF-SOP\n\n" + "Evidence preserves source bytes. "*50)
    headers = {"Authorization":"Bearer reader"}
    body = {"case_id":"case-42", "query":"HANDOFF-SOP", "limit":40}
    default = handoff.client.post("/search", headers=headers, json=body).json()
    assert default["passages"] and default["evidence_budget"] is None
    bounded = handoff.client.post("/search", headers=headers, json={**body,"token_budget":1000}).json()
    assert bounded["passages"] == default["passages"]
    budget = bounded["evidence_budget"]
    assert budget["used_tokens"] == PassageTokenizer(HandoffIndex.model_cache_dir).count("\n\n".join(p["text"] for p in bounded["passages"]))
    assert budget["tokenizer"]["truncation"] is False
    empty = handoff.client.post("/search", headers=headers, json={**body,"token_budget":1}).json()
    assert empty["passages"] == [] and empty["evidence_budget"]["used_tokens"] == 0
    assert empty["evidence_budget"]["truncated"] is True
    assert handoff.client.post("/search", headers=headers, json={**body,"limit":41}).status_code == 422


def test_retrieval_tokenizer_counts_beyond_embedding_truncation():
    tokenizer = PassageTokenizer(HandoffIndex.model_cache_dir)
    assert tokenizer.count("evidence "*2000) > 1000


def test_coverage_batches_more_than100_sources_and_rechecks_drift(tmp_path):
    import time

    from evidence_agent.ingest.pipeline import IngestPipeline
    from evidence_agent.retrieval.coverage import source_coverage
    from evidence_agent.retrieval.hybrid import HybridSearch
    from evidence_agent.storage.exact import ExactIndex

    from .test_pipeline import _setup
    database, registry, catalog, uploader, revision, _ = _setup(tmp_path)
    try:
        index = HandoffIndex()
        IngestPipeline(catalog,index).index(uploader,revision)
        admin = registry.access.authenticate("approver")
        for number in range(129):
            other = registry.register_source(uploader,tenant_id="tenant-a",case_id="case-1",
                family_id="COVERAGE",content=f"# Scope\n\nEvidence {number}.".encode(),
                source_path=f"source-{number}.md", owner_id="uploader")
            registry.approve_source(admin,other)
            IngestPipeline(catalog,index).index(uploader,other)
            ExactIndex(catalog).register_approved(admin,other)
        statements = []
        database.connection.set_trace_callback(statements.append)
        started = time.perf_counter()
        result = source_coverage(registry,uploader,"case-1",index)
        elapsed = time.perf_counter()-started
        database.connection.set_trace_callback(None)
        assert len(statements) < 30  # Includes current auth, source list and3 manifest batches.
        assert result.index_coverage and result.source_counts_complete
        assert result.accepted_source_count == result.indexed_source_count == 130
        assert index.batches == 3  # Three transport batches replace130 per-source reads.
        search = HybridSearch(catalog,index)
        result = search.search(uploader,"case-1","COVERAGE",limit=1)
        assert len(result.passages) == 1
        assert "EXACT_CANDIDATES_TRUNCATED" in result.warnings
        assert result.status == "DEGRADED"
        assert len(search.exact.lookup(uploader,"case-1","COVERAGE")) == 100
        index.readback_mode = "missing"
        drift = source_coverage(registry,uploader,"case-1",index)
        assert not drift.index_coverage and drift.indexed_source_count == 0
        assert "INDEX_MANIFEST_MISMATCH" in drift.warnings
        print({"sources":130,"batch_requests":3,"coverage_seconds":elapsed})
    finally:
        database.close()


def test_physical_batch_validates_every_generation_and_empty_vectors():
    from evidence_agent.storage.qdrant import IndexConsistencyError, QdrantIndex

    from .test_retrieval import _chunk, _Client, _Encoder
    client = _Client()
    index = QdrantIndex(client=client,encoder=_Encoder())
    index.ensure_collection()
    index.upsert((_chunk(),),"generation-1",())
    result = index.readback_many("tenant-a",{"revision-1":"generation-1","revision-2":"generation-2"})
    assert result[("revision-1","generation-1")]
    assert ("revision-2","generation-2") not in result
    assert len([name for name,_ in client.calls if name=="scroll"]) == 1
    client.points[0].vector.pop("bm25")
    with pytest.raises(IndexConsistencyError,match="missing"):
        index.readback_many("tenant-a",{"revision-1":"generation-1"})


def test_http_twenty_passages_and_tool_cap_remain_distinct(handoff):
    from pydantic import ValidationError

    from evidence_agent.agent.tools import KnowledgeArgs
    content = "# Passage budget\n"+"".join(f"\n## Section {n}\n\nCanonical evidence paragraph {n}.\n" for n in range(25))
    upload_approved(handoff,content=content)
    response = handoff.client.post("/search",headers={"Authorization":"Bearer reader"},
        json={"case_id":"case-42","query":"evidence paragraph","limit":20})
    assert response.status_code == 200,response.text
    assert len(response.json()["passages"]) == 20
    with pytest.raises(ValidationError):
        KnowledgeArgs(query="evidence",limit=20)


def test_provisioned_principal_source_acl_applies_before_limit(handoff):
    client = handoff.client
    admin = {"Authorization":"Bearer admin"}
    create = client.post("/v1/admin/principals",headers=admin,
        json={"principal_id":"private-reader","grants":["case:read","source:read"]})
    assert create.status_code == 200
    canonical = create.json()["principal_id"]
    assert client.post("/v1/admin/cases/case-42/memberships",headers=admin,
        json={"principal_id":canonical}).json()["active"]
    # Operator provisions a synthetic opaque token; no API mints one.
    client.app.state.tokens["operator-private"] = canonical
    uploaded = client.post("/sources",headers={"Authorization":"Bearer uploader"},json={
        "case_id":"case-42","family_id":"PRIVATE-SOURCE","filename":"private.md",
        "mime_type":"text/markdown","content":"# Private\n\nPRIVATE_SCOPE_CANARY evidence.",
        "owner_id":"uploader-a","allowed_principal_ids":["admin-a",canonical]})
    assert uploaded.status_code == 201,uploaded.text
    assert client.post("/sources/"+uploaded.json()["revision_id"]+"/approve",headers=admin).status_code == 200
    upload_approved(handoff,family="PUBLIC-SOURCE",content="# Public\n\nPublic scoped evidence.")
    body={"case_id":"case-42","query":"scoped evidence","limit":1}
    private=client.post("/search",headers={"Authorization":"Bearer operator-private"},json=body)
    ordinary=client.post("/search",headers={"Authorization":"Bearer reader"},json=body)
    assert "PRIVATE_SCOPE_CANARY" in private.text
    assert "PRIVATE_SCOPE_CANARY" not in ordinary.text
    assert len(ordinary.json()["passages"]) == 1
    assert "Public scoped evidence" in ordinary.json()["passages"][0]["text"]


def test_budget_cache_miss_stays_local_and_returns_typed_unavailable(handoff, monkeypatch):
    upload_approved(handoff)
    called = []
    def missing(**kwargs):
        called.append(kwargs)
        assert kwargs["local_files_only"] is True and kwargs["token"] is False
        raise OSError("No local pinned tokenizer")
    monkeypatch.setattr("evidence_agent.retrieval.embeddings.snapshot_download",missing)
    response = handoff.client.post("/search",headers={"Authorization":"Bearer reader"},
        json={"case_id":"case-42","query":"HANDOFF-SOP","token_budget":50})
    assert response.status_code == 503,response.text
    assert len(called) == 1


def test_exact_alias_acl_is_filtered_before_candidate_cap(handoff):
    client=handoff.client
    headers={"Authorization":"Bearer uploader"}
    content="# Private\n"+"".join(f"\n## Heading {n}\n\nPRIVATE_BULK_CANARY {n}.\n" for n in range(120))
    uploaded=client.post("/sources",headers=headers,json={"case_id":"case-42","family_id":"ACL-BULK",
        "filename":"private.md","mime_type":"text/markdown","content":content,"owner_id":"uploader-a",
        "allowed_principal_ids":["admin-a"]})
    assert uploaded.status_code == 201,uploaded.text
    assert client.post("/sources/"+uploaded.json()["revision_id"]+"/approve",
        headers={"Authorization":"Bearer admin"}).status_code == 200
    revision=upload_approved(handoff,family="ACL-BULK",content="# Public\n\nVisible bulk evidence.")
    result=client.post("/search",headers={"Authorization":"Bearer reader"},
        json={"case_id":"case-42","query":"ACL-BULK","limit":1})
    assert result.status_code == 200,result.text
    assert result.json()["passages"][0]["revision_id"] == revision
    assert "PRIVATE_BULK_CANARY" not in result.text
    assert "EXACT_CANDIDATES_TRUNCATED" not in result.json()["warnings"]


@pytest.mark.parametrize("change", ["source", "acl", "generation", "membership", "grant"])
def test_coverage_rechecks_authority_after_physical_readback(tmp_path, change):
    from evidence_agent.core.errors import PermissionDenied
    from evidence_agent.ingest.pipeline import IngestPipeline
    from evidence_agent.retrieval.coverage import source_coverage

    from .test_pipeline import _setup

    database, registry, catalog, uploader, revision, _ = _setup(tmp_path)
    try:
        index = HandoffIndex()
        IngestPipeline(catalog, index).index(uploader, revision)
        original = index.readback_many
        def mutate_after_readback(tenant, revisions):
            result = original(tenant, revisions)
            if change == "source":
                registry.revoke_source(registry.access.authenticate("approver"), revision)
            elif change == "acl":
                database.connection.execute("UPDATE document_revisions SET acl_json=? WHERE revision_id=?",
                    ('{"allowed_principal_ids":["approver"]}', revision))
            elif change == "generation":
                database.connection.execute("UPDATE document_revisions SET index_generation='replaced' WHERE revision_id=?",
                    (revision,))
            elif change == "membership":
                database.connection.execute("UPDATE case_memberships SET revoked_at='now' WHERE principal_id='uploader'")
            else:
                database.connection.execute("DELETE FROM principal_grants WHERE principal_id='uploader'")
            return result
        index.readback_many = mutate_after_readback
        with pytest.raises(PermissionDenied):
            source_coverage(registry, uploader, "case-1", index)
    finally:
        database.close()


def _index_reader_sources(handoff):
    from evidence_agent.core.errors import PermissionDenied
    from evidence_agent.ingest.pipeline import IngestPipeline
    from evidence_agent.storage.catalog import Catalog
    registry = handoff.p03.registry
    reader = registry.access.authenticate("reader-a")
    for row in registry.database.connection.execute(
            "SELECT revision_id FROM document_revisions WHERE case_id='case-42' AND approval_status='APPROVED'").fetchall():
        try:
            registry.source_metadata(reader,row[0])
        except PermissionDenied:
            continue
        IngestPipeline(Catalog(registry),handoff.index).index(reader,row[0])


def test_http_explicit_audit_cache_reopens_and_discloses_window(handoff, monkeypatch):
    import time

    from evidence_agent.retrieval import audit_cache
    upload_approved(handoff)
    _index_reader_sources(handoff)
    headers = {"Authorization": "Bearer reader"}
    body = {"case_id": "case-42", "query": "scoped evidence"}
    strict = handoff.client.post("/search", headers=headers, json=body).json()["coverage"]
    assert strict["physical_audit_mode"] == "FRESH"
    assert strict["physical_cache_status"] == "DISABLED"
    body["reuse_physical_audit"] = True
    first = handoff.client.post("/search", headers=headers, json=body).json()["coverage"]
    assert first["index_coverage"] and first["physical_cache_status"] == "MISS"
    batches = handoff.index.batches
    second = handoff.client.post("/search", headers=headers, json=body).json()["coverage"]
    assert second["index_coverage"] and second["physical_cache_status"] == "HIT"
    assert second["physical_audit_mode"] == "CACHED"
    assert second["physical_verified_at"] == first["physical_verified_at"]
    assert handoff.index.batches == batches
    # Deliberate out-of-band corruption is the explicitly approved detection window.
    handoff.index.readback_mode = "missing"
    cached = handoff.client.get("/index-health", headers=headers,
        params={"case_id": "case-42", "reuse_physical_audit": True}).json()
    assert cached["index_coverage"] and cached["physical_audit_mode"] == "CACHED"
    strict = handoff.client.get("/index-health", headers=headers, params={"case_id": "case-42"}).json()
    import sqlite3
    with sqlite3.connect(handoff.p03.registry.database.path+".coverage-cache.sqlite") as connection:
        assert connection.execute("SELECT COUNT(*) FROM audits").fetchone()[0] == 0
    assert not strict["index_coverage"] and "INDEX_MANIFEST_MISMATCH" in strict["warnings"]
    monkeypatch.setattr(audit_cache, "time", SimpleNamespace(
        time=lambda: time.time()+6, monotonic=lambda: time.monotonic()+6))
    expired = handoff.client.post("/search", headers=headers, json=body).json()["coverage"]
    assert expired["physical_cache_status"] == "MISS" and not expired["index_coverage"]
    assert expired["physical_audit_mode"] == "FRESH"


def test_audit_cache_current_scope_backend_and_failure_controls(handoff, monkeypatch):
    import sqlite3
    revision = upload_approved(handoff)
    _index_reader_sources(handoff)
    headers = {"Authorization": "Bearer reader"}
    params = {"case_id": "case-42", "reuse_physical_audit": True}
    def get():
        response = handoff.client.get("/index-health", headers=headers, params=params)
        assert response.status_code == 200, response.text
        return response.json()
    assert get()["physical_cache_status"] == "MISS"
    assert get()["physical_cache_status"] == "HIT"
    handoff.index.audit_cache_identity = "other-isolated-backend"
    assert get()["physical_cache_status"] == "MISS"
    from evidence_agent.retrieval import coverage
    def locked(*_): raise sqlite3.OperationalError("locked")
    monkeypatch.setattr(coverage, "read_audit", locked)
    result = get()
    assert result["index_coverage"] and result["physical_cache_status"] == "UNAVAILABLE"
    assert result["physical_audit_mode"] == "FRESH"
    # Revocation cannot be bypassed by a warm physical snapshot.
    assert handoff.client.post(f"/sources/{revision}/revoke", headers={"Authorization":"Bearer admin"}).status_code == 200
    result = get()
    assert result["physical_cache_status"] != "HIT"


def test_audit_cache_storage_bounds_clocks_and_concurrency(tmp_path):
    import hashlib
    import sqlite3
    import time
    from concurrent.futures import ThreadPoolExecutor

    from evidence_agent.retrieval.audit_cache import MAX_BYTES, read_audit, write_audit
    path = tmp_path/"audit.sqlite"
    def write(number):
        try:
            write_audit(path,hashlib.sha256(str(number).encode()).hexdigest(),time.time(),time.monotonic())
            return True
        except sqlite3.OperationalError:
            return False # Busy cache is optional; caller's fresh fallback is tested above.
    assert write(0)
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(write,range(1,41)))
    assert any(results)
    with sqlite3.connect(path) as connection:
        assert 1 <= connection.execute("SELECT COUNT(*) FROM audits").fetchone()[0] <= 32
        row = connection.execute("SELECT key,wall,monotonic FROM audits LIMIT 1").fetchone()
        assert len(row[0]) == 64
        connection.execute("UPDATE audits SET wall=?,monotonic=? WHERE key=?",
            (time.time()+100,time.monotonic()+100,row[0]))
    assert read_audit(path,row[0]) is None
    assert path.stat().st_size <= MAX_BYTES
    oversized = tmp_path/"oversized.sqlite"
    oversized.write_bytes(b"x"*(MAX_BYTES+1))
    with pytest.raises(ValueError,match="size"):
        read_audit(oversized,"x")
    foreign = tmp_path/"foreign.sqlite"
    with sqlite3.connect(foreign) as connection:
        connection.execute("CREATE TABLE private(value TEXT)")
    before = foreign.read_bytes()
    with pytest.raises(ValueError,match="Unrecognized"):
        read_audit(foreign,"x")
    assert foreign.read_bytes() == before


@pytest.mark.parametrize("boundary", ["canonical", "physical"])
def test_coverage_aggregate_chunk_limit_degrades(tmp_path, monkeypatch, boundary):
    from evidence_agent.ingest.pipeline import IngestPipeline
    from evidence_agent.retrieval import coverage
    from evidence_agent.storage import catalog as catalog_module

    from .test_pipeline import _setup
    database, registry, catalog, uploader, revision, _ = _setup(tmp_path)
    try:
        index = HandoffIndex()
        IngestPipeline(catalog,index).index(uploader,revision)
        monkeypatch.setattr(catalog_module if boundary == "canonical" else coverage,
            "MAX_COVERAGE_CHUNKS",0)
        result = coverage.source_coverage(registry,uploader,"case-1",index)
        assert not result.index_coverage and result.indexed_source_count == 0
        assert ("CANONICAL_MANIFEST_UNAVAILABLE" if boundary == "canonical" else
            "COVERAGE_POINT_LIMIT") in result.warnings
    finally:
        database.close()


@pytest.mark.parametrize("change", ["source", "grant", "generation"])
def test_warm_cache_rechecks_canonical_state_after_lookup(tmp_path, monkeypatch, change):
    from evidence_agent.core.errors import PermissionDenied
    from evidence_agent.ingest.pipeline import IngestPipeline
    from evidence_agent.retrieval import coverage

    from .test_pipeline import _setup
    database, registry, catalog, uploader, revision, _ = _setup(tmp_path)
    try:
        index = HandoffIndex()
        IngestPipeline(catalog,index).index(uploader,revision)
        assert coverage.source_coverage(registry,uploader,"case-1",index,
            reuse_physical_audit=True).index_coverage
        original = coverage.read_audit
        def mutate_after_lookup(*args):
            result = original(*args)
            assert result is not None
            if change == "source":
                registry.revoke_source(registry.access.authenticate("approver"),revision)
            elif change == "grant":
                database.connection.execute("DELETE FROM principal_grants WHERE principal_id='uploader'")
            else:
                database.connection.execute("UPDATE document_revisions SET index_generation='replaced' WHERE revision_id=?",(revision,))
            return result
        monkeypatch.setattr(coverage,"read_audit",mutate_after_lookup)
        with pytest.raises(PermissionDenied):
            coverage.source_coverage(registry,uploader,"case-1",index,reuse_physical_audit=True)
    finally:
        database.close()


def test_the_approve_response_reports_the_aliases_it_registered(handoff):
    client = handoff.client
    body = {"case_id": "case-42", "family_id": "ALIAS-SOP", "filename": "ALIAS-SOP.md", "mime_type": "text/markdown",
            "content": "# ALIAS-SOP\n\nCites MS-1954 and ERR-77.", "owner_id": "uploader-a"}
    revision = client.post("/sources", headers={"Authorization": "Bearer uploader"}, json=body).json()["revision_id"]
    approved = client.post(f"/sources/{revision}/approve", headers={"Authorization": "Bearer admin"})
    assert approved.status_code == 200, approved.text
    aliases = approved.json()["aliases"]
    assert aliases["registered"] >= 4 and aliases["truncated"] is False, "family, revision and the two codes"


def test_reading_a_citation_back_takes_seven_extra_instants_and_not_eight(handoff):
    revision = upload_approved(handoff, valid_from="2020-01-01T00:00:00Z")
    headers = {"Authorization": "Bearer reader"}
    passage = handoff.client.post("/search", headers=headers,
                                  json={"case_id": "case-42", "query": "HANDOFF-SOP"}).json()["passages"][0]
    assert passage["revision_id"] == revision
    route = "/evidence/" + passage["citation_id"]
    seven = [f"2025-01-0{day}T00:00:00Z" for day in range(1, 8)]
    assert handoff.client.get(route, headers=headers,
                              params={"case_id": "case-42", "applicability_instants": seven}).status_code == 200
    assert handoff.client.get(route, headers=headers, params={
        "case_id": "case-42", "applicability_instants": [*seven, "2025-01-08T00:00:00Z"]}).status_code == 422
