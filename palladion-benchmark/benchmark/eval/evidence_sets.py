"""Required Evidence Coverage: SlotCoverage@K and CompleteSet@K (B03-T02.01, protocol 8.2).

A record's required evidence is its satisfiable slots, each satisfied by any one of its alternative clauses. A
candidate satisfies a slot when it identity-matches one of the slot's alternatives (headline) or, separately, aligns to
it by text. Relevance is binary (BADR-0024). Records with no satisfiable, citable slot (unanswerable, blocked,
live-unavailable, or all live reads) are not applicable: the score is ``None``, never zero or one.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from benchmark.eval.normalize import Alignment
from benchmark.fixtures.questions import LIVE_PREFIX, EvidenceSlot, GoldRecord, SlotState, derive_minimal_sets

Unit = tuple[str, str]


def citable_slots(record: GoldRecord) -> list[EvidenceSlot]:
    """Satisfiable slots that a document retriever can be asked to find (live reads are not documents)."""
    return [
        s
        for s in record.slots
        if s.state is SlotState.SATISFIABLE and not any(c.doc_id.startswith(LIVE_PREFIX) for c in s.alternatives)
    ]


def matched_units(alignments: Iterable[Alignment], k: int, *, include_alignment: bool = False) -> set[Unit]:
    """Gold units credited by the top-K candidates: identity matches, plus text alignments when asked."""
    units: set[Unit] = set()
    for alignment in alignments:
        if alignment.rank <= k:
            units |= alignment.units()
            if include_alignment:
                units |= alignment.text_units()
    return units


def slot_is_covered(slot: EvidenceSlot, units: set[Unit]) -> bool:
    return any(c.key in units for c in slot.alternatives)


def covered_slots(
    record: GoldRecord, alignments: Sequence[Alignment], k: int, *, include_alignment: bool = False
) -> list[str]:
    units = matched_units(alignments, k, include_alignment=include_alignment)
    return [s.slot for s in citable_slots(record) if slot_is_covered(s, units)]


@dataclass(frozen=True)
class SetScores:
    slots_total: int
    slot_coverage: float | None
    complete_set: float | None
    alignment_slot_coverage: float | None
    alignment_complete_set: float | None


def _score(record: GoldRecord, units: set[Unit]) -> tuple[float | None, float | None]:
    slots = citable_slots(record)
    if not slots:
        return None, None
    coverage = sum(slot_is_covered(s, units) for s in slots) / len(slots)
    minimal = derive_minimal_sets(slots)
    complete = float(any(all(c.key in units for c in group) for group in minimal))
    return coverage, complete


def score_sets(record: GoldRecord, alignments: Sequence[Alignment], k: int) -> SetScores:
    coverage, complete = _score(record, matched_units(alignments, k))
    a_coverage, a_complete = _score(record, matched_units(alignments, k, include_alignment=True))
    return SetScores(len(citable_slots(record)), coverage, complete, a_coverage, a_complete)
