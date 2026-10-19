"""R1 dense arm: index construction, access filter, approximate-vs-exact check and the pinned model (B04-T01.02)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from support import HashingEncoder

from benchmark.adapters.common import AdapterError, Condition, PublishedView
from benchmark.adapters.dense import DenseArm, FastEmbedEncoder, ensure_benchmark_qdrant
from benchmark.adapters.models import ModelIntegrityError, ModelSpec, spec_from_pin
from benchmark.config import load_comparators_config
from benchmark.contracts import RetrievalRequest, RetrieverAdapter

ROOT = Path(__file__).resolve().parents[1]
QUERIES = (
    "refund window hours transaction",
    "approval exception level two",
    "settlement dispute chargeback",
    "error code MS-4021",
)


def request(query: str, principal_id: str, limit: int = 10, budget: int = 4000) -> RetrievalRequest:
    return RetrievalRequest(
        question_id="q-0000000000000001",
        query=query,
        principal_id=principal_id,
        corpus_snapshot_id="snap1",
        evaluation_time="2026-10-18T03:00:00Z",
        event_time=None,
        filters={},
        limit=limit,
        max_evidence_tokens=budget,
    )


@pytest.fixture(scope="module")
def view(s_published: Path) -> PublishedView:
    return PublishedView.load(s_published)


@pytest.fixture(scope="module")
def stand_in(
    qdrant_server: str, view: PublishedView, s_published: Path, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[DenseArm]:
    arm = DenseArm(
        view,
        HashingEncoder(),
        tmp_path_factory.mktemp("index"),
        qdrant_url=qdrant_server,
        collection="bench_test_standin",
    )
    arm.build_index(str(s_published), "S")
    yield arm
    arm.close()


# --------------------------------------------------------------------------- refusals (no server needed)


@pytest.mark.parametrize(
    "url", ["http://127.0.0.1:16333", "http://localhost:16334", "http://127.0.0.1", "http://10.0.0.5:17333"]
)
def test_palladions_server_and_remote_hosts_are_refused(url: str) -> None:
    with pytest.raises(AdapterError):
        ensure_benchmark_qdrant(url)


def test_the_benchmarks_own_server_is_accepted() -> None:
    assert ensure_benchmark_qdrant("http://127.0.0.1:17333") == "http://127.0.0.1:17333"


# --------------------------------------------------------------------------- the index


def test_every_chunk_is_in_the_collection_and_stats_are_recorded(stand_in: DenseArm) -> None:
    stats = stand_in.index_stats()
    assert stats["chunks"] > 1200 and stats["dimension"] == 384 and stats["collection"] == "bench_test_standin"
    assert stats["hnsw"] == {"m": 16, "ef_construct": 100, "ef_search": 64}
    assert stats["model_fingerprint"] == HashingEncoder.fingerprint and stats["build_ms"] > 0
    assert isinstance(stand_in, RetrieverAdapter)


def test_a_rebuild_reuses_the_cached_vectors_and_gives_identical_results(
    stand_in: DenseArm, view: PublishedView, s_published: Path, qdrant_server: str
) -> None:
    principal = view.identity.principals[0].principal_id
    before = [c.content for c in stand_in.retrieve(request(QUERIES[0], principal))]
    again = DenseArm(
        view, HashingEncoder(), stand_in.index_dir, qdrant_url=qdrant_server, collection="bench_test_standin"
    )
    again.build_index(str(s_published), "S")
    assert again.index_stats()["embeddings_from_cache"] is True
    assert [c.content for c in again.retrieve(request(QUERIES[0], principal))] == before
    again.close()


def test_the_published_directory_is_the_only_source(stand_in: DenseArm, tmp_path: Path) -> None:
    with pytest.raises(AdapterError, match="published directory"):
        stand_in.build_index(str(tmp_path), "S")


def test_retrieve_before_build_is_refused(view: PublishedView, tmp_path: Path, qdrant_server: str) -> None:
    arm = DenseArm(view, HashingEncoder(), tmp_path, qdrant_url=qdrant_server, collection="bench_test_unbuilt")
    with pytest.raises(AdapterError, match="build_index"):
        arm.retrieve(request("refund", view.identity.principals[0].principal_id))
    arm.close()


# --------------------------------------------------------------------------- access, budget, exactness


def test_the_neutral_filter_acts_inside_the_search(stand_in: DenseArm, view: PublishedView) -> None:
    checked = 0
    for principal in view.identity.principals:
        denied = {r.doc_id for r in view.records} - stand_in.access.visible_documents(principal.principal_id)
        for query in QUERIES:
            hits = stand_in.retrieve(request(query, principal.principal_id, limit=20))
            assert len(hits) == 20, "the filter must not shrink the result by post-filtering"
            assert not {c.source_document_id for c in hits} & denied
            checked += 1
    assert checked >= len(QUERIES)


def test_c1_can_return_a_document_the_manifest_denies_and_c2_cannot(
    stand_in: DenseArm, view: PublishedView, s_published: Path, tmp_path: Path, qdrant_server: str
) -> None:
    principal = view.identity.principals[0].principal_id
    visible = stand_in.access.visible_documents(principal)
    denied = next(r.doc_id for r in view.records if r.doc_id not in visible)
    query = view.document(denied).text[:600]
    arm = DenseArm(
        view, HashingEncoder(), tmp_path, qdrant_url=qdrant_server, condition=Condition.C1, collection="bench_test_c1"
    )
    arm.build_index(str(s_published), "S")
    try:
        assert denied in {c.source_document_id for c in arm.retrieve(request(query, principal, limit=5))}
        assert denied not in {c.source_document_id for c in stand_in.retrieve(request(query, principal, limit=20))}
    finally:
        arm.close()


def test_the_budget_and_limit_are_enforced(stand_in: DenseArm, view: PublishedView) -> None:
    principal = view.identity.principals[0].principal_id
    assert len(stand_in.retrieve(request(QUERIES[0], principal, limit=3))) == 3
    small = stand_in.retrieve(request(QUERIES[0], principal, limit=10, budget=40))
    assert sum(len(c.content.split()) for c in small) <= 40 and stand_in.last_notes["truncated"] is True


def test_the_server_scores_match_cosine_computed_locally(stand_in: DenseArm, view: PublishedView) -> None:
    principal = view.identity.principals[0].principal_id
    hits = stand_in.search(QUERIES[1], principal, 8, exact=True)
    local = stand_in.exact_scores(QUERIES[1], [c for c, _ in hits])
    assert [round(s, 4) for _, s in hits] == [round(s, 4) for s in local]


def test_approximate_search_is_measured_against_exact_search(stand_in: DenseArm, view: PublishedView) -> None:
    pairs = [(q, p.principal_id) for q in QUERIES for p in view.identity.principals[:4]]
    report = stand_in.ann_recall(pairs, 10)
    assert report["queries"] == len(pairs) and report["k"] == 10
    assert 0.9 <= report["mean_recall"] <= 1.0 and report["min_recall"] > 0.5
    with pytest.raises(AdapterError):
        stand_in.ann_recall([], 10)


# --------------------------------------------------------------------------- the pinned model


def embeddings_spec() -> ModelSpec:
    pin = load_comparators_config(ROOT / "configs" / "comparators.yaml").shared_models["embeddings"]
    return spec_from_pin(pin)


def embeddings_snapshot() -> Path | None:
    spec = embeddings_spec()
    found = sorted((ROOT / "artifacts" / "models" / "embeddings").glob(f"models--*/snapshots/{spec.revision}"))
    return found[0] if found else None


@pytest.fixture(scope="module")
def pinned_encoder() -> FastEmbedEncoder:
    snapshot = embeddings_snapshot()
    if snapshot is None:
        pytest.skip("the embedding model is not downloaded on this machine")
    return FastEmbedEncoder(snapshot, embeddings_spec())


def test_a_snapshot_that_differs_from_the_pin_is_refused() -> None:
    snapshot = embeddings_snapshot()
    if snapshot is None:
        pytest.skip("the embedding model is not downloaded on this machine")
    spec = embeddings_spec()
    wrong = ModelSpec(spec.repository, spec.revision, spec.files, {**spec.digests, "config.json": "0" * 64})
    with pytest.raises(ModelIntegrityError, match=r"differ from the pin: config\.json"):
        FastEmbedEncoder(snapshot, wrong)


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return float(dot / (sum(x * x for x in a) ** 0.5 * sum(y * y for y in b) ** 0.5))


def test_the_pinned_encoder_is_multilingual_and_deterministic(pinned_encoder: FastEmbedEncoder) -> None:
    english = pinned_encoder.embed_query("How long do I have to raise a refund request?")
    clause = pinned_encoder.embed_documents(["A request may be raised within seventy two hours of the transaction."])[0]
    indonesian = pinned_encoder.embed_query("Berapa lama saya boleh mengajukan permintaan pengembalian dana?")
    unrelated = pinned_encoder.embed_documents(["The cafeteria menu lists soup and bread for lunch."])[0]
    assert len(english) == 384 == pinned_encoder.dimension
    assert cosine(english, clause) > cosine(english, unrelated) + 0.1
    assert cosine(indonesian, clause) > cosine(indonesian, unrelated)
    assert english == pinned_encoder.embed_query("How long do I have to raise a refund request?")
    assert len(pinned_encoder.fingerprint) == 64


def test_the_pinned_model_retrieves_a_semantic_paraphrase_over_the_real_corpus(
    pinned_encoder: FastEmbedEncoder, view: PublishedView, s_published: Path, qdrant_server: str
) -> None:
    index_dir = ROOT / "artifacts" / "index" / "R1-test"
    arm = DenseArm(
        view,
        pinned_encoder,
        index_dir,
        qdrant_url=qdrant_server,
        condition=Condition.C1,
        collection="bench_test_pinned",
    )
    arm.build_index(str(s_published), "S")
    try:
        stats = arm.index_stats()
        assert stats["model_fingerprint"] == pinned_encoder.fingerprint and stats["chunks"] > 1200
        principal = view.identity.principals[0].principal_id
        hits = arm.retrieve(request("how many hours do I have to raise a dispute", principal, limit=10))
        top = " ".join(c.content.casefold() for c in hits[:5])
        assert "hours" in top and "jam" in top, "the model reaches time-limit text in both languages"
        report = arm.ann_recall([(q, principal) for q in QUERIES], 10)
        assert report["mean_recall"] >= 0.9
    finally:
        arm.close()
