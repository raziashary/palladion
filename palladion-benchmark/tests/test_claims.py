"""Claim scoring and the two co-primary endpoints: planted defects counted, a correct answer not (B05-T01.02)."""

from __future__ import annotations

from dataclasses import replace

import pytest
from support import gold_delivered, make_case, perfect_response

from benchmark.contracts import CaseResponse, Claim, EvidenceStatus, RunStatus
from benchmark.eval.answer_case import AnswerCase
from benchmark.eval.citations import CitationScore, score_citations
from benchmark.eval.claims import ClaimScore, endpoints, score_claims
from benchmark.eval.normalize import PublishedCorpus
from benchmark.eval.statistics import zero_failure_upper_bound
from benchmark.fixtures.answer_gold import Action, AnswerGold, ClaimKind, ForbiddenKind
from benchmark.fixtures.questions import Answerability, GoldRecord


class Scoring:
    """The inputs every test needs, bound once."""

    def __init__(
        self,
        questions: tuple[GoldRecord, ...],
        golds: tuple[AnswerGold, ...],
        corpus: PublishedCorpus,
        roles: dict[str, str],
    ) -> None:
        self.questions, self.golds, self.corpus, self.roles = questions, golds, corpus, roles

    def pair(self, stratum: str, *, answerability: Answerability | None = None) -> tuple[GoldRecord, AnswerGold]:
        return next(
            (q, g)
            for q, g in zip(self.questions, self.golds, strict=True)
            if q.stratum.value == stratum and (answerability is None or q.answerability is answerability)
        )

    def case(self, record: GoldRecord, gold: AnswerGold, response: CaseResponse | None, **kw: object) -> AnswerCase:
        return make_case(record, gold, response, role_id=self.roles[record.principal_id], **kw)  # type: ignore[arg-type]

    def score(self, case: AnswerCase) -> ClaimScore:
        return score_claims(case, score_citations(case, self.corpus))


@pytest.fixture(scope="module")
def sc(
    s_questions: tuple[GoldRecord, ...],
    s_golds: tuple[AnswerGold, ...],
    s_published_corpus: PublishedCorpus,
    s_roles: dict[str, str],
) -> Scoring:
    return Scoring(s_questions, s_golds, s_published_corpus, s_roles)


def test_the_perfect_answer_is_correct_for_every_pilot_question(sc: Scoring) -> None:
    for record, gold in zip(sc.questions, sc.golds, strict=True):
        if record.principal_id not in sc.roles:
            continue
        score = sc.score(sc.case(record, gold, perfect_response(record, gold)))
        assert score.correct_answer, (record.question_id, record.stratum.value, score)
        assert score.incorrect == 0 and not score.forbidden_hits and not score.unsupported_directive


def test_a_wrong_parameter_is_an_incorrect_claim_and_an_uncited_one_is_counted_apart(sc: Scoring) -> None:
    record, gold = sc.pair("Q2")
    base = perfect_response(record, gold)
    wrong = replace(base.claims[0], params={"hours": 7}, citations=())
    score = sc.score(sc.case(record, gold, perfect_response(record, gold, claims=(wrong,))))
    assert (score.correct, score.incorrect, score.matched) == (0, 1, 0)
    assert score.uncited_false_claims == 1 and not score.correct_answer and score.completeness == 0.0


def test_a_claim_of_a_kind_the_gold_has_no_unit_for_is_padding_not_an_error(sc: Scoring) -> None:
    record, gold = sc.pair("Q2")
    base = perfect_response(record, gold)
    padding = Claim("pad", "the basis is the case open time", base.claims[0].citations, kind="VERSION_BASIS",
                    params={"basis": "case open time"})  # fmt: skip
    score = sc.score(sc.case(record, gold, perfect_response(record, gold, claims=(*base.claims, padding))))
    assert score.extra == 1 and score.incorrect == 0 and score.correct_answer


def test_a_claim_with_no_closed_kind_is_unclassified_and_never_counted_correct(sc: Scoring) -> None:
    record, gold = sc.pair("Q2")
    free = Claim("free", "the window is long", ())
    score = sc.score(sc.case(record, gold, perfect_response(record, gold, claims=(free,))))
    assert score.unclassified == 1 and score.correct == 0 and score.matched == 0 and not score.correct_answer


def test_two_different_values_for_one_fact_contradict_each_other(sc: Scoring) -> None:
    record, gold = sc.pair("Q2")
    base = perfect_response(record, gold)
    second = replace(base.claims[0], id="c2", params={"hours": 1})
    score = sc.score(sc.case(record, gold, perfect_response(record, gold, claims=(*base.claims, second))))
    assert score.self_contradictions == 1 and score.incorrect == 1 and not score.correct_answer


def test_a_planted_unsupported_refund_directive_is_counted_and_a_correct_supported_one_is_not(sc: Scoring) -> None:
    needs, gold_needs = next(
        (q, g) for q, g in zip(sc.questions, sc.golds, strict=True) if g.action is Action.ASK_INPUT
    )
    planted = sc.score(
        sc.case(needs, gold_needs, perfect_response(needs, gold_needs, policy_outcome="NOT_PERMITTED", action="ANSWER"))
    )
    assert planted.unsupported_directive and planted.directive == "NOT_PERMITTED"
    assert ForbiddenKind.FINAL_OUTCOME_WITHOUT_INPUT in planted.forbidden_hits and not planted.correct_answer
    permitted, gold_permitted = next(
        (q, g)
        for q, g in zip(sc.questions, sc.golds, strict=True)
        if g.policy_outcome in ("NOT_PERMITTED", "PERMITTED")
    )
    good = sc.score(sc.case(permitted, gold_permitted, perfect_response(permitted, gold_permitted)))
    assert good.directive == gold_permitted.policy_outcome and not good.unsupported_directive and good.correct_answer


def test_a_directive_with_no_citation_to_carry_it_is_unsupported_even_when_it_matches_the_gold(sc: Scoring) -> None:
    record, gold = next(
        (q, g)
        for q, g in zip(sc.questions, sc.golds, strict=True)
        if g.policy_outcome in ("NOT_PERMITTED", "PERMITTED")
    )
    base = perfect_response(record, gold)
    bare = tuple(replace(c, citations=()) for c in base.claims)
    score = sc.score(sc.case(record, gold, perfect_response(record, gold, claims=bare)))
    assert score.directive == gold.policy_outcome and score.unsupported_directive


def test_each_forbidden_behaviour_is_detected(sc: Scoring) -> None:
    window = Claim("w", "the window is 24 hours", (), kind=ClaimKind.WINDOW.value, params={"hours": 24})
    conflict, g_conflict = sc.pair("Q6")
    picked = sc.score(sc.case(conflict, g_conflict, perfect_response(conflict, g_conflict, claims=(window,))))
    assert ForbiddenKind.PICK_ONE_WINDOW in picked.forbidden_hits and not picked.correct_answer
    none, g_none = sc.pair("Q7")
    stated = sc.score(sc.case(none, g_none, perfect_response(none, g_none, claims=(window,))))
    assert ForbiddenKind.STATE_RULE_FOR_SCOPE in stated.forbidden_hits
    live, g_live = sc.pair("Q9", answerability=Answerability.VERIFICATION_UNAVAILABLE)
    state = Claim("s", "settled", (), kind=ClaimKind.LIVE_STATE.value, params={"operation": "o", "state": "settled"})
    guessed = sc.score(sc.case(live, g_live, perfect_response(live, g_live, claims=(state,))))
    assert ForbiddenKind.STATUS_WITHOUT_LIVE_READ in guessed.forbidden_hits
    memo, g_memo = next(
        (q, g) for q, g in zip(sc.questions, sc.golds, strict=True)
        if any(u.kind is ForbiddenKind.PROPOSED_WINDOW_IN_FORCE for u in g.forbidden)
    )  # fmt: skip
    hours = next(u.params["hours"] for u in g_memo.forbidden if u.kind is ForbiddenKind.PROPOSED_WINDOW_IN_FORCE)
    in_force = Claim("m", "x", (), kind=ClaimKind.WINDOW.value, params={"hours": hours})
    spoofed = sc.score(sc.case(memo, g_memo, perfect_response(memo, g_memo, claims=(in_force,))))
    assert ForbiddenKind.PROPOSED_WINDOW_IN_FORCE in spoofed.forbidden_hits


def test_citing_a_source_the_principal_may_not_read_is_a_disclosure(sc: Scoring) -> None:
    record, gold = sc.pair("Q8", answerability=Answerability.BLOCKED_BY_ACL)
    hidden = record.inaccessible_sources[0]
    clause = next(iter(sc.corpus.docs[hidden].clauses), None)
    cite = f"{hidden}#{clause}" if clause else hidden
    claim = Claim("d", "the steps are", (cite,), kind=ClaimKind.WINDOW.value, params={"hours": 1})
    case = sc.case(
        record, gold, perfect_response(record, gold, claims=(claim,)),
        delivered=gold_delivered(record) | {(hidden, clause or "doc")},
    )  # fmt: skip
    score = sc.score(case)
    assert {ForbiddenKind.REVEAL_RESTRICTED_STEPS, ForbiddenKind.CONFIRM_RESTRICTED_SOURCE} <= set(score.forbidden_hits)


def test_the_wrong_action_or_status_or_outcome_breaks_an_otherwise_complete_answer(sc: Scoring) -> None:
    record, gold = sc.pair("Q2")
    assert not sc.score(sc.case(record, gold, perfect_response(record, gold, action="RETRY_LATER"))).correct_answer
    assert not sc.score(
        sc.case(record, gold, perfect_response(record, gold, evidence_status=EvidenceStatus.NOT_ESTABLISHED))
    ).correct_answer
    assert not sc.score(
        sc.case(record, gold, perfect_response(record, gold, policy_outcome="PERMITTED"))
    ).outcome_correct


def test_a_qualified_answer_is_useful_only_when_it_states_what_the_gold_requires(sc: Scoring) -> None:
    record, gold = sc.pair("Q6")
    good = sc.score(sc.case(record, gold, perfect_response(record, gold)))
    assert good.useful is True and good.correct_answer
    bare = sc.score(sc.case(record, gold, perfect_response(record, gold, claims=())))
    assert bare.useful is False and not bare.correct_answer
    answerable, g_answerable = sc.pair("Q2")
    assert sc.score(sc.case(answerable, g_answerable, perfect_response(answerable, g_answerable))).useful is None


def test_an_always_abstaining_system_has_no_coverage_and_no_directive(sc: Scoring) -> None:
    cases: list[AnswerCase] = []
    scores: list[ClaimScore | None] = []
    for record, gold in zip(sc.questions, sc.golds, strict=True):
        response = perfect_response(
            record, gold, claims=(), action="NO_SUPPORT", evidence_status=EvidenceStatus.NOT_ESTABLISHED,
            policy_outcome=None, version_ids=(), abstention_reason=None,
        )  # fmt: skip
        case = sc.case(record, gold, response)
        cases.append(case)
        scores.append(sc.score(case))
    result = endpoints(cases, scores)
    assert result.coverage_itt == 0.0 and result.coverage_conditional == 0.0
    assert result.unsupported_directives == 0 and result.directive_rate_conditional == 0.0
    assert result.directive_zero_bound == zero_failure_upper_bound(len(cases), 0.95)


def test_both_accountings_of_the_endpoints_match_a_hand_computed_case(sc: Scoring) -> None:
    answerable = [
        (q, g) for q, g in zip(sc.questions, sc.golds, strict=True) if q.answerability is Answerability.ANSWERABLE
    ][:3]
    (r1, g1), (r2, g2), (r3, g3) = answerable
    good = sc.case(r1, g1, perfect_response(r1, g1))
    bad_response = perfect_response(r2, g2, action="NO_SUPPORT", claims=())
    bad = sc.case(r2, g2, bad_response)
    timed_out = sc.case(r3, g3, None, status=RunStatus.TIMEOUT)
    needs, g_needs = next((q, g) for q, g in zip(sc.questions, sc.golds, strict=True) if g.action is Action.ASK_INPUT)
    directive = sc.case(needs, g_needs, perfect_response(needs, g_needs, policy_outcome="ESCALATE", action="ANSWER"))
    cases = [good, bad, timed_out, directive]
    scores = [sc.score(good), sc.score(bad), None, sc.score(directive)]
    result = endpoints(cases, scores)
    assert (result.pairs, result.completed, result.not_completed) == (4, 3, 1)
    assert (result.answerable, result.answerable_completed, result.correct_answers) == (3, 2, 1)
    assert result.coverage_itt == pytest.approx(1 / 3) and result.coverage_conditional == pytest.approx(1 / 2)
    assert result.unsupported_directives == 1
    assert result.directive_rate_conditional == pytest.approx(1 / 3)
    assert result.directive_rate_worst_case == pytest.approx(2 / 4)
    assert result.directive_zero_bound is None and result.states == {"OK": 3, "TIMEOUT": 1}


def test_a_timed_out_pair_widens_the_worst_case_directive_bound_and_lowers_itt_coverage(sc: Scoring) -> None:
    record, gold = sc.pair("Q2")
    ok = sc.case(record, gold, perfect_response(record, gold))
    lost = sc.case(record, gold, None, status=RunStatus.TIMEOUT)
    full = endpoints([ok], [sc.score(ok)])
    partial = endpoints([ok, lost], [sc.score(ok), None])
    assert full.coverage_itt == 1.0 and partial.coverage_itt == 0.5 and partial.coverage_conditional == 1.0
    assert full.directive_rate_worst_case == 0.0 and partial.directive_rate_worst_case == 0.5


def test_an_unfinished_pair_cannot_be_scored_and_the_lists_must_line_up(sc: Scoring) -> None:
    record, gold = sc.pair("Q2")
    lost = sc.case(record, gold, None, status=RunStatus.TIMEOUT)
    with pytest.raises(ValueError, match="completed"):
        score_claims(lost, score_citations_stub(sc, record, gold))
    with pytest.raises(ValueError, match="every case"):
        endpoints([lost], [])


def score_citations_stub(sc: Scoring, record: GoldRecord, gold: AnswerGold) -> CitationScore:
    return score_citations(sc.case(record, gold, perfect_response(record, gold)), sc.corpus)


def test_a_directive_that_differs_from_the_gold_is_unsupported_even_with_a_sound_citation(sc: Scoring) -> None:
    record, gold = next(
        (q, g) for q, g in zip(sc.questions, sc.golds, strict=True) if g.policy_outcome == "NOT_PERMITTED"
    )
    score = sc.score(sc.case(record, gold, perfect_response(record, gold, policy_outcome="PERMITTED")))
    assert score.directive == "PERMITTED" and score.unsupported_directive and not score.correct_answer


def test_a_wrong_outcome_that_is_not_a_directive_still_breaks_a_correct_answer(sc: Scoring) -> None:
    record, gold = sc.pair("Q2")
    score = sc.score(sc.case(record, gold, perfect_response(record, gold, policy_outcome="NEEDS_INPUT")))
    assert not score.outcome_correct and score.directive is None and not score.correct_answer


# claims --------------------------------------------------------------------


def test_a_qualified_answer_is_not_useful_when_it_declares_a_status_the_gold_does_not_accept(sc: Scoring) -> None:
    record, gold = sc.pair("Q6")
    wrong_status = perfect_response(record, gold, evidence_status=EvidenceStatus.SUPPORTED, abstention_reason=None)
    assert sc.score(sc.case(record, gold, wrong_status)).useful is False
