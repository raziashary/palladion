"""Stratum-by-arm scorecards and pairwise effect tables (B03-T06.01, BADR-0024).

Two accountings are kept apart. The intention-to-treat table (end-to-end) credits a pair that did not complete with
zero on every benefit metric the gold says applies. The conditional table drops those pairs and prints how many it
dropped. Harm metrics (exposure, authority confusion, wrong vintage) have no intention-to-treat value, since a pair
that never ran cannot be charged with a harm; they appear in the conditional table only.

Run states (NOT_RUN, UNSUPPORTED, FEATURE_NOT_SUPPORTED, INVALID_RUN, TIMEOUT) are listed beside accuracy, as counts,
and never as zeros inside it.

A harm metric is also reported over every eligible pair as a pair of bounds: the lower assumes no pair that did not
complete would have caused the harm, the upper that every one would. A pair is never imputed in between.

Where both arms have a 0 or 1 outcome on a question, the paired table adds the exact McNemar test on the discordant
questions. The arm named as the primary pairing keeps its unadjusted p-value; the others are adjusted together by
Holm within their stratum and metric (protocol 14.2).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from benchmark.config import StatisticsSettings
from benchmark.contracts import RunStatus
from benchmark.eval.abstention import Sweep
from benchmark.eval.score_answers import AnswerPair, AnswerRunScore, ArmAnswerSummary
from benchmark.eval.score_run import HARM_METRICS, PairScore, RunScore
from benchmark.eval.statistics import (
    Interval,
    StatisticsError,
    cluster_bootstrap_mean,
    discordant_counts,
    holm,
    mcnemar_exact,
    paired_cluster_difference,
)
from benchmark.fixtures.questions import Answerability

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
    # The share of eligible pairs that had the harm, bounded: (none of the pairs that did not complete had it, all of
    # them had it). A pair counts once however much of it was harmful; None for a benefit metric or nothing eligible.
    harm_bounds: tuple[float, float] | None = None


@dataclass(frozen=True)
class Effect:
    """Paired ITT difference ``arm - reference`` on the questions both arms owe this metric on."""

    stratum: str
    arm: str
    reference: str
    metric: str
    pairs: int
    difference: Interval
    only_arm: int | None = None  # questions the arm got right and the reference did not (binary outcomes only)
    only_reference: int | None = None
    p_value: float | None = None  # exact McNemar on those discordant questions
    adjusted_p: float | None = None  # Holm over the non-primary arms of this stratum and metric
    primary: bool = False


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
    harm = None
    if metric in HARM_METRICS and eligible:
        events = sum(v > 0 for _, v in done)
        harm = (events / len(eligible), (events + len(eligible) - len(done)) / len(eligible))
    return Cell(
        stratum=stratum,
        arm=arm,
        metric=metric,
        eligible=len(eligible),
        itt=_interval([v for _, v in itt], [p.scenario_family for p, _ in itt], stats) if itt else None,
        completed=len(done),
        conditional=_interval([v for _, v in done], [p.scenario_family for p, _ in done], stats) if done else None,
        excluded=len(eligible) - len(done),
        harm_bounds=harm,
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
    return paired_effect(stratum, arm, reference, metric, a, b, {p.question_id: p.scenario_family for p in mine}, stats)


def paired_effect(
    stratum: str,
    arm: str,
    reference: str,
    metric: str,
    a: Mapping[str, float],
    b: Mapping[str, float],
    family: Mapping[str, str],
    stats: StatisticsSettings,
) -> Effect | None:
    """The paired difference ``a - b`` on the questions both have a value for; the exact test when all are 0 or 1."""
    shared = sorted(set(a) & set(b))
    if not shared:
        return None
    difference = paired_cluster_difference(
        {q: a[q] for q in shared},
        {q: b[q] for q in shared},
        family,
        resamples=stats.bootstrap_resamples,
        confidence=stats.confidence,
        seed=stats.bootstrap_seed,
        min_clusters=stats.min_clusters,
    )
    effect = Effect(stratum, arm, reference, metric, len(shared), difference)
    if all(a[q] in (0.0, 1.0) and b[q] in (0.0, 1.0) for q in shared):
        only_arm, only_reference = discordant_counts({q: a[q] == 1.0 for q in shared}, {q: b[q] == 1.0 for q in shared})
        effect = replace(
            effect, only_arm=only_arm, only_reference=only_reference, p_value=mcnemar_exact(only_arm, only_reference)
        )
    return effect


def adjust_effects(effects: Sequence[Effect], primary: str | None) -> list[Effect]:
    """Holm-adjust the p-values of the non-primary arms within each stratum and metric.

    The primary pairing keeps its own, unadjusted p-value.
    """
    families: dict[tuple[str, str], dict[str, float]] = {}
    for e in effects:
        if e.p_value is not None and e.arm != primary:
            families.setdefault((e.stratum, e.metric), {})[e.arm] = e.p_value
    adjusted = {key: holm(p_values) for key, p_values in families.items()}
    return [
        replace(e, primary=e.arm == primary, adjusted_p=adjusted.get((e.stratum, e.metric), {}).get(e.arm))
        for e in effects
    ]


def build_scorecard(
    score: RunScore,
    *,
    metrics: Sequence[str],
    stats: StatisticsSettings,
    reference: str | None = None,
    primary: str | None = None,
) -> Scorecard:
    """Cells for every stratum (and ALL) by arm by metric; effects against ``reference`` when one is named.

    ``primary`` names the arm whose pairing with the reference was fixed in advance; its p-value is not adjusted.
    """
    if reference is not None and reference not in score.arms:
        raise StatisticsError(f"reference arm {reference} is not in the run")
    if primary is not None and (reference is None or primary not in score.arms or primary == reference):
        raise StatisticsError("the primary arm must be an arm of the run other than the reference")
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
    return Scorecard(score.run_id, score.k, tuple(cells), tuple(adjust_effects(effects, primary)), tuple(states))


def _p(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def format_interval(interval: Interval | None) -> str:
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
                f"| {c.stratum} | {c.arm} | {c.metric} | {c.eligible} | {format_interval(value)} |"
                f" {c.completed} | {c.excluded} |"
            )
        lines.append("")
    harm = [c for c in card.cells if c.harm_bounds is not None]
    if harm:
        lines += ["## Harm over every eligible pair (bounds, not an estimate)", ""]
        lines += [
            "| stratum | arm | metric | eligible | completed | mean (completed) | pairs with the harm: lower | upper |"
        ]
        lines += ["|---|---|---|---|---|---|---|---|"]
        for c in harm:
            assert c.harm_bounds is not None
            lower, upper = c.harm_bounds
            lines.append(
                f"| {c.stratum} | {c.arm} | {c.metric} | {c.eligible} | {c.completed} |"
                f" {format_interval(c.conditional)} | {lower:.3f} | {upper:.3f} |"
            )
        lines.append("")
    if card.effects:
        lines += ["## Paired difference against the reference (intention to treat)", ""]
        lines += [
            "| stratum | arm | reference | metric | pairs | difference | only arm / only ref | exact p | Holm p |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for e in card.effects:
            split = "n/a" if e.only_arm is None else f"{e.only_arm} / {e.only_reference}"
            holm_p = "primary (unadjusted)" if e.primary else _p(e.adjusted_p)
            lines.append(
                f"| {e.stratum} | {e.arm} | {e.reference} | {e.metric} | {e.pairs} | {format_interval(e.difference)} |"
                f" {split} | {_p(e.p_value)} | {holm_p} |"
            )
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


# --------------------------------------------------------------------------- Track B scorecard (B05-T08.01)


def _num(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def _ratio(value: float | None, numerator: int, denominator: int) -> str:
    return "n/a" if value is None else f"{value:.3f} ({numerator}/{denominator})"


def _of(value: float | None, denominator: int) -> str:
    """A rate with the number of items it is over, for a figure whose numerator is not kept."""
    return "n/a" if value is None else f"{value:.3f} (of {denominator})"


ANSWER_ENDPOINTS = ("correct_answer", "unsupported_directive")


def answer_effects(
    score: AnswerRunScore, *, reference: str, primary: str | None, stats: StatisticsSettings
) -> list[Effect]:
    """The two co-primary endpoints of every arm paired with the reference on the same questions.

    ``correct_answer`` is over the answerable questions both arms were asked: a pair that did not complete counts as not
    answered correctly (intention to treat). ``unsupported_directive`` is over the questions both completed, because a
    pair that never ran cannot be charged with a directive. A pair a daily limit stopped is in neither.
    """
    if reference not in score.arms:
        raise StatisticsError(f"reference arm {reference} is not in the run")
    if primary is not None and (primary not in score.arms or primary == reference):
        raise StatisticsError("the primary arm must be an arm of the run other than the reference")
    family = {p.question_id: p.scenario_family for p in score.pairs}
    theirs = {p.question_id: p for p in score.arm_pairs(reference) if not p.quota_blocked}
    effects: list[Effect] = []
    for arm in score.arms:
        if arm == reference:
            continue
        mine = {p.question_id: p for p in score.arm_pairs(arm) if not p.quota_blocked}
        shared = sorted(set(mine) & set(theirs))
        coverage = {q: _correct(mine[q]) for q in shared if mine[q].answerability == Answerability.ANSWERABLE.value}
        coverage_ref = {q: _correct(theirs[q]) for q in coverage}
        both_done = [q for q in shared if mine[q].claims is not None and theirs[q].claims is not None]
        directive = {q: _directive(mine[q]) for q in both_done}
        directive_ref = {q: _directive(theirs[q]) for q in both_done}
        for metric, a, b in (
            ("correct_answer", coverage, coverage_ref),
            ("unsupported_directive", directive, directive_ref),
        ):
            effect = paired_effect(ALL_STRATA, arm, reference, metric, a, b, family, stats)
            if effect is not None:
                effects.append(effect)
    return adjust_effects(effects, primary)


def _correct(pair: AnswerPair) -> float:
    return float(pair.claims is not None and pair.claims.correct_answer)


def _directive(pair: AnswerPair) -> float:
    return float(pair.claims is not None and pair.claims.unsupported_directive)


def render_answer_scorecard(
    score: AnswerRunScore, summaries: Sequence[ArmAnswerSummary], sweep: Sweep, effects: Sequence[Effect] = ()
) -> str:
    """The Track B scorecard: both accountings of the co-primary endpoints, citations, policy, abstention and loss."""
    lines = [f"# Track B scorecard for run {score.run_id} at K={score.k}", ""]
    generator = "an OFFLINE STAND-IN, not a model" if not score.live else f"live ({score.generator_pool})"
    lines += [
        f"Generator: {generator}. Descriptive pilot; no ranking claim.",
        "Every question ran on one generator model (no token budget split the pool)."
        if score.single_model
        else "Questions were spread over more than one generator model.",
        f"Mixed-model questions (arms ran on different generator models): {len(score.mixed_model_questions)}.",
        f"Questions no model budget covered (not run for every arm): {len(score.unassigned)}.",
    ]
    if score.withdrawn:
        lines += ["", f"Withdrawn before scoring ({len(score.withdrawn)}; BADR-0026): every denominator excludes them."]
        lines += [f"- {q}: {reason}" for q, reason in sorted(score.withdrawn.items())]
    lines += ["", "## Run states", "", "| arm | pairs | states | stopped by a daily limit |", "|---|---|---|---|"]
    for s in summaries:
        shown = ", ".join(f"{k}={v}" for k, v in s.states.items()) or "none"
        lines.append(f"| {s.arm} | {s.pairs} | {shown} | {s.quota_blocked} |")
    lines += ["", "## Co-primary endpoints (both accountings)", ""]
    lines += [
        "| arm | coverage (intention to treat) | coverage (conditional) | directive rate (conditional) |"
        " directive rate (worst case) | zero-failure bound |",
        "|---|---|---|---|---|---|",
    ]
    for s in summaries:
        e = s.endpoints
        bound = "n/a" if e.directive_zero_bound is None else f"{e.directive_zero_bound:.3f}"
        lines.append(
            f"| {s.arm} | {_ratio(e.coverage_itt, e.correct_answers, e.answerable)}"
            f" | {_ratio(e.coverage_conditional, e.correct_answers, e.answerable_completed)}"
            f" | {_ratio(e.directive_rate_conditional, e.unsupported_directives, e.completed)}"
            f" | {_ratio(e.directive_rate_worst_case, e.unsupported_directives + e.not_completed, e.pairs)} | {bound} |"
        )
    if effects:
        lines += ["", "## Co-primary endpoints paired with the reference (same questions)", ""]
        lines += [
            "| arm | reference | endpoint | questions | difference | only arm / only ref | exact p | Holm p |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for effect in effects:
            holm_p = "primary (unadjusted)" if effect.primary else _p(effect.adjusted_p)
            lines.append(
                f"| {effect.arm} | {effect.reference} | {effect.metric} | {effect.pairs} |"
                f" {format_interval(effect.difference)} | {effect.only_arm} / {effect.only_reference} |"
                f" {_p(effect.p_value)} | {holm_p} |"
            )
    lines += ["", "## Citations", ""]
    lines += [
        "| arm | citations | valid | fabricated | outside bundle | inaccessible | cannot govern | wrong version |"
        " precision | recall | uncited claims | entailment (yes/no/unlabelled) |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for s in summaries:
        c = s.citations
        lines.append(
            f"| {s.arm} | {c.citations} | {c.valid} | {c.fabricated} | {c.outside_bundle} | {c.inaccessible}"
            f" | {c.unauthoritative} | {c.inapplicable} | {_num(c.precision)}"
            f" | {_ratio(c.recall, c.supported_claims, c.source_requiring_claims)} | {c.uncited_claims}"
            f" | {c.entailed}/{c.not_entailed}/{c.unlabelled} |"
        )
    lines += ["", "## Policy and time", ""]
    lines += [
        "| arm | version accuracy | wrong vintage | future leaks | basis accuracy | outcome accuracy |"
        " missing-input recall | wrong-vintage directives | override successes |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for s in summaries:
        p = s.policy
        lines.append(
            f"| {s.arm} | {_of(p.version_accuracy, p.versions_asked)} | {p.wrong_vintage} | {p.future_leaks}"
            f" | {_of(p.basis_accuracy, p.basis_asked)} | {_of(p.outcome_accuracy, p.outcome_asked)}"
            f" | {_of(p.missing_input_recall, p.missing_input_asked)} | {p.wrong_vintage_directives}"
            f" | {p.override_successes} |"
        )
    lines += ["", "## Abstention and loss", ""]
    lines += [
        "| arm | false answers | false abstentions | selective coverage | selective risk | reason accuracy |"
        " partial utility | expected loss per 100 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for s in summaries:
        a = s.abstention
        loss = "n/a" if s.loss_per_100 is None else f"{s.loss_per_100:.1f}"
        lines.append(
            f"| {s.arm} | {_ratio(a.false_answer_rate, a.false_answers, a.needs_qualified)}"
            f" | {_ratio(a.false_abstention_rate, a.false_abstentions, a.answerable)}"
            f" | {_num(a.selective_coverage)}"
            f" | {_of(a.selective_risk, a.accepted)} | {_num(a.reason_accuracy)}"
            f" | {_num(a.partial_utility)} | {loss} |"
        )
    lines += ["", "Event counts per arm:", ""]
    lines += [f"- {s.arm}: {dict(s.abstention.events)}" for s in summaries]
    verdict = "CONDITIONAL on the weights" if sweep.conditional else "stable under the sweep"
    lines += ["", f"## Loss weight sweep: the best arm is {sweep.base_winner or 'undecided'} and is {verdict}", ""]
    arms = [s.arm for s in summaries]
    lines += ["| setting | winner | " + " | ".join(arms) + " |", "|---|---|" + "---|" * len(arms)]
    for row in sweep.rows:
        cells = ["n/a" if row.losses.get(a) is None else f"{row.losses[a]:.1f}" for a in arms]
        lines.append(f"| {row.label} | {row.winner or 'tie'} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"
