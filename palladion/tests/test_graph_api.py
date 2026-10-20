"""Scoped exact-proof graph API consumers, no live services."""
import pytest

from evidence_agent.core.models import Principal
from evidence_agent.ingest.pipeline import IngestPipeline
from evidence_agent.storage.catalog import Catalog

from .test_pipeline import MemoryIndex
from .test_runtime_api import api as runtime_api


@pytest.fixture
def api(p03):
    yield from runtime_api.__wrapped__(p03)


def test_graph_link_atomic_idempotent_readback_denial_and_revocation(api, p03):
    client, app = api
    index = MemoryIndex()
    app.state.index = index
    catalog = Catalog(p03.registry)
    revision = p03.revisions["SOP-2026-B"]
    IngestPipeline(catalog, index).index(p03.admin, revision)
    left, right = catalog.chunks_for_revision(p03.admin, revision)[:2]
    link = {"from_chunk_id": left.chunk_id, "to_chunk_id": right.chunk_id,
            "relation_type": "REFERENCES", "evidence_chunk_id": right.chunk_id,
            "revision_id": right.revision_id, "start_byte": right.start_byte,
            "end_byte": right.end_byte, "quote": right.text}
    route = "/v1/admin/cases/case-42/graph-links"
    admin = {"Authorization": "Bearer admin-test"}
    reader = {"Authorization": "Bearer reader-test"}
    assert client.post(route, headers=reader, json={"links": [link]}).status_code == 403
    assert client.post(route, headers=admin, json={"links": [{**link, "quote": "wrong"}]}).status_code == 400
    assert client.post(route, headers=admin, json={"links": [link, {**link, "quote": "wrong"}]}).status_code == 400
    assert p03.registry.database.connection.execute("SELECT count(*) FROM graph_relations").fetchone()[0] == 0
    response = client.post(route, headers=admin, json={"links": [link]})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["projection"] == "NOT_ENABLED"
    proof = result["links"][0]
    assert proof["quote"] == right.text and proof["navigation_only"] is True
    assert client.post(route, headers=admin, json={"links": [link]}).json() == result
    read_route = f'/v1/cases/case-42/graph-links/{proof["edge_id"]}'
    assert client.get(read_route, headers=reader).json() == proof
    assert client.post(route, headers=admin, json={"links": [{**link, "quote": link["quote"][1:],
        "start_byte": right.start_byte + 1}]}).status_code == 409
    p03.registry.revoke_source(p03.admin, right.revision_id)
    assert client.get(read_route, headers=reader).status_code == 403


def test_admin_cannot_link_unreadable_endpoint_or_spoof_proof(api, p03):
    client, app = api

    class HashOnlyIndex(MemoryIndex):
        def upsert(self, chunks, generation, allowed_principal_ids):
            # The test index acknowledges hashes only; canonical readers enforce the ACL.
            super().upsert(chunks, generation, ())

    app.state.index = index = HashOnlyIndex()
    catalog = Catalog(p03.registry)
    chunks = []
    for family in ("SOP-2026-B", "EX-2026-04"):
        revision = p03.revisions[family]
        IngestPipeline(catalog, index).index(p03.admin, revision)
        chunks.append(catalog.chunks_for_revision(p03.admin, revision)[0])
    left, right = chunks
    limited = p03.registry.bootstrap_principal(Principal(principal_id="limited-admin",
        tenant_id="tenant-a", roles=("admin",), grants=("case:read", "source:read", "document:approve")))
    p03.registry.bootstrap_membership(limited, "case-42")
    app.state.tokens["limited-test"] = limited.principal_id
    link = {"from_chunk_id": left.chunk_id, "to_chunk_id": right.chunk_id,
            "relation_type": "REFERENCES", "evidence_chunk_id": right.chunk_id,
            "revision_id": right.revision_id, "start_byte": right.start_byte,
            "end_byte": right.end_byte, "quote": right.text}
    route = "/v1/admin/cases/case-42/graph-links"
    assert client.post(route, headers={"Authorization": "Bearer limited-test"},
                       json={"links": [link]}).status_code == 403
    admin = {"Authorization": "Bearer admin-test"}
    assert client.post(route, headers=admin, json={"links": [{**link, "revision_id": left.revision_id}]}).status_code == 400
    assert client.post(route, headers=admin, json={"links": [{k: v for k, v in link.items() if k != "quote"}]}).status_code == 422
    assert client.post(route, headers=admin, json={"links": [{**link, "relation_type": "DELETE"}]}).status_code == 422
    assert client.post("/v1/admin/cases/foreign-case/graph-links", headers=admin,
                       json={"links": [link]}).status_code == 403
