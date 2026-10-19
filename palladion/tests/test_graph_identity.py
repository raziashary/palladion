import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from evidence_agent.core.errors import PermissionDenied, ResourceConflict
from evidence_agent.core.ids import (
    canonical_entity_key,
    chunk_id,
    digest_bytes,
    evidence_ref_id,
    provisional_entity_key,
    revision_id,
)
from evidence_agent.core.retrieval import Candidate
from evidence_agent.graph.registry import GraphRegistry
from evidence_agent.graph.relations import RelationCandidate, TraversalLimits
from evidence_agent.ingest.pipeline import IngestPipeline
from evidence_agent.retrieval.graph_expand import GraphExpansion
from evidence_agent.retrieval.hybrid import HybridSearch
from evidence_agent.storage.catalog import Catalog
from evidence_agent.storage.neo4j import Neo4jIndex
from evidence_agent.storage.originals import OriginalStore
from evidence_agent.storage.registry import Registry
from evidence_agent.storage.sqlite import Database

from .test_pipeline import MemoryIndex, _setup


def test_revision_chunk_and_evidence_ids_are_stable_and_namespace_scoped() -> None:
    content_hash = digest_bytes(b"immutable source")
    revision = revision_id("tenant-a", "family-1", content_hash)
    assert revision == revision_id("tenant-a", "family-1", content_hash)
    assert revision != revision_id("tenant-b", "family-1", content_hash)
    assert revision != revision_id("tenant-a", "family-2", content_hash)
    assert revision != revision_id("tenant-a", "family-1", digest_bytes(b"changed source"))

    first_chunk = chunk_id("tenant-a", revision, 0, 10)
    assert first_chunk == chunk_id("tenant-a", revision, 0, 10)
    assert first_chunk != chunk_id("tenant-a", revision, 0, 11)
    assert first_chunk != chunk_id("tenant-b", revision, 0, 10)
    assert evidence_ref_id("tenant-a", revision, 0, 10, content_hash) == evidence_ref_id(
        "tenant-a", revision, 0, 10, content_hash
    )


def test_digest_requires_bytes_and_spans_are_validated() -> None:
    with pytest.raises(TypeError):
        digest_bytes("source")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        chunk_id("tenant-a", "rev-1", -1, 2)
    with pytest.raises(ValueError):
        chunk_id("tenant-a", "rev-1", 4, 2)


def test_verified_namespace_id_is_the_only_canonical_entity_identity() -> None:
    key = canonical_entity_key(
        "tenant-a", "merchant-registry", "merchant", "merchant-1042"
    )
    assert key == canonical_entity_key(
        "tenant-a", "merchant-registry", "merchant", "merchant-1042"
    )
    assert key != canonical_entity_key(
        "tenant-b", "merchant-registry", "merchant", "merchant-1042"
    )
    assert key != canonical_entity_key(
        "tenant-a", "different-registry", "merchant", "merchant-1042"
    )

    provisional = provisional_entity_key("tenant-a", "rev-1", 10, 20)
    assert provisional != provisional_entity_key("tenant-a", "rev-2", 10, 20)
    assert provisional != provisional_entity_key("tenant-a", "rev-1", 10, 21)
    assert provisional != key
    # There is deliberately no name/category based merge helper.


def test_attestation_authority_distinct_ids_reviews_merge_history_and_revocation(tmp_path):
    database, registry, catalog, uploader, revision, _ = _setup(tmp_path)
    try:
        IngestPipeline(catalog, MemoryIndex()).index(uploader, revision)
        chunks = catalog.chunks_for_revision(uploader, revision)
        admin = registry.access.authenticate("approver")
        graph = GraphRegistry(catalog, admin, "case-1")
        with pytest.raises(PermissionDenied):
            GraphRegistry(catalog, uploader, "case-1").attest(chunks[0].chunk_id,
                kind="concept",display_name="Same name",external_id="A")
        first = graph.attest(chunks[0].chunk_id,kind="concept",display_name="Same name",external_id="A")
        second = graph.attest(chunks[-1].chunk_id,kind="concept",display_name="Same name",external_id="B")
        assert first != second
        assert first == graph.attest(chunks[0].chunk_id,kind="concept",display_name="Same name",external_id="A")
        assert len(graph.entity(first)) == 1
        edge = graph.relation(RelationCandidate(from_key=first,to_key=second,
            relation_type="EXCEPTION_TO",evidence_chunk_id=chunks[-1].chunk_id))
        assert graph.edge(edge)["evidence_kind"] == "EXTRACTED_UNREVIEWED"
        graph.review(edge,accepted=False,reason="Unsupported proposed connection")
        with pytest.raises(PermissionDenied):
            graph.edge(edge)
        rejected = graph.merge(first,second,evidence_chunk_id=chunks[-1].chunk_id,
            accepted=False,reason="Different verified external IDs")
        accepted = graph.merge(first,second,evidence_chunk_id=chunks[-1].chunk_id,
            accepted=True,reason="Explicit synthetic equivalence attestation")
        assert graph.canonical_key(first)==second
        with pytest.raises(ValueError,match="Cyclic"):
            graph.merge(second,first,evidence_chunk_id=chunks[-1].chunk_id,
                accepted=True,reason="Cycle must not be admitted")
        history = graph.merge_history(first)
        assert [r["decision_id"] for r in history] == [rejected,accepted]
        assert history[1]["from_key"] == first and history[1]["to_key"] == second
        registry.revoke_source(admin,revision)
        with pytest.raises(PermissionDenied):
            graph.entity(first)
    finally:
        database.close()


def test_merge_writer_rejects_chain_its_bounded_reader_cannot_open(tmp_path):
    database,registry,catalog,_,revision,_=_setup(tmp_path)
    try:
        admin=registry.access.authenticate("approver")
        IngestPipeline(catalog,MemoryIndex()).index(admin,revision)
        chunk=catalog.chunks_for_revision(admin,revision)[0]
        control=GraphRegistry(catalog,admin,"case-1")
        keys=[control.attest(chunk.chunk_id,kind="concept",display_name="Depth control",external_id=f"depth-{i}") for i in range(9)]
        for i in range(7,0,-1):
            control.merge(keys[i],keys[i+1],evidence_chunk_id=chunk.chunk_id,accepted=True,reason="Bounded synthetic equivalence")
        assert control.canonical_key(keys[1])==keys[8]
        with pytest.raises(ValueError,match="depth"):
            control.merge(keys[0],keys[1],evidence_chunk_id=chunk.chunk_id,accepted=True,reason="Would exceed reader depth")
        assert control.canonical_key(keys[0])==keys[0]
        assert database.connection.execute("SELECT count(*) FROM graph_merge_decisions").fetchone()[0]==7
    finally:
        database.close()


def test_canonical_attestation_race_and_graph_off_has_no_connection(tmp_path,monkeypatch):
    database,registry,catalog,uploader,revision,_=_setup(tmp_path)
    def forbidden(*args,**kwargs):
        raise AssertionError("Graph-off connected to Neo4j")
    monkeypatch.setattr("neo4j.GraphDatabase.driver",forbidden)
    try:
        IngestPipeline(catalog,MemoryIndex()).index(uploader,revision)
        chunk=catalog.chunks_for_revision(uploader,revision)[0]
        def attest(_):
            with Database(tmp_path/"registry.sqlite") as db:
                owner=Registry(db,OriginalStore(tmp_path/"originals"))
                return GraphRegistry(Catalog(owner),owner.access.authenticate("approver"),"case-1").attest(
                    chunk.chunk_id,kind="concept",display_name="Same",external_id="external-A")
        with ThreadPoolExecutor(max_workers=4) as pool:
            keys=list(pool.map(attest,range(8)))
        assert len(set(keys))==1
        assert database.connection.execute("SELECT count(*) FROM graph_entity_attestations").fetchone()[0]==1
    finally:
        database.close()


@pytest.mark.skipif(os.environ.get("PALLADION_TEST_NEO4J") != "1",
                    reason="Explicit isolated local Neo4j enablement required")
def test_real_neo4j_concurrent_unique_identity_and_scoped_neighbors():
    partition = "p07_test_" + uuid.uuid4().hex
    graph = Neo4jIndex(partition=partition, timeout_seconds=10)
    try:
        graph.ensure_constraints()
        first = canonical_entity_key("a","registry","concept","A")
        second = canonical_entity_key("a","registry","concept","B")
        def upsert(_):
            graph.upsert_chunk("a","case","rev","generation","source","a"*64,(first,))
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(upsert,range(8)))
        assert graph.entity_count("a","case",first) == 1
        graph.upsert_chunk("a","case","rev2","generation2","exception","b"*64,(second,))
        graph.upsert_edge("a","case","edge",first,second,"EXCEPTION_TO","exception","EXPLICIT_SOURCE")
        rows = graph.neighbors("a","case",("source",),fanout=2)
        assert rows == ({"edge_id":"edge","chunk_id":"exception","generation":"generation2"},)
        assert graph.neighbors("b","case",("source",),fanout=2) == ()
        assert graph.neighbors("a","other-case",("source",),fanout=2) == ()
        # A real high-degree hub remains bounded and private neighbors are filtered
        # before returning any IDs; these raw rows still need canonical resolver checks.
        for number in range(33):
            key=canonical_entity_key("a","registry","concept",f"private-{number}")
            graph.upsert_chunk("a","case",f"private-rev-{number}","private-generation",
                f"RESTRICTED_CANARY_{number}","c"*64,(key,),allowed_principal_ids=("private-reader",))
            graph.upsert_edge("a","case",f"hub-{number}",first,key,"REFERENCES",
                f"RESTRICTED_CANARY_{number}","EXTRACTED_UNREVIEWED")
        public=graph.neighbors("a","case",("source",),fanout=2,principal_id="public-reader")
        assert public==rows
        private=graph.neighbors("a","case",("source",),fanout=2,principal_id="private-reader")
        assert len(private)==2
        assert graph._run("MATCH(e:PalladionEdge {partition:$partition}) RETURN count(e) AS count")[0]["count"]==34
        assert graph.readback("a","rev","generation") == {"source":"a"*64}
        with pytest.raises(ValueError):
            graph.neighbors("a","case",("source",),fanout=33)
        with pytest.raises(ValueError):
            graph.upsert_edge("a","case","bad",first,second,"DELETE", "source","EXPLICIT_SOURCE")
    finally:
        # Owner-approved cleanup of this test's fresh UUID only, never a shared reset.
        assert partition.startswith("p07_test_")
        graph._run("MATCH (n) WHERE n.partition=$partition DETACH DELETE n")
        graph.close()


@pytest.mark.skipif(os.environ.get("PALLADION_TEST_NEO4J") != "1",
                    reason="Explicit isolated local Neo4j enablement required")
def test_real_graph_publication_freezes_entities_relations_and_recovers_missing_readback(tmp_path, monkeypatch):
    database, registry, catalog, _, revision, _ = _setup(tmp_path)
    graph = Neo4jIndex(partition="p07_test_"+uuid.uuid4().hex, timeout_seconds=10)
    try:
        admin = registry.access.authenticate("approver")
        index = MemoryIndex()
        pipeline = IngestPipeline(catalog,index,graph)
        initial = pipeline.index(admin,revision)
        metadata = catalog.eligible_generation_metadata(admin,revision)
        assert metadata is not None and metadata["graph_enabled"] is True
        assert set(metadata["required_backends"]) == {"qdrant","neo4j"}
        chunks=catalog.chunks_for_revision(admin,revision)
        control=GraphRegistry(catalog,admin,"case-1")
        first=control.attest(chunks[0].chunk_id,kind="concept",display_name="procedure",external_id="A")
        second=control.attest(chunks[-1].chunk_id,kind="concept",display_name="exception",external_id="B")
        edge=control.relation(RelationCandidate(from_key=first,to_key=second,
            relation_type="EXCEPTION_TO",evidence_chunk_id=chunks[-1].chunk_id))
        original=graph.projection_readback
        def missing(*args):
            result=original(*args)
            assert "r:"+edge in result  # Actual producer wrote its relation.
            result.pop("r:"+edge)       # Deliberately corrupt the reader envelope.
            return result
        monkeypatch.setattr(graph,"projection_readback",missing)
        with pytest.raises(ResourceConflict):
            pipeline.index(admin,revision)
        assert catalog.eligible_generation_metadata(admin,revision) is None
        monkeypatch.setattr(graph,"projection_readback",original)
        revised=pipeline.index(admin,revision)
        assert revised!=initial
        assert catalog.eligible_generation_metadata(admin,revision) is not None
        assert "r:"+edge in original("tenant-a",revision,revised)
        def broken_adjacency(*args):
            graph._run("MATCH(r:PalladionEdge {partition:$partition,edge_id:$edge})-[link:TO]->() DELETE link",edge=edge)
            return original(*args)
        monkeypatch.setattr(graph,"projection_readback",broken_adjacency)
        with pytest.raises(ResourceConflict):
            pipeline.index(admin,revision)
        monkeypatch.setattr(graph,"projection_readback",original)
        assert pipeline.index(admin,revision)==revised
        control.merge(first,second,evidence_chunk_id=chunks[-1].chunk_id,accepted=True,
                      reason="Explicit source-backed equivalence")
        merged=pipeline.index(admin,revision)
        assert merged!=revised
        assert control.canonical_key(first)==second
        assert graph.entity_count("tenant-a","case-1",second)==1
        mentions=graph._run("MATCH(e:PalladionEntity)-[:MENTIONED_IN]->(c:PalladionChunk "
            "{partition:$partition,generation:$generation}) RETURN collect(DISTINCT e.entity_key) AS keys",
            generation=merged)[0]["keys"]
        assert first not in mentions and second in mentions
    finally:
        graph._run("MATCH(n) WHERE n.partition=$partition DETACH DELETE n")
        graph.close()
        database.close()


@pytest.mark.skipif(os.environ.get("PALLADION_TEST_NEO4J")!="1",reason="Explicit isolated local Neo4j")
def test_real_bounded_two_hop_navigation_canonical_revocation_and_required_outage(tmp_path,monkeypatch):
    database,registry,catalog,uploader,revision,_=_setup(tmp_path)
    backend=Neo4jIndex(partition="p07_test_"+uuid.uuid4().hex,timeout_seconds=10)
    admin=registry.access.authenticate("approver")
    class AnchorIndex(MemoryIndex):
        def query(self,*args,**kwargs):
            return (Candidate(chunk_id=anchor,generation=generation,score=1,channel="controlled-anchor"),)
    index=AnchorIndex()
    index.fingerprint="a"*64
    try:
        revisions=[revision]
        for number in (1,2):
            identifier=registry.register_source(uploader,tenant_id="tenant-a",case_id="case-1",
                family_id=f"P07.NAV.{number}",content=f"# Navigation {number}\n\nSynthetic source relation {number}.".encode(),
                source_path=f"nav-{number}.md",owner_id="uploader")
            registry.approve_source(admin,identifier)
            revisions.append(identifier)
        for identifier in revisions:
            IngestPipeline(catalog,index).index(admin,identifier)
        chunks=[catalog.chunks_for_revision(admin,r)[0] for r in revisions]
        control=GraphRegistry(catalog,admin,"case-1")
        keys=[control.attest(c.chunk_id,kind="concept",display_name=f"Navigation {i}") for i,c in enumerate(chunks)]
        for i in (0,1):
            control.relation(RelationCandidate(from_key=keys[i],to_key=keys[i+1],relation_type="REFERENCES",
                evidence_chunk_id=chunks[i+1].chunk_id))
        for identifier in revisions:
            IngestPipeline(catalog,index,backend).index(admin,identifier)
        anchor=chunks[0].chunk_id
        generation=catalog.eligible_generation_metadata(uploader,revision)["generation"]
        base=HybridSearch(catalog,index)
        assert [p.citation_id for p in base.search(uploader,"case-1","navigation",limit=3).passages]==[anchor]
        search=HybridSearch(catalog,index,graph=GraphExpansion(backend,TraversalLimits(timeout_seconds=10)))
        result=search.search(uploader,"case-1","navigation",limit=3,require_graph=True)
        assert {p.citation_id for p in result.passages}=={c.chunk_id for c in chunks},result.model_dump()
        assert len(result.graph_paths)==2 and all(p.navigation_only and p.includes_unreviewed for p in result.graph_paths)
        assert {p.target_chunk_id for p in result.graph_paths}=={c.chunk_id for c in chunks[1:]}
        one=GraphExpansion(backend,TraversalLimits(hops=1,timeout_seconds=10)).expand(base.resolver,uploader,"case-1",(result.passages[0],))
        assert [p.citation_id for p in one.passages]==[chunks[1].chunk_id]
        capped=GraphExpansion(backend,TraversalLimits(nodes=2,timeout_seconds=10)).expand(base.resolver,uploader,"case-1",(result.passages[0],))
        assert capped.bounded and len(capped.passages)==1
        limited=GraphExpansion(backend,TraversalLimits(fanout=1,timeout_seconds=10)).expand(
            base.resolver,uploader,"case-1",(result.passages[0],))
        assert limited.bounded
        def outage(*args,**kwargs):
            from evidence_agent.core.errors import DependencyUnavailable
            raise DependencyUnavailable("deliberate graph failure")
        original=backend.neighbors
        raw=original("tenant-a","case-1",(anchor,),fanout=8,principal_id=uploader.principal_id)
        def poisoned(*args,**kwargs):
            return ({"edge_id":raw[0]["edge_id"],"chunk_id":chunks[-1].chunk_id,
                "generation":catalog.eligible_generation_metadata(uploader,revisions[-1])["generation"]},)
        monkeypatch.setattr(backend,"neighbors",poisoned)
        assert search.graph.expand(base.resolver,uploader,"case-1",(result.passages[0],)).passages==()
        monkeypatch.setattr(backend,"neighbors",original)
        from evidence_agent.core.errors import DependencyUnavailable
        with pytest.raises(DependencyUnavailable):
            GraphExpansion(backend,TraversalLimits(timeout_seconds=0.0001)).expand(
                base.resolver,uploader,"case-1",(result.passages[0],))
        monkeypatch.setattr(backend,"neighbors",outage)
        optional=search.search(uploader,"case-1","navigation")
        assert optional.status=="DEGRADED" and optional.passages and "GRAPH_UNAVAILABLE" in optional.warnings
        required=search.search(uploader,"case-1","navigation",require_graph=True)
        assert required.status=="UNAVAILABLE" and "GRAPH_REQUIRED_UNAVAILABLE" in required.warnings
        monkeypatch.setattr(backend,"neighbors",original)
        registry.revoke_source(admin,revisions[-1])
        final=search.search(uploader,"case-1","navigation")
        assert chunks[-1].chunk_id not in {p.citation_id for p in final.passages}
        generation=IngestPipeline(catalog,index).index(admin,revision)
        graph_off_anchor=search.search(uploader,"case-1","navigation",require_graph=True)
        assert graph_off_anchor.status=="UNAVAILABLE"
        assert "GRAPH_REQUIRED_UNAVAILABLE" in graph_off_anchor.warnings
    finally:
        backend._run("MATCH(n) WHERE n.partition=$partition DETACH DELETE n")
        backend.close()
        database.close()
