from __future__ import annotations

import hashlib
from types import SimpleNamespace
from typing import Any

import pytest
from qdrant_client import models
from qdrant_client.http.exceptions import ResponseHandlingException

from evidence_agent.core.errors import DependencyUnavailable
from evidence_agent.core.models import Principal
from evidence_agent.core.retrieval import Chunk
from evidence_agent.retrieval.embeddings import (
    EMBEDDING_DIMENSION,
    MODEL_NAME,
    MODEL_REVISION,
)
from evidence_agent.retrieval.rerank import FastEmbedReranker
from evidence_agent.storage.qdrant import IndexConsistencyError, QdrantIndex


class _Encoder:
    dimension = 3
    fingerprint = "a" * 64

    def embed_documents(self, texts: Any) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]


class _Client:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.created = False
        self.points: list[Any] = []
        self.payload_schema: dict[str, Any] = {}
        self.dense_size = 3
        self.dense_distance = models.Distance.COSINE
        self.sparse_modifier = models.Modifier.IDF
        self.query_response = SimpleNamespace(points=[])
        self.query_error: Exception | None = None

    def collection_exists(self, collection_name: str) -> bool:
        self.calls.append(("collection_exists", {"collection_name": collection_name}))
        return self.created

    def info(self) -> Any:
        return SimpleNamespace(version="1.19.2")

    def create_collection(self, **kwargs: Any) -> None:
        self.calls.append(("create_collection", kwargs))
        self.created = True
        self.dense_size = kwargs["vectors_config"]["dense"].size
        self.dense_distance = kwargs["vectors_config"]["dense"].distance
        self.sparse_modifier = kwargs["sparse_vectors_config"]["bm25"].modifier

    def get_collection(self, **kwargs: Any) -> Any:
        self.calls.append(("get_collection", kwargs))
        return SimpleNamespace(
            config=SimpleNamespace(
                params=SimpleNamespace(
                    vectors={
                        "dense": models.VectorParams(
                            size=self.dense_size, distance=self.dense_distance
                        )
                    },
                    sparse_vectors={
                        "bm25": models.SparseVectorParams(modifier=self.sparse_modifier)
                    },
                )
            ),
            payload_schema=self.payload_schema,
            status="green",
            points_count=len(self.points),
            indexed_vectors_count=len(self.points) * 2,
        )

    def create_payload_index(self, **kwargs: Any) -> None:
        self.calls.append(("create_payload_index", kwargs))
        self.payload_schema[kwargs["field_name"]] = SimpleNamespace(
            data_type=kwargs["field_schema"]
        )

    def upsert(self, **kwargs: Any) -> None:
        self.calls.append(("upsert", kwargs))
        self.points.extend(kwargs["points"])

    def scroll(self, **kwargs: Any) -> tuple[list[Any], None]:
        self.calls.append(("scroll", kwargs))
        points = [
            SimpleNamespace(
                payload=point.payload,
                vector={
                    **({"dense": point.vector["dense"]} if "dense" in point.vector else {}),
                    **(
                        {"bm25": models.SparseVector(indices=[2], values=[1.0])}
                        if "bm25" in point.vector
                        else {}
                    ),
                },
            )
            for point in self.points
            if point.payload["tenant_id"] == "tenant-a"
            and point.payload["revision_id"] == "revision-1"
            and point.payload["index_generation"] == "generation-1"
        ]
        return points, None

    def query_points(self, **kwargs: Any) -> Any:
        self.calls.append(("query_points", kwargs))
        if self.query_error is not None:
            raise self.query_error
        return self.query_response

    def close(self) -> None:
        self.calls.append(("close", {}))


def _chunk(chunk_id: str = "chunk-1", text: str = "A synthetic source clause.") -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        tenant_id="tenant-a",
        case_id="case-a",
        revision_id="revision-1",
        section_id="section-1",
        start_byte=0,
        end_byte=len(text.encode()),
        line_start=1,
        line_end=1,
        text=text,
        content_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        source_sha256="2" * 64,
    )


def _principal() -> Principal:
    return Principal(
        principal_id="principal-a",
        tenant_id="tenant-a",
        allowed_case_ids=("case-a",),
    )


def _index(profile: str = "english") -> tuple[QdrantIndex, _Client]:
    client = _Client()
    return (
        QdrantIndex(
            collection_name="p02_test_contract",
            client=client,  # type: ignore[arg-type]
            encoder=_Encoder(),
            bm25_profile=profile,  # type: ignore[arg-type]
            active_generation="generation-1",
        ),
        client,
    )


def test_embedding_selection_is_pinned_and_multilingual() -> None:
    assert MODEL_NAME == "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    assert MODEL_REVISION == "faf4aa4225822f3bc6376869cb1164e8e3feedd0"
    assert EMBEDDING_DIMENSION == 384


def test_ensure_collection_indexes_scope_before_upsert_and_stores_both_vectors() -> None:
    index, client = _index()

    index.upsert((_chunk(),), "generation-1", ("principal-a",))

    names = [call[0] for call in client.calls]
    upsert_position = names.index("upsert")
    assert names.index("create_collection") < upsert_position
    indexed = [
        call[1]["field_name"]
        for call in client.calls
        if call[0] == "create_payload_index"
    ]
    assert indexed == [
        "tenant_id",
        "case_id",
        "revision_id",
        "index_generation",
        "case_members",
        "allowed_principal_ids",
    ]
    case_members_index = next(
        call[1]["field_schema"]
        for call in client.calls
        if call[0] == "create_payload_index" and call[1]["field_name"] == "case_members"
    )
    assert case_members_index == models.PayloadSchemaType.BOOL
    point = client.points[0]
    assert set(point.vector) == {"dense", "bm25"}
    assert point.vector["bm25"].model == "Qdrant/bm25"
    assert point.payload["allowed_principal_ids"] == ["principal-a"]
    assert point.payload["index_generation"] == "generation-1"
    assert point.payload["case_members"] is False
    assert "text" not in point.payload


def test_ensure_collection_creates_only_missing_indexes_and_checks_existing_schema() -> None:
    index, client = _index()

    index.ensure_collection()
    index.ensure_collection()

    index_calls = [call for call in client.calls if call[0] == "create_payload_index"]
    assert len(index_calls) == 6
    client.dense_size = 4
    with pytest.raises(IndexConsistencyError, match="configured dimension"):
        index.ensure_collection()


def test_readback_requires_both_vectors_and_valid_payload_hashes() -> None:
    index, client = _index()
    index.upsert((_chunk(),), "generation-1", ("principal-a",))

    expected_hash = hashlib.sha256(_chunk().text.encode()).hexdigest()
    assert index.readback("tenant-a", "revision-1", "generation-1") == {
        "chunk-1": expected_hash
    }
    client.points[0].vector.pop("dense")
    with pytest.raises(IndexConsistencyError, match="missing a dense or BM25 vector"):
        index.readback("tenant-a", "revision-1", "generation-1")


def test_query_uses_native_rrf_once_and_prefilters_tenant_case_acl_generation() -> None:
    index, client = _index()
    client.query_response = SimpleNamespace(
        points=[
            SimpleNamespace(
                payload={
                    "chunk_id": "chunk-1",
                    "tenant_id": "tenant-a",
                    "case_id": "case-a",
                    "allowed_principal_ids": ["principal-a"],
                    "index_generation": "generation-1",
                    "content_sha256": "1" * 64,
                    "source_sha256": "2" * 64,
                },
                score=0.12,
            )
        ]
    )

    results = index.query("find this clause", _principal(), "case-a", limit=5)

    assert len(results) == 1
    assert results[0].chunk_id == "chunk-1"
    request = [call[1] for call in client.calls if call[0] == "query_points"][-1]
    assert isinstance(request["query"], models.RrfQuery)
    assert request["query"].rrf.k == 60
    assert len(request["prefetch"]) == 2
    assert all(item.filter == request["prefetch"][0].filter for item in request["prefetch"])
    must = request["prefetch"][0].filter.must
    filters = {condition.key: condition.match.value for condition in must}
    assert filters == {
        "tenant_id": "tenant-a",
        "case_id": "case-a",
        "index_generation": "generation-1",
    }
    should = request["prefetch"][0].filter.min_should.conditions
    assert [(condition.key, condition.match.value) for condition in should] == [
        ("case_members", True),
        ("allowed_principal_ids", "principal-a"),
    ]


def test_lexical_and_dense_modes_do_not_invoke_hybrid_fusion() -> None:
    index, client = _index()
    for mode in ("lexical", "dense"):
        index.query("find clause", _principal(), "case-a", mode=mode)  # type: ignore[arg-type]
        request = [call[1] for call in client.calls if call[0] == "query_points"][-1]
        assert "prefetch" not in request
        assert "query" in request


def test_query_rejects_unauthorized_scope_and_unbounded_limits() -> None:
    index, _ = _index()
    with pytest.raises(PermissionError):
        index.query("find clause", _principal(), "case-b")
    with pytest.raises(ValueError, match="limit"):
        index.query("find clause", _principal(), "case-a", limit=101)


def test_qdrant_transport_failure_becomes_typed_dependency_unavailable() -> None:
    index, client = _index()
    client.query_error = ResponseHandlingException(RuntimeError("synthetic transport failure"))

    with pytest.raises(DependencyUnavailable):
        index.query("find clause", _principal(), "case-a")


def test_case_member_can_search_casewide_sources_but_not_another_principals_sources() -> None:
    index, client = _index()
    unrestricted, restricted = _chunk("unrestricted"), _chunk("restricted")
    index.upsert((unrestricted,), "generation-1", ())
    index.upsert((restricted,), "generation-1", ("principal-a",))
    assert client.points[0].payload["case_members"] is True
    assert client.points[0].payload["allowed_principal_ids"] == []
    assert client.points[1].payload["case_members"] is False

    case_member = Principal(
        principal_id="principal-b",
        tenant_id="tenant-a",
        allowed_case_ids=("case-a",),
    )
    client.query_response = SimpleNamespace(
        points=[
            SimpleNamespace(
                payload={
                    "chunk_id": "unrestricted",
                    "tenant_id": "tenant-a",
                    "case_id": "case-a",
                    "case_members": True,
                    "allowed_principal_ids": [],
                    "index_generation": "generation-1",
                    "content_sha256": hashlib.sha256(unrestricted.text.encode()).hexdigest(),
                    "source_sha256": "2" * 64,
                },
                score=0.4,
            )
        ]
    )
    assert index.query("find clause", case_member, "case-a")[0].chunk_id == "unrestricted"

    client.query_response = SimpleNamespace(
        points=[
            SimpleNamespace(
                payload={
                    "chunk_id": "restricted",
                    "tenant_id": "tenant-a",
                    "case_id": "case-a",
                    "case_members": False,
                    "allowed_principal_ids": ["principal-a"],
                    "index_generation": "generation-1",
                    "content_sha256": hashlib.sha256(restricted.text.encode()).hexdigest(),
                    "source_sha256": "2" * 64,
                },
                score=0.9,
            )
        ]
    )
    with pytest.raises(IndexConsistencyError, match="outside its requested ACL scope"):
        index.query("find clause", case_member, "case-a")


def test_bm25_profiles_are_explicit_and_have_distinct_fingerprints() -> None:
    english, _ = _index("english")
    unstemmed, _ = _index("no_stemming")

    assert english.fingerprint != unstemmed.fingerprint
    assert english._bm25.language == "english"
    assert unstemmed._bm25.stemmer.type.value == "none"
    assert unstemmed._bm25.stopwords.languages == []


def test_disabled_reranker_preserves_candidates_and_enforces_bound() -> None:
    reranker = FastEmbedReranker(enabled=False, max_candidates=2)
    chunks = (_chunk("one"), _chunk("two"))

    assert reranker.rank("question", chunks) == chunks
    assert reranker.fingerprint == "disabled"
    with pytest.raises(ValueError, match="candidate count"):
        reranker.rank("question", (*chunks, _chunk("three")))
    with pytest.raises(ValueError, match="query"):
        reranker.rank("  ", chunks)


def test_enabled_reranker_sorts_stably_without_changing_chunk_objects() -> None:
    reranker = FastEmbedReranker(enabled=True, max_candidates=3)

    class _Model:
        def rerank(self, query: str, documents: list[str], batch_size: int) -> list[float]:
            assert query == "question"
            assert len(documents) == 3
            assert batch_size == 16
            return [0.4, 0.9, 0.9]

    reranker._load = lambda: _Model()  # type: ignore[method-assign,return-value]
    chunks = (_chunk("one"), _chunk("two"), _chunk("three"))

    ranked = reranker.rank("question", chunks)

    assert ranked == (chunks[1], chunks[2], chunks[0])
    assert all(actual is expected for actual, expected in zip(ranked, (chunks[1], chunks[2], chunks[0]), strict=True))
