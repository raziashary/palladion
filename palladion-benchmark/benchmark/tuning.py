"""The tuning budget every arm gets on the development worlds, and how a setting is chosen (B08-T02.01, BADR-0047).

Palladion was tuned on the smoke split while the other arms were not, so a gain over them mixes design with effort.
Every arm now gets the same budget: one baseline run and at most six one-lever trials on the development worlds, each
logged whether it helped or not. The setting that scored best is kept only when it beats the baseline by a stated
margin, so a lucky trial is not mistaken for an improvement; otherwise the defaults stay. The chosen settings are frozen
and sealed before the test worlds are touched, and the log shows every trial, not only the winner.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from benchmark.contracts import ContractError

MAX_TRIALS = 6
BASELINE = "baseline"
METRIC = "complete_set_at_k"


class TuningError(ContractError):
    """A trial cannot be logged, or a setting cannot be chosen from the log."""


@dataclass(frozen=True)
class Trial:
    arm: str
    name: str  # "baseline" or "lever=value"
    settings: Mapping[str, float | int]  # the full levers the trial ran with
    worlds: tuple[str, ...]
    pairs: int
    scores: Mapping[str, float]  # metric -> pooled intention-to-treat mean over the development worlds

    @property
    def is_baseline(self) -> bool:
        return self.name == BASELINE

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm": self.arm,
            "name": self.name,
            "settings": dict(self.settings),
            "worlds": list(self.worlds),
            "pairs": self.pairs,
            "scores": dict(self.scores),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Trial:
        return cls(
            str(data["arm"]), str(data["name"]), dict(data["settings"]), tuple(data["worlds"]), int(data["pairs"]),
            {str(k): float(v) for k, v in data["scores"].items()},
        )  # fmt: skip


def one_lever(base: Mapping[str, float | int], lever: str, value: float | int) -> dict[str, float | int]:
    """The base levers with one changed; a lever the arm does not have, or the value it already has, is refused."""
    if lever not in base:
        raise TuningError(f"{lever} is not a lever ({', '.join(sorted(base))})")
    if type(value) is not type(base[lever]) and not (isinstance(base[lever], float) and isinstance(value, int)):
        raise TuningError(f"{lever} takes a {type(base[lever]).__name__}")
    if value == base[lever]:
        raise TuningError(f"{lever}={value} is the baseline, not a trial")
    return {**base, lever: value}


class TuningLog:
    """An append-only file of trials. It enforces the budget and one run per (arm, trial, worlds)."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def read(self) -> list[Trial]:
        if not self.path.exists():
            return []
        try:
            return [Trial.from_dict(json.loads(line)) for line in self.path.read_text(encoding="utf-8").splitlines()]
        except (ValueError, KeyError, TypeError) as error:
            raise TuningError(f"{self.path.name} is not a tuning log") from error

    def spent(self, arm: str) -> int:
        return sum(1 for t in self.read() if t.arm == arm and not t.is_baseline)

    def append(self, trial: Trial) -> None:
        held = self.read()
        if any((t.arm, t.name, t.worlds) == (trial.arm, trial.name, trial.worlds) for t in held):
            raise TuningError(f"{trial.arm} {trial.name} on {','.join(trial.worlds)} is already in the log")
        if not trial.is_baseline and self.spent(trial.arm) >= MAX_TRIALS:
            raise TuningError(f"{trial.arm} has used its {MAX_TRIALS} trials")
        if METRIC not in trial.scores:
            raise TuningError(f"a trial records {METRIC}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(trial.to_dict(), sort_keys=True) + "\n")


def choose(trials: Sequence[Trial], arm: str, *, min_gain: float) -> Trial:
    """The arm's best trial when it beats the baseline by ``min_gain`` or more, else the baseline.

    Ties go to the earlier trial, so the defaults win a tie. Every trial must have run on the baseline's worlds.
    """
    mine = [t for t in trials if t.arm == arm]
    baselines = [t for t in mine if t.is_baseline]
    if len(baselines) != 1:
        raise TuningError(f"{arm} needs exactly one baseline in the log, found {len(baselines)}")
    base = baselines[0]
    if min_gain < 0:
        raise TuningError("the margin is zero or more")
    others = [t for t in mine if not t.is_baseline]
    if any(t.worlds != base.worlds for t in others):
        raise TuningError(f"{arm} has trials on other worlds than its baseline")
    best = base
    for trial in others:
        if trial.scores[METRIC] > best.scores[METRIC]:
            best = trial
    gain = round(best.scores[METRIC] - base.scores[METRIC], 9)  # 0.24 - 0.20 is 0.0399999..., a gain of 0.04
    return best if gain >= min_gain else base
