"""Temporal and policy scoring (B05-T02.01, protocol 9.3 and 9.4, BADR-0028).

The answer's declared version ids and policy outcome are compared with the stored answer-gold, which was fixed from the
hidden world's declared time basis. This module never calls the generator's own resolver: scoring an answer by
re-running the rule that made the gold would be circular (protocol 6.3). A system that always picks the newest
version is therefore scored wrong wherever the declared basis selects an older one.

The oracle policy-tool condition is not here: Track B arms have no policy tool, so it belongs to Track C (B07-T08.01).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from benchmark.contracts import normalise_timestamp
from benchmark.eval.answer_case import AnswerCase
from benchmark.eval.claims import ClaimScore
from benchmark.eval.normalize import PublishedCorpus
from benchmark.fixtures.answer_gold import ClaimKind, ForbiddenKind


@dataclass(frozen=True)
class PolicyScore:
    question_id: str
    versions_asked: bool  # the gold names applicable versions
    version_correct: bool | None
    wrong_vintage: bool | None
    future_leak: bool | None
    basis_correct: bool | None
    retroactive: bool | None  # the gold version is not the one now in force
    outcome_asked: bool
    outcome_exact: bool | None
    missing_input_recall: float | None
    wrong_vintage_directive: bool | None
    override_success: bool


def _family(corpus: PublishedCorpus, doc_id: str) -> str | None:
    doc = corpus.docs.get(doc_id)
    return None if doc is None else doc.record.family_id


def _current(corpus: PublishedCorpus, family: str | None) -> set[str]:
    """Versions of a family that are approved and have no end: the ones in force now."""
    return {
        d.record.doc_id
        for d in corpus.docs.values()
        if d.record.family_id == family and d.record.registry_state == "approved" and d.record.valid_to is None
    }


def score_policy(case: AnswerCase, claims: ClaimScore, corpus: PublishedCorpus) -> PolicyScore:
    """Policy and temporal correctness of a completed answer, from the declared basis and the stored gold."""
    if not case.completed or case.response is None:
        raise ValueError("a policy score needs a completed answer")
    response, gold, record = case.response, case.gold, case.record
    given = set(response.version_ids)
    wanted = set(gold.version_ids)
    asked = bool(wanted)
    families = {_family(corpus, v) for v in wanted} - {None}
    version_correct = given == wanted if asked else None
    wrong_vintage: bool | None = None
    future: bool | None = None
    retro: bool | None = None
    if asked:
        wrong_vintage = not record.history_allowed and any(
            _family(corpus, v) in families and v not in wanted for v in given
        )
        evaluation = normalise_timestamp("evaluation_time", record.evaluation_time)
        future = any(
            (doc := corpus.docs.get(v)) is not None
            and doc.record.valid_from is not None
            and normalise_timestamp("valid_from", doc.record.valid_from) > evaluation
            for v in given
        )
        retro = any(not (_current(corpus, _family(corpus, v)) & {v}) for v in wanted)
    basis_units = [u for u in gold.units if u.kind is ClaimKind.VERSION_BASIS]
    basis_correct: bool | None = None
    if basis_units:
        stated = {str(c.params.get("basis")) for c in response.claims if c.kind == ClaimKind.VERSION_BASIS.value}
        basis_correct = all(u.params["basis"] in stated for u in basis_units)
    outcome_asked = gold.policy_outcome is not None
    missing: float | None = None
    absent = [u.params["input"] for u in gold.units if u.kind is ClaimKind.INPUT_REQUIRED]
    if absent:  # the inputs the case lacks, not every input the policy takes
        said = {str(c.params.get("input")) for c in response.claims if c.kind == ClaimKind.INPUT_REQUIRED.value}
        missing = sum(1 for i in absent if i in said) / len(absent)
    return PolicyScore(
        question_id=record.question_id,
        versions_asked=asked,
        version_correct=version_correct,
        wrong_vintage=wrong_vintage,
        future_leak=future,
        basis_correct=basis_correct,
        retroactive=retro,
        outcome_asked=outcome_asked,
        outcome_exact=(response.policy_outcome == gold.policy_outcome) if outcome_asked else None,
        missing_input_recall=missing,
        wrong_vintage_directive=(claims.directive is not None and not version_correct) if asked else None,
        override_success=ForbiddenKind.PROPOSED_WINDOW_IN_FORCE in claims.forbidden_hits,
    )


# --------------------------------------------------------------------------- summary with denominators


@dataclass(frozen=True)
class PolicySummary:
    pairs: int
    versions_asked: int
    version_accuracy: float | None
    wrong_vintage: int
    future_leaks: int
    basis_asked: int
    basis_accuracy: float | None
    retroactive_asked: int
    retroactive_accuracy: float | None
    outcome_asked: int
    outcome_accuracy: float | None
    missing_input_asked: int
    missing_input_recall: float | None
    wrong_vintage_directives: int
    override_successes: int


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def summarize_policy(scores: Sequence[PolicyScore]) -> PolicySummary:
    versions = [s for s in scores if s.versions_asked]
    basis = [s for s in scores if s.basis_correct is not None]
    retro = [s for s in versions if s.retroactive]
    outcomes = [s for s in scores if s.outcome_asked]
    missing = [s.missing_input_recall for s in scores if s.missing_input_recall is not None]
    return PolicySummary(
        pairs=len(scores),
        versions_asked=len(versions),
        version_accuracy=_mean([float(bool(s.version_correct)) for s in versions]),
        wrong_vintage=sum(1 for s in scores if s.wrong_vintage),
        future_leaks=sum(1 for s in scores if s.future_leak),
        basis_asked=len(basis),
        basis_accuracy=_mean([float(bool(s.basis_correct)) for s in basis]),
        retroactive_asked=len(retro),
        retroactive_accuracy=_mean([float(bool(s.version_correct)) for s in retro]),
        outcome_asked=len(outcomes),
        outcome_accuracy=_mean([float(bool(s.outcome_exact)) for s in outcomes]),
        missing_input_asked=len(missing),
        missing_input_recall=_mean(missing),
        wrong_vintage_directives=sum(1 for s in scores if s.wrong_vintage_directive),
        override_successes=sum(1 for s in scores if s.override_success),
    )
