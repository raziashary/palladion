"""Paired statistics for arm comparisons (B03-T04.01, protocol 9, BADR-0024).

Method is fixed so a number can be reproduced: a percentile bootstrap that resamples whole scenario families (the unit
of dependence) with a recorded seed, an exact McNemar test for paired binary outcomes, Holm over an explicit family,
equivalence by the (1 - 2*alpha) interval against a stated margin and harm direction, and the exact zero-failure upper
bound. With fewer clusters than ``min_clusters`` an interval is labelled descriptive and carries no bounds.
Non-completed pairs enter a binary endpoint as failures in the intention-to-treat table; the conditional table drops
them and counts how many were dropped. No third-party numerics are used, so the module has no new dependency.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum


class StatisticsError(ValueError):
    """An estimator was called with inputs it cannot interpret. Never a silently adjusted number."""


@dataclass(frozen=True)
class Interval:
    """A mean with a percentile interval. ``descriptive`` intervals have no bounds: too few clusters to infer from."""

    estimate: float
    low: float | None
    high: float | None
    n: int
    clusters: int
    descriptive: bool


def _quantile(sorted_values: Sequence[float], q: float) -> float:
    """Linear interpolation between order statistics (the method evaluation.yaml fixes)."""
    if not sorted_values:
        raise StatisticsError("a quantile needs at least one value")
    if not 0.0 <= q <= 1.0:
        raise StatisticsError("a quantile level must lie in [0, 1]")
    position = q * (len(sorted_values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (position - lower)


def quantile(values: Sequence[float], q: float) -> float:
    return _quantile(sorted(values), q)


def _aggregate(values: Sequence[float], clusters: Sequence[str]) -> list[tuple[float, int]]:
    if len(values) != len(clusters):
        raise StatisticsError("values and cluster labels must have the same length")
    if not values:
        raise StatisticsError("an interval needs at least one value")
    totals: dict[str, tuple[float, int]] = defaultdict(lambda: (0.0, 0))
    for value, cluster in zip(values, clusters, strict=True):
        total, count = totals[cluster]
        totals[cluster] = (total + value, count + 1)
    return [totals[c] for c in sorted(totals)]


def _percentile_interval(means: list[float], confidence: float) -> tuple[float, float]:
    ordered = sorted(means)
    alpha = 1.0 - confidence
    return _quantile(ordered, alpha / 2), _quantile(ordered, 1.0 - alpha / 2)


def _resampled_means(parts: list[tuple[float, int]], resamples: int, seed: int) -> list[float]:
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(resamples):
        drawn = rng.choices(parts, k=len(parts))
        total = sum(t for t, _ in drawn)
        count = sum(c for _, c in drawn)
        means.append(total / count)
    return means


def cluster_bootstrap_mean(
    values: Sequence[float],
    clusters: Sequence[str],
    *,
    resamples: int,
    confidence: float,
    seed: int,
    min_clusters: int,
) -> Interval:
    """Mean of ``values`` with a percentile interval from resampling whole clusters with replacement."""
    parts = _aggregate(values, clusters)
    estimate = sum(t for t, _ in parts) / sum(c for _, c in parts)
    if len(parts) < min_clusters:
        return Interval(estimate, None, None, len(values), len(parts), descriptive=True)
    low, high = _percentile_interval(_resampled_means(parts, resamples, seed), confidence)
    return Interval(estimate, low, high, len(values), len(parts), descriptive=False)


def naive_bootstrap_mean(values: Sequence[float], *, resamples: int, confidence: float, seed: int) -> Interval:
    """Item-level bootstrap that ignores clustering. Kept only as the contrast that shows why clusters are resampled."""
    parts = [(v, 1) for v in values]
    if not parts:
        raise StatisticsError("an interval needs at least one value")
    low, high = _percentile_interval(_resampled_means(parts, resamples, seed), confidence)
    return Interval(sum(values) / len(values), low, high, len(values), len(values), descriptive=False)


def paired_differences(a: Mapping[str, float], b: Mapping[str, float]) -> dict[str, float]:
    """``a - b`` per question. The two arms must have scored exactly the same questions."""
    if set(a) != set(b):
        raise StatisticsError("paired arms must be scored on the same questions")
    return {q: a[q] - b[q] for q in sorted(a)}


def paired_cluster_difference(
    a: Mapping[str, float],
    b: Mapping[str, float],
    family_of: Mapping[str, str],
    *,
    resamples: int,
    confidence: float,
    seed: int,
    min_clusters: int,
) -> Interval:
    diffs = paired_differences(a, b)
    return cluster_bootstrap_mean(
        list(diffs.values()),
        [family_of[q] for q in diffs],
        resamples=resamples,
        confidence=confidence,
        seed=seed,
        min_clusters=min_clusters,
    )


# --------------------------------------------------------------------------- tests of hypotheses


def mcnemar_exact(only_a: int, only_b: int) -> float:
    """Two-sided exact p-value for paired binary outcomes from the two discordant counts."""
    if only_a < 0 or only_b < 0:
        raise StatisticsError("discordant counts cannot be negative")
    n = only_a + only_b
    if n == 0:
        return 1.0
    smaller = min(only_a, only_b)
    tail = sum(math.comb(n, i) for i in range(smaller + 1)) / (1 << n)
    return min(1.0, 2 * tail)


def discordant_counts(a: Mapping[str, bool], b: Mapping[str, bool]) -> tuple[int, int]:
    """(only A succeeded, only B succeeded) over the same questions."""
    if set(a) != set(b):
        raise StatisticsError("paired arms must be scored on the same questions")
    return sum(a[q] and not b[q] for q in a), sum(b[q] and not a[q] for q in a)


def holm(p_values: Mapping[str, float]) -> dict[str, float]:
    """Holm step-down adjusted p-values over exactly the family supplied. The caller names the family."""
    if not p_values:
        raise StatisticsError("a Holm family needs at least one p-value")
    if any(not 0.0 <= p <= 1.0 for p in p_values.values()):
        raise StatisticsError("p-values must lie in [0, 1]")
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    m = len(ordered)
    adjusted: dict[str, float] = {}
    running = 0.0
    for rank, (name, p) in enumerate(ordered):
        running = max(running, min(1.0, (m - rank) * p))
        adjusted[name] = running
    return adjusted


class Harm(StrEnum):
    """Which direction of the difference counts as harm when judging equivalence."""

    EITHER = "either"
    DECREASE = "decrease"
    INCREASE = "increase"


@dataclass(frozen=True)
class Equivalence:
    equivalent: bool
    low: float | None
    high: float | None
    margin: float
    harm: Harm
    descriptive: bool


def equivalence(
    differences: Sequence[float],
    clusters: Sequence[str],
    *,
    margin: float,
    harm: Harm,
    resamples: int,
    confidence: float,
    seed: int,
    min_clusters: int,
) -> Equivalence:
    """TOST by interval: equivalent when the (1 - 2*alpha) interval of the difference stays inside the margin.

    ``harm`` decides which side matters: ``DECREASE`` only requires the lower bound to clear ``-margin`` (a
    non-inferiority check), ``INCREASE`` only the upper bound to stay below ``+margin``, ``EITHER`` both.
    """
    if margin <= 0:
        raise StatisticsError("an equivalence margin must be positive")
    parts = _aggregate(differences, clusters)
    if len(parts) < min_clusters:
        return Equivalence(False, None, None, margin, harm, descriptive=True)
    alpha = 1.0 - confidence
    means = sorted(_resampled_means(parts, resamples, seed))
    low, high = _quantile(means, alpha), _quantile(means, 1.0 - alpha)
    inside_low = low > -margin
    inside_high = high < margin
    ok = {Harm.EITHER: inside_low and inside_high, Harm.DECREASE: inside_low, Harm.INCREASE: inside_high}[harm]
    return Equivalence(ok, low, high, margin, harm, descriptive=False)


def zero_failure_upper_bound(n: int, confidence: float) -> float:
    """Exact one-sided upper bound on a failure rate after ``n`` trials with no failure: 1 - (1 - c)^(1/n)."""
    if n < 1:
        raise StatisticsError("a zero-failure bound needs at least one trial")
    if not 0.0 < confidence < 1.0:
        raise StatisticsError("confidence must lie strictly between 0 and 1")
    return 1.0 - float((1.0 - confidence) ** (1.0 / n))


# --------------------------------------------------------------------------- calibration


def brier(probabilities: Sequence[float], outcomes: Sequence[bool]) -> float:
    _check_probabilities(probabilities, outcomes)
    return sum((p - float(o)) ** 2 for p, o in zip(probabilities, outcomes, strict=True)) / len(outcomes)


def log_loss(probabilities: Sequence[float], outcomes: Sequence[bool], *, eps: float = 1e-12) -> float:
    """Mean negative log likelihood; probabilities are clipped to [eps, 1 - eps], a clip the caller discloses."""
    _check_probabilities(probabilities, outcomes)
    total = 0.0
    for p, o in zip(probabilities, outcomes, strict=True):
        clipped = min(max(p, eps), 1.0 - eps)
        total -= math.log(clipped if o else 1.0 - clipped)
    return total / len(outcomes)


@dataclass(frozen=True)
class CalibrationBin:
    low: float
    high: float
    count: int
    mean_confidence: float | None
    accuracy: float | None


@dataclass(frozen=True)
class Calibration:
    ece: float
    bins: tuple[CalibrationBin, ...]


def ece(probabilities: Sequence[float], outcomes: Sequence[bool], *, bins: int) -> Calibration:
    """Expected calibration error over ``bins`` equal-width bins, returned with every bin so the choice is disclosed."""
    _check_probabilities(probabilities, outcomes)
    if bins < 1:
        raise StatisticsError("ECE needs at least one bin")
    members: list[list[tuple[float, bool]]] = [[] for _ in range(bins)]
    for p, o in zip(probabilities, outcomes, strict=True):
        members[min(int(p * bins), bins - 1)].append((p, o))
    total = len(outcomes)
    summary: list[CalibrationBin] = []
    error = 0.0
    for index, group in enumerate(members):
        low, high = index / bins, (index + 1) / bins
        if not group:
            summary.append(CalibrationBin(low, high, 0, None, None))
            continue
        confidence = sum(p for p, _ in group) / len(group)
        accuracy = sum(o for _, o in group) / len(group)
        error += len(group) / total * abs(confidence - accuracy)
        summary.append(CalibrationBin(low, high, len(group), confidence, accuracy))
    return Calibration(error, tuple(summary))


def _check_probabilities(probabilities: Sequence[float], outcomes: Sequence[bool]) -> None:
    if len(probabilities) != len(outcomes) or not outcomes:
        raise StatisticsError("probabilities and outcomes must be non-empty and the same length")
    if any(not 0.0 <= p <= 1.0 for p in probabilities):
        raise StatisticsError("probabilities must lie in [0, 1]")


# --------------------------------------------------------------------------- completion accounting


@dataclass(frozen=True)
class EndpointTables:
    """The same binary endpoint under both accountings. ``excluded`` is the number the conditional table dropped."""

    itt: tuple[float, ...]
    conditional: tuple[float, ...]
    conditional_index: tuple[int, ...]
    excluded: int


def completion_tables(outcomes: Sequence[bool | None]) -> EndpointTables:
    """``None`` marks a pair that did not complete (timeout, outage, not run). It is a failure in the
    intention-to-treat series and absent, but counted, in the conditional one."""
    itt = tuple(1.0 if o else 0.0 for o in outcomes)
    kept = [(i, 1.0 if o else 0.0) for i, o in enumerate(outcomes) if o is not None]
    return EndpointTables(
        itt=itt,
        conditional=tuple(v for _, v in kept),
        conditional_index=tuple(i for i, _ in kept),
        excluded=len(outcomes) - len(kept),
    )


# --------------------------------------------------------------------------- power


@dataclass(frozen=True)
class PowerEstimate:
    power: float
    simulations: int
    clusters: int
    per_cluster: int
    rate_a: float
    rate_b: float
    cluster_sd: float


def simulate_power(
    *,
    clusters: int,
    per_cluster: int,
    rate_a: float,
    rate_b: float,
    cluster_sd: float,
    simulations: int,
    resamples: int,
    confidence: float,
    seed: int,
    min_clusters: int,
) -> PowerEstimate:
    """Monte Carlo power of the paired cluster bootstrap to exclude zero for true rates ``rate_a`` and ``rate_b``.

    Each family shifts both arms by one shared normal draw (``cluster_sd``), which is what makes a family's questions
    correlated; the two arms are then drawn independently within a question.
    """
    if clusters < 1 or per_cluster < 1 or simulations < 1:
        raise StatisticsError("power simulation sizes must be positive")
    rng = random.Random(seed)
    rejected = 0
    for sim in range(simulations):
        diffs: list[float] = []
        labels: list[str] = []
        for cluster in range(clusters):
            shift = rng.gauss(0.0, cluster_sd)
            p_a = min(1.0, max(0.0, rate_a + shift))
            p_b = min(1.0, max(0.0, rate_b + shift))
            for _ in range(per_cluster):
                diffs.append(float(rng.random() < p_a) - float(rng.random() < p_b))
                labels.append(f"f{cluster}")
        interval = cluster_bootstrap_mean(
            diffs,
            labels,
            resamples=resamples,
            confidence=confidence,
            seed=seed + sim + 1,
            min_clusters=min_clusters,
        )
        if not interval.descriptive and interval.low is not None and interval.high is not None:
            rejected += interval.low > 0 or interval.high < 0
    return PowerEstimate(rejected / simulations, simulations, clusters, per_cluster, rate_a, rate_b, cluster_sd)
