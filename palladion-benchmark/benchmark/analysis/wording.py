"""Wording sensitivity: how a system's result moves when the same questions are asked in other words (BADR-0047).

The questions of the benchmark come from one generator, so a system may have learned its phrasing. A model of another
family rewrote them; the variants keep every identifier, number and negation count. The same system is then scored on
the same questions in both wordings, and the paired difference (variant minus original) says how much the wording
moved the result. It is a measure of sensitivity, not a claim: a rewrite can still change meaning in ways the check
does not read, and a second run of the original questions is the control for what mere re-running does (Palladion's
lists repeat for 92 to 95 percent of questions on a fresh load).

Only totals leave this module: no function returns or prints a question or a per-question value.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from benchmark.analysis.tables import Effect, itt_value, paired_effect
from benchmark.config import StatisticsSettings
from benchmark.eval.score_run import PairScore, RunScore
from benchmark.eval.statistics import StatisticsError

_WORD = re.compile(r"[^\W_]+(?:'[^\W_]+)?")


class WordingError(StatisticsError):
    """Two runs cannot be compared as the same questions in two wordings."""


@dataclass(frozen=True)
class Sensitivity:
    arm: str
    questions: int
    original: float  # mean of the metric over the questions, original wording (or the first run)
    variant: float  # the same over the same questions, other wording (or the second run)
    effect: Effect  # variant minus original, with the family-clustered interval and the discordant counts


def _values(pairs: Sequence[PairScore], metric: str) -> dict[str, float]:
    return {p.question_id: v for p in pairs if (v := itt_value(p, metric)) is not None}


def compare(
    original: RunScore, variant: RunScore, arms: Sequence[str], metric: str, stats: StatisticsSettings
) -> tuple[Sensitivity, ...]:
    """Each arm's paired difference between two scored runs over the questions both scored and both owe the metric."""
    family = {p.question_id: p.scenario_family for p in original.pairs}
    found: list[Sensitivity] = []
    for arm in arms:
        before, after = _values(original.arm_pairs(arm), metric), _values(variant.arm_pairs(arm), metric)
        shared = sorted(set(before) & set(after))
        if not shared:
            raise WordingError(f"{arm} has no question scored in both runs")
        effect = paired_effect("ALL", arm, "original", metric, after, before, family, stats)
        assert effect is not None
        found.append(
            Sensitivity(
                arm,
                len(shared),
                sum(before[q] for q in shared) / len(shared),
                sum(after[q] for q in shared) / len(shared),
                effect,
            )
        )
    return tuple(found)


def change_share(original: str, rewrite: str) -> float:
    """The share of the words of the two texts that only one of them has (Jaccard distance over case-folded words)."""
    a = {w.casefold() for w in _WORD.findall(original)}
    b = {w.casefold() for w in _WORD.findall(rewrite)}
    return 0.0 if not (a | b) else 1.0 - len(a & b) / len(a | b)
