"""Pooling the worlds of a sealed run and the comparisons registered before it (B08-T03.01, B08-T04.01, BADR-0047).

The sealed Track A run asks the same questions' kind in several independent worlds. Pooling puts their scored pairs in
one table so that one interval covers all of them; a document family or a question id repeats from world to world
(``POL-002`` exists in every world), so both are prefixed with the world's name and nothing is merged across worlds.

The registered comparisons are fixed before the run: one primary pairing, the secondary pairings, the metric and the
smallest difference that counts. A claim is made only when the lower bound of the paired interval clears that
difference; the exact test is reported beside it as a description (questions of one family are not independent, so the
clustered interval, not the exact test, decides).
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum

from benchmark.analysis.tables import Effect, itt_value, paired_effect
from benchmark.config import StatisticsSettings
from benchmark.eval.score_run import PairScore, RunScore
from benchmark.eval.statistics import StatisticsError, holm


class PoolError(StatisticsError):
    """Worlds cannot be pooled, or a registration cannot be applied to the pooled run."""


def pool_runs(runs: Mapping[str, RunScore]) -> RunScore:
    """One scored run from several worlds' runs: same K and arms in each, ids and families prefixed by the world."""
    if not runs:
        raise PoolError("there is no world to pool")
    first = next(iter(runs.values()))
    for world, run in runs.items():
        if run.k != first.k:
            raise PoolError(f"{world} was scored at K={run.k}, the others at K={first.k}")
        if run.arms != first.arms:
            raise PoolError(f"{world} has arms {run.arms}, the others {first.arms}")
    pairs: list[PairScore] = []
    withdrawn: dict[str, str] = {}
    for world, run in sorted(runs.items()):
        pairs += [
            replace(p, question_id=f"{world}:{p.question_id}", scenario_family=f"{world}:{p.scenario_family}")
            for p in run.pairs
        ]
        withdrawn |= {f"{world}:{q}": reason for q, reason in run.withdrawn.items()}
    digest = hashlib.sha256("\n".join(f"{w}:{r.gold_sha256}" for w, r in sorted(runs.items())).encode()).hexdigest()
    ledger = tuple(
        replace(record, question_id=f"{world}:{record.question_id}")
        for world, run in sorted(runs.items())
        for record in run.ledger_records
    )
    return RunScore(f"pooled:{','.join(sorted(runs))}", first.k, digest, tuple(pairs), ledger, withdrawn)


class Claim(StrEnum):
    CONFIRMED = "CONFIRMED"  # the lower bound clears the registered minimum effect
    BELOW_MINIMUM = "BELOW_MINIMUM"  # the lower bound is above zero but not above the minimum effect
    INCONCLUSIVE = "INCONCLUSIVE"  # the interval holds zero, or there are too few clusters to give one
    ADVERSE = "ADVERSE"  # the upper bound is below zero


@dataclass(frozen=True)
class Registration:
    """What was fixed before the sealed run; the registration file's text is hashed into the seal."""

    primary_arm: str
    reference_arm: str
    secondary_references: tuple[str, ...]
    metric: str
    minimum_effect: float

    def __post_init__(self) -> None:
        arms = (self.reference_arm, *self.secondary_references)
        if self.primary_arm in arms or len(set(arms)) != len(arms) or self.minimum_effect < 0:
            raise PoolError(
                "a registration pairs one arm with distinct other arms and a minimum effect of zero or more"
            )


@dataclass(frozen=True)
class Registered:
    registration: Registration
    primary: Effect
    claim: Claim
    secondaries: tuple[Effect, ...]  # the primary arm against each secondary reference, Holm-adjusted among them


def decide(effect: Effect, minimum_effect: float) -> Claim:
    interval = effect.difference
    if interval.low is None or interval.high is None:
        return Claim.INCONCLUSIVE
    if interval.low > max(0.0, minimum_effect):
        return Claim.CONFIRMED
    if interval.low > 0.0:
        return Claim.BELOW_MINIMUM
    return Claim.ADVERSE if interval.high < 0.0 else Claim.INCONCLUSIVE


def _values(pairs: Sequence[PairScore], metric: str) -> dict[str, float]:
    return {p.question_id: v for p in pairs if (v := itt_value(p, metric)) is not None}


def registered_comparisons(score: RunScore, registration: Registration, stats: StatisticsSettings) -> Registered:
    """The registered pairings on the pooled run, under intention to treat."""
    needed = {registration.primary_arm, registration.reference_arm, *registration.secondary_references}
    if not needed <= set(score.arms):
        raise PoolError(f"the run lacks arm(s) {sorted(needed - set(score.arms))}")
    family = {p.question_id: p.scenario_family for p in score.pairs}
    mine = _values(score.arm_pairs(registration.primary_arm), registration.metric)

    def against(reference: str) -> Effect:
        theirs = _values(score.arm_pairs(reference), registration.metric)
        effect = paired_effect(
            "ALL", registration.primary_arm, reference, registration.metric, mine, theirs, family, stats
        )
        if effect is None:
            raise PoolError(f"{registration.primary_arm} and {reference} share no question owing {registration.metric}")
        return effect

    primary = replace(against(registration.reference_arm), primary=True)
    secondary = [against(r) for r in registration.secondary_references]
    p_values = {e.reference: e.p_value for e in secondary if e.p_value is not None}
    adjusted = holm(p_values) if p_values else {}  # a metric that is not 0 or 1 has no exact test to adjust
    secondaries = tuple(replace(e, adjusted_p=adjusted.get(e.reference)) for e in secondary)
    return Registered(registration, primary, decide(primary, registration.minimum_effect), secondaries)


def _returned(score: RunScore) -> dict[tuple[str, str], tuple[str, ...]]:
    """The documents each final record returned, in rank order, by (arm, question)."""
    found: dict[tuple[str, str], tuple[str, ...]] = {}
    for record in score.ledger_records:
        if record.is_final and isinstance(record.payload, list):
            found[(record.arm, record.question_id)] = tuple(str(c.get("source_document_id")) for c in record.payload)
    return found


def repeat_agreement(first: RunScore, other: RunScore) -> dict[str, tuple[int, int]]:
    """Per arm, how many questions returned the same documents in the same order in both runs, of how many asked.

    Two runs of an arm that is deterministic agree everywhere; a question one run answered and the other did not
    counts as a disagreement. Only counts leave this function, never a question.
    """
    a, b = _returned(first), _returned(other)
    result: dict[str, tuple[int, int]] = {}
    for arm in sorted({arm for arm, _ in (*a, *b)}):
        asked = {q for (x, q) in (*a, *b) if x == arm}
        same = sum(1 for q in asked if (arm, q) in a and (arm, q) in b and a[(arm, q)] == b[(arm, q)])
        result[arm] = (same, len(asked))
    return result
