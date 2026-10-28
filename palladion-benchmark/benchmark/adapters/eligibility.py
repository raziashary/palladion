"""Which documents a question may be answered from at its own time: approval, window, supersession (BADR-0047).

Palladion offers the index only the documents that are approved and, at one instant of the question, inside their
validity window with no successor yet in effect, a revoked successor counting as in effect (its ADR-0102, ADR-0108);
a question that names a version (``POL-004@v1``) is answered by that version alone, and by nothing of that family when
the version is not retrievable or does not exist (its ADR-0110). The other arms here rank the whole published
namespace, so a gain that Palladion shows over them mixes what its design does with what a rule does. R3f is R3 plus
this rule, so the two can be told apart.

The rule is computed from the published manifest alone (state, window, ``supersedes``, family), the same facts the
adapter sends Palladion when it loads the corpus; nothing is read from Palladion (BADR-0002). It mirrors Palladion's
rule; it is not Palladion's code, and the arm's description says so. One difference is not removed: Palladion counts
``FAMILY@vN`` as the Nth version of the family it holds, the manifest names versions by their ids, and the two agree
only while a family's ids run without gaps.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from benchmark.adapters.bm25 import identifiers
from benchmark.adapters.common import PublishedView
from benchmark.contracts import RetrievalRequest
from benchmark.fixtures.manifest import ManifestRecord

# The states Palladion approves (withdrawn is approved, then revoked); drafts and unapproved proposals never are.
RETRIEVABLE_STATES = frozenset({"approved", "retired", "non_normative"})
# A revoked successor still ends its predecessor (Palladion's ADR-0108), so a withdrawn version names a predecessor too.
RETIRING_STATES = RETRIEVABLE_STATES | {"withdrawn"}


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value)


class Eligibility:
    """The documents a request may be answered from, from its evaluation and event times and the versions it names."""

    def __init__(self, view: PublishedView) -> None:
        self._records = {r.doc_id: r for r in view.records if r.registry_state in RETRIEVABLE_STATES}
        # A predecessor stops applying when an approved successor that names it takes effect (its valid_from), even if
        # that successor was revoked since.
        successors: dict[str, list[datetime]] = defaultdict(list)
        for record in view.records:
            if record.registry_state in RETIRING_STATES and record.supersedes and record.valid_from is not None:
                successors[record.supersedes].append(_instant(record.valid_from))
        self._successors = {doc_id: tuple(times) for doc_id, times in successors.items()}
        self._versions: dict[str, ManifestRecord] = {
            r.version_id.casefold(): r for r in self._records.values() if r.version_id and r.family_id
        }
        self._families = {r.family_id.casefold(): r.family_id for r in view.records if r.family_id}
        self._memo: dict[tuple[tuple[datetime, ...], tuple[str, ...]], frozenset[str]] = {}

    def documents(self, request: RetrievalRequest) -> frozenset[str]:
        instants = tuple(dict.fromkeys(_instant(t) for t in (request.evaluation_time, request.event_time) if t))
        key = (instants, tuple(identifiers(request.query)))
        if key not in self._memo:  # the same instants and versions give the same documents
            self._memo[key] = self._eligible(*key)
        return self._memo[key]

    def _eligible(self, instants: tuple[datetime, ...], named: tuple[str, ...]) -> frozenset[str]:
        # A family the question names a version of is answered by the named versions that are retrievable, so a
        # withdrawn or nonexistent version leaves the family with nothing.
        allowed: dict[str, set[str]] = {}
        for token in named:
            family, marker, _ = token.rpartition("@v")
            family_id = self._families.get(family) if marker else None
            if family_id is not None:
                allowed.setdefault(family_id, set())
                if token in self._versions:
                    allowed[family_id].add(self._versions[token].doc_id)
        return frozenset(
            doc_id
            for doc_id, record in self._records.items()
            if (doc_id in allowed[record.family_id] if record.family_id in allowed else self._applies(record, instants))
        )

    def _applies(self, record: ManifestRecord, instants: tuple[datetime, ...]) -> bool:
        """Some instant is inside the half-open window and before every successor's effective time."""
        start = None if record.valid_from is None else _instant(record.valid_from)
        end = None if record.valid_to is None else _instant(record.valid_to)
        later = self._successors.get(record.doc_id, ())
        return any(
            (start is None or instant >= start)
            and (end is None or instant < end)
            and not any(t <= instant for t in later)
            for instant in instants
        )

    def describe(self) -> dict[str, Any]:
        return {
            "rule": "approved, inside the validity window at the evaluation or event time, no successor in effect "
            "(a revoked successor counts); a named version (FAMILY@vN) is answered by that version alone, or by "
            "nothing of its family when it is not retrievable",
            "mirrors": "Palladion's applicability rule (its ADR-0102, ADR-0110), computed from the manifest only",
            "retrievable_states": sorted(RETRIEVABLE_STATES),
        }
