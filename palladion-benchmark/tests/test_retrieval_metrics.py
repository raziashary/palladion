"""Ranking and provenance-aware retrieval metrics over the real S-tier fixture (B03-T03.01 and B03-T03.02)."""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import pytest
from support import cited, make_candidate, oracle

from benchmark.config import load_evaluation_config
from benchmark.contracts import EvidenceCandidate
from benchmark.eval.evidence_sets import citable_slots
from benchmark.eval.normalize import PublishedCorpus, align_all
from benchmark.eval.retrieval import (
    RETRIEVAL_METRICS,
    ProvenanceScores,
    rank_gains,
    score_provenance,
    score_ranking,
    slot_kind,
)
from benchmark.fixtures import sha256_hex
from benchmark.fixtures.questions import Answerability, Citation, GoldRecord, derive_minimal_sets
from benchmark.fixtures.world import World

CONFIGS = Path(__file__).resolve().parents[1] / "configs"
JUNK = "Quarterly newsletter about the office plants and the cafeteria menu for the coming month."


def junk(rank: int) -> EvidenceCandidate:
    return make_candidate(f"{JUNK} Edition {rank}.", rank)


def multi_slot(questions: tuple[GoldRecord, ...]) -> GoldRecord:
    return next(q for q in questions if len(citable_slots(q)) >= 2)


def provenance(
    record: GoldRecord, candidates: list[EvidenceCandidate], corpus: PublishedCorpus, world: World, k: int = 10
) -> ProvenanceScores:
    role = world.entities.principal(record.principal_id).role_id
    kinds = load_evaluation_config(CONFIGS / "evaluation.yaml").slot_kinds
    return score_provenance(record, candidates, align_all(candidates, corpus), corpus, role_id=role, kinds=kinds, k=k)


# --------------------------------------------------------------------------- ranking


def test_oracle_ranking_is_perfect(s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus) -> None:
    for record in (q for q in s_questions if citable_slots(q)):
        got = score_ranking(record, align_all(oracle(s_published_corpus, record), s_published_corpus), k=10)
        assert (got.precision, got.recall, got.mrr, got.map, got.success) == (1.0, 1.0, 1.0, 1.0, 1.0)
        assert got.ndcg == pytest.approx(1.0)


def test_empty_return_scores_zero(s_questions: tuple[GoldRecord, ...]) -> None:
    got = score_ranking(multi_slot(s_questions), [], k=10)
    assert (got.returned, got.precision, got.recall, got.mrr, got.ndcg, got.map, got.success) == (0,) + (0.0,) * 6


def test_no_citable_slot_is_not_applicable(s_questions: tuple[GoldRecord, ...]) -> None:
    record = next(q for q in s_questions if not citable_slots(q))
    got = score_ranking(record, [], k=10)
    assert got.returned == 0
    assert None is got.precision is got.recall is got.mrr is got.ndcg is got.map is got.success


def test_hand_computed_ranking(s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus) -> None:
    record = next(q for q in s_questions if len(citable_slots(q)) == 2)
    hit_a, hit_b = (cited(s_published_corpus, s.alternatives[0], 1) for s in citable_slots(record))
    ranked = [junk(1), replace(hit_a, rank=2), junk(3), replace(hit_b, rank=4)]
    got = score_ranking(record, align_all(ranked, s_published_corpus), k=10)
    assert rank_gains(record, align_all(ranked, s_published_corpus), 10) == [0, 1, 0, 1]
    assert got.precision == 0.5
    assert got.recall == 1.0
    assert got.mrr == 0.5
    assert got.map == pytest.approx((1 / 2 + 2 / 4) / 2)
    ideal = 1 + 1 / math.log2(3)
    assert got.ndcg == pytest.approx((1 / math.log2(3) + 1 / math.log2(5)) / ideal)


def test_ranking_order_changes_rank_metrics_not_recall(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus
) -> None:
    record = multi_slot(s_questions)
    good = oracle(s_published_corpus, record)
    pushed_down = [junk(i) for i in range(1, 4)] + [replace(c, rank=c.rank + 3) for c in good]
    a = score_ranking(record, align_all(good, s_published_corpus), 10)
    b = score_ranking(record, align_all(pushed_down, s_published_corpus), 10)
    assert a.recall == b.recall == 1.0
    assert b.mrr is not None and a.mrr is not None and b.mrr < a.mrr
    assert b.ndcg is not None and a.ndcg is not None and b.ndcg < a.ndcg
    assert b.precision is not None and a.precision is not None and b.precision < a.precision


def test_repeating_a_relevant_chunk_earns_no_second_gain(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus
) -> None:
    record = multi_slot(s_questions)
    first = cited(s_published_corpus, citable_slots(record)[0].alternatives[0], 1)
    ranked = [first, replace(first, rank=2), replace(first, rank=3)]
    assert rank_gains(record, align_all(ranked, s_published_corpus), 10) == [1, 0, 0]


def test_k_cuts_the_list(s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus) -> None:
    record = multi_slot(s_questions)
    ranked = [junk(1), junk(2)] + [replace(c, rank=c.rank + 2) for c in oracle(s_published_corpus, record)]
    alignments = align_all(ranked, s_published_corpus)
    assert score_ranking(record, alignments, k=2).success == 0.0
    assert score_ranking(record, alignments, k=len(ranked)).success == 1.0


def test_pasted_text_has_no_identity_credit(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus
) -> None:
    record = multi_slot(s_questions)
    pasted = [make_candidate(c.content, c.rank) for c in oracle(s_published_corpus, record)]
    alignments = align_all(pasted, s_published_corpus)
    assert score_ranking(record, alignments, 10).recall == 0.0
    assert (score_ranking(record, alignments, 10, include_alignment=True).recall or 0.0) > 0.0


# --------------------------------------------------------------------------- provenance


def test_oracle_has_clean_provenance(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus, s_world: World
) -> None:
    checked = 0
    for record in (q for q in s_questions if citable_slots(q)):
        got = provenance(record, oracle(s_published_corpus, record), s_published_corpus, s_world)
        assert got.forbidden_exposure_count == 0 and got.authority_confusion_count == 0, record.question_id
        assert got.citation_locator_resolution == 1.0
        assert got.valid_source_recall == 1.0
        assert got.wrong_vintage_intrusion in (None, 0.0)
        checked += 1
    assert checked >= 5


def test_an_unauthorized_source_is_counted_as_exposure(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus, s_world: World
) -> None:
    record = next(q for q in s_questions if q.inaccessible_sources)
    leak = make_candidate("anything", 1, source_document_id=record.inaccessible_sources[0], locator="doc")
    assert provenance(record, [leak], s_published_corpus, s_world).forbidden_exposure_count == 1
    assert provenance(record, [junk(1)], s_published_corpus, s_world).forbidden_exposure_count == 0


def test_a_source_the_gold_lists_as_inaccessible_is_exposure_even_when_the_manifest_would_allow_it(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus, s_world: World
) -> None:
    record = next(q for q in s_questions if citable_slots(q))
    role = s_world.entities.principal(record.principal_id).role_id
    cited_docs = {c.doc_id for c in record.citation_gold_spans}
    open_doc = next(
        d.record.doc_id
        for d in s_published_corpus.docs.values()
        if d.record.doc_id not in cited_docs
        and (not d.record.acl_tenants or record.tenant_id in d.record.acl_tenants)
        and (not d.record.acl_roles or role in d.record.acl_roles)
    )
    ranked = [make_candidate("x", 1, source_document_id=open_doc, locator="doc")]
    assert provenance(record, ranked, s_published_corpus, s_world).forbidden_exposure_count == 0
    declared = replace(record, inaccessible_sources=(*record.inaccessible_sources, open_doc))
    assert provenance(declared, ranked, s_published_corpus, s_world).forbidden_exposure_count == 1


def test_a_document_outside_the_principals_acl_is_exposure_even_if_gold_does_not_list_it(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus, s_world: World
) -> None:
    record = next(q for q in s_questions if citable_slots(q))
    role = s_world.entities.principal(record.principal_id).role_id
    hidden = next(
        d
        for d in s_published_corpus.docs.values()
        if (d.record.acl_tenants and record.tenant_id not in d.record.acl_tenants)
        or (d.record.acl_roles and role not in d.record.acl_roles)
    )
    leak = make_candidate("x", 1, source_document_id=hidden.record.doc_id, locator="doc")
    assert provenance(record, [leak], s_published_corpus, s_world).forbidden_exposure_count == 1


def test_unauthoritative_states_are_authority_confusion(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus, s_world: World
) -> None:
    record = next(q for q in s_questions if citable_slots(q))
    states = {"draft", "unapproved_proposal", "withdrawn"}
    bad = [d.record.doc_id for d in s_published_corpus.docs.values() if d.record.registry_state in states]
    assert bad, "the fixture should contain unauthoritative documents"
    ranked = [make_candidate("x", i, source_document_id=doc, locator="doc") for i, doc in enumerate(bad[:3], start=1)]
    got = provenance(record, ranked, s_published_corpus, s_world)
    assert got.authority_confusion_count == len(ranked)
    assert provenance(record, ranked, s_published_corpus, s_world, k=1).authority_confusion_count == 1


def test_an_older_version_of_the_governing_policy_is_wrong_vintage(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus, s_world: World
) -> None:
    for record in s_questions:
        applicable = set(record.gold_applicable_version_ids)
        if not applicable or record.history_allowed:
            continue
        families = {s_published_corpus.docs[v].record.family_id for v in applicable if v in s_published_corpus.docs}
        stale = next(
            (
                d.record.doc_id
                for d in s_published_corpus.docs.values()
                if d.record.family_id in families and d.record.doc_id not in applicable
            ),
            None,
        )
        if stale is None:
            continue
        right = oracle(s_published_corpus, record)
        wrong = [make_candidate("x", len(right) + 1, source_document_id=stale, locator="doc")]
        got = provenance(record, right + wrong, s_published_corpus, s_world)
        assert got.wrong_vintage_count == 1
        assert (got.wrong_vintage_intrusion or 0.0) > 0.0
        return
    pytest.fail("no record with a superseded sibling version in the fixture")


def test_history_questions_may_cite_old_versions(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus, s_world: World
) -> None:
    record = next(q for q in s_questions if q.gold_applicable_version_ids)
    older = next(
        d.record.doc_id
        for d in s_published_corpus.docs.values()
        if d.record.family_id == s_published_corpus.docs[record.gold_applicable_version_ids[0]].record.family_id
        and d.record.doc_id not in record.gold_applicable_version_ids
    )
    ranked = [make_candidate("x", 1, source_document_id=older, locator="doc")]
    allowed = replace(record, history_allowed=True)
    assert provenance(allowed, ranked, s_published_corpus, s_world).wrong_vintage_count == 0
    assert provenance(record, ranked, s_published_corpus, s_world).wrong_vintage_count == 1


def test_a_fabricated_locator_does_not_resolve(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus, s_world: World
) -> None:
    record = next(q for q in s_questions if citable_slots(q))
    real = oracle(s_published_corpus, record)[0]
    fake = replace(real, locator="clause:99.99")
    assert provenance(record, [real], s_published_corpus, s_world).citation_locator_resolution == 1.0
    assert provenance(record, [fake], s_published_corpus, s_world).citation_locator_resolution == 0.0
    assert provenance(record, [junk(1)], s_published_corpus, s_world).citation_locator_resolution is None


def test_exception_and_conflict_recall(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus, s_world: World
) -> None:
    kinds = load_evaluation_config(CONFIGS / "evaluation.yaml").slot_kinds
    with_exception = next(
        q for q in s_questions if any(slot_kind(s.slot, kinds) == "exception" for s in citable_slots(q))
    )
    full = oracle(s_published_corpus, with_exception)
    assert provenance(with_exception, full, s_published_corpus, s_world).exception_recall == 1.0
    assert provenance(with_exception, [junk(1)], s_published_corpus, s_world).exception_recall == 0.0
    plain = next(
        q
        for q in s_questions
        if q.answerability is Answerability.ANSWERABLE
        and not any(slot_kind(s.slot, kinds) == "exception" for s in q.slots)
    )
    assert provenance(plain, [], s_published_corpus, s_world).exception_recall is None
    conflict = next(q for q in s_questions if q.answerability is Answerability.CONFLICT)
    both = oracle(s_published_corpus, conflict)
    assert provenance(conflict, both, s_published_corpus, s_world).conflicting_pair_recall == 1.0
    assert provenance(conflict, both[:1], s_published_corpus, s_world).conflicting_pair_recall == 0.5
    assert provenance(plain, [], s_published_corpus, s_world).conflicting_pair_recall is None


def test_density_collapses_near_identical_passages(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus, s_world: World
) -> None:
    record = multi_slot(s_questions)
    good = oracle(s_published_corpus, record)
    copies = [replace(c, rank=c.rank + len(good)) for c in good]
    single = provenance(record, good, s_published_corpus, s_world)
    doubled = provenance(record, good + copies, s_published_corpus, s_world)
    assert single.evidence_density == pytest.approx(doubled.evidence_density or -1.0)
    assert doubled.words_returned == 2 * single.words_returned
    assert (doubled.evidence_token_efficiency or 0.0) == pytest.approx((single.evidence_token_efficiency or 0.0) / 2)
    empty = provenance(record, [], s_published_corpus, s_world)
    assert empty.evidence_density == 0.0 and empty.evidence_token_efficiency == 0.0


# --------------------------------------------------------------------------- configuration is consumed


def test_every_generated_slot_name_has_a_kind(s_questions: tuple[GoldRecord, ...]) -> None:
    kinds = load_evaluation_config(CONFIGS / "evaluation.yaml").slot_kinds
    names = {s.slot for q in s_questions for s in q.slots}
    assert names
    assert {n for n in names if slot_kind(n, kinds) is None} == set()
    assert slot_kind("exception_clause_3", kinds) == "exception"
    assert slot_kind("no_such_slot", kinds) is None


def test_every_retrieval_metric_is_in_exactly_one_group() -> None:
    groups = load_evaluation_config(CONFIGS / "evaluation.yaml").metric_groups
    listed = [m for members in groups.values() for m in members]
    for metric in RETRIEVAL_METRICS:
        assert listed.count(metric) == 1, metric


# --------------------------------------------------------------------------- audit follow-ups


def test_a_partial_excerpt_of_forbidden_text_is_exposure(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus, s_world: World
) -> None:
    record = next(q for q in s_questions if q.inaccessible_sources)
    hidden = s_published_corpus.docs[record.inaccessible_sources[0]]
    words = hidden.text.split()[:40]
    excerpt = " ".join(words[:22]) + " " + " ".join(f"filler{i}" for i in range(30))
    ranked = [make_candidate(excerpt, 1)]
    assert provenance(record, ranked, s_published_corpus, s_world).forbidden_exposure_count == 1
    assert provenance(record, [junk(1)], s_published_corpus, s_world).forbidden_exposure_count == 0


def test_a_repeated_relevant_chunk_is_relevant_for_precision_but_adds_no_gain(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus
) -> None:
    record = multi_slot(s_questions)
    first = cited(s_published_corpus, citable_slots(record)[0].alternatives[0], 1)
    ranked = [first, replace(first, rank=2)]
    got = score_ranking(record, align_all(ranked, s_published_corpus), 10)
    assert got.precision == 1.0
    assert rank_gains(record, align_all(ranked, s_published_corpus), 10) == [1, 0]


def test_live_citations_do_not_lower_the_locator_resolution_rate(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus, s_world: World
) -> None:
    record = next(q for q in s_questions if citable_slots(q))
    real = oracle(s_published_corpus, record)
    live = make_candidate("transaction state failed", len(real) + 1, source_document_id="live:txn-1", locator="doc")
    got = provenance(record, [*real, live], s_published_corpus, s_world)
    assert got.citation_locator_resolution == 1.0


def test_a_stale_version_ranked_first_is_an_intrusion(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus, s_world: World
) -> None:
    for record in s_questions:
        applicable = set(record.gold_applicable_version_ids)
        if not applicable or record.history_allowed:
            continue
        families = {s_published_corpus.docs[v].record.family_id for v in applicable if v in s_published_corpus.docs}
        stale = next(
            (
                d.record.doc_id
                for d in s_published_corpus.docs.values()
                if d.record.family_id in families and d.record.doc_id not in applicable
            ),
            None,
        )
        if stale is None:
            continue
        first = make_candidate("x", 1, source_document_id=stale, locator="doc")
        right = [replace(c, rank=c.rank + 1) for c in oracle(s_published_corpus, record)]
        got = provenance(record, [first, *right], s_published_corpus, s_world)
        assert got.wrong_vintage_count == 1
        assert provenance(record, [first, *right], s_published_corpus, s_world, k=1).wrong_vintage_intrusion == 1.0
        return
    pytest.fail("no record with a superseded sibling version in the fixture")


def test_repeated_short_passages_are_collapsed_in_density(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus, s_world: World
) -> None:
    record = multi_slot(s_questions)
    good = oracle(s_published_corpus, record)
    short = [make_candidate("see rule", len(good) + i) for i in (1, 2, 3)]
    once = provenance(record, [*good, short[0]], s_published_corpus, s_world)
    thrice = provenance(record, [*good, *short], s_published_corpus, s_world)
    assert once.evidence_density == pytest.approx(thrice.evidence_density or -1.0)


def test_a_near_identical_copy_is_collapsed_in_density(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus, s_world: World
) -> None:
    record = multi_slot(s_questions)
    good = oracle(s_published_corpus, record)
    words = good[0].content.split()
    assert len(words) >= 12, "the fixture clause must be long enough to alter one word"
    altered = " ".join([*words[:-1], "changed"])
    copy = make_candidate(altered, len(good) + 1)
    alone = provenance(record, good, s_published_corpus, s_world)
    with_copy = provenance(record, [*good, copy], s_published_corpus, s_world)
    assert with_copy.evidence_density == pytest.approx(alone.evidence_density or -1.0)
    assert with_copy.words_returned > alone.words_returned


def test_valid_source_recall_does_not_credit_a_gold_source_the_principal_cannot_see(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus, s_world: World
) -> None:
    record = next(q for q in s_questions if citable_slots(q))
    role = s_world.entities.principal(record.principal_id).role_id
    hidden = next(
        d
        for d in s_published_corpus.docs.values()
        if (d.record.acl_tenants and record.tenant_id not in d.record.acl_tenants)
        or (d.record.acl_roles and role not in d.record.acl_roles)
    )
    ranked = [make_candidate(hidden.text, 1, source_document_id=hidden.record.doc_id, locator="doc")]
    slot = replace(
        citable_slots(record)[0],
        alternatives=(Citation(hidden.record.doc_id, "doc", 0, len(hidden.text), sha256_hex(hidden.text)),),
    )
    broken = replace(
        record, slots=(slot,), minimal_sets=derive_minimal_sets((slot,)), citation_gold_spans=slot.alternatives
    )
    got = provenance(broken, ranked, s_published_corpus, s_world)
    assert got.valid_source_recall == 0.0
    assert score_ranking(broken, align_all(ranked, s_published_corpus), 10).recall == 1.0
