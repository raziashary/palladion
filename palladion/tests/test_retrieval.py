from __future__ import annotations

import hashlib
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import Response
from qdrant_client import models
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

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
        self.facet_counts: dict[str, int] = {}

    def collection_exists(self, collection_name: str) -> bool:
        self.calls.append(("collection_exists", {"collection_name": collection_name}))
        return self.created

    def info(self) -> Any:
        return SimpleNamespace(version="1.19.2")

    def facet(self, **kwargs: Any) -> Any:
        self.calls.append(("facet", kwargs))
        return SimpleNamespace(hits=[SimpleNamespace(value=g, count=n) for g, n in self.facet_counts.items()])

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


def test_generation_filter_restricts_every_prefetch_and_an_empty_list_asks_the_index_nothing() -> None:
    index, client = _index()
    index.query("find this clause", _principal(), "case-a", limit=5, generations=("gen-1", "gen-2"))
    request = [call[1] for call in client.calls if call[0] == "query_points"][-1]
    assert len(request["prefetch"]) == 2, "the dense and the lexical prefetch both carry the filter"
    for prefetch in request["prefetch"]:
        generation = [c for c in prefetch.filter.must if c.key == "index_generation" and hasattr(c.match, "any")]
        assert len(generation) == 1 and generation[0].match.any == ["gen-1", "gen-2"]
    before = len(client.calls)
    assert index.query("find this clause", _principal(), "case-a", limit=5, generations=()) == ()
    assert len(client.calls) == before, "no eligible generation means no query is sent"
    index.query("find this clause", _principal(), "case-a", limit=5)
    unfiltered = [call[1] for call in client.calls if call[0] == "query_points"][-1]
    assert not any(hasattr(c.match, "any") for c in unfiltered["prefetch"][0].filter.must)


def test_generation_counts_are_one_exact_facet_call_scoped_to_the_tenant_and_case() -> None:
    index, client = _index()
    client.facet_counts = {"gen-1": 3, "gen-2": 5}
    assert index.generation_counts("tenant-a", "case-a", ["gen-1", "gen-2"]) == {"gen-1": 3, "gen-2": 5}
    call = [c[1] for c in client.calls if c[0] == "facet"][-1]
    assert call["key"] == "index_generation" and call["exact"] is True and call["limit"] == 2
    conditions = {c.key: c.match for c in call["facet_filter"].must}
    assert conditions["tenant_id"].value == "tenant-a" and conditions["case_id"].value == "case-a"
    assert conditions["index_generation"].any == ["gen-1", "gen-2"], "only the generations asked about are counted"
    before = len(client.calls)
    assert index.generation_counts("tenant-a", "case-a", []) == {} and len(client.calls) == before


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


@pytest.mark.parametrize("status",[408,429,503,400,403])
def test_p08_native_qdrant_timeout_throttle_normalization_preserves_other_errors(status):
    index,client=_index()
    client.query_error=UnexpectedResponse.for_response(Response(status_code=status,content=b"diagnostic"))
    with pytest.raises(DependencyUnavailable if status in {408,429,503} else UnexpectedResponse):
        index.query("find clause",_principal(),"case-a")


def test_a_collection_another_caller_created_first_is_not_an_error_but_other_failures_are() -> None:
    class Racing(_Client):
        def __init__(self, status: int, exists_afterwards: bool) -> None:
            super().__init__()
            self.status, self.exists_afterwards = status, exists_afterwards

        def create_collection(self, **kwargs: Any) -> None:
            super().create_collection(**kwargs)
            self.created = self.exists_afterwards
            raise UnexpectedResponse.for_response(Response(status_code=self.status, content=b"exists"))

    for status, exists, raises in ((409, True, False), (409, False, True), (400, True, True)):
        client = Racing(status, exists)
        index = QdrantIndex(collection_name="race", client=client, encoder=_Encoder())  # type: ignore[arg-type]
        if raises:
            with pytest.raises(UnexpectedResponse):
                index.ensure_collection()
        else:
            index.ensure_collection()


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
        def __init__(self) -> None:
            self.batches: list[list[str]] = []

        def rerank(self, query: str, documents: list[str], batch_size: int) -> list[float]:
            assert query == "question"
            assert len(documents) == 3
            assert batch_size == 8
            self.batches.append(documents)
            return [{"first text": 0.4, "second text": 0.9, "third text": 0.9}[document] for document in documents]

    model = _Model()
    reranker._load = lambda: model  # type: ignore[method-assign,return-value]
    chunks = (_chunk("one", "first text"), _chunk("two", "second text"), _chunk("three", "third text"))

    ranked = reranker.rank("question", chunks)

    assert ranked == (chunks[1], chunks[2], chunks[0])
    assert all(actual is expected for actual, expected in zip(ranked, (chunks[1], chunks[2], chunks[0]), strict=True))


def test_the_reranker_hands_the_model_passages_shortest_first_and_scores_each_its_own() -> None:
    reranker = FastEmbedReranker(enabled=True, max_candidates=4)
    long, middle, short = "x" * 300, "x" * 100, "x" * 5

    class _Model:
        seen: list[str] = []

        def rerank(self, query: str, documents: list[str], batch_size: int) -> list[float]:
            self.seen = list(documents)
            return [float(len(document)) for document in documents]  # longer text scores higher

    model = _Model()
    reranker._load = lambda: model  # type: ignore[method-assign,return-value]
    chunks = tuple(_chunk(f"chunk-{n}", text) for n, text in enumerate((long, short, middle, short + "y")))

    ranked = reranker.rank("question", chunks)

    assert [len(text) for text in model.seen] == sorted(len(text) for text in model.seen), "shortest first"
    assert ranked == (chunks[0], chunks[2], chunks[3], chunks[1]), "each passage keeps the score of its own text"


@pytest.mark.parametrize("affinity, cpus, expected", [(2, None, 2), (4, None, 4), (16, None, 4), (None, 1, 1), (None, 8, 4)])
def test_reranker_threads_follow_the_usable_cores_up_to_four(monkeypatch, affinity, cpus, expected) -> None:
    import os

    from evidence_agent.retrieval import rerank
    if affinity is None:
        monkeypatch.delattr(os, "sched_getaffinity", raising=False)
        monkeypatch.setattr(os, "cpu_count", lambda: cpus)
    else:
        monkeypatch.setattr(os, "sched_getaffinity", lambda pid: set(range(affinity)), raising=False)
    assert min(rerank.MAX_RERANK_THREADS, rerank._usable_cores()) == expected


def test_the_reranker_fingerprint_pins_the_model_and_not_the_machine(monkeypatch) -> None:
    from evidence_agent.retrieval import rerank
    hashes = {name: "a" * 64 for name in rerank.RERANKER_FILES}
    seen = []
    for threads in (2, 4):
        monkeypatch.setattr(rerank, "CPU_THREADS", threads)
        reranker = FastEmbedReranker(enabled=True)
        reranker._describe(hashes)
        seen.append((reranker._fingerprint, reranker._manifest))
    assert seen[0][0] == seen[1][0], "the same model has the same fingerprint on a 2-core and a 4-core host"
    assert [m["threads"] for _, m in seen] == [2, 4] and all(m["batch_size"] == 8 for _, m in seen)
    monkeypatch.setattr(rerank, "RERANKER_REVISION", "b" * 40)
    changed = FastEmbedReranker(enabled=True)
    changed._describe(hashes)
    assert changed._fingerprint != seen[0][0], "another model revision is another fingerprint"
