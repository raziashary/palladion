"""SlotCoverage@K and CompleteSet@K over the real S-tier fixture (B03-T02.01)."""

from __future__ import annotations

from dataclasses import replace

import pytest
from support import cited, make_candidate, oracle

from benchmark.eval.evidence_sets import citable_slots, covered_slots, matched_units, score_sets
from benchmark.eval.normalize import PublishedCorpus, align_all
from benchmark.fixtures.questions import Answerability, GoldRecord, SlotState, derive_minimal_sets


def multi_slot(questions: tuple[GoldRecord, ...]) -> GoldRecord:
    return next(q for q in questions if len(citable_slots(q)) >= 2)


def test_oracle_scores_one_everywhere(s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus) -> None:
    scored = 0
    for record in s_questions:
        if not citable_slots(record):
            continue
        scores = score_sets(record, align_all(oracle(s_published_corpus, record), s_published_corpus), k=10)
        assert scores.slot_coverage == 1.0, record.question_id
        assert scores.complete_set == 1.0, record.question_id
        scored += 1
    assert scored >= 5


def test_empty_return_scores_zero_not_none(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus
) -> None:
    record = multi_slot(s_questions)
    scores = score_sets(record, [], k=10)
    assert (scores.slot_coverage, scores.complete_set) == (0.0, 0.0)


def test_unscorable_records_are_not_applicable(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus
) -> None:
    empty = [q for q in s_questions if not citable_slots(q)]
    assert empty, "the fixture should contain records without a citable slot"
    for record in empty:
        scores = score_sets(record, [], k=10)
        assert scores.slot_coverage is None and scores.complete_set is None
        assert scores.slots_total == 0
    for record in (q for q in s_questions if q.answerability is Answerability.UNANSWERABLE):
        assert score_sets(record, [], k=10).complete_set is None


def test_missing_one_slot_keeps_partial_coverage_but_fails_complete_set(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus
) -> None:
    record = multi_slot(s_questions)
    full = oracle(s_published_corpus, record)
    scores = score_sets(record, align_all(full[:-1], s_published_corpus), k=10)
    slots = len(citable_slots(record))
    assert scores.slot_coverage == pytest.approx((slots - 1) / slots)
    assert scores.complete_set == 0.0


def test_many_relevant_chunks_missing_the_exception_do_not_complete_the_set(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus
) -> None:
    record = next(q for q in s_questions if any(s.slot.startswith("exception_clause") for s in citable_slots(q)))
    keep = [s for s in citable_slots(record) if not s.slot.startswith("exception_clause")]
    others = [cited(s_published_corpus, s.alternatives[0], i) for i, s in enumerate(keep, start=1)]
    padding = [cited(s_published_corpus, keep[0].alternatives[0], 10 + i) for i in range(7)]
    scores = score_sets(record, align_all(others + padding, s_published_corpus), k=20)
    assert scores.complete_set == 0.0
    assert 0.0 < (scores.slot_coverage or 0.0) < 1.0


def test_duplicates_add_nothing(s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus) -> None:
    record = multi_slot(s_questions)
    one = oracle(s_published_corpus, record)[:1]
    twice = [*one, cited(s_published_corpus, citable_slots(record)[0].alternatives[0], 2)]
    assert score_sets(record, align_all(one, s_published_corpus), 10) == score_sets(
        record, align_all(twice, s_published_corpus), 10
    )


def test_k_truncates_the_returned_list(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus
) -> None:
    record = multi_slot(s_questions)
    alignments = align_all(oracle(s_published_corpus, record), s_published_corpus)
    assert score_sets(record, alignments, k=1).complete_set == 0.0
    assert score_sets(record, alignments, k=len(alignments)).complete_set == 1.0
    assert matched_units(alignments, 0) == set()


def test_alternatives_are_or_within_a_slot(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus
) -> None:
    record = multi_slot(s_questions)
    first, *rest = record.slots
    spare = next(
        c for q in s_questions for s in citable_slots(q) for c in s.alternatives if c not in first.alternatives
    )
    slots = (replace(first, alternatives=(spare, *first.alternatives)), *rest)
    widened = replace(
        record,
        slots=slots,
        minimal_sets=derive_minimal_sets(slots),
        citation_gold_spans=(*record.citation_gold_spans, spare),
    )
    via_original = oracle(s_published_corpus, record)
    via_spare = [cited(s_published_corpus, spare, 1), *via_original[1:]]
    renumbered = [replace(c, rank=i) for i, c in enumerate(via_spare, start=1)]
    assert score_sets(widened, align_all(via_original, s_published_corpus), 10).complete_set == 1.0
    assert score_sets(widened, align_all(renumbered, s_published_corpus), 10).complete_set == 1.0
    assert score_sets(record, align_all(renumbered, s_published_corpus), 10).complete_set == 0.0


def test_pasted_text_earns_alignment_credit_only(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus
) -> None:
    record = multi_slot(s_questions)
    pasted = [make_candidate(c.content, c.rank) for c in oracle(s_published_corpus, record)]  # same text, no provenance
    scores = score_sets(record, align_all(pasted, s_published_corpus), k=10)
    assert scores.slot_coverage == 0.0 and scores.complete_set == 0.0
    assert (scores.alignment_slot_coverage or 0.0) > 0.0


def test_covered_slots_names_the_satisfied_ones(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus
) -> None:
    record = multi_slot(s_questions)
    full = oracle(s_published_corpus, record)
    names = covered_slots(record, align_all(full[:1], s_published_corpus), 10)
    assert names == [citable_slots(record)[0].slot]


def test_live_reads_are_not_citable(s_questions: tuple[GoldRecord, ...]) -> None:
    live = [s for q in s_questions for s in q.slots if any(c.doc_id.startswith("live:") for c in s.alternatives)]
    assert live, "the fixture should contain live-read slots"
    for record in s_questions:
        assert all(s.state is SlotState.SATISFIABLE for s in citable_slots(record))
        assert not any(c.doc_id.startswith("live:") for s in citable_slots(record) for c in s.alternatives)
