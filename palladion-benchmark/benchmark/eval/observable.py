"""A measure a system cannot expose is NOT_OBSERVABLE, never zero (B07-T05.02, T06.01, T06.02, protocol 11 and 17).

An absent signal and a score of zero mean different things: a system that reports no tool arguments has not made
invalid calls. :class:`Rate` keeps the counts behind a proportion and has no value when nothing was eligible, and
:class:`NotObservable` carries the reason the measure cannot be taken. Both print what they are, so a report never
shows a bare number where the evidence is missing.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class NotObservable:
    """A measure the evidence does not allow, with the reason."""

    reason: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("NOT_OBSERVABLE needs a reason")

    def __str__(self) -> str:
        return f"NOT_OBSERVABLE ({self.reason})"


@dataclass(frozen=True)
class Rate:
    """``hits`` out of ``total`` eligible observations. With nothing eligible there is no value, which is not zero."""

    hits: int
    total: int

    def __post_init__(self) -> None:
        if self.total < 0 or not 0 <= self.hits <= self.total:
            raise ValueError(f"a rate needs 0 <= hits <= total, got {self.hits}/{self.total}")

    @property
    def value(self) -> float | None:
        return None if self.total == 0 else self.hits / self.total

    def __str__(self) -> str:
        return (
            "no eligible observation" if self.total == 0 else f"{self.hits}/{self.total} = {self.hits / self.total:.3f}"
        )


Measure = Rate | NotObservable


def render(measures: Mapping[str, Measure]) -> str:
    """One line per measure, the missing ones printed beside the scores."""
    return "\n".join(f"{name}: {measure}" for name, measure in measures.items())
