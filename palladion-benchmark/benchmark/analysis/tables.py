"""Stratum-by-arm scorecards and pairwise effect tables (B03-T06.01, BADR-0024).

Two accountings are kept apart. The intention-to-treat table (end-to-end) credits a pair that did not complete with
zero on every benefit metric the gold says applies. The conditional table drops those pairs and prints how many it
dropped. Harm metrics (exposure, authority confusion, wrong vintage) have no intention-to-treat value, since a pair
that never ran cannot be charged with a harm; they appear in the conditional table only.

Run states (NOT_RUN, UNSUPPORTED, FEATURE_NOT_SUPPORTED, INVALID_RUN, TIMEOUT) are listed beside accuracy, as counts,
and never as zeros inside it.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from benchmark.config import StatisticsSettings
from benchmark.contracts import RunStatus
from benchmark.eval.score_run import HARM_METRICS, PairScore, RunScore
from benchmark.eval.statistics import Interval, StatisticsError, cluster_bootstrap_mean, paired_cluster_difference

ALL_STRATA = "ALL"


@dataclass(frozen=True)
class Cell:
    """One metric for one arm over one stratum, under both accountings."""

    stratum: str
    arm: str
    metric: str
    eligible: int  # pairs the gold says this metric applies to, completed or not
    itt: Interval | None  # None for a harm metric or when nothing is eligible
    completed: int
    conditional: Interval | None
    excluded: int  # eligible pairs the conditional table dropped because they did not complete


@dataclass(frozen=True)
class Effect:
    """Paired ITT difference ``arm - reference`` on the questions both arms owe this metric on."""

    stratum: str
    arm: str
    reference: str
    metric: str
    pairs: int
    difference: Interval


@dataclass(frozen=True)
class StateRow:
    stratum: str
    arm: str
    states: Mapping[str, int]  # non-OK states only
    completed: int
    severe: Mapping[str, int]  # completed pairs with a forbidden exposure, an authority confusion, a wrong vintage


@dataclass(frozen=True)
class Scorecard:
    run_id: str
    k: int
    cells: tuple[Cell, ...]
    effects: tuple[Effect, ...]
    states: tuple[StateRow, ...]

    def cell(self, stratum: str, arm: str, metric: str) -> Cell:
        return next(c for c in self.cells if (c.stratum, c.arm, c.metric) == (stratum, arm, metric))


def _itt_value(pair: PairScore, metric: str) -> float | None:
    """The pair's value under intention to treat, or None when the metric does not apply or is a harm metric."""
    if metric in HARM_METRICS:
        return None
    if metric in pair.metrics:
        return pair.metrics[metric]
    if pair.status is not RunStatus.OK and metric in pair.applicable:
        return 0.0
    return None


def _interval(values: Sequence[float], families: Sequence[str], stats: StatisticsSettings) -> Interval:
    return cluster_bootstrap_mean(
        values,
        families,
        resamples=stats.bootstrap_resamples,
        confidence=stats.confidence,
        seed=stats.bootstrap_seed,
        min_clusters=stats.min_clusters,
    )


def _cell(stratum: str, arm: str, metric: str, pairs: Sequence[PairScore], stats: StatisticsSettings) -> Cell:
    eligible = [p for p in pairs if metric in p.applicable or metric in p.metrics]
    itt = [(p, v) for p in eligible if (v := _itt_value(p, metric)) is not None]
    done = [(p, p.metrics[metric]) for p in eligible if p.status is RunStatus.OK and metric in p.metrics]
    return Cell(
        stratum=stratum,
        arm=arm,
        metric=metric,
        eligible=len(eligible),
        itt=_interval([v for _, v in itt], [p.scenario_family for p, _ in itt], stats) if itt else None,
        completed=len(done),
        conditional=_interval([v for _, v in done], [p.scenario_family for p, _ in done], stats) if done else None,
        excluded=len(eligible) - len(done),
    )


def _state_row(stratum: str, arm: str, pairs: Sequence[PairScore]) -> StateRow:
    done = [p for p in pairs if p.status is RunStatus.OK]
    return StateRow(
        stratum=stratum,
        arm=arm,
        states=dict(sorted(Counter(p.status.value for p in pairs if p.status is not RunStatus.OK).items())),
        completed=len(done),
        severe={
            "forbidden_source": sum(p.forbidden_exposures > 0 for p in done),
            "authority_confusion": sum(p.authority_confusions > 0 for p in done),
            "wrong_vintage": sum(p.wrong_vintages > 0 for p in done),
        },
    )


def _effect(
    stratum: str,
    arm: str,
    reference: str,
    metric: str,
    mine: Sequence[PairScore],
    theirs: Sequence[PairScore],
    stats: StatisticsSettings,
) -> Effect | None:
    a = {p.question_id: v for p in mine if (v := _itt_value(p, metric)) is not None}
    b = {p.question_id: v for p in theirs if (v := _itt_value(p, metric)) is not None}
    shared = sorted(set(a) & set(b))
    if not shared:
        return None
    family = {p.question_id: p.scenario_family for p in mine}
    return Effect(
        stratum,
        arm,
        reference,
        metric,
        len(shared),
        paired_cluster_difference(
            {q: a[q] for q in shared},
            {q: b[q] for q in shared},
            family,
            resamples=stats.bootstrap_resamples,
            confidence=stats.confidence,
            seed=stats.bootstrap_seed,
            min_clusters=stats.min_clusters,
        ),
    )


def build_scorecard(
    score: RunScore,
    *,
    metrics: Sequence[str],
    stats: StatisticsSettings,
    reference: str | None = None,
) -> Scorecard:
    """Cells for every stratum (and ALL) by arm by metric; effects against ``reference`` when one is named."""
    if reference is not None and reference not in score.arms:
        raise StatisticsError(f"reference arm {reference} is not in the run")
    strata = [*sorted({p.stratum for p in score.pairs}), ALL_STRATA]
    cells: list[Cell] = []
    effects: list[Effect] = []
    states: list[StateRow] = []
    for stratum in strata:
        in_stratum = [p for p in score.pairs if stratum == ALL_STRATA or p.stratum == stratum]
        for arm in score.arms:
            mine = [p for p in in_stratum if p.arm == arm]
            states.append(_state_row(stratum, arm, mine))
            cells.extend(_cell(stratum, arm, metric, mine, stats) for metric in metrics)
            if reference is not None and arm != reference:
                theirs = [p for p in in_stratum if p.arm == reference]
                for metric in metrics:
                    effect = _effect(stratum, arm, reference, metric, mine, theirs, stats)
                    if effect is not None:
                        effects.append(effect)
    return Scorecard(score.run_id, score.k, tuple(cells), tuple(effects), tuple(states))


def _fmt(interval: Interval | None) -> str:
    if interval is None:
        return "n/a"
    if interval.low is None or interval.high is None:
        return f"{interval.estimate:.3f} (descriptive, {interval.clusters} families)"
    return f"{interval.estimate:.3f} [{interval.low:.3f}, {interval.high:.3f}]"


def render_markdown(card: Scorecard) -> str:
    """The scorecard as Markdown: ITT and conditional tables, then effects, then run states and severe failures."""
    lines = [f"# Scorecard for run {card.run_id} at K={card.k}", ""]
    for title, pick in (("End-to-end (intention to treat)", "itt"), ("Conditional on completion", "conditional")):
        lines += [
            f"## {title}",
            "",
            "| stratum | arm | metric | eligible | value | completed | excluded |",
            "|---|---|---|---|---|---|---|",
        ]
        for c in card.cells:
            value = c.itt if pick == "itt" else c.conditional
            if pick == "itt" and c.metric in HARM_METRICS:
                continue
            lines.append(
                f"| {c.stratum} | {c.arm} | {c.metric} | {c.eligible} | {_fmt(value)} | {c.completed} | {c.excluded} |"
            )
        lines.append("")
    if card.effects:
        lines += ["## Paired difference against the reference (intention to treat)", ""]
        lines += ["| stratum | arm | reference | metric | pairs | difference |", "|---|---|---|---|---|---|"]
        lines += [
            f"| {e.stratum} | {e.arm} | {e.reference} | {e.metric} | {e.pairs} | {_fmt(e.difference)} |"
            for e in card.effects
        ]
        lines.append("")
    lines += ["## Run states and severe failures (beside, not inside, accuracy)", ""]
    lines += ["| stratum | arm | completed | states | forbidden source | authority confusion | wrong vintage |"]
    lines += ["|---|---|---|---|---|---|---|"]
    for s in card.states:
        shown = ", ".join(f"{k}={v}" for k, v in s.states.items()) or "none"
        lines.append(
            f"| {s.stratum} | {s.arm} | {s.completed} | {shown} | {s.severe['forbidden_source']} |"
            f" {s.severe['authority_confusion']} | {s.severe['wrong_vintage']} |"
        )
    return "\n".join(lines) + "\n"
