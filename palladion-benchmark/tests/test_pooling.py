"""Pooling the worlds of a sealed run and deciding the registered pairing (B08-T03.01, BADR-0047)."""

from __future__ import annotations

import pytest

from benchmark.analysis.pooling import (
    Claim,
    PoolError,
    Registration,
    decide,
    pool_runs,
    registered_comparisons,
    repeat_agreement,
)
from benchmark.analysis.tables import Effect
from benchmark.config import StatisticsSettings
from benchmark.contracts import RunStatus
from benchmark.eval.score_run import PairScore, RunScore
from benchmark.eval.statistics import Interval
from benchmark.runner import LedgerRecord

METRIC = "complete_set_at_k"
STATS = StatisticsSettings(
    bootstrap_resamples=500, confidence=0.95, multiplicity="holm", cluster_by="family",
    zero_failure_bound_numerator=3, bootstrap_seed=7, min_clusters=3,
)  # fmt: skip


def pair(arm: str, question: str, family: str, value: float, status: RunStatus = RunStatus.OK) -> PairScore:
    return PairScore(
        arm, question, "Q1", family, status, None, {METRIC: value} if status is RunStatus.OK else {},
        frozenset({METRIC}), {}, 0, 0, 0, 10, 1.0,
    )  # fmt: skip


def world(values: dict[str, list[float]], *, k: int = 10, gold: str = "g", family: str | None = None) -> RunScore:
    """One world: each arm's value per question; question ``i`` is its own family unless ``family`` names one."""
    pairs = [
        pair(arm, f"q-{i:016d}", family or f"POL-{i:03d}", v)
        for arm, scores in values.items()
        for i, v in enumerate(scores)
    ]
    return RunScore("run", k, gold, tuple(pairs), (), {})


def registration(minimum: float = 0.05, secondaries: tuple[str, ...] = ("R0", "R0x")) -> Registration:
    return Registration("R7a", "R3", secondaries, METRIC, minimum)


def arms(r7a: float, r3: float, others: float = 0.0, n: int = 20) -> dict[str, list[float]]:
    return {"R7a": [r7a] * n, "R3": [r3] * n, "R0": [others] * n, "R0x": [others] * n}


# -- pooling --------------------------------------------------------------------------------------------------------


def test_pooling_prefixes_questions_and_families_so_nothing_merges_across_worlds() -> None:
    pooled = pool_runs({"T101": world(arms(1, 0)), "T102": world(arms(1, 0))})
    ids = [p.question_id for p in pooled.arm_pairs("R7a")]
    assert len(ids) == len(set(ids)) == 40 and ids[0].startswith("T101:") and ids[-1].startswith("T102:")
    families = {p.scenario_family for p in pooled.arm_pairs("R7a")}
    assert len(families) == 40, "POL-000 of one world is not POL-000 of the other"
    assert pooled.arms == ["R0", "R0x", "R3", "R7a"] and pooled.run_id == "pooled:T101,T102"


def test_a_family_shared_by_every_question_of_a_world_is_one_cluster_per_world() -> None:
    pooled = pool_runs({"T101": world(arms(1, 0), family="F"), "T102": world(arms(1, 0), family="F")})
    result = registered_comparisons(pooled, registration(), STATS)
    assert result.primary.difference.clusters == 2, "the same label in two worlds is two clusters, not one"


def test_the_gold_digest_follows_every_world_and_withdrawn_questions_keep_their_world() -> None:
    a = pool_runs({"T101": world(arms(1, 0), gold="x"), "T102": world(arms(1, 0), gold="y")})
    b = pool_runs({"T101": world(arms(1, 0), gold="x"), "T102": world(arms(1, 0), gold="z")})
    assert a.gold_sha256 != b.gold_sha256
    gone = RunScore("r", 10, "g", world(arms(1, 0)).pairs, (), {"q-0000000000000001": "gold fixed"})
    assert pool_runs({"T101": gone}).withdrawn == {"T101:q-0000000000000001": "gold fixed"}


def test_worlds_scored_at_another_k_or_with_other_arms_are_refused() -> None:
    with pytest.raises(PoolError, match="K=5"):
        pool_runs({"T101": world(arms(1, 0)), "T102": world(arms(1, 0), k=5)})
    other = world({"R7a": [1.0], "R3": [0.0]})
    with pytest.raises(PoolError, match="arms"):
        pool_runs({"T101": world(arms(1, 0)), "T102": other})
    with pytest.raises(PoolError, match="no world"):
        pool_runs({})


# -- the registered pairing ------------------------------------------------------------------------------------------


def test_a_gain_that_clears_the_minimum_is_confirmed_and_the_counts_are_the_hand_computed_ones() -> None:
    pooled = pool_runs({"T101": world(arms(1, 0)), "T102": world(arms(1, 0))})
    result = registered_comparisons(pooled, registration(), STATS)
    effect = result.primary
    assert (effect.difference.estimate, effect.difference.low, effect.difference.high) == (1.0, 1.0, 1.0)
    assert (effect.pairs, effect.only_arm, effect.only_reference, effect.primary) == (40, 40, 0, True)
    assert effect.p_value == pytest.approx(2 / 2**40) and result.claim is Claim.CONFIRMED


def test_identical_arms_are_inconclusive_not_confirmed() -> None:
    result = registered_comparisons(pool_runs({"T101": world(arms(1, 1))}), registration(), STATS)
    assert result.primary.difference.estimate == 0.0 and result.claim is Claim.INCONCLUSIVE


def test_a_reference_that_is_better_everywhere_is_adverse() -> None:
    assert registered_comparisons(pool_runs({"T101": world(arms(0, 1))}), registration(), STATS).claim is Claim.ADVERSE


def test_a_gain_above_zero_but_under_the_minimum_is_named_so() -> None:
    result = registered_comparisons(pool_runs({"T101": world(arms(0.54, 0.5))}), registration(0.05), STATS)
    assert result.claim is Claim.BELOW_MINIMUM
    assert (
        registered_comparisons(pool_runs({"T101": world(arms(0.54, 0.5))}), registration(0.0), STATS).claim
        is Claim.CONFIRMED
    )


def test_too_few_clusters_give_no_interval_and_so_no_claim() -> None:
    few = world({"R7a": [1.0, 1.0], "R3": [0.0, 0.0], "R0": [0.0, 0.0], "R0x": [0.0, 0.0]}, family="F")
    assert registered_comparisons(pool_runs({"T101": few}), registration(), STATS).claim is Claim.INCONCLUSIVE


def test_the_secondaries_are_holm_adjusted_among_themselves_and_the_primary_is_not() -> None:
    values = {
        "R7a": [1.0] * 12 + [0.0] * 8,
        "R3": [0.0] * 20,
        "R0": [1.0] * 4 + [0.0] * 16,
        "R0x": [1.0] * 9 + [0.0] * 11,
    }
    result = registered_comparisons(pool_runs({"T101": world(values)}), registration(), STATS)
    by_arm = {e.reference: e for e in result.secondaries}
    assert by_arm["R0"].p_value == pytest.approx(2 * 0.5**8 * 1)  # 8 only-R7a, 0 only-R0: two-sided exact
    assert by_arm["R0x"].only_arm == 3 and by_arm["R0x"].only_reference == 0
    for effect in result.secondaries:
        assert effect.adjusted_p is not None and effect.p_value is not None and effect.adjusted_p >= effect.p_value
    assert result.primary.adjusted_p is None


def test_an_arm_the_run_lacks_is_refused() -> None:
    with pytest.raises(PoolError, match="R3f"):
        registered_comparisons(pool_runs({"T101": world(arms(1, 0))}), registration(secondaries=("R3f",)), STATS)


@pytest.mark.parametrize(
    ("primary", "reference", "secondaries", "minimum"),
    [
        ("R7a", "R7a", (), 0.05),
        ("R7a", "R3", ("R3",), 0.05),
        ("R7a", "R3", ("R0", "R0"), 0.05),
        ("R7a", "R3", (), -0.1),
    ],
)
def test_a_registration_with_a_repeated_arm_or_a_negative_minimum_is_refused(
    primary: str, reference: str, secondaries: tuple[str, ...], minimum: float
) -> None:
    with pytest.raises(PoolError):
        Registration(primary, reference, secondaries, METRIC, minimum)


def test_the_decision_rule_on_a_bare_interval() -> None:
    def effect(low: float | None, high: float | None) -> Effect:
        return Effect("ALL", "R7a", "R3", METRIC, 10, Interval(0.1, low, high, 10, 5, low is None))

    assert decide(effect(0.06, 0.2), 0.05) is Claim.CONFIRMED
    assert decide(effect(0.05, 0.2), 0.05) is Claim.BELOW_MINIMUM, "the lower bound must be above the minimum"
    assert decide(effect(-0.01, 0.2), 0.05) is Claim.INCONCLUSIVE
    assert decide(effect(-0.3, -0.01), 0.05) is Claim.ADVERSE
    assert decide(effect(None, None), 0.05) is Claim.INCONCLUSIVE


def final(arm: str, question: str, documents: list[str] | None) -> LedgerRecord:
    payload = None if documents is None else [{"source_document_id": d} for d in documents]
    status = RunStatus.OK if documents is not None else RunStatus.INVALID_RUN
    return LedgerRecord("r", "m" * 64, arm, question, 1, True, status, None, None, "t", 1.0, status, 1, payload)


def ledger(*records: LedgerRecord) -> RunScore:
    return RunScore("run", 10, "g", (), tuple(records), {})


def test_repeat_agreement_counts_the_questions_that_returned_the_same_documents_in_the_same_order() -> None:
    q1, q2, q3 = (f"q-{i:016d}" for i in (1, 2, 3))
    first = ledger(
        final("R7a", q1, ["a", "b"]), final("R7a", q2, ["a", "b"]), final("R7a", q3, ["c"]), final("R0", q1, ["x"])
    )
    second = ledger(
        final("R7a", q1, ["a", "b"]), final("R7a", q2, ["b", "a"]), final("R7a", q3, None), final("R0", q1, ["x"])
    )
    assert repeat_agreement(first, second) == {"R0": (1, 1), "R7a": (1, 3)}


def test_a_question_only_one_run_asked_is_a_disagreement_and_two_empty_runs_agree_on_nothing() -> None:
    q1, q2 = (f"q-{i:016d}" for i in (1, 2))
    assert repeat_agreement(
        ledger(final("R7a", q1, ["a"])), ledger(final("R7a", q1, ["a"]), final("R7a", q2, ["a"]))
    ) == {"R7a": (1, 2)}
    assert repeat_agreement(ledger(), ledger()) == {}


def test_repeat_agreement_keeps_worlds_apart_when_their_question_ids_repeat() -> None:
    q = "q-0000000000000001"
    first = {"T101": ledger_world(final("R7a", q, ["a"])), "T102": ledger_world(final("R7a", q, ["b"]))}
    same = {"T101": ledger_world(final("R7a", q, ["a"])), "T102": ledger_world(final("R7a", q, ["b"]))}
    other = {"T101": ledger_world(final("R7a", q, ["a"])), "T102": ledger_world(final("R7a", q, ["z"]))}
    assert repeat_agreement(pool_runs(first), pool_runs(same)) == {"R7a": (2, 2)}
    assert repeat_agreement(pool_runs(first), pool_runs(other)) == {"R7a": (1, 2)}


def ledger_world(*records: LedgerRecord) -> RunScore:
    return RunScore("run", 10, "g", (), tuple(records), {})
