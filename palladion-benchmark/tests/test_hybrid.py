"""R2 fusion and R3 reranking: hand-computed fusion, conditions, exact keys, budgets and the pinned cross-encoder."""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from support import HashingEncoder

from benchmark.adapters.bm25 import Bm25Arm
from benchmark.adapters.common import AdapterError, Condition, PublishedView, count_words
from benchmark.adapters.dense import DenseArm, FastEmbedEncoder
from benchmark.adapters.eligibility import Eligibility
from benchmark.adapters.hybrid import (
    RERANKER_LANGUAGE_NOTE,
    RRF_K,
    FastEmbedReranker,
    HybridArm,
    RerankedArm,
    reciprocal_rank_fusion,
)
from benchmark.adapters.models import ModelIntegrityError, ModelSpec, spec_from_pin
from benchmark.config import load_comparators_config
from benchmark.contracts import RetrievalRequest, RetrieverAdapter

ROOT = Path(__file__).resolve().parents[1]
ERROR_CODE = re.compile(r"MS-\d{4}")
QUERY = "refund window hours transaction"


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


class OverlapReranker:
    """A stand-in cross-encoder: counts shared words. For tests of the arm's plumbing, not of quality."""

    fingerprint = "overlap-reranker-test-only"

    def rerank(self, query: str, texts: Sequence[str]) -> list[float]:
        wanted = set(query.casefold().split())
        return [float(len(wanted & set(text.casefold().split()))) for text in texts]


# --------------------------------------------------------------------------- fusion (pure)


def test_reciprocal_rank_fusion_matches_a_hand_computed_example() -> None:
    fused = dict(reciprocal_rank_fusion([["a", "b", "c"], ["b", "c", "d"]], k=60))
    assert fused["a"] == pytest.approx(1 / 61)
    assert fused["b"] == pytest.approx(1 / 62 + 1 / 61)
    assert fused["c"] == pytest.approx(1 / 63 + 1 / 62)
    assert fused["d"] == pytest.approx(1 / 63)
    assert [item for item, _ in reciprocal_rank_fusion([["a", "b", "c"], ["b", "c", "d"]], k=60)] == [
        "b",
        "c",
        "a",
        "d",
    ]


def test_fusion_ties_order_by_id() -> None:
    assert [i for i, _ in reciprocal_rank_fusion([["z"], ["a"]], 60)] == ["a", "z"]
    with pytest.raises(AdapterError):
        reciprocal_rank_fusion([["a"]], 0)


def test_the_fusion_constant_decides_between_a_high_single_rank_and_two_middling_ranks() -> None:
    lists = [["a", "x", "y", "b"], ["c", "u", "v", "b"]]  # a: first once; b: fourth twice
    assert reciprocal_rank_fusion(lists, k=1)[0][0] == "a"
    assert reciprocal_rank_fusion(lists, k=100)[0][0] == "b"


# --------------------------------------------------------------------------- the arms over the real corpus


@pytest.fixture(scope="module")
def view(s_published: Path) -> PublishedView:
    return PublishedView.load(s_published)


def stack(view: PublishedView, published: Path, url: str, condition: Condition, index: Path, name: str) -> HybridArm:
    hybrid = HybridArm(
        Bm25Arm(view, condition),
        DenseArm(view, HashingEncoder(), index, qdrant_url=url, condition=condition, collection=name),
    )
    hybrid.build_index(str(published), "S")
    return hybrid


@pytest.fixture(scope="module")
def r2(
    qdrant_server: str, view: PublishedView, s_published: Path, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[HybridArm]:
    hybrid = stack(view, s_published, qdrant_server, Condition.C2, tmp_path_factory.mktemp("c2"), "bench_test_r2_c2")
    yield hybrid
    hybrid.dense.close()


def test_the_fusion_constant_and_conditions_are_recorded(r2: HybridArm) -> None:
    description = r2.describe()
    assert description["rrf_k"] == RRF_K == 60 and description["condition"] == "C2"
    assert description["lexical"]["arm"] == "R0" and description["dense"]["arm"] == "R1"
    assert r2.index_stats()["rrf_k"] == 60 and isinstance(r2, RetrieverAdapter)


def test_fused_results_draw_on_both_channels_and_keep_the_contract(r2: HybridArm, view: PublishedView) -> None:
    principal = view.identity.principals[0].principal_id
    hits = r2.retrieve(request(QUERY, principal, limit=10))
    assert 0 < len(hits) <= 10 and [c.rank for c in hits] == list(range(1, len(hits) + 1))
    channels = {name for c in hits for name in c.additional_metadata["channel_ranks"]}
    assert channels == {"bm25", "dense"}
    scores = [c.native_score for c in hits]
    assert scores == sorted(scores, reverse=True)  # type: ignore[type-var]
    assert all(c.retrieval_channel == "hybrid" for c in hits)


def test_exact_identifier_chunks_are_reported_separately(r2: HybridArm, view: PublishedView) -> None:
    code = next(code for chunk in r2.lexical.chunks for code in ERROR_CODE.findall(chunk.text))
    principal = view.identity.principals[0].principal_id
    hits = r2.retrieve(request(f"what does {code} mean", principal, limit=20))
    named = {c.chunk_id: c for c in r2.lexical.chunks}
    exact = r2.last_notes["exact_key_chunks"]
    assert exact and all(code.casefold() in named[chunk_id].text.casefold() for chunk_id in exact)
    flagged = {c.additional_metadata["chunk_id"] for c in hits if c.additional_metadata["exact_key_match"]}
    assert flagged and flagged <= set(exact)
    assert all(not c.additional_metadata["exact_key_match"] for c in r2.retrieve(request(QUERY, principal)))
    assert r2.last_notes["exact_key_chunks"] == []


def test_the_budget_is_enforced_after_fusion(r2: HybridArm, view: PublishedView) -> None:
    principal = view.identity.principals[0].principal_id
    small = r2.retrieve(request(QUERY, principal, limit=20, budget=60))
    assert sum(count_words(c.content) for c in small) <= 60 and r2.last_notes["truncated"] is True


def test_c1_and_c2_differ_only_in_the_neutral_filter(
    r2: HybridArm, view: PublishedView, s_published: Path, qdrant_server: str, tmp_path: Path
) -> None:
    c1 = stack(view, s_published, qdrant_server, Condition.C1, tmp_path, "bench_test_r2_c1")
    try:
        declared_c1, declared_c2 = c1.describe(), r2.describe()
        for description in (declared_c1, declared_c2):
            description["condition"] = description["lexical"]["condition"] = description["dense"]["condition"] = "-"
        assert declared_c1 == declared_c2, "the declared settings are identical apart from the condition"
        shared = ("documents", "chunks", "words", "characters")
        assert {k: c1.dense.index_stats()[k] for k in shared} == {k: r2.dense.index_stats()[k] for k in shared}
        principal = view.identity.principals[0].principal_id
        denied = next(r.doc_id for r in view.records if r.doc_id not in r2.lexical.access.visible_documents(principal))
        query = view.document(denied).text[:600]
        assert denied in {c.source_document_id for c in c1.retrieve(request(query, principal, limit=10))}
        assert denied not in {c.source_document_id for c in r2.retrieve(request(query, principal, limit=30))}
    finally:
        c1.dense.close()


def test_mismatched_components_are_refused(
    r2: HybridArm, view: PublishedView, qdrant_server: str, tmp_path: Path
) -> None:
    other = DenseArm(
        view,
        HashingEncoder(),
        tmp_path,
        qdrant_url=qdrant_server,
        condition=Condition.C1,
        collection="bench_test_mismatch",
    )
    with pytest.raises(AdapterError, match="condition"):
        HybridArm(r2.lexical, other)
    other.close()
    with pytest.raises(AdapterError):
        HybridArm(r2.lexical, r2.dense, rrf_k=0)


# --------------------------------------------------------------------------- R3 plumbing


def test_the_reranker_reorders_and_the_budget_still_holds(r2: HybridArm, view: PublishedView) -> None:
    r3 = RerankedArm(r2, OverlapReranker(), depth=20)
    principal = view.identity.principals[0].principal_id
    hits = r3.retrieve(request(QUERY, principal, limit=10))
    scores = [c.native_score for c in hits]
    assert scores == sorted(scores, reverse=True)  # type: ignore[type-var]
    assert all(c.retrieval_channel == "rerank" for c in hits) and len(hits) <= 10
    description = r3.describe()
    assert description["reranker_language_note"] == RERANKER_LANGUAGE_NOTE and description["depth"] == 20
    small = r3.retrieve(request(QUERY, principal, limit=20, budget=50))
    assert sum(count_words(c.content) for c in small) <= 50 and r3.last_notes["truncated"] is True


def test_rerank_depth_is_bounded(r2: HybridArm) -> None:
    for depth in (0, 31):
        with pytest.raises(AdapterError):
            RerankedArm(r2, OverlapReranker(), depth=depth)


def test_arms_at_the_same_budget_deliver_within_one_chunk_of_the_same_words(r2: HybridArm, view: PublishedView) -> None:
    r3 = RerankedArm(r2, OverlapReranker(), depth=30)
    widest = max(c.words for c in r2.lexical.chunks)
    principal = view.identity.principals[0].principal_id
    for budget in (150, 400):
        delivered = [
            sum(count_words(c.content) for c in arm.retrieve(request(QUERY, principal, limit=30, budget=budget)))
            for arm in (r2.lexical, r2, r3)
        ]
        assert max(delivered) <= budget
        assert max(delivered) - min(delivered) <= widest


# --------------------------------------------------------------------------- the pinned cross-encoder


def reranker_spec() -> ModelSpec:
    return spec_from_pin(load_comparators_config(ROOT / "configs" / "comparators.yaml").shared_models["reranker"])


def reranker_snapshot() -> Path | None:
    found = sorted((ROOT / "artifacts" / "models" / "reranker").glob(f"models--*/snapshots/{reranker_spec().revision}"))
    return found[0] if found else None


@pytest.fixture(scope="module")
def pinned_reranker() -> FastEmbedReranker:
    snapshot = reranker_snapshot()
    if snapshot is None:
        pytest.skip("the reranker model is not downloaded on this machine")
    return FastEmbedReranker(snapshot, reranker_spec())


def test_a_reranker_snapshot_that_differs_from_the_pin_is_refused() -> None:
    snapshot = reranker_snapshot()
    if snapshot is None:
        pytest.skip("the reranker model is not downloaded on this machine")
    spec = reranker_spec()
    wrong = ModelSpec(spec.repository, spec.revision, spec.files, {**spec.digests, "vocab.txt": "0" * 64})
    with pytest.raises(ModelIntegrityError, match=r"differ from the pin: vocab\.txt"):
        FastEmbedReranker(snapshot, wrong)


def test_the_pinned_cross_encoder_prefers_the_relevant_passage(pinned_reranker: FastEmbedReranker) -> None:
    texts = [
        "The cafeteria menu lists soup and bread for lunch.",
        "A refund request must be raised within seventy two hours of the transaction.",
        "Quarterly newsletter about the office plants.",
    ]
    scores = pinned_reranker.rerank("how long do I have to raise a refund request", texts)
    assert scores.index(max(scores)) == 1
    assert scores == pinned_reranker.rerank("how long do I have to raise a refund request", texts)
    assert len(pinned_reranker.fingerprint) == 64


def test_the_full_pinned_stack_over_the_real_corpus(
    pinned_reranker: FastEmbedReranker, qdrant_server: str, view: PublishedView, s_published: Path
) -> None:
    snapshot = next((ROOT / "artifacts" / "models" / "embeddings").glob("models--*/snapshots/*"), None)
    if snapshot is None:
        pytest.skip("the embedding model is not downloaded on this machine")
    spec = spec_from_pin(load_comparators_config(ROOT / "configs" / "comparators.yaml").shared_models["embeddings"])
    dense = DenseArm(
        view,
        FastEmbedEncoder(snapshot, spec),
        ROOT / "artifacts" / "index" / "R1-test",
        qdrant_url=qdrant_server,
        condition=Condition.C1,
        collection="bench_test_stack",
    )
    r3 = RerankedArm(HybridArm(Bm25Arm(view, Condition.C1), dense), pinned_reranker)
    r3.build_index(str(s_published), "S")
    try:
        principal = view.identity.principals[0].principal_id
        hits = r3.retrieve(request("how many hours do I have to raise a dispute", principal, limit=5))
        assert len(hits) == 5 and all(c.retrieval_channel == "rerank" for c in hits)
        top = " ".join(c.content.casefold() for c in hits[:3])
        assert "hours" in top or "jam" in top
        assert r3.describe()["hybrid"]["rrf_k"] == 60
    finally:
        dense.close()


# --------------------------------------------------------------------------- R3f: the eligibility rule before ranking


def test_the_eligibility_rule_keeps_documents_the_time_rules_out_from_the_ranking_in_every_channel(
    r2: HybridArm, view: PublishedView
) -> None:
    rule = Eligibility(view)
    at = request(QUERY, view.identity.principals[0].principal_id).evaluation_time
    out = next(
        r.doc_id
        for r in view.records
        if r.registry_state == "retired"
        and r.valid_to
        and r.valid_to < at
        and r.doc_id not in rule.documents(request(QUERY, view.identity.principals[0].principal_id))
    )
    principal = next(
        p.principal_id for p in view.identity.principals if out in r2.lexical.access.visible_documents(p.principal_id)
    )
    query = view.document(out).text[:400]
    plain = {c.source_document_id for c in r2.retrieve(request(query, principal, limit=30))}
    assert out in plain, "positive control: without the rule the retired version is found by its own text"
    ruled = HybridArm(r2.lexical, r2.dense, eligibility=rule)
    ruled.adopt_built_indexes()
    assert out not in {c.source_document_id for c in ruled.retrieve(request(query, principal, limit=30))}
    assert "eligibility" in ruled.describe() and "eligibility" not in r2.describe()


def test_r3f_is_a_reranked_arm_under_its_own_id_that_applies_the_rule(r2: HybridArm, view: PublishedView) -> None:
    ruled = HybridArm(r2.lexical, r2.dense, eligibility=Eligibility(view))
    ruled.adopt_built_indexes()
    arm = RerankedArm(ruled, OverlapReranker(), arm_id="R3f")
    assert arm.arm_id == "R3f" and arm.describe()["arm"] == "R3f" and arm.index_stats()["arm"] == "R3f"
    assert RerankedArm(r2, OverlapReranker()).arm_id == "R3"
    principal = view.identity.principals[0].principal_id
    assert arm.retrieve(request(QUERY, principal, limit=10))
