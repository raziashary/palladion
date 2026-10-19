"""Paired statistics: known effects recovered, coverage near nominal, clustering widens intervals (B03-T04.01)."""

from __future__ import annotations

import math
import random
from pathlib import Path
from typing import TypedDict

import pytest

from benchmark.config import load_evaluation_config
from benchmark.eval.statistics import (
    Harm,
    StatisticsError,
    brier,
    cluster_bootstrap_mean,
    completion_tables,
    discordant_counts,
    ece,
    equivalence,
    holm,
    log_loss,
    mcnemar_exact,
    naive_bootstrap_mean,
    paired_cluster_difference,
    paired_differences,
    quantile,
    simulate_power,
    zero_failure_upper_bound,
)


class Boot(TypedDict):
    resamples: int
    confidence: float
    seed: int
    min_clusters: int


class PowerBase(TypedDict):
    per_cluster: int
    simulations: int
    resamples: int
    confidence: float
    seed: int
    min_clusters: int


KW = Boot(resamples=400, confidence=0.95, seed=7, min_clusters=8)


def labelled(per_cluster: dict[str, list[float]]) -> tuple[list[float], list[str]]:
    values = [v for vs in per_cluster.values() for v in vs]
    labels = [c for c, vs in per_cluster.items() for _ in vs]
    return values, labels


# --------------------------------------------------------------------------- intervals


def test_quantile_matches_hand_computation() -> None:
    values = [1.0, 2.0, 3.0, 4.0]
    assert quantile(values, 0.0) == 1.0
    assert quantile(values, 0.5) == 2.5
    assert quantile(values, 1.0) == 4.0
    assert quantile(values, 0.9) == pytest.approx(3.7)
    with pytest.raises(StatisticsError):
        quantile([], 0.5)
    with pytest.raises(StatisticsError):
        quantile(values, 1.5)


def test_interval_is_reproducible_and_seed_sensitive() -> None:
    rng = random.Random(1)
    values, labels = labelled({f"f{i}": [rng.random() for _ in range(5)] for i in range(12)})
    first = cluster_bootstrap_mean(values, labels, **KW)
    assert first == cluster_bootstrap_mean(values, labels, **KW)
    assert first != cluster_bootstrap_mean(values, labels, resamples=400, confidence=0.95, seed=8, min_clusters=8)
    assert first.low is not None and first.high is not None and first.low < first.estimate < first.high


def test_too_few_clusters_is_descriptive_without_bounds() -> None:
    values, labels = labelled({f"f{i}": [0.0, 1.0] for i in range(7)})
    got = cluster_bootstrap_mean(values, labels, **KW)
    assert got.descriptive and got.low is None and got.high is None
    assert got.clusters == 7 and got.estimate == 0.5
    at_minimum = cluster_bootstrap_mean(*labelled({f"f{i}": [0.0, 1.0] for i in range(8)}), **KW)
    assert not at_minimum.descriptive


def test_bad_inputs_are_refused() -> None:
    with pytest.raises(StatisticsError):
        cluster_bootstrap_mean([1.0], ["a", "b"], **KW)
    with pytest.raises(StatisticsError):
        cluster_bootstrap_mean([], [], **KW)
    with pytest.raises(StatisticsError):
        naive_bootstrap_mean([], resamples=10, confidence=0.9, seed=1)


def test_known_paired_effect_is_recovered() -> None:
    rng = random.Random(3)
    a, b, family = {}, {}, {}
    for i in range(240):
        q = f"q{i}"
        family[q] = f"f{i % 20}"
        base = rng.random() < 0.5
        a[q] = float(base or rng.random() < 0.3)  # arm A is better by about 0.15
        b[q] = float(base)
    got = paired_cluster_difference(a, b, family, **KW)
    assert got.low is not None and got.high is not None
    assert 0.05 < got.estimate < 0.25
    assert got.low > 0.0, "the interval should exclude zero for a real effect"
    null = paired_cluster_difference(b, b, family, **KW)
    assert null.estimate == 0.0 and null.low == 0.0 == null.high


def test_pairing_requires_the_same_questions() -> None:
    with pytest.raises(StatisticsError):
        paired_differences({"q1": 1.0}, {"q2": 1.0})
    with pytest.raises(StatisticsError):
        discordant_counts({"q1": True}, {"q2": True})


def simulated_coverage(clusters: int, per_cluster: int, trials: int) -> float:
    """Share of intervals that contain the true mean when families share a random effect (true mean 0.5)."""
    rng = random.Random(11)
    hits = 0
    for trial in range(trials):
        values: list[float] = []
        labels: list[str] = []
        for cluster in range(clusters):
            p = min(1.0, max(0.0, 0.5 + rng.gauss(0.0, 0.2)))
            values += [float(rng.random() < p) for _ in range(per_cluster)]
            labels += [f"f{cluster}"] * per_cluster
        got = cluster_bootstrap_mean(values, labels, resamples=300, confidence=0.95, seed=trial, min_clusters=8)
        assert got.low is not None and got.high is not None
        hits += got.low <= 0.5 <= got.high
    return hits / trials


@pytest.mark.parametrize(("clusters", "floor"), [(12, 0.88), (30, 0.91)])
def test_cluster_interval_coverage_is_near_nominal(clusters: int, floor: float) -> None:
    assert simulated_coverage(clusters, per_cluster=6, trials=250) >= floor


def test_clustering_widens_the_interval_against_the_naive_one() -> None:
    rng = random.Random(5)
    values: list[float] = []
    labels: list[str] = []
    for cluster in range(15):
        p = 0.9 if cluster % 2 else 0.1  # strong within-family correlation
        values += [float(rng.random() < p) for _ in range(8)]
        labels += [f"f{cluster}"] * 8
    clustered = cluster_bootstrap_mean(values, labels, **KW)
    naive = naive_bootstrap_mean(values, resamples=400, confidence=0.95, seed=7)
    assert clustered.low is not None and clustered.high is not None
    assert naive.low is not None and naive.high is not None
    assert (clustered.high - clustered.low) > 1.5 * (naive.high - naive.low)
    assert clustered.estimate == pytest.approx(naive.estimate)


# --------------------------------------------------------------------------- hypothesis tests


def test_mcnemar_exact_matches_binomial_tails() -> None:
    assert mcnemar_exact(0, 0) == 1.0
    assert mcnemar_exact(5, 5) == 1.0
    assert mcnemar_exact(10, 0) == pytest.approx(2 / 1024)
    assert mcnemar_exact(0, 10) == mcnemar_exact(10, 0)
    assert mcnemar_exact(2, 8) == pytest.approx(2 * (1 + 10 + 45) / 1024)
    with pytest.raises(StatisticsError):
        mcnemar_exact(-1, 3)


def test_discordant_counts() -> None:
    a = {"1": True, "2": True, "3": False, "4": False}
    b = {"1": True, "2": False, "3": True, "4": True}
    assert discordant_counts(a, b) == (1, 2)


def test_holm_matches_hand_computation_and_is_monotone() -> None:
    adjusted = holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adjusted == {"a": pytest.approx(0.03), "c": pytest.approx(0.06), "b": pytest.approx(0.06)}
    assert holm({"only": 0.2}) == {"only": 0.2}
    assert holm({"x": 0.9, "y": 0.9})["x"] == pytest.approx(1.0)
    with pytest.raises(StatisticsError):
        holm({})
    with pytest.raises(StatisticsError):
        holm({"a": 1.2})


def test_holm_depends_on_the_family_supplied() -> None:
    small = holm({"a": 0.02, "b": 0.5})
    large = holm({"a": 0.02, "b": 0.5, "c": 0.5, "d": 0.5})
    assert small["a"] == pytest.approx(0.04) and large["a"] == pytest.approx(0.08)


def test_zero_failure_bound_is_exact_and_below_rule_of_three() -> None:
    assert zero_failure_upper_bound(1, 0.95) == pytest.approx(0.95)
    n = 59
    bound = zero_failure_upper_bound(n, 0.95)
    assert (1 - bound) ** n == pytest.approx(0.05)
    assert bound < 3 / n
    assert zero_failure_upper_bound(300, 0.95) < zero_failure_upper_bound(100, 0.95)
    for bad in (0, -3):
        with pytest.raises(StatisticsError):
            zero_failure_upper_bound(bad, 0.95)
    with pytest.raises(StatisticsError):
        zero_failure_upper_bound(10, 1.0)


# --------------------------------------------------------------------------- equivalence


def paired_noise(mean: float, clusters: int = 16, per: int = 6, sd: float = 0.05) -> tuple[list[float], list[str]]:
    rng = random.Random(2)
    return labelled({f"f{i}": [mean + rng.gauss(0.0, sd) for _ in range(per)] for i in range(clusters)})


def test_equivalence_inside_and_outside_the_margin() -> None:
    inside = equivalence(*paired_noise(0.0), margin=0.1, harm=Harm.EITHER, **KW)
    assert inside.equivalent and inside.low is not None and inside.low > -0.1
    shifted = equivalence(*paired_noise(0.15), margin=0.1, harm=Harm.EITHER, **KW)
    assert not shifted.equivalent


def test_harm_direction_changes_the_verdict() -> None:
    values = paired_noise(0.15)  # arm A is better by more than the margin
    assert not equivalence(*values, margin=0.1, harm=Harm.EITHER, **KW).equivalent
    assert equivalence(*values, margin=0.1, harm=Harm.DECREASE, **KW).equivalent  # not worse is all that is asked
    assert not equivalence(*values, margin=0.1, harm=Harm.INCREASE, **KW).equivalent


def test_equivalence_needs_a_positive_margin_and_enough_clusters() -> None:
    with pytest.raises(StatisticsError):
        equivalence(*paired_noise(0.0), margin=0.0, harm=Harm.EITHER, **KW)
    few = equivalence(*paired_noise(0.0, clusters=5), margin=0.1, harm=Harm.EITHER, **KW)
    assert few.descriptive and not few.equivalent and few.low is None


# --------------------------------------------------------------------------- calibration


def test_brier_and_log_loss_hand_computed() -> None:
    p, o = [0.9, 0.2, 0.5], [True, False, True]
    assert brier(p, o) == pytest.approx((0.01 + 0.04 + 0.25) / 3)
    assert log_loss(p, o) == pytest.approx(-(math.log(0.9) + math.log(0.8) + math.log(0.5)) / 3)
    assert log_loss([0.0], [True]) > 20  # clipped, finite
    assert math.isfinite(log_loss([1.0], [False]))


def test_ece_discloses_its_bins() -> None:
    got = ece([0.1, 0.1, 0.9, 0.9], [False, False, True, False], bins=2)
    assert [b.count for b in got.bins] == [2, 2]
    assert got.ece == pytest.approx(0.5 * 0.1 + 0.5 * 0.4)
    assert got.bins[1].accuracy == 0.5 and got.bins[1].mean_confidence == pytest.approx(0.9)
    sparse = ece([0.05, 0.05], [False, False], bins=10)
    assert sparse.bins[5].count == 0 and sparse.bins[5].accuracy is None
    assert ece([1.0], [True], bins=4).bins[3].count == 1  # probability 1 falls in the last bin


def test_calibration_inputs_are_checked() -> None:
    for call in (
        lambda: brier([0.5], [True, False]),
        lambda: brier([1.5], [True]),
        lambda: log_loss([], []),
        lambda: ece([0.5], [True], bins=0),
    ):
        with pytest.raises(StatisticsError):
            call()


# --------------------------------------------------------------------------- completion accounting


def test_non_completion_is_a_failure_in_itt_and_absent_in_conditional() -> None:
    tables = completion_tables([True, None, False, None, True])
    assert tables.itt == (1.0, 0.0, 0.0, 0.0, 1.0)
    assert tables.conditional == (1.0, 0.0, 1.0)
    assert tables.conditional_index == (0, 2, 4)
    assert tables.excluded == 2


def test_an_arm_that_times_out_on_hard_cases_changes_itt_and_not_conditional() -> None:
    questions = [f"q{i}" for i in range(40)]
    hard = set(questions[20:])
    family = {q: f"f{i % 10}" for i, q in enumerate(questions)}
    steady = {q: True for q in questions}
    timeouts: dict[str, bool | None] = {q: (None if q in hard else True) for q in questions}
    itt_steady = completion_tables([steady[q] for q in questions])
    itt_timeout = completion_tables([timeouts[q] for q in questions])
    assert sum(itt_timeout.itt) / 40 == 0.5 and sum(itt_steady.itt) / 40 == 1.0
    assert sum(itt_timeout.conditional) / len(itt_timeout.conditional) == 1.0
    assert itt_timeout.excluded == 20
    a = {q: float(v) for q, v in zip(questions, itt_steady.itt, strict=True)}
    b = {q: float(v) for q, v in zip(questions, itt_timeout.itt, strict=True)}
    got = paired_cluster_difference(a, b, family, **KW)
    assert got.estimate == 0.5 and got.low is not None and got.low > 0.0
    kept = [q for q in questions if q not in hard]
    same = paired_cluster_difference({q: 1.0 for q in kept}, {q: 1.0 for q in kept}, family, **KW)
    assert same.estimate == 0.0


# --------------------------------------------------------------------------- power


def test_power_rises_with_effect_and_falls_with_noise() -> None:
    base = PowerBase(per_cluster=5, simulations=60, resamples=150, confidence=0.95, seed=9, min_clusters=8)
    big = simulate_power(clusters=20, rate_a=0.8, rate_b=0.5, cluster_sd=0.05, **base)
    none = simulate_power(clusters=20, rate_a=0.6, rate_b=0.6, cluster_sd=0.05, **base)
    noisy = simulate_power(clusters=20, rate_a=0.65, rate_b=0.55, cluster_sd=0.05, **base)
    assert big.power > 0.9
    assert none.power < 0.2
    assert none.power <= noisy.power <= big.power


def test_power_with_too_few_clusters_is_zero_not_hidden() -> None:
    got = simulate_power(
        clusters=4, per_cluster=5, rate_a=0.9, rate_b=0.1, cluster_sd=0.0,
        simulations=10, resamples=50, confidence=0.95, seed=1, min_clusters=8,
    )  # fmt: skip
    assert got.power == 0.0 and got.clusters == 4
    with pytest.raises(StatisticsError):
        simulate_power(
            clusters=0, per_cluster=5, rate_a=0.9, rate_b=0.1, cluster_sd=0.0,
            simulations=10, resamples=50, confidence=0.95, seed=1, min_clusters=8,
        )  # fmt: skip


def test_the_configured_quantile_method_is_the_one_implemented() -> None:
    config = load_evaluation_config(Path(__file__).resolve().parents[1] / "configs" / "evaluation.yaml")
    assert config.quantile_method == "linear"
    assert quantile([0.0, 10.0], 0.25) == 2.5
