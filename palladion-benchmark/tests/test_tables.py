"""Scorecards: run states sit beside accuracy, ITT and conditional tables differ as defined (B03-T06.01)."""

from __future__ import annotations

from pathlib import Path

import pytest

from benchmark.analysis.tables import ALL_STRATA, Scorecard, build_scorecard, render_markdown
from benchmark.config import StatisticsSettings, load_evaluation_config
from benchmark.contracts import RunStatus
from benchmark.eval.score_run import PairScore, RunScore
from benchmark.eval.statistics import StatisticsError

CONFIGS = Path(__file__).resolve().parents[1] / "configs"
STATS: StatisticsSettings = load_evaluation_config(CONFIGS / "evaluation.yaml").statistics
OWED = frozenset({"complete_set_at_k", "forbidden_source_exposure"})
FAMILIES = 10


def pair(
    arm: str,
    index: int,
    status: RunStatus = RunStatus.OK,
    value: float = 1.0,
    *,
    stratum: str = "Q1",
    exposed: int = 0,
) -> PairScore:
    done = status is RunStatus.OK
    return PairScore(
        arm=arm,
        question_id=f"q-{index:08x}",
        stratum=stratum,
        scenario_family=f"fam{index % FAMILIES}",
        status=status,
        code=None if done else status.value,
        metrics={"complete_set_at_k": value, "forbidden_source_exposure": float(exposed > 0)} if done else {},
        applicable=OWED,
        alignment_only={},
        forbidden_exposures=exposed,
        authority_confusions=0,
        wrong_vintages=0,
        returned=3 if done else 0,
        duration_ms=10.0 if done else None,
    )


def score(pairs: list[PairScore]) -> RunScore:
    return RunScore("run-0001", 10, "0" * 64, tuple(pairs), ())


def card(pairs: list[PairScore], reference: str | None = "base") -> Scorecard:
    return build_scorecard(
        score(pairs), metrics=("complete_set_at_k", "forbidden_source_exposure"), stats=STATS, reference=reference
    )


def test_a_not_run_arm_is_a_state_beside_accuracy_not_a_zero_inside_it() -> None:
    pairs = [pair("base", i) for i in range(40)] + [pair("down", i, RunStatus.NOT_RUN) for i in range(40)]
    result = card(pairs)
    row = next(r for r in result.states if r.arm == "down" and r.stratum == ALL_STRATA)
    assert row.states == {"NOT_RUN": 40} and row.completed == 0
    conditional = result.cell(ALL_STRATA, "down", "complete_set_at_k")
    assert conditional.conditional is None and conditional.completed == 0 and conditional.excluded == 40
    assert result.cell(ALL_STRATA, "base", "complete_set_at_k").conditional is not None
    text = render_markdown(result)
    assert "NOT_RUN=40" in text


def test_itt_counts_non_completion_as_failure_and_conditional_drops_it() -> None:
    pairs = [pair("base", i) for i in range(40)]
    pairs += [pair("slow", i, RunStatus.TIMEOUT if i >= 20 else RunStatus.OK) for i in range(40)]
    result = card(pairs)
    cell = result.cell(ALL_STRATA, "slow", "complete_set_at_k")
    assert cell.eligible == 40 and cell.completed == 20 and cell.excluded == 20
    assert cell.itt is not None and cell.itt.estimate == pytest.approx(0.5)
    assert cell.conditional is not None and cell.conditional.estimate == pytest.approx(1.0)


def test_the_paired_difference_uses_itt_and_names_its_pairs() -> None:
    pairs = [pair("base", i) for i in range(40)]
    pairs += [pair("slow", i, RunStatus.TIMEOUT if i >= 20 else RunStatus.OK) for i in range(40)]
    effect = next(e for e in card(pairs).effects if e.stratum == ALL_STRATA and e.metric == "complete_set_at_k")
    assert effect.arm == "slow" and effect.reference == "base" and effect.pairs == 40
    assert effect.difference.estimate == pytest.approx(-0.5)
    assert effect.difference.high is not None and effect.difference.high < 0.0


def test_harm_metrics_have_no_itt_value_and_are_reported_only_conditionally() -> None:
    pairs = [pair("base", i, exposed=1 if i % 4 == 0 else 0) for i in range(40)]
    pairs += [pair("slow", i, RunStatus.TIMEOUT if i >= 20 else RunStatus.OK) for i in range(40)]
    result = card(pairs)
    harm = result.cell(ALL_STRATA, "slow", "forbidden_source_exposure")
    assert harm.itt is None, "a pair that never ran cannot be charged with an exposure"
    assert harm.conditional is not None and harm.conditional.estimate == 0.0
    assert result.cell(ALL_STRATA, "base", "forbidden_source_exposure").conditional is not None
    assert not [e for e in result.effects if e.metric == "forbidden_source_exposure"]
    itt_section = render_markdown(result).split("## Conditional on completion")[0]
    assert "forbidden_source_exposure" not in itt_section


def test_severe_failures_are_counted_over_completed_pairs_only() -> None:
    pairs = [pair("base", i, exposed=2 if i < 5 else 0) for i in range(20)]
    pairs += [pair("base", 100 + i, RunStatus.NOT_RUN, exposed=3) for i in range(5)]  # a charge that must not count
    row = next(r for r in card(pairs, reference=None).states if r.stratum == ALL_STRATA)
    assert row.severe["forbidden_source"] == 5 and row.completed == 20 and row.states == {"NOT_RUN": 5}


def test_strata_are_separate_rows_and_all_sums_them() -> None:
    pairs = [pair("base", i, stratum="Q1" if i < 20 else "Q2", value=1.0 if i < 20 else 0.0) for i in range(40)]
    result = card(pairs, reference=None)
    q1, q2 = result.cell("Q1", "base", "complete_set_at_k").itt, result.cell("Q2", "base", "complete_set_at_k").itt
    assert q1 is not None and q1.estimate == 1.0
    assert q2 is not None and q2.estimate == 0.0
    assert result.cell(ALL_STRATA, "base", "complete_set_at_k").eligible == 40


def test_few_families_give_a_descriptive_interval() -> None:
    pairs = [pair("base", i) for i in range(4)]
    cell = card(pairs, reference=None).cell(ALL_STRATA, "base", "complete_set_at_k")
    assert cell.itt is not None and cell.itt.descriptive and cell.itt.low is None
    assert "descriptive" in render_markdown(card(pairs, reference=None))


def test_an_unknown_reference_is_refused() -> None:
    with pytest.raises(StatisticsError):
        card([pair("base", 1)], reference="ghost")


# --------------------------------------------------------------------------- paired tests and harm bounds (B08-T08.10)


def binary_pairs(arm: str, wins: set[int], total: int = 10) -> list[PairScore]:
    return [pair(arm, i, value=1.0 if i in wins else 0.0) for i in range(total)]


def test_the_exact_test_is_computed_on_the_discordant_questions_and_matches_a_hand_value() -> None:
    # the arm alone is right on questions 0-7, the reference alone on 8-9: 8 against 2
    pairs = binary_pairs("arm", set(range(8))) + binary_pairs("base", {8, 9})
    effect = next(e for e in card(pairs).effects if e.stratum == ALL_STRATA and e.metric == "complete_set_at_k")
    assert (effect.only_arm, effect.only_reference) == (8, 2)
    assert effect.p_value == pytest.approx(2 * (1 + 10 + 45) / 1024)  # two-sided exact binomial, hand computed
    assert effect.pairs == 10 and effect.difference.estimate == pytest.approx(0.6)


def test_a_metric_that_is_not_zero_or_one_has_a_difference_and_no_exact_test() -> None:
    pairs = [pair("arm", i, value=0.5) for i in range(10)] + [pair("base", i, value=0.25) for i in range(10)]
    effect = next(e for e in card(pairs).effects if e.stratum == ALL_STRATA and e.metric == "complete_set_at_k")
    assert effect.p_value is None and effect.only_arm is None and effect.difference.estimate == pytest.approx(0.25)


def test_holm_adjusts_the_other_arms_together_and_leaves_the_primary_pairing_alone() -> None:
    pairs = binary_pairs("base", set(), 20)
    pairs += binary_pairs("lead", set(range(8)), 20)  # 8 against 0: p = 2 / 256
    pairs += binary_pairs("mid", set(range(5)), 20)  # 5 against 0: p = 2 / 32
    pairs += binary_pairs("low", {0}, 20)  # 1 against 0: p = 1
    result = build_scorecard(
        score(pairs), metrics=("complete_set_at_k",), stats=STATS, reference="base", primary="lead"
    )
    by_arm = {e.arm: e for e in result.effects if e.stratum == ALL_STRATA}
    assert by_arm["lead"].primary and by_arm["lead"].adjusted_p is None
    assert by_arm["lead"].p_value == pytest.approx(2 / 256)
    # mid and low are adjusted together (two tests): the smaller p times 2, the larger kept at least that, capped at 1
    assert by_arm["mid"].adjusted_p == pytest.approx(min(1.0, 2 * (2 / 32)))
    assert by_arm["low"].adjusted_p == pytest.approx(1.0)
    assert not by_arm["mid"].primary and not by_arm["low"].primary
    text = render_markdown(result)
    assert "primary (unadjusted)" in text and "only arm / only ref" in text


def test_a_primary_arm_that_is_not_in_the_run_or_is_the_reference_is_refused() -> None:
    pairs = binary_pairs("arm", {0}) + binary_pairs("base", {1})
    for primary in ("ghost", "base"):
        with pytest.raises(StatisticsError, match="primary arm"):
            build_scorecard(
                score(pairs), metrics=("complete_set_at_k",), stats=STATS, reference="base", primary=primary
            )
    with pytest.raises(StatisticsError, match="primary arm"):
        build_scorecard(score(pairs), metrics=("complete_set_at_k",), stats=STATS, reference=None, primary="arm")


def test_a_harm_is_bounded_over_every_eligible_pair_and_never_imputed() -> None:
    pairs = [pair("arm", i, exposed=1 if i < 3 else 0) for i in range(30)]
    pairs += [pair("arm", 30 + i, RunStatus.TIMEOUT) for i in range(10)]
    pairs += [pair("base", i) for i in range(40)]
    result = card(pairs)
    harmed = result.cell(ALL_STRATA, "arm", "forbidden_source_exposure")
    assert harmed.harm_bounds == pytest.approx((3 / 40, 13 / 40))  # none of the 10 unfinished / all of them
    assert harmed.conditional is not None and harmed.conditional.estimate == pytest.approx(0.1)
    clean = result.cell(ALL_STRATA, "base", "forbidden_source_exposure")
    assert clean.harm_bounds == (0.0, 0.0), (
        "zero observed harm over a complete run is a bound of zero, not a claim of safety"
    )
    assert result.cell(ALL_STRATA, "arm", "complete_set_at_k").harm_bounds is None
    text = render_markdown(result)
    assert "Harm over every eligible pair" in text and "0.075" in text and "0.325" in text


def test_a_pair_that_never_ran_widens_the_upper_bound_only() -> None:
    complete = [pair("arm", i) for i in range(20)]
    cut = [pair("arm", i) for i in range(10)] + [pair("arm", 10 + i, RunStatus.NOT_RUN) for i in range(10)]
    full = build_scorecard(score(complete), metrics=("forbidden_source_exposure",), stats=STATS)
    short = build_scorecard(score(cut), metrics=("forbidden_source_exposure",), stats=STATS)
    assert full.cell(ALL_STRATA, "arm", "forbidden_source_exposure").harm_bounds == (0.0, 0.0)
    assert short.cell(ALL_STRATA, "arm", "forbidden_source_exposure").harm_bounds == (0.0, 0.5)
