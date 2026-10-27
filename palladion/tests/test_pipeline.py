from __future__ import annotations

from pathlib import Path

import pytest

from evidence_agent.core.errors import PermissionDenied, ResourceConflict
from evidence_agent.core.models import Principal
from evidence_agent.core.retrieval import Chunk
from evidence_agent.ingest.parsing import PARSER_VERSION
from evidence_agent.ingest.pipeline import IngestPipeline
from evidence_agent.storage.catalog import Catalog
from evidence_agent.storage.originals import OriginalStore
from evidence_agent.storage.registry import Registry
from evidence_agent.storage.sqlite import Database


def _principal(
    principal_id: str,
    *,
    roles: tuple[str, ...] = (),
    grants: tuple[str, ...] = (),
) -> Principal:
    return Principal(
        principal_id=principal_id,
        tenant_id="tenant-a",
        roles=roles,
        grants=grants,
    )


def _setup(tmp_path: Path) -> tuple[Database, Registry, Catalog, Principal, str, bytes]:
    database = Database(tmp_path / "registry.sqlite").open()
    registry = Registry(database, OriginalStore(tmp_path / "originals"))
    uploader = registry.bootstrap_principal(
        _principal("uploader", grants=("document:upload", "source:read"))
    )
    approver = registry.bootstrap_principal(
        _principal("approver", roles=("admin",), grants=("document:approve", "source:read"))
    )
    registry.bootstrap_case("tenant-a", "case-1")
    uploader = registry.bootstrap_membership(uploader, "case-1")
    approver = registry.bootstrap_membership(approver, "case-1")
    content = (
        "# Settlement\n\nHold settlement until the confirmation arrives.\n\n"
        "Exception: unless duplicate capture is confirmed.\n"
    ).encode("utf-8")
    revision = registry.register_source(
        uploader,
        tenant_id="tenant-a",
        case_id="case-1",
        family_id="DEMO.SETTLEMENT",
        content=content,
        source_path="demo/settlement.md",
        owner_id="uploader",
    )
    registry.approve_source(approver, revision)
    return database, registry, Catalog(registry), uploader, revision, content


class MemoryIndex:
    def __init__(self) -> None:
        self.fingerprint = "test-embedder-v1|test-tokenizer-v1"
        self.points: dict[tuple[str, str], dict[str, str]] = {}
        self.readback_mode = "actual"
        self.collection_ready = False

    def ensure_collection(self) -> None:
        self.collection_ready = True

    def upsert(
        self, chunks: tuple[Chunk, ...], generation: str, allowed_principal_ids: tuple[str, ...]
    ) -> None:
        assert self.collection_ready
        assert generation
        assert allowed_principal_ids == ()
        if chunks:
            self.points.setdefault((chunks[0].revision_id, generation), {}).update(
                {chunk.chunk_id: chunk.content_sha256 for chunk in chunks}
            )

    def generation_counts(self, tenant_id: str, case_id: str) -> dict[str, int]:
        if self.readback_mode == "missing":
            return {}
        return {generation: len(chunks) for (_, generation), chunks in self.points.items()}

    def readback(self, tenant_id: str, revision_id: str, generation: str) -> dict[str, str]:
        assert tenant_id == "tenant-a"
        assert revision_id
        assert generation
        if self.readback_mode == "missing":
            return {}
        actual = dict(self.points.get((revision_id, generation), {}))
        if self.readback_mode == "wrong_hash" and actual:
            first = next(iter(actual))
            actual[first] = "0" * 64
        elif self.readback_mode == "extra_id":
            actual["unexpected-chunk"] = "0" * 64
        return actual

    def query(self, query: str, principal: Principal, case_id: str, mode: str = "hybrid", limit: int = 20,
              exact: bool = False, generations: tuple[str, ...] | None = None):
        raise NotImplementedError


def test_p08_fixed_candidate_consumer_skips_native_query_but_rechecks_revocation(tmp_path):
    from evidence_agent.core.retrieval import Candidate
    from evidence_agent.retrieval.hybrid import HybridSearch
    database,registry,catalog,reader,revision,_=_setup(tmp_path)
    try:
        index=MemoryIndex()
        index.fingerprint="a"*64
        generation=IngestPipeline(catalog,index).index(reader,revision)
        chunk=catalog.chunks_for_revision(reader,revision)[0]
        frozen=(Candidate(chunk_id=chunk.chunk_id,generation=generation,score=1,channel="alternative"),)
        search=HybridSearch(catalog,index)
        positive=search.search(reader,"case-1","settlement",evaluator_candidates=frozen)
        assert positive.passages and positive.passages[0].citation_id==chunk.chunk_id
        assert positive.passages[0].text==chunk.text
        with pytest.raises(ValueError,match="bound"):
            search.search(reader,"case-1","settlement",evaluator_candidates=frozen*101)
        registry.revoke_source(registry.access.authenticate("approver"),revision)
        denied=search.search(reader,"case-1","settlement",evaluator_candidates=frozen)
        assert denied.passages==()
    finally:
        database.close()


def test_pipeline_publishes_only_exact_id_hash_readback_and_is_retry_safe(tmp_path: Path) -> None:
    database, registry, catalog, uploader, revision, original = _setup(tmp_path)
    index = MemoryIndex()
    index.readback_mode = "missing"
    pipeline = IngestPipeline(catalog, index)

    for mode in ("missing", "wrong_hash", "extra_id"):
        index.readback_mode = mode
        with pytest.raises(ResourceConflict):
            pipeline.index(uploader, revision)
        failed = catalog.generation_for_revision(uploader, revision)
        assert failed is not None and failed["state"] == "FAILED"
    assert catalog.eligible_generation_metadata(uploader, revision) is None

    index.readback_mode = "actual"
    generation = pipeline.index(uploader, revision)
    assert failed["generation"] == generation
    ready = catalog.eligible_generation_metadata(uploader, revision)
    assert ready is not None
    assert ready["generation"] == generation
    assert ready["state"] == "READY"
    chunks = catalog.chunks_for_revision(uploader, revision)
    manifest = catalog.manifest_for_generation(uploader, revision, generation)
    assert chunks
    assert manifest == {chunk.chunk_id: chunk.content_sha256 for chunk in chunks}
    assert all(original[chunk.start_byte : chunk.end_byte].decode("utf-8") == chunk.text for chunk in chunks)
    assert catalog.get_chunk(uploader, chunks[0].chunk_id) == chunks[0]

    database.close()
    reopened_db = Database(tmp_path / "registry.sqlite").open()
    reopened = Catalog(Registry(reopened_db, OriginalStore(tmp_path / "originals")))
    assert reopened.generation_for_revision(uploader, revision) == ready
    reopened_db.close()


def test_pipeline_requires_approved_authorized_source_and_graph_off_is_explicit(tmp_path: Path) -> None:
    database, registry, catalog, uploader, revision, _ = _setup(tmp_path)
    reader = registry.bootstrap_principal(_principal("reader", grants=("case:read",)))
    reader = registry.bootstrap_membership(reader, "case-1")
    index = MemoryIndex()
    pipeline = IngestPipeline(catalog, index)

    with pytest.raises(PermissionDenied):
        pipeline.index(reader, revision)
    assert index.points == {}
    database.close()


def test_pipeline_reuses_active_generation_after_fingerprint_returns_to_prior_value(
    tmp_path: Path,
) -> None:
    database, _, catalog, uploader, revision, _ = _setup(tmp_path)
    index = MemoryIndex()
    pipeline = IngestPipeline(catalog, index)

    generation_a = pipeline.index(uploader, revision)
    index.fingerprint = "test-embedder-v2|test-tokenizer-v1"
    generation_b = pipeline.index(uploader, revision)
    assert generation_b != generation_a

    index.fingerprint = "test-embedder-v1|test-tokenizer-v1"
    assert pipeline.index(uploader, revision) == generation_a
    active = catalog.eligible_generation_metadata(uploader, revision)
    assert active is not None
    assert active["generation"] == generation_a
    assert active["state"] == "READY"

    database.close()


def test_catalog_exact_alias_and_exception_link_are_scoped_and_audited(tmp_path: Path) -> None:
    database, registry, catalog, uploader, revision, content = _setup(tmp_path)
    index = MemoryIndex()
    generation = IngestPipeline(catalog, index).index(uploader, revision)
    chunks = catalog.chunks_for_revision(uploader, revision)
    rule = next(chunk for chunk in chunks if "Hold settlement" in chunk.text)
    approver = registry.get_principal("approver")
    assert approver is not None
    with pytest.raises(PermissionDenied):
        catalog.add_aliases(uploader, revision, [("ERR-DEMO-429", rule.chunk_id)])
    catalog.add_aliases(approver, revision, [("ERR-DEMO-429", rule.chunk_id)])
    assert [hit.chunk_id for hit in catalog.alias_hits(uploader, "case-1", "err-demo-429")] == [rule.chunk_id]
    assert catalog.alias_hits(uploader, "case-1", "ERR-DEMO-42") == ()

    appendix = b"# Appendix\n\nException: duplicate capture is confirmed.\n"
    appendix_revision = registry.register_source(
        uploader,
        tenant_id="tenant-a",
        case_id="case-1",
        family_id="DEMO.SETTLEMENT.APPENDIX",
        content=appendix,
        source_path="demo/settlement-appendix.md",
        owner_id="uploader",
    )
    registry.approve_source(approver, appendix_revision)
    IngestPipeline(catalog, index).index(uploader, appendix_revision)
    appendix_chunk = catalog.chunks_for_revision(uploader, appendix_revision)[-1]
    catalog.add_context_link(approver, rule.chunk_id, appendix_chunk.chunk_id)
    assert catalog.context_links(uploader, rule.chunk_id) == (appendix_chunk.chunk_id,)

    other = registry.bootstrap_principal(
        _principal("other", grants=("document:upload", "source:read"))
    )
    registry.bootstrap_case("tenant-a", "case-2")
    other = registry.bootstrap_membership(other, "case-2")
    with pytest.raises(PermissionDenied):
        catalog.context_links(other, rule.chunk_id)
    assert generation
    database.close()


def test_delayed_generation_cannot_publish_over_newer_staged_generation(tmp_path: Path) -> None:
    database, _, catalog, uploader, revision, content = _setup(tmp_path)
    index = MemoryIndex()
    IngestPipeline(catalog, index).index(uploader, revision)
    chunks = catalog.chunks_for_revision(uploader, revision)
    older = catalog.stage_generation(uploader, revision, chunks, source_bytes=content,
                                     fingerprint="older-config", parser_version=PARSER_VERSION)
    newer = catalog.stage_generation(uploader, revision, chunks, source_bytes=content,
                                     fingerprint="newer-config", parser_version=PARSER_VERSION)
    readback = {chunk.chunk_id: chunk.content_sha256 for chunk in chunks}
    with pytest.raises(ResourceConflict):
        catalog.reconcile(uploader, revision, older, readback)
    source = catalog.registry.source_metadata(uploader, revision)
    assert source["index_generation"] == newer
    assert source["index_state"] == "INDEXING"
    assert catalog.reconcile(uploader, revision, newer, readback)
    assert catalog.eligible_generation_metadata(uploader, revision)["generation"] == newer
    database.close()


def test_exact_alias_write_rechecks_revocation_inside_transaction(tmp_path, monkeypatch):
    from contextlib import contextmanager
    database, registry, catalog, uploader, revision, _ = _setup(tmp_path)
    try:
        IngestPipeline(catalog,MemoryIndex()).index(uploader,revision)
        actor = registry.access.authenticate("approver")
        chunk = catalog.chunks_for_revision(actor,revision)[0]
        original = database.transaction
        @contextmanager
        def revoke_before_begin():
            monkeypatch.setattr(database,"transaction",original)
            registry.revoke_grant(actor,"approver","document:approve")
            with original() as connection:
                yield connection
        monkeypatch.setattr(database,"transaction",revoke_before_begin)
        with pytest.raises(PermissionDenied):
            catalog.add_aliases(actor,revision,[("RACE-GUARD",chunk.chunk_id)])
        assert not database.connection.execute("SELECT 1 FROM exact_aliases WHERE alias='RACE-GUARD'").fetchall()
    finally:
        database.close()
