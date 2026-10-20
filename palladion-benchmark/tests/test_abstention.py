"""Abstention and loss: silence earns no credit and a flipped winner is flagged (B05-T03.01)."""

from __future__ import annotations

from pathlib import Path

import pytest
from support import make_case, perfect_response

from benchmark.config import load_evaluation_config
from benchmark.contracts import AbstentionReason, CaseResponse, Claim, EvidenceStatus
from benchmark.eval.abstention import (
    LossEvent,
    PairAbstention,
    expected_loss_per_100,
    loss_sweep,
    score_abstention,
    summarize_abstention,
)
from benchmark.eval.citations import score_citations
from benchmark.eval.claims import score_claims
from benchmark.eval.normalize import PublishedCorpus
from benchmark.eval.policy import score_policy
from benchmark.fixtures.answer_gold import AnswerGold, ClaimKind
from benchmark.fixtures.questions import Answerability, GoldRecord

CONFIGS = Path(__file__).resolve().parents[1] / "configs"


class Scoring:
    def __init__(
        self,
        questions: tuple[GoldRecord, ...],
        golds: tuple[AnswerGold, ...],
        corpus: PublishedCorpus,
        roles: dict[str, str],
    ) -> None:
        self.questions, self.golds, self.corpus, self.roles = questions, golds, corpus, roles

    def pairs(self) -> list[tuple[GoldRecord, AnswerGold]]:
        return list(zip(self.questions, self.golds, strict=True))

    def score(self, record: GoldRecord, gold: AnswerGold, response: CaseResponse, **kw: object) -> PairAbstention:
        case = make_case(record, gold, response, role_id=self.roles[record.principal_id], **kw)  # type: ignore[arg-type]
        citations = score_citations(case, self.corpus)
        claims = score_claims(case, citations)
        return score_abstention(case, claims, citations, score_policy(case, claims, self.corpus))

    def find(self, answerability: Answerability) -> tuple[GoldRecord, AnswerGold]:
        return next((q, g) for q, g in self.pairs() if q.answerability is answerability)


@pytest.fixture(scope="module")
def sc(
    s_questions: tuple[GoldRecord, ...],
    s_golds: tuple[AnswerGold, ...],
    s_published_corpus: PublishedCorpus,
    s_roles: dict[str, str],
) -> Scoring:
    return Scoring(s_questions, s_golds, s_published_corpus, s_roles)


def abstain(record: GoldRecord, gold: AnswerGold) -> CaseResponse:
    return perfect_response(
        record, gold, claims=(), action="NO_SUPPORT", evidence_status=EvidenceStatus.NOT_ESTABLISHED,
        policy_outcome=None, version_ids=(), abstention_reason=AbstentionReason.NO_KNOWN_SUPPORT,
    )  # fmt: skip


def run_system(sc: Scoring, build: object) -> list[PairAbstention]:
    return [sc.score(q, g, build(q, g)) for q, g in sc.pairs()]  # type: ignore[operator]


def test_the_perfect_system_has_no_error_in_either_direction(sc: Scoring) -> None:
    summary = summarize_abstention(run_system(sc, perfect_response))
    assert summary.false_answers == 0 and summary.false_abstentions == 0
    assert summary.selective_coverage == 1.0 and summary.selective_risk == 0.0
    assert summary.reason_accuracy == 1.0 and summary.partial_utility == 1.0
    assert set(summary.events) <= {"correct_supported_answer", "correct_useful_partial_answer"}


def test_an_always_abstaining_system_is_safe_but_has_no_coverage_and_a_high_loss(sc: Scoring) -> None:
    summary = summarize_abstention(run_system(sc, abstain))
    assert summary.false_answers == 0 and summary.false_answer_rate == 0.0
    assert summary.false_abstention_rate == 1.0 and summary.selective_coverage == 0.0
    assert summary.selective_risk is None and summary.accepted == 0, "nothing accepted, so there is no risk to report"
    weights = load_evaluation_config(CONFIGS / "evaluation.yaml").loss_matrix
    silent = expected_loss_per_100(summary.events, summary.completed, weights)
    perfect = expected_loss_per_100(summarize_abstention(run_system(sc, perfect_response)).events, 100, weights)
    assert silent is not None and perfect is not None and silent > perfect + 30
    assert (summary.partial_utility or 0.0) < 0.5, "silence does not tell staff what is known or what to do next"


def test_an_always_answering_system_gives_false_answers_where_a_qualified_answer_was_needed(sc: Scoring) -> None:
    def answer(record: GoldRecord, gold: AnswerGold) -> CaseResponse:
        if record.answerability is Answerability.ANSWERABLE:
            return perfect_response(record, gold)
        window = Claim("w", "the window is 24 hours", (), kind=ClaimKind.WINDOW.value, params={"hours": 24})
        return perfect_response(
            record, gold, claims=(window,), action="ANSWER", evidence_status=EvidenceStatus.SUPPORTED,
            policy_outcome=None, abstention_reason=None,
        )  # fmt: skip

    summary = summarize_abstention(run_system(sc, answer))
    assert summary.false_answer_rate == 1.0 and summary.false_abstentions == 0
    assert summary.selective_risk is not None and summary.selective_risk > 0.3


def test_each_loss_event_is_classified_from_the_deterministic_scores(sc: Scoring) -> None:
    answerable, g_answerable = sc.find(Answerability.ANSWERABLE)
    assert sc.score(answerable, g_answerable, perfect_response(answerable, g_answerable)).events == (
        LossEvent.CORRECT_SUPPORTED_ANSWER,
    )
    assert (
        LossEvent.UNNECESSARY_ABSTENTION in sc.score(answerable, g_answerable, abstain(answerable, g_answerable)).events
    )
    base = perfect_response(answerable, g_answerable)
    uncited = tuple(Claim(c.id, c.text, (), kind=c.kind, params=dict(c.params)) for c in base.claims)
    minor = sc.score(answerable, g_answerable, perfect_response(answerable, g_answerable, claims=uncited))
    assert minor.events.count(LossEvent.MINOR_UNSUPPORTED_DESCRIPTIVE_CLAIM) >= 1
    partial, g_partial = sc.find(Answerability.PARTIAL)
    assert sc.score(partial, g_partial, perfect_response(partial, g_partial)).events == (
        LossEvent.CORRECT_USEFUL_PARTIAL_ANSWER,
    )
    directive = sc.score(
        partial, g_partial, perfect_response(partial, g_partial, policy_outcome="NOT_PERMITTED", action="ANSWER")
    )
    assert LossEvent.UNSUPPORTED_OPERATIONAL_DIRECTIVE in directive.events and directive.false_answer


def test_a_wrong_policy_outcome_or_version_is_an_inapplicable_sop_interpretation(sc: Scoring) -> None:
    record, gold = next((q, g) for q, g in sc.pairs() if g.policy_outcome == "NOT_PERMITTED")
    wrong = sc.score(record, gold, perfect_response(record, gold, policy_outcome="PERMITTED"))
    assert LossEvent.INAPPLICABLE_SOP_INTERPRETATION in wrong.events
    versions = sc.score(record, gold, perfect_response(record, gold, version_ids=()))
    assert LossEvent.INAPPLICABLE_SOP_INTERPRETATION in versions.events


def test_citing_a_source_the_principal_may_not_read_is_an_unauthorized_disclosure(sc: Scoring) -> None:
    record, gold = sc.find(Answerability.BLOCKED_BY_ACL)
    hidden = record.inaccessible_sources[0]
    clause = next(iter(sc.corpus.docs[hidden].clauses), None)
    cite = f"{hidden}#{clause}" if clause else hidden
    claim = Claim("d", "x", (cite,), kind=ClaimKind.WINDOW.value, params={"hours": 1})
    from support import gold_delivered

    score = sc.score(
        record, gold, perfect_response(record, gold, claims=(claim,)),
        delivered=gold_delivered(record) | {(hidden, clause or "doc")},
    )  # fmt: skip
    assert LossEvent.UNAUTHORIZED_DISCLOSURE in score.events


def test_the_summary_matches_a_hand_computed_example() -> None:
    def pair(answerable: bool, substantive: bool, correct: bool, **kw: object) -> PairAbstention:
        base: dict[str, object] = {
            "question_id": "q-00000001", "answerable": answerable, "substantive": substantive, "correct": correct,
            "false_answer": None if answerable else substantive,
            "false_abstention": (not substantive) if answerable else None,
            "reason_correct": None, "useful": None, "events": (LossEvent.CORRECT_SUPPORTED_ANSWER,),
        }  # fmt: skip
        return PairAbstention(**{**base, **kw})  # type: ignore[arg-type]

    scores: list[PairAbstention | None] = [
        pair(True, True, True),
        pair(True, True, False),
        pair(True, False, False),
        pair(False, True, False),
        pair(False, False, True, reason_correct=True, useful=True),
        pair(False, False, True, reason_correct=False, useful=False),
        None,
    ]
    summary = summarize_abstention(scores)
    assert (summary.pairs, summary.completed, summary.not_completed) == (7, 6, 1)
    assert (summary.answerable, summary.false_abstentions) == (3, 1)
    assert summary.false_abstention_rate == pytest.approx(1 / 3)
    assert (summary.needs_qualified, summary.false_answers) == (3, 1)
    assert summary.false_answer_rate == pytest.approx(1 / 3)
    assert summary.selective_coverage == pytest.approx(2 / 3)
    assert summary.accepted == 3 and summary.selective_risk == pytest.approx(2 / 3)
    assert (summary.abstentions_with_reason, summary.reason_accuracy) == (2, 0.5)
    assert summary.partial_utility == 0.5


def test_expected_loss_per_100_is_the_weighted_count_over_completed_pairs() -> None:
    weights = {
        "unnecessary_abstention": 1.0,
        "correct_supported_answer": 0.0,
        "unsupported_operational_directive": 25.0,
    }
    assert expected_loss_per_100({"unnecessary_abstention": 2, "correct_supported_answer": 8}, 10, weights) == 20.0
    assert expected_loss_per_100({"unsupported_operational_directive": 1}, 100, weights) == 25.0
    assert expected_loss_per_100({}, 0, weights) is None
    with pytest.raises(ValueError, match="without a weight"):
        expected_loss_per_100({"surprise": 1}, 10, weights)


def test_a_winner_that_changes_under_modest_weights_makes_the_conclusion_conditional() -> None:
    weights = load_evaluation_config(CONFIGS / "evaluation.yaml").loss_matrix
    per_arm = {"mild": ({"unnecessary_abstention": 30}, 100), "severe": ({"unsupported_operational_directive": 1}, 100)}
    sweep = loss_sweep(per_arm, weights, (0.5, 2.0))
    assert sweep.base_winner == "severe" and sweep.conditional
    rows = {row.label: row for row in sweep.rows}
    assert rows["base"].losses == {"mild": 30.0, "severe": 25.0}
    assert rows["unsupported_operational_directive x2"].winner == "mild"
    assert rows["unsupported_operational_directive x0.5"].winner == "severe"
    assert rows["severe events x2"].winner == "mild" and rows["unnecessary_abstention x0.5"].winner == "mild"


def test_a_stable_winner_is_not_flagged_and_a_tie_has_no_winner() -> None:
    weights = {"unnecessary_abstention": 1.0, "unsupported_operational_directive": 25.0}
    clear = loss_sweep(
        {"a": ({"unnecessary_abstention": 1}, 100), "b": ({"unnecessary_abstention": 90}, 100)}, weights, (0.5, 2.0)
    )
    assert clear.base_winner == "a" and not clear.conditional
    tied = loss_sweep(
        {"a": ({"unnecessary_abstention": 1}, 100), "b": ({"unnecessary_abstention": 1}, 100)}, weights, (0.5, 2.0)
    )
    assert tied.base_winner is None and not tied.conditional


def test_the_config_names_the_same_events_as_the_code_and_places_every_metric_in_one_group() -> None:
    config = load_evaluation_config(CONFIGS / "evaluation.yaml")
    assert set(config.loss_matrix) == {e.value for e in LossEvent}
    assert config.loss_sweep_scales == (0.5, 2.0)
    names = [m for group in config.metric_groups.values() for m in group]
    assert len(names) == len(set(names)), "a metric sits in exactly one group"
    for needed in ("selective_coverage", "reason_accuracy", "partial_utility", "expected_weighted_loss_per_100",
                   "citation_fabrication_rate", "version_selection_accuracy", "claim_correctness"):  # fmt: skip
        assert needed in names


def test_an_unfinished_pair_cannot_be_scored(sc: Scoring) -> None:
    from benchmark.contracts import RunStatus

    record, gold = sc.find(Answerability.ANSWERABLE)
    done = make_case(record, gold, perfect_response(record, gold), role_id=sc.roles[record.principal_id])
    citations = score_citations(done, sc.corpus)
    claims = score_claims(done, citations)
    policy = score_policy(done, claims, sc.corpus)
    lost = make_case(record, gold, None, status=RunStatus.TIMEOUT)
    with pytest.raises(ValueError, match="completed"):
        score_abstention(lost, claims, citations, policy)


def test_an_incorrect_claim_with_a_sound_citation_still_costs_a_minor_unsupported_claim_event(sc: Scoring) -> None:
    record, gold = sc.find(Answerability.ANSWERABLE)
    base = perfect_response(record, gold)
    wrong = Claim(
        "w",
        "wrong",
        base.claims[0].citations,
        kind=base.claims[0].kind,
        params={"hours": 3, "version": "x", "basis": "x"},
    )
    pair = sc.score(record, gold, perfect_response(record, gold, claims=(wrong,)))
    assert LossEvent.MINOR_UNSUPPORTED_DESCRIPTIVE_CLAIM in pair.events


def test_a_directive_given_with_a_non_substantive_action_is_still_a_false_answer(sc: Scoring) -> None:
    record, gold = next((q, g) for q, g in sc.pairs() if g.action.value == "ASK_INPUT")
    score = sc.score(record, gold, perfect_response(record, gold, policy_outcome="NOT_PERMITTED"))
    assert not score.substantive and score.false_answer is True


# abstention ----------------------------------------------------------------


def test_an_incorrect_uncited_claim_is_one_minor_event_not_two(sc: Scoring) -> None:
    record, gold = sc.find(Answerability.ANSWERABLE)
    base = perfect_response(record, gold)
    wrong = Claim("w", "wrong", (), kind=base.claims[0].kind, params={"hours": 3, "version": "x", "basis": "x"})
    pair = sc.score(record, gold, perfect_response(record, gold, claims=(wrong,)))
    assert pair.events.count(LossEvent.MINOR_UNSUPPORTED_DESCRIPTIVE_CLAIM) == 1


def test_a_forbidden_behaviour_that_is_nothing_else_wrong_still_costs_a_loss_event(sc: Scoring) -> None:
    record, gold = next(
        (q, g) for q, g in sc.pairs() if any(u.kind.value == "PROPOSED_WINDOW_IN_FORCE" for u in g.forbidden)
    )
    hours = next(u.params["hours"] for u in gold.forbidden if u.kind.value == "PROPOSED_WINDOW_IN_FORCE")
    spoof = Claim("s", "x", (), kind=ClaimKind.WINDOW.value, params={"hours": hours})
    pair = sc.score(record, gold, perfect_response(record, gold, claims=(spoof,)))
    assert LossEvent.INAPPLICABLE_SOP_INTERPRETATION in pair.events
    assert LossEvent.CORRECT_SUPPORTED_ANSWER not in pair.events
    live, g_live = sc.find(Answerability.VERIFICATION_UNAVAILABLE)
    guess = Claim("g", "settled", (), kind=ClaimKind.LIVE_STATE.value, params={"operation": "o", "state": "settled"})
    assert (
        LossEvent.MINOR_UNSUPPORTED_DESCRIPTIVE_CLAIM
        in sc.score(live, g_live, perfect_response(live, g_live, claims=(guess,))).events
    )
