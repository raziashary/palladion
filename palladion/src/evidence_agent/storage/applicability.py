"""When a revision applies: one value object shared by the evidence resolver, the prefilter and coverage."""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

MAX_APPLICABILITY_INSTANTS = 8
MAX_EXTRA_INSTANTS = MAX_APPLICABILITY_INSTANTS - 1  # the evaluation instant takes the first place
MAX_NAMED_VERSIONS = 8


@dataclass(frozen=True)
class Applicability:
    """The instants at which a revision may apply: the evaluation instant first, then trusted case instants.

    A revision applies when, at one same instant, it is inside its half-open validity window (`valid_from`
    inclusive, `valid_to` exclusive, no bound is open) and no successor has taken effect (ADR-0102). The
    constructor enforces what makes that sound: at least one instant, all timezone-aware, distinct, and bounded.
    A question that names a version of a family (`POL-1@v2`) asks for that revision, so its window and successors do
    not apply to it and no other revision of that family does (ADR-0110).
    """

    instants: tuple[datetime, ...]
    # Versions the question names: each family with the revisions asked for, none when the family has no such version.
    # A named family is answered by those revisions alone, whatever their windows or successors (ADR-0110).
    named: tuple[tuple[str, tuple[str, ...]], ...] = ()

    def __post_init__(self) -> None:
        if not self.instants:
            raise ValueError("Source applicability requires an instant")
        if any(instant.tzinfo is None or instant.utcoffset() is None for instant in self.instants):
            raise ValueError("Source applicability requires an aware instant")
        if len(set(self.instants)) != len(self.instants):
            raise ValueError("Source applicability instants must be distinct")
        if len(self.instants) > MAX_APPLICABILITY_INSTANTS:
            raise ValueError("Applicability instants exceed the bound")
        if len({family for family, _ in self.named}) != len(self.named) or sum(
                len(revisions) for _, revisions in self.named) > MAX_NAMED_VERSIONS:
            raise ValueError("Named versions must be distinct families within the bound")

    @classmethod
    def at(cls, primary: datetime, also: Iterable[datetime] = ()) -> Applicability:
        """The evaluation instant plus any further trusted instants; repeats are collapsed."""
        return cls(tuple(dict.fromkeys((primary, *also))))

    def naming(self, versions: Iterable[tuple[str, str | None]]) -> Applicability:
        """The same instants with the versions the question names, as (family ID, revision ID or None) pairs."""
        by_family: dict[str, list[str]] = {}
        for family, revision in versions:
            by_family.setdefault(family, [])
            if revision is not None and revision not in by_family[family]:
                by_family[family].append(revision)
        return Applicability(self.instants, tuple((family, tuple(revisions)) for family, revisions in by_family.items()))

    @property
    def primary(self) -> datetime:
        return self.instants[0]

    @property
    def also(self) -> tuple[datetime, ...]:
        return self.instants[1:]

    def admits(self, revision_id: str, family_id: str, valid_from: str | None, valid_to: str | None,
               successor_effective_from: Sequence[str]) -> bool:
        """True when the revision is one of the versions its family was named for, or, for a family not named, when some
        instant is inside the window and before every successor's effective time."""
        for family, revisions in self.named:
            if family == family_id:
                return revision_id in revisions
        return any(
            (valid_from is None or instant >= datetime.fromisoformat(valid_from))
            and (valid_to is None or instant < datetime.fromisoformat(valid_to))
            and not any(datetime.fromisoformat(effective) <= instant for effective in successor_effective_from)
            for instant in self.instants
        )
