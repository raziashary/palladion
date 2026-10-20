"""Citation metrics: each defect is caught for its own reason, and the denominators stay visible (B05-T01.01)."""

from __future__ import annotations

from dataclasses import replace

import pytest
from support import gold_delivered, make_case, perfect_response

from benchmark.contracts import CaseResponse, Claim, RunStatus
from benchmark.eval.citations import CitationStatus, check_citation, score_citations
from benchmark.eval.normalize import PublishedCorpus
from benchmark.fixtures.answer_gold import AnswerGold
from benchmark.fixtures.questions import Answerability, GoldRecord


def pairs(questions: tuple[GoldRecord, ...], golds: tuple[AnswerGold, ...]) -> list[tuple[GoldRecord, AnswerGold]]:
    return list(zip(questions, golds, strict=True))


def with_citations(record: GoldRecord, gold: AnswerGold, citations: tuple[str, ...]) -> CaseResponse:
    base = perfect_response(record, gold)
    first = replace(base.claims[0], citations=citations)
    return perfect_response(record, gold, claims=(first, *base.claims[1:]))


def first_with_claim(
    questions: tuple[GoldRecord, ...], golds: tuple[AnswerGold, ...], stratum: str
) -> tuple[GoldRecord, AnswerGold]:
    return next((q, g) for q, g in pairs(questions, golds) if q.stratum.value == stratum and g.units)


def test_a_perfect_answer_has_no_fabrication_and_full_citation_support(
    s_questions: tuple[GoldRecord, ...],
    s_golds: tuple[AnswerGold, ...],
    s_published_corpus: PublishedCorpus,
    s_roles: dict[str, str],
) -> None:
    checked = 0
    for record, gold in pairs(s_questions, s_golds):
        if record.answerability is not Answerability.ANSWERABLE or not gold.units:
            continue
        case = make_case(record, gold, perfect_response(record, gold), role_id=s_roles[record.principal_id])
        score = score_citations(case, s_published_corpus)
        assert score.fabricated == 0 and score.inaccessible == 0 and score.unauthoritative == 0, record.question_id
        assert score.inapplicable == 0
        if score.source_requiring_claims:
            assert score.recall == 1.0 and score.precision == 1.0, record.question_id
            assert score.uncited_claims == 0
        checked += 1
    assert checked >= 50


def test_a_perfect_answer_completes_a_minimal_evidence_set(
    s_questions: tuple[GoldRecord, ...],
    s_golds: tuple[AnswerGold, ...],
    s_published_corpus: PublishedCorpus,
    s_roles: dict[str, str],
) -> None:
    record, gold = first_with_claim(s_questions, s_golds, "Q4")
    case = make_case(record, gold, perfect_response(record, gold), role_id=s_roles[record.principal_id])
    assert score_citations(case, s_published_corpus).set_complete is True
    empty = make_case(record, gold, perfect_response(record, gold, claims=()), role_id=s_roles[record.principal_id])
    assert score_citations(empty, s_published_corpus).set_complete is False


def test_a_fabricated_locator_a_missing_document_and_a_bad_string_are_each_detected(
    s_questions: tuple[GoldRecord, ...],
    s_golds: tuple[AnswerGold, ...],
    s_published_corpus: PublishedCorpus,
    s_roles: dict[str, str],
) -> None:
    record, gold = first_with_claim(s_questions, s_golds, "Q2")
    doc = record.citation_gold_spans[0].doc_id
    for fake in (f"{doc}#99.99", "POL-999@v1#4.1", "not a citation!"):
        case = make_case(
            record,
            gold,
            with_citations(record, gold, (fake,)),
            role_id=s_roles[record.principal_id],
        )
        score = score_citations(case, s_published_corpus)
        assert [c.status for c in score.checks] == [CitationStatus.FABRICATED], fake
        assert score.fabricated == 1 and score.supported_claims < score.source_requiring_claims


def test_a_citation_to_something_the_generator_was_not_shown_is_outside_the_bundle(
    s_questions: tuple[GoldRecord, ...],
    s_golds: tuple[AnswerGold, ...],
    s_published_corpus: PublishedCorpus,
    s_roles: dict[str, str],
) -> None:
    record, gold = first_with_claim(s_questions, s_golds, "Q2")
    case = make_case(
        record, gold, perfect_response(record, gold), delivered=frozenset(), role_id=s_roles[record.principal_id]
    )
    score = score_citations(case, s_published_corpus)
    assert score.count(CitationStatus.OUTSIDE_BUNDLE) == len(score.checks) > 0
    assert score.fabricated == len(score.checks) and score.recall == 0.0


def test_uncited_claims_are_counted_apart_from_wrongly_cited_ones(
    s_questions: tuple[GoldRecord, ...],
    s_golds: tuple[AnswerGold, ...],
    s_published_corpus: PublishedCorpus,
    s_roles: dict[str, str],
) -> None:
    record, gold = first_with_claim(s_questions, s_golds, "Q2")
    case = make_case(
        record,
        gold,
        with_citations(record, gold, ()),
        role_id=s_roles[record.principal_id],
    )
    score = score_citations(case, s_published_corpus)
    assert score.uncited_claims == 1 and score.fabricated == 0 and score.checks == ()
    assert score.recall == 0.0 and score.precision is None


def test_a_draft_or_withdrawn_document_cannot_govern_a_claim(
    s_questions: tuple[GoldRecord, ...],
    s_golds: tuple[AnswerGold, ...],
    s_published_corpus: PublishedCorpus,
    s_roles: dict[str, str],
) -> None:
    record, gold = first_with_claim(s_questions, s_golds, "Q2")
    draft = next(d for d in s_published_corpus.docs.values() if d.record.registry_state == "draft" and d.clauses)
    clause = next(iter(draft.clauses))
    cite = f"{draft.record.doc_id}#{clause}"
    case = make_case(
        record, gold, with_citations(record, gold, (cite,)),
        delivered=gold_delivered(record) | {(draft.record.doc_id, clause)}, role_id="auditor",
    )  # fmt: skip
    score = score_citations(case, s_published_corpus)
    check = score.checks[0]
    assert check.status is CitationStatus.VALID and check.authoritative is False and not check.sound
    assert score.unauthoritative == 1 and score.supported_claims == 0


def test_a_document_the_principal_may_not_read_is_inaccessible(
    s_questions: tuple[GoldRecord, ...],
    s_golds: tuple[AnswerGold, ...],
    s_published_corpus: PublishedCorpus,
    s_roles: dict[str, str],
) -> None:
    record, gold = first_with_claim(s_questions, s_golds, "Q2")
    role = s_roles[record.principal_id]
    hidden = next(
        d
        for d in s_published_corpus.docs.values()
        if d.clauses
        and d.record.registry_state == "approved"
        and (
            (d.record.acl_tenants and record.tenant_id not in d.record.acl_tenants)
            or role not in (d.record.acl_roles or (role,))
        )
    )
    clause = next(iter(hidden.clauses))
    case = make_case(
        record, gold, with_citations(record, gold, (f"{hidden.record.doc_id}#{clause}",)),
        delivered=gold_delivered(record) | {(hidden.record.doc_id, clause)}, role_id=role,
    )  # fmt: skip
    score = score_citations(case, s_published_corpus)
    assert score.checks[0].accessible is False and score.inaccessible == 1 and not score.checks[0].sound


def test_a_wrong_version_of_the_applicable_family_is_inapplicable(
    s_questions: tuple[GoldRecord, ...],
    s_golds: tuple[AnswerGold, ...],
    s_published_corpus: PublishedCorpus,
    s_roles: dict[str, str],
) -> None:
    for record, gold in pairs(s_questions, s_golds):
        if record.stratum.value != "Q4" or not gold.version_ids or record.history_allowed:
            continue
        applicable = gold.version_ids[0]
        family = s_published_corpus.docs[applicable].record.family_id
        other = next(
            (
                d
                for d in s_published_corpus.docs.values()
                if d.record.family_id == family and d.record.doc_id not in gold.version_ids and d.clauses
            ),
            None,
        )
        if other is None:
            continue
        clause = next(iter(other.clauses))
        case = make_case(
            record, gold, with_citations(record, gold, (f"{other.record.doc_id}#{clause}",)),
            delivered=gold_delivered(record) | {(other.record.doc_id, clause)}, role_id=s_roles[record.principal_id],
        )  # fmt: skip
        score = score_citations(case, s_published_corpus)
        assert score.checks[0].applicable is False and score.inapplicable == 1
        return
    pytest.fail("no Q4 question with a second version to cite was found")


def test_a_whole_document_citation_is_coarse_and_a_clause_citation_is_not(
    s_questions: tuple[GoldRecord, ...],
    s_golds: tuple[AnswerGold, ...],
    s_published_corpus: PublishedCorpus,
    s_roles: dict[str, str],
) -> None:
    record, gold = first_with_claim(s_questions, s_golds, "Q2")
    span = record.citation_gold_spans[0]
    role = s_roles[record.principal_id]
    coarse = make_case(
        record,
        gold,
        with_citations(record, gold, (span.doc_id,)),
        role_id=role,
    )
    fine = make_case(
        record,
        gold,
        with_citations(record, gold, (f"{span.doc_id}#{span.clause_id}",)),
        role_id=role,
    )
    assert score_citations(coarse, s_published_corpus).granularity == 0.0
    assert score_citations(fine, s_published_corpus).granularity == 1.0


def test_a_valid_citation_that_is_not_one_the_gold_names_lowers_precision_not_recall(
    s_questions: tuple[GoldRecord, ...],
    s_golds: tuple[AnswerGold, ...],
    s_published_corpus: PublishedCorpus,
    s_roles: dict[str, str],
) -> None:
    record, gold = first_with_claim(s_questions, s_golds, "Q2")
    span = record.citation_gold_spans[0]
    other = next(
        d for d in s_published_corpus.docs.values()
        if d.record.registry_state == "approved" and d.clauses and d.record.doc_id != span.doc_id
        and not d.record.acl_tenants and not d.record.acl_roles
    )  # fmt: skip
    clause = next(iter(other.clauses))
    mine = (f"{span.doc_id}#{span.clause_id}", f"{other.record.doc_id}#{clause}")
    case = make_case(
        record, gold, with_citations(record, gold, mine),
        delivered=gold_delivered(record) | {(other.record.doc_id, clause)}, role_id=s_roles[record.principal_id],
    )  # fmt: skip
    score = score_citations(case, s_published_corpus)
    assert score.precision == 0.5 and score.recall == 1.0 and score.diversity is not None


def test_entailment_reads_labels_and_counts_the_pairs_it_has_none_for(
    s_questions: tuple[GoldRecord, ...],
    s_golds: tuple[AnswerGold, ...],
    s_published_corpus: PublishedCorpus,
    s_roles: dict[str, str],
) -> None:
    record, gold = first_with_claim(s_questions, s_golds, "Q2")
    span = record.citation_gold_spans[0]
    cite = f"{span.doc_id}#{span.clause_id}"
    case = make_case(record, gold, perfect_response(record, gold), role_id=s_roles[record.principal_id])
    none = score_citations(case, s_published_corpus)
    assert (none.entailed, none.not_entailed, none.unlabelled) == (0, 0, len(none.checks))
    yes = score_citations(case, s_published_corpus, {(record.question_id, "", "c1", cite): True})
    assert yes.entailed == 1 and yes.unlabelled == len(none.checks) - 1
    no = score_citations(case, s_published_corpus, {(record.question_id, "", "c1", cite): False})
    assert no.not_entailed == 1 and no.entailed == 0


def test_a_live_read_is_not_a_document_and_is_not_scored_as_one(
    s_questions: tuple[GoldRecord, ...],
    s_golds: tuple[AnswerGold, ...],
    s_published_corpus: PublishedCorpus,
    s_roles: dict[str, str],
) -> None:
    record, gold = first_with_claim(s_questions, s_golds, "Q2")
    case = make_case(record, gold, perfect_response(record, gold), role_id=s_roles[record.principal_id])
    check = check_citation(case, s_published_corpus, "c1", "live:settlement_state#TXN-1", set())
    assert check.status is CitationStatus.LIVE and check.accessible is None and not check.sound


def test_a_pair_that_did_not_complete_has_no_citation_score(
    s_questions: tuple[GoldRecord, ...],
    s_golds: tuple[AnswerGold, ...],
    s_published_corpus: PublishedCorpus,
) -> None:
    record, gold = first_with_claim(s_questions, s_golds, "Q2")
    case = make_case(record, gold, None, status=RunStatus.TIMEOUT)
    with pytest.raises(ValueError, match="completed"):
        score_citations(case, s_published_corpus)


def test_claims_that_rest_on_no_document_do_not_count_as_source_requiring(
    s_questions: tuple[GoldRecord, ...],
    s_golds: tuple[AnswerGold, ...],
    s_published_corpus: PublishedCorpus,
    s_roles: dict[str, str],
) -> None:
    record, gold = first_with_claim(s_questions, s_golds, "Q2")
    extra = Claim("live1", "the live read says settled", (), kind="LIVE_STATE", params={"operation": "x", "state": "y"})
    base = perfect_response(record, gold)
    case = make_case(
        record, gold, perfect_response(record, gold, claims=(*base.claims, extra)), role_id=s_roles[record.principal_id]
    )
    score = score_citations(case, s_published_corpus)
    assert score.claims == len(base.claims) + 1 and score.source_requiring_claims == len(base.claims)
    assert score.uncited_claims == 1


def test_precision_is_over_the_valid_citations_so_a_fabricated_one_does_not_hide_in_it(
    s_questions: tuple[GoldRecord, ...],
    s_golds: tuple[AnswerGold, ...],
    s_published_corpus: PublishedCorpus,
    s_roles: dict[str, str],
) -> None:
    record, gold = first_with_claim(s_questions, s_golds, "Q2")
    span = record.citation_gold_spans[0]
    mixed = (f"{span.doc_id}#{span.clause_id}", "POL-999@v1#4.1")
    case = make_case(record, gold, with_citations(record, gold, mixed), role_id=s_roles[record.principal_id])
    score = score_citations(case, s_published_corpus)
    assert score.precision == 1.0 and score.fabricated == 1 and score.recall == 1.0
