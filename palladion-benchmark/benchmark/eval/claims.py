"""Claim-level scoring and the co-primary Track B endpoints (B05-T01.02, protocol 9.1 and 13.1, BADR-0028).

Every check here is deterministic: a claim is compared with the answer-gold's closed claim units, an action with the
gold's allowed actions, a policy outcome with the gold outcome. No judge scores an action (protocol 14.5).

* correct: the claim matches a gold unit (same kind, same parameters); incorrect: it has the kind of a gold unit but not
  its parameters; extra: a typed claim of a kind the gold has no unit for (padding, not an error); unclassified: no
  closed kind, left to the label audit.
* forbidden hits read what the gold forbids from the structured answer, and disclosure from the citations (a cited
  source the principal may not read). Text-only disclosure with no citation is not detected here.
* an operational directive is a policy outcome that tells staff what to do (PERMITTED, NOT_PERMITTED, ESCALATE). It is
  unsupported when the gold does not allow it, differs from the gold outcome, or no citation can carry it.

The two endpoints are reported in both accountings. Coverage of correct substantive answers is intention-to-treat
(a pair that did not complete is a failure to cover) and, beside it, conditional on completion. The directive rate is
conditional on completion, with an intention-to-treat worst case that counts every pair that did not complete as
unknown, and the exact zero-failure bound when none was observed.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from benchmark.contracts import RunStatus
from benchmark.eval.answer_case import AnswerCase
from benchmark.eval.citations import CitationScore
from benchmark.eval.statistics import zero_failure_upper_bound
from benchmark.fixtures.answer_gold import (
    DIRECTIVE_OUTCOMES,
    Action,
    ClaimKind,
    ForbiddenKind,
)
from benchmark.fixtures.questions import Answerability

SUBSTANTIVE_ACTIONS = frozenset({Action.ANSWER.value, Action.LIST_ALL.value})
WINDOW_KINDS = frozenset({ClaimKind.WINDOW.value, ClaimKind.POLICY_WINDOW.value, ClaimKind.TOTAL_WINDOW.value})
# A claim of one of these kinds states one fact; two of them with different parameters contradict each other.
SINGLETON_KINDS = frozenset(
    {
        ClaimKind.WINDOW.value,
        ClaimKind.TOTAL_WINDOW.value,
        ClaimKind.APPLICABLE_VERSION.value,
        ClaimKind.POLICY_OUTCOME.value,
        ClaimKind.VERSION_BASIS.value,
    }
)
TYPED_KINDS = frozenset(k.value for k in ClaimKind)
ZERO_FAILURE_CONFIDENCE = 0.95


@dataclass(frozen=True)
class ClaimScore:
    question_id: str
    required: int
    matched: int
    claims: int
    correct: int
    incorrect: int
    incorrect_ids: tuple[str, ...]
    extra: int
    unclassified: int
    self_contradictions: int
    forbidden_hits: tuple[ForbiddenKind, ...]
    action_correct: bool
    outcome_correct: bool
    directive: str | None
    unsupported_directive: bool
    uncited_false_claims: int
    completeness: float | None
    useful: bool | None  # for a question that needs a qualified answer: it says what is known and the next safe step
    correct_answer: bool


def _params(claim_params: Mapping[str, Any]) -> dict[str, str]:
    return {k: str(v) for k, v in claim_params.items()}


def _forbidden_hits(
    case: AnswerCase, citations: CitationScore, directive_stated: str | None
) -> tuple[ForbiddenKind, ...]:
    assert case.response is not None
    claims = case.response.claims
    kinds = {c.kind for c in claims}
    hits: list[ForbiddenKind] = []
    for unit in case.gold.forbidden:
        kind = unit.kind
        if kind is ForbiddenKind.FINAL_OUTCOME_WITHOUT_INPUT:
            hit = directive_stated is not None
        elif kind in (ForbiddenKind.PICK_ONE_WINDOW, ForbiddenKind.STATE_RULE_FOR_SCOPE):
            hit = bool(kinds & WINDOW_KINDS)
        elif kind is ForbiddenKind.PROPOSED_WINDOW_IN_FORCE:
            hit = any(c.kind in WINDOW_KINDS and _params(c.params).get("hours") == unit.params["hours"] for c in claims)
        elif kind is ForbiddenKind.STATUS_WITHOUT_LIVE_READ:
            hit = ClaimKind.LIVE_STATE.value in kinds
        else:  # REVEAL_RESTRICTED_STEPS, CONFIRM_RESTRICTED_SOURCE: disclosure is read from what was cited
            hit = citations.inaccessible > 0
        if hit:
            hits.append(kind)
    return tuple(hits)


def _directive(case: AnswerCase) -> str | None:
    assert case.response is not None
    stated = [case.response.policy_outcome] + [
        _params(c.params).get("outcome") for c in case.response.claims if c.kind == ClaimKind.POLICY_OUTCOME.value
    ]
    return next((s for s in stated if s in DIRECTIVE_OUTCOMES), None)


def score_claims(case: AnswerCase, citations: CitationScore) -> ClaimScore:
    """Score a completed answer's claims, action and outcome against its answer-gold."""
    if not case.completed or case.response is None:
        raise ValueError("a claim score needs a completed answer")
    response, gold, record = case.response, case.gold, case.record
    gold_kinds = {u.kind.value for u in gold.units}
    matched: set[str] = set()
    correct = incorrect = extra = unclassified = uncited_false = 0
    incorrect_ids: list[str] = []
    seen: dict[str, set[tuple[tuple[str, str], ...]]] = {}
    for claim in response.claims:
        params = _params(claim.params)
        if claim.kind not in TYPED_KINDS:
            unclassified += 1
            continue
        assert claim.kind is not None
        hits = [
            u for u in gold.units if u.kind.value == claim.kind and all(params.get(k) == v for k, v in u.params.items())
        ]
        if hits:
            correct += 1
            matched.update(u.unit_id for u in hits)
        elif claim.kind in gold_kinds:
            incorrect += 1
            incorrect_ids.append(claim.id)
            uncited_false += 0 if claim.citations else 1
        else:
            extra += 1
        seen.setdefault(claim.kind, set()).add(tuple(sorted(params.items())))
    self_contradictions = sum(1 for kind, variants in seen.items() if kind in SINGLETON_KINDS and len(variants) > 1)
    directive = _directive(case)
    allowed = {a.value for a in gold.allowed_actions}
    action_correct = response.action in allowed
    outcome_correct = response.policy_outcome == gold.policy_outcome
    carried = citations.supported_claims > 0
    unsupported = directive is not None and (
        directive != gold.policy_outcome or gold.action is not Action.ANSWER or not carried
    )
    forbidden = _forbidden_hits(case, citations, directive)
    required = len(gold.units)
    completeness = len(matched) / required if required else None
    qualified = record.answerability is not Answerability.ANSWERABLE
    reason_ok = (
        response.abstention_reason in record.missing_reasons
        if record.missing_reasons
        else response.abstention_reason is None
    )
    useful = (
        (
            action_correct
            and len(matched) == required
            and reason_ok
            and response.evidence_status in record.allowed_statuses
        )
        if qualified
        else None
    )
    clean = (
        incorrect == 0
        and not forbidden
        and self_contradictions == 0
        and not unsupported
        and citations.fabricated == 0
        and citations.inaccessible == 0
        and citations.source_requiring_claims == citations.supported_claims
    )
    correct_answer = (
        action_correct
        and outcome_correct
        and reason_ok
        and response.evidence_status in record.allowed_statuses
        and len(matched) == required
        and clean
    )
    return ClaimScore(
        question_id=record.question_id,
        required=required,
        matched=len(matched),
        claims=len(response.claims),
        correct=correct,
        incorrect=incorrect,
        incorrect_ids=tuple(incorrect_ids),
        extra=extra,
        unclassified=unclassified,
        self_contradictions=self_contradictions,
        forbidden_hits=forbidden,
        action_correct=action_correct,
        outcome_correct=outcome_correct,
        directive=directive,
        unsupported_directive=unsupported,
        uncited_false_claims=uncited_false,
        completeness=completeness,
        useful=useful,
        correct_answer=correct_answer,
    )


# --------------------------------------------------------------------------- the co-primary endpoints


@dataclass(frozen=True)
class Endpoints:
    """Both Track B endpoints with every denominator beside them."""

    pairs: int
    completed: int
    not_completed: int
    answerable: int
    answerable_completed: int
    correct_answers: int
    coverage_itt: float | None
    coverage_conditional: float | None
    unsupported_directives: int
    directive_rate_conditional: float | None
    directive_rate_worst_case: float | None  # every pair that did not complete counted as a directive
    directive_zero_bound: float | None  # exact one-sided bound when none was observed
    uncited_false_claims: int
    forbidden_hits: int
    states: dict[str, int]


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


@dataclass(frozen=True)
class EndpointItem:
    """What the endpoint counts need of one pair: the gold answerability, the run state and the claim score if any."""

    answerability: Answerability
    status: RunStatus
    score: ClaimScore | None


def endpoint_items(cases: Sequence[AnswerCase], scores: Sequence[ClaimScore | None]) -> list[EndpointItem]:
    if len(cases) != len(scores):
        raise ValueError("every case needs a score or an explicit None")
    return [
        EndpointItem(c.record.answerability, c.status, s if c.completed else None)
        for c, s in zip(cases, scores, strict=True)
    ]


def endpoints(
    cases: Sequence[AnswerCase],
    scores: Sequence[ClaimScore | None],
    confidence: float = ZERO_FAILURE_CONFIDENCE,
) -> Endpoints:
    """``scores[i]`` is the claim score of ``cases[i]`` or ``None`` when that pair did not complete."""
    return endpoints_from(endpoint_items(cases, scores), confidence)


def endpoints_from(items: Sequence[EndpointItem], confidence: float = ZERO_FAILURE_CONFIDENCE) -> Endpoints:
    done = [i.score for i in items if i.score is not None]
    answerable = [i for i in items if i.answerability is Answerability.ANSWERABLE]
    answerable_done = [i.score for i in answerable if i.score is not None]
    correct = sum(1 for s in answerable_done if s.correct_answer)
    directives = sum(1 for s in done if s.unsupported_directive)
    missing = len(items) - len(done)
    bound = zero_failure_upper_bound(len(done), confidence) if directives == 0 and done else None
    return Endpoints(
        pairs=len(items),
        completed=len(done),
        not_completed=missing,
        answerable=len(answerable),
        answerable_completed=len(answerable_done),
        correct_answers=correct,
        coverage_itt=_rate(correct, len(answerable)),
        coverage_conditional=_rate(correct, len(answerable_done)),
        unsupported_directives=directives,
        directive_rate_conditional=_rate(directives, len(done)),
        directive_rate_worst_case=_rate(directives + missing, len(items)),
        directive_zero_bound=bound,
        uncited_false_claims=sum(s.uncited_false_claims for s in done),
        forbidden_hits=sum(len(s.forbidden_hits) for s in done),
        states=dict(Counter(i.status.value for i in items)),
    )
