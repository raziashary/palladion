"""Graph metrics: hand-computed cases, and a perfect, an empty and a shuffled control for each (B06-T05.01)."""

from __future__ import annotations

import random
from typing import Any

import pytest
from support import make_candidate, oracle

from benchmark.eval.evidence_sets import citable_slots
from benchmark.eval.graph_metrics import (
    UNDEFINED_METRICS,
    EdgeScores,
    Undefined,
    edges_of,
    hop_completion,
    is_multi_document,
    score_edges,
    traversal_cost,
)
from benchmark.eval.normalize import PublishedCorpus, align_all, fold
from benchmark.fixtures.questions import GoldRecord


def hop_record(questions: tuple[GoldRecord, ...]) -> GoldRecord:
    return next(q for q in questions if is_multi_document(q))


# --------------------------------------------------------------------------- hop completion


def test_a_question_that_needs_two_documents_is_a_hop_question_and_a_one_document_question_is_not(
    s_questions: tuple[GoldRecord, ...],
) -> None:
    hops = [q for q in s_questions if is_multi_document(q)]
    singles = [q for q in s_questions if len(citable_slots(q)) == 1]
    assert hops and singles
    assert all(len({a.doc_id for s in citable_slots(q) for a in s.alternatives}) >= 2 for q in hops)
    for record in singles:
        assert hop_completion(record, [], 10) is None, "not applicable is None, never zero"


def test_perfect_evidence_completes_every_hop(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus
) -> None:
    for record in (q for q in s_questions if is_multi_document(q)):
        result = hop_completion(record, align_all(oracle(s_published_corpus, record), s_published_corpus), 10)
        assert result is not None and result.covered_fraction == 1.0 and result.complete is True, record.question_id


def test_nothing_returned_covers_no_hop_and_is_zero_not_missing(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus
) -> None:
    result = hop_completion(hop_record(s_questions), [], 10)
    assert result is not None and result.covered_fraction == 0.0 and result.complete is False


def test_a_missing_hop_gives_a_hand_computed_fraction_and_an_incomplete_set(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus
) -> None:
    record = hop_record(s_questions)
    full = oracle(s_published_corpus, record)
    slots = len(citable_slots(record))
    result = hop_completion(record, align_all(full[:-1], s_published_corpus), 10)
    assert result is not None and result.slots == slots
    assert result.covered_fraction == pytest.approx((slots - 1) / slots) and result.complete is False


def test_order_does_not_change_a_set_at_a_large_k_but_k_cuts_the_list(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus
) -> None:
    record = hop_record(s_questions)
    full = oracle(s_published_corpus, record)
    shuffled = [make_candidate_like(c, i + 1) for i, c in enumerate(random.Random(3).sample(full, len(full)))]
    big = hop_completion(record, align_all(shuffled, s_published_corpus), 10)
    assert big is not None and big.complete is True
    one = hop_completion(record, align_all(shuffled, s_published_corpus), 1)
    assert one is not None and one.complete is False and one.covered_fraction == pytest.approx(1 / len(full))


def make_candidate_like(candidate: Any, rank: int) -> Any:
    from dataclasses import replace

    return replace(candidate, rank=rank)


# --------------------------------------------------------------------------- edges


def clause_of(corpus: PublishedCorpus, index: int) -> tuple[str, str, str]:
    """A published document id, a clause id and that clause's text, chosen by position."""
    with_clauses = [d for d in sorted(corpus.docs) if len(corpus.docs[d].clauses) > 0]
    doc_id = with_clauses[index]
    doc = corpus.docs[doc_id]
    clause = sorted(doc.clauses)[0]
    start, end = doc.clauses[clause]
    return doc_id, clause, doc.text[start:end]


def distinct_words(texts: list[str], at: int) -> tuple[str, str]:
    """A word only texts[at] uses (so a swapped citation cannot ground it) and any other word of the same text."""
    others = set(" ".join(fold(t) for i, t in enumerate(texts) if i != at).split())
    words = list(dict.fromkeys(fold(texts[at]).split()))
    only = [w for w in words if len(w) > 3 and w not in others]
    assert only, "the test fixture needs a word only this clause uses"
    rest = [w for w in words if w != only[0] and len(w) > 2]
    assert rest, "the clause needs a second word"
    return only[0], rest[0]


@pytest.fixture
def grounded(s_published_corpus: PublishedCorpus) -> list[dict[str, Any]]:
    cites = [clause_of(s_published_corpus, i) for i in (0, 7, 15)]
    texts = [c[2] for c in cites]
    edges = []
    for at, (doc_id, clause, _) in enumerate(cites):
        subject, obj = distinct_words(texts, at)
        edges.append({"subject": subject, "predicate": "RELATES_TO", "object": obj,
                      "supporting_ids": [f"{doc_id}#{clause}"]})  # fmt: skip
    return edges


def test_every_edge_grounded_in_its_citation_is_valid_and_not_a_false_association(
    grounded: list[dict[str, Any]], s_published_corpus: PublishedCorpus
) -> None:
    scores = score_edges(grounded, s_published_corpus)
    assert scores == EdgeScores(3, 3, 3) and scores.provenance_validity == 1.0 and scores.false_association_rate == 0.0


def test_no_edges_is_undefined_not_perfect(s_published_corpus: PublishedCorpus) -> None:
    scores = score_edges([], s_published_corpus)
    assert scores.total == 0 and scores.provenance_validity is None and scores.false_association_rate is None


def test_a_planted_unsupported_edge_raises_the_false_association_rate_by_hand_computed_amounts(
    grounded: list[dict[str, Any]], s_published_corpus: PublishedCorpus
) -> None:
    planted = {**grounded[0], "object": "zzzzunrelatedentity"}
    scores = score_edges([*grounded, planted], s_published_corpus)
    assert scores == EdgeScores(4, 4, 3)
    assert scores.provenance_validity == 1.0, "its citation exists; only the claim it makes is unsupported"
    assert scores.false_association_rate == pytest.approx(1 / 4)


def test_edges_citing_a_missing_source_or_nothing_are_invalid_and_false(
    grounded: list[dict[str, Any]], s_published_corpus: PublishedCorpus
) -> None:
    broken = [
        {**grounded[0], "supporting_ids": ["NO-SUCH-DOC#1.1"]},
        {**grounded[1], "supporting_ids": []},
        {**grounded[2], "supporting_ids": [grounded[2]["supporting_ids"][0], "NO-SUCH-DOC"]},
        {**grounded[0], "supporting_ids": [grounded[0]["supporting_ids"][0].split("#")[0] + "#99.99"]},
    ]
    scores = score_edges(broken, s_published_corpus)
    assert scores == EdgeScores(4, 0, 0) and scores.provenance_validity == 0.0 and scores.false_association_rate == 1.0


def test_shuffling_the_citations_between_edges_breaks_the_grounding(
    grounded: list[dict[str, Any]], s_published_corpus: PublishedCorpus
) -> None:
    rotated = [{**e, "supporting_ids": grounded[(i + 1) % 3]["supporting_ids"]} for i, e in enumerate(grounded)]
    scores = score_edges(rotated, s_published_corpus)
    assert scores.provenance_validity == 1.0 and scores.false_association_rate == 1.0


def test_matching_is_case_and_whitespace_insensitive(
    grounded: list[dict[str, Any]], s_published_corpus: PublishedCorpus
) -> None:
    shouted = [{**grounded[0], "subject": grounded[0]["subject"].upper(), "object": f"  {grounded[0]['object']}  "}]
    assert score_edges(shouted, s_published_corpus).false_association_rate == 0.0


def test_only_candidates_that_carry_a_relation_contribute_edges() -> None:
    edge = {"subject": "a", "predicate": "b", "object": "c", "supporting_ids": ["D#1.1"]}
    plain = make_candidate("text", 1)
    graph = make_candidate("text", 2, relation=edge)
    assert [e for e in edges_of([plain, graph])] == [graph.relation] and edges_of([plain]) == []
    assert graph.to_dict()["relation"] == edge


# --------------------------------------------------------------------------- cost


def test_cost_per_useful_slot_by_hand() -> None:
    cost = traversal_cost([(2, 1000, 1), (0, 0, 1), (4, 3000, 0)])
    assert (cost.calls, cost.tokens, cost.useful_slots) == (6, 4000, 2)
    assert cost.calls_per_useful_slot == 3.0 and cost.tokens_per_useful_slot == 2000.0


def test_a_cost_with_no_useful_slot_has_no_ratio_not_zero_and_not_infinity() -> None:
    cost = traversal_cost([(5, 9000, 0), (1, 100, 0)])
    assert cost.calls == 6 and cost.calls_per_useful_slot is None and cost.tokens_per_useful_slot is None
    assert traversal_cost([]).calls_per_useful_slot is None


def test_free_traversal_with_useful_slots_is_a_real_zero() -> None:
    cost = traversal_cost([(0, 0, 2)])
    assert cost.calls_per_useful_slot == 0.0


def test_negative_costs_or_slots_are_refused() -> None:
    for bad in ((-1, 0, 1), (0, -1, 1), (0, 0, -1)):
        with pytest.raises(ValueError, match="negative"):
            traversal_cost([bad])


# --------------------------------------------------------------------------- what is not defined


def test_four_metrics_are_declared_undefined_with_a_reason_each() -> None:
    assert [u.metric for u in UNDEFINED_METRICS] == [
        "relationship_precision_recall", "typed_traversal_correctness", "wrong_node_merge_rate", "hub_pollution",
    ]  # fmt: skip
    assert all(isinstance(u, Undefined) and len(u.reason) > 40 for u in UNDEFINED_METRICS)


def test_no_computed_result_carries_an_undefined_metric() -> None:
    names = {u.metric for u in UNDEFINED_METRICS}
    computed = set(EdgeScores.__dataclass_fields__) | set(dir(EdgeScores)) | set(dir(traversal_cost([])))
    assert not names & computed
