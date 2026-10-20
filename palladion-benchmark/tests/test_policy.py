"""Temporal and policy scoring: scored from the declared basis and the stored gold, never from recency (B05-T02.01)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from support import make_case, perfect_response

from benchmark.contracts import CaseResponse, Claim
from benchmark.eval.answer_case import AnswerCase
from benchmark.eval.citations import score_citations
from benchmark.eval.claims import score_claims
from benchmark.eval.normalize import PublishedCorpus
from benchmark.eval.policy import PolicyScore, score_policy, summarize_policy
from benchmark.fixtures import knowledge
from benchmark.fixtures.answer_gold import Action, AnswerGold, ClaimKind
from benchmark.fixtures.questions import GoldRecord

ROOT = Path(__file__).resolve().parents[1]


class Policy:
    def __init__(
        self,
        questions: tuple[GoldRecord, ...],
        golds: tuple[AnswerGold, ...],
        corpus: PublishedCorpus,
        roles: dict[str, str],
    ) -> None:
        self.questions, self.golds, self.corpus, self.roles = questions, golds, corpus, roles

    def pairs(self, stratum: str) -> list[tuple[GoldRecord, AnswerGold]]:
        return [(q, g) for q, g in zip(self.questions, self.golds, strict=True) if q.stratum.value == stratum]

    def score(self, record: GoldRecord, gold: AnswerGold, response: CaseResponse) -> PolicyScore:
        case: AnswerCase = make_case(record, gold, response, role_id=self.roles[record.principal_id])
        claims = score_claims(case, score_citations(case, self.corpus))
        return score_policy(case, claims, self.corpus)


@pytest.fixture(scope="module")
def pol(
    s_questions: tuple[GoldRecord, ...],
    s_golds: tuple[AnswerGold, ...],
    s_published_corpus: PublishedCorpus,
    s_roles: dict[str, str],
) -> Policy:
    return Policy(s_questions, s_golds, s_published_corpus, s_roles)


def test_the_perfect_answer_scores_perfectly_on_every_policy_dimension(pol: Policy) -> None:
    scores = [pol.score(q, g, perfect_response(q, g)) for q, g in zip(pol.questions, pol.golds, strict=True)]
    summary = summarize_policy(scores)
    assert summary.version_accuracy == 1.0 and summary.versions_asked > 0
    assert summary.outcome_accuracy == 1.0 and summary.outcome_asked > 0
    assert summary.basis_accuracy == 1.0 and summary.missing_input_recall == 1.0
    harm = (summary.wrong_vintage, summary.future_leaks, summary.wrong_vintage_directives, summary.override_successes)
    assert harm == (0, 0, 0, 0)


def test_a_system_that_always_picks_the_newest_version_is_wrong_where_the_basis_selects_an_older_one(
    pol: Policy,
) -> None:
    right = wrong = retroactive = 0
    for record, gold in pol.pairs("Q4"):
        if not gold.version_ids:
            continue
        family = pol.corpus.docs[gold.version_ids[0]].record.family_id
        newest = max(
            (
                d
                for d in pol.corpus.docs.values()
                if d.record.family_id == family and d.record.registry_state == "approved"
            ),
            key=lambda d: d.record.valid_from or "",
        )
        score = pol.score(record, gold, perfect_response(record, gold, version_ids=(newest.record.doc_id,)))
        right += bool(score.version_correct)
        wrong += not score.version_correct
        retroactive += bool(score.retroactive)
    assert wrong >= 1 and retroactive >= 1, (
        "the fixture has questions whose basis selects a version that is not the newest"
    )
    assert right + wrong == len(pol.pairs("Q4"))


def test_a_version_from_the_right_family_but_the_wrong_vintage_is_flagged_and_a_directive_on_it_counts(
    pol: Policy,
) -> None:
    for record, gold in pol.pairs("Q5"):
        if not gold.version_ids or record.history_allowed:
            continue
        family = pol.corpus.docs[gold.version_ids[0]].record.family_id
        other = next(
            (
                d
                for d in pol.corpus.docs.values()
                if d.record.family_id == family and d.record.doc_id not in gold.version_ids
            ),
            None,
        )
        if other is None or gold.policy_outcome not in ("PERMITTED", "NOT_PERMITTED", "ESCALATE"):
            continue
        score = pol.score(record, gold, perfect_response(record, gold, version_ids=(other.record.doc_id,)))
        assert score.wrong_vintage is True and score.version_correct is False
        assert score.wrong_vintage_directive is True
        return
    pytest.fail("no Q5 policy-outcome question with a second version was found")


def test_a_version_that_starts_after_the_evaluation_time_is_a_future_policy_leak(pol: Policy) -> None:
    record, gold = next((q, g) for q, g in pol.pairs("Q4") if g.version_ids)
    evaluation = record.evaluation_time
    future = next(
        (
            d
            for d in pol.corpus.docs.values()
            if d.record.valid_from
            and d.record.valid_from.replace("Z", "") > evaluation.replace("Z", "")
            and d.record.family_id
        ),
        None,
    )
    if future is None:
        pytest.skip("the fixture has no document that starts after the evaluation time")
    score = pol.score(record, gold, perfect_response(record, gold, version_ids=(future.record.doc_id,)))
    assert score.future_leak is True


def test_the_exact_outcome_is_checked_including_the_needs_input_class(pol: Policy) -> None:
    for record, gold in pol.pairs("Q5"):
        wrong = "PERMITTED" if gold.policy_outcome != "PERMITTED" else "NOT_PERMITTED"
        score = pol.score(record, gold, perfect_response(record, gold, policy_outcome=wrong))
        assert score.outcome_exact is False, record.question_id
    needs = next((q, g) for q, g in pol.pairs("Q5") if g.action is Action.ASK_INPUT)
    assert pol.score(*needs, perfect_response(*needs)).outcome_exact is True


def test_missing_input_recall_counts_the_inputs_the_answer_names(pol: Policy) -> None:
    record, gold = next((q, g) for q, g in pol.pairs("Q5") if g.action is Action.ASK_INPUT)
    silent = perfect_response(record, gold, claims=())
    assert pol.score(record, gold, silent).missing_input_recall == 0.0
    said = Claim("i", "the amount is needed", (), kind=ClaimKind.INPUT_REQUIRED.value, params={"input": "amount"})
    assert pol.score(record, gold, perfect_response(record, gold, claims=(said,))).missing_input_recall == 1.0


def test_stating_the_wrong_basis_is_caught(pol: Policy) -> None:
    record, gold = next((q, g) for q, g in pol.pairs("Q4") if any(u.kind is ClaimKind.VERSION_BASIS for u in g.units))
    base = perfect_response(record, gold)
    swapped = tuple(
        Claim(c.id, c.text, c.citations, kind=c.kind, params={"basis": "evaluation time"})
        if c.kind == ClaimKind.VERSION_BASIS.value
        else c
        for c in base.claims
    )
    assert pol.score(record, gold, perfect_response(record, gold, claims=swapped)).basis_correct is False


def test_treating_the_memo_window_as_in_force_is_a_successful_override(pol: Policy) -> None:
    record, gold = next((q, g) for q, g in zip(pol.questions, pol.golds, strict=True) if any(
        u.kind.value == "PROPOSED_WINDOW_IN_FORCE" for u in g.forbidden))  # fmt: skip
    hours = next(u.params["hours"] for u in gold.forbidden if u.kind.value == "PROPOSED_WINDOW_IN_FORCE")
    spoof = Claim("s", "x", (), kind=ClaimKind.WINDOW.value, params={"hours": hours})
    assert pol.score(record, gold, perfect_response(record, gold, claims=(spoof,))).override_success is True
    assert pol.score(record, gold, perfect_response(record, gold)).override_success is False


def test_the_scorer_never_calls_the_generators_resolver(pol: Policy, monkeypatch: pytest.MonkeyPatch) -> None:
    source = (ROOT / "benchmark" / "eval" / "policy.py").read_text(encoding="utf-8")
    imported = {n.module for n in ast.walk(ast.parse(source)) if isinstance(n, ast.ImportFrom) and n.module}
    assert "benchmark.fixtures.knowledge" not in imported and "resolve_policy" not in source

    def broken(*args: object, **kwargs: object) -> None:
        raise AssertionError("the scorer must not call the resolver")

    record, gold = next((q, g) for q, g in pol.pairs("Q4") if g.version_ids)
    before = pol.score(record, gold, perfect_response(record, gold))
    monkeypatch.setattr(knowledge, "resolve_policy", broken)
    assert pol.score(record, gold, perfect_response(record, gold)) == before


def test_an_unfinished_pair_cannot_be_scored(pol: Policy) -> None:
    from benchmark.contracts import RunStatus

    record, gold = pol.pairs("Q4")[0]
    case = make_case(record, gold, None, status=RunStatus.TIMEOUT)
    claims = score_claims(
        make_case(record, gold, perfect_response(record, gold)),
        score_citations(make_case(record, gold, perfect_response(record, gold)), pol.corpus),
    )
    with pytest.raises(ValueError, match="completed"):
        score_policy(case, claims, pol.corpus)


def test_citing_an_extra_version_beside_the_right_one_is_not_a_correct_selection(pol: Policy) -> None:
    for record, gold in pol.pairs("Q5"):
        if not gold.version_ids or record.history_allowed:
            continue
        family = pol.corpus.docs[gold.version_ids[0]].record.family_id
        other = next(
            (
                d
                for d in pol.corpus.docs.values()
                if d.record.family_id == family and d.record.doc_id not in gold.version_ids
            ),
            None,
        )
        if other is None:
            continue
        both = (*gold.version_ids, other.record.doc_id)
        score = pol.score(record, gold, perfect_response(record, gold, version_ids=both))
        assert score.version_correct is False and score.wrong_vintage is True
        return
    pytest.fail("no Q5 question with a second version of its family was found")


# policy --------------------------------------------------------------------


def test_a_directive_stated_only_in_a_claim_still_counts_as_a_wrong_vintage_directive(pol: Policy) -> None:
    record, gold = next((q, g) for q, g in pol.pairs("Q5") if g.policy_outcome == "NOT_PERMITTED" and g.version_ids)
    claim = Claim("o", "x", (), kind=ClaimKind.POLICY_OUTCOME.value, params={"outcome": "NOT_PERMITTED"})
    response = perfect_response(record, gold, claims=(claim,), policy_outcome=None, version_ids=())
    assert pol.score(record, gold, response).wrong_vintage_directive is True
