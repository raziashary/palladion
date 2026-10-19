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
