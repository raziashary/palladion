"""When a revision applies: one value object shared by the evidence resolver, the prefilter and coverage."""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

MAX_APPLICABILITY_INSTANTS = 8
MAX_EXTRA_INSTANTS = MAX_APPLICABILITY_INSTANTS - 1  # the evaluation instant takes the first place


@dataclass(frozen=True)
class Applicability:
    """The instants at which a revision may apply: the evaluation instant first, then trusted case instants.

    A revision applies when, at one same instant, it is inside its half-open validity window (`valid_from`
    inclusive, `valid_to` exclusive, no bound is open) and no successor has taken effect (ADR-0102). The
    constructor enforces what makes that sound: at least one instant, all timezone-aware, distinct, and bounded.
    """

    instants: tuple[datetime, ...]

    def __post_init__(self) -> None:
        if not self.instants:
            raise ValueError("Source applicability requires an instant")
        if any(instant.tzinfo is None or instant.utcoffset() is None for instant in self.instants):
            raise ValueError("Source applicability requires an aware instant")
        if len(set(self.instants)) != len(self.instants):
            raise ValueError("Source applicability instants must be distinct")
        if len(self.instants) > MAX_APPLICABILITY_INSTANTS:
            raise ValueError("Applicability instants exceed the bound")

    @classmethod
    def at(cls, primary: datetime, also: Iterable[datetime] = ()) -> Applicability:
        """The evaluation instant plus any further trusted instants; repeats are collapsed."""
        return cls(tuple(dict.fromkeys((primary, *also))))

    @property
    def primary(self) -> datetime:
        return self.instants[0]

    @property
    def also(self) -> tuple[datetime, ...]:
        return self.instants[1:]

    def admits(self, valid_from: str | None, valid_to: str | None, successor_effective_from: Sequence[str]) -> bool:
        """True when some instant is inside the window and before every successor's effective time."""
        return any(
            (valid_from is None or instant >= datetime.fromisoformat(valid_from))
            and (valid_to is None or instant < datetime.fromisoformat(valid_to))
            and not any(datetime.fromisoformat(effective) <= instant for effective in successor_effective_from)
            for instant in self.instants
        )
