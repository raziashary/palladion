"""The document update stream: 1,000 deterministic events over a few fictional months (B07-T05.01, protocol 5.4).

An event is a committed change of the source state: a document is created, amended, approved, withdrawn, superseded,
reclassified, has an access role revoked, or is deleted. Gold for the update benchmark is the *committed* source state
at an instant, never the state any index happens to have reached: :func:`replay` folds the events up to an instant and
:func:`visible` says which documents a role may be shown then. Evaluator-side: nothing here is arm-visible, and the
metrics in ``benchmark/eval/cost_latency.py`` compare a system's observed answers with this state.

The stream is built from the published manifest records (their ids, states and version chains), so it needs nothing
hidden. The same records and seed always give the same stream.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from enum import StrEnum

from benchmark.fixtures import digest_of, sha256_hex
from benchmark.fixtures.knowledge import iso, parse_ts
from benchmark.fixtures.manifest import ManifestRecord

STREAM_START = "2026-06-01T00:00:00Z"
STREAM_DAYS = 120
DEFAULT_EVENTS = 1000


class UpdateError(ValueError):
    """The stream or a state is outside what the rules allow. The message names the rule."""


class EventKind(StrEnum):
    CREATE = "create"
    AMEND = "amend"
    APPROVE = "approve"
    WITHDRAW = "withdraw"
    SUPERSEDE = "supersede"
    RECLASSIFY = "reclassify"
    REVOKE_ACL = "revoke_acl"
    DELETE = "delete"


@dataclass(frozen=True)
class DocEvent:
    event_id: str
    at: str
    kind: EventKind
    doc_id: str
    detail: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DocState:
    """What is committed about one document at an instant."""

    created: bool = False
    approved: bool = False
    withdrawn: bool = False
    deleted: bool = False
    superseded_by: str | None = None
    revision: int = 0  # number of amendments
    classification: str = "internal"
    revoked_roles: frozenset[str] = frozenset()


def build_events(records: Sequence[ManifestRecord], seed: int, count: int = DEFAULT_EVENTS) -> tuple[DocEvent, ...]:
    """A valid lifecycle for documents drawn from ``records`` until ``count`` events exist, ordered in time.

    Every document's events follow its lifecycle (create, amend, approve, then change or end); a successor's approval
    supersedes the predecessor it names, one second later; no event follows a delete.
    """
    if count < 1 or not records:
        raise UpdateError("a stream needs documents and at least one event")
    rng = random.Random(int(sha256_hex(f"{seed}:updates")[:12], 16))
    by_version = {r.version_id: r for r in records if r.version_id}
    depth: dict[str, int] = {}
    root: dict[str, str] = {}
    for record in records:  # how many predecessors each document has; a chain that loops is refused
        links, cursor, seen = 0, record, {record.doc_id}
        while cursor.supersedes and cursor.supersedes in by_version:
            cursor = by_version[cursor.supersedes]
            if cursor.doc_id in seen:
                raise UpdateError(f"{record.doc_id}: the version chain loops")
            seen.add(cursor.doc_id)
            links += 1
        depth[record.doc_id] = links
        root[record.doc_id] = cursor.doc_id

    # whole version chains together, oldest first, so a successor is never cut off from the version it supersedes
    order = sorted(records, key=lambda r: (sha256_hex(f"{seed}:{root[r.doc_id]}"), depth[r.doc_id]))
    begin = parse_ts(STREAM_START)
    span_minutes = STREAM_DAYS * 24 * 60
    drafts: list[tuple[str, EventKind, str, dict[str, str]]] = []
    approved_at: dict[str, str] = {}
    deleted_at: dict[str, str] = {}
    for record in order:
        if len(drafts) >= count:
            break
        predecessor = by_version.get(record.supersedes) if record.supersedes else None
        floor = approved_at.get(predecessor.doc_id) if predecessor else None
        start = begin + timedelta(minutes=rng.randrange(span_minutes // 2))
        if floor is not None and start <= parse_ts(floor):
            start = parse_ts(floor) + timedelta(hours=rng.randint(1, 72))
        clock = start
        steps: list[tuple[EventKind, dict[str, str]]] = [(EventKind.CREATE, {})]
        steps += [(EventKind.AMEND, {}) for _ in range(rng.choice((0, 0, 1, 2)))]
        steps.append((EventKind.APPROVE, {}))
        later = rng.random()
        if later < 0.25:
            steps.append((EventKind.RECLASSIFY, {"classification": rng.choice(("restricted", "internal", "public"))}))
        elif later < 0.45 and record.acl_roles:
            steps.append((EventKind.REVOKE_ACL, {"role": rng.choice(sorted(record.acl_roles))}))
        elif later < 0.65:
            steps.append((EventKind.WITHDRAW, {}))
        if rng.random() < 0.12:
            steps.append((EventKind.DELETE, {}))
        for kind, detail in steps:
            clock += timedelta(minutes=rng.randint(5, 60 * 24 * 3))
            if kind is EventKind.APPROVE:
                approved_at[record.doc_id] = iso(clock)
            drafts.append((iso(clock), kind, record.doc_id, detail))
            if kind is EventKind.DELETE:
                deleted_at[record.doc_id] = iso(clock)
            # a predecessor already deleted has nothing left to supersede
            if (
                kind is EventKind.APPROVE
                and predecessor is not None
                and not _deleted_by(deleted_at, predecessor, clock)
            ):
                drafts.append((iso(clock + timedelta(seconds=1)), EventKind.SUPERSEDE, predecessor.doc_id,
                               {"by": record.doc_id}))  # fmt: skip
    drafts.sort(key=lambda d: (d[0], d[2], d[1].value))
    events = tuple(
        DocEvent(f"ev-{number:04d}", at, kind, doc_id, detail)
        for number, (at, kind, doc_id, detail) in enumerate(drafts[:count], start=1)
    )
    if len(events) < count:
        raise UpdateError(f"the records support only {len(events)} events, not {count}")
    validate_events(events, records)
    return events


def _deleted_by(deleted_at: Mapping[str, str], record: ManifestRecord, instant: datetime) -> bool:
    ended = deleted_at.get(record.doc_id)
    return ended is not None and parse_ts(ended) <= instant


def apply(states: dict[str, DocState], event: DocEvent) -> None:
    """Fold one event into the committed state. An event that the lifecycle forbids is an error, not a no-op."""
    state = states.get(event.doc_id, DocState())
    kind = event.kind
    if kind is EventKind.CREATE:
        if state.created:
            raise UpdateError(f"{event.doc_id}: created twice")
        states[event.doc_id] = DocState(created=True)
        return
    if not state.created or state.deleted:
        raise UpdateError(f"{event.doc_id}: {kind.value} on a document that does not exist")
    if kind is EventKind.AMEND:
        states[event.doc_id] = replace(state, revision=state.revision + 1)
    elif kind is EventKind.APPROVE:
        if state.approved:
            raise UpdateError(f"{event.doc_id}: approved twice")
        states[event.doc_id] = replace(state, approved=True)
    elif kind is EventKind.WITHDRAW:
        states[event.doc_id] = replace(state, withdrawn=True)
    elif kind is EventKind.SUPERSEDE:
        states[event.doc_id] = replace(state, superseded_by=event.detail["by"])
    elif kind is EventKind.RECLASSIFY:
        states[event.doc_id] = replace(state, classification=event.detail["classification"])
    elif kind is EventKind.REVOKE_ACL:
        states[event.doc_id] = replace(state, revoked_roles=state.revoked_roles | {event.detail["role"]})
    elif kind is EventKind.DELETE:
        states[event.doc_id] = replace(state, deleted=True)


def replay(events: Sequence[DocEvent], at: str) -> dict[str, DocState]:
    """The committed state after every event at or before ``at``. Same events and instant, same result."""
    instant = parse_ts(at)
    states: dict[str, DocState] = {}
    for event in events:
        if parse_ts(event.at) <= instant:
            apply(states, event)
    return states


def shown(state: DocState, record: ManifestRecord, role: str) -> bool:
    """Whether one document in ``state`` may be shown to ``role``: approved, not withdrawn, superseded or deleted, and
    the role is in the access list and not revoked."""
    if not state.created or not state.approved:
        return False
    if state.withdrawn or state.deleted or state.superseded_by or role in state.revoked_roles:
        return False
    return not record.acl_roles or role in record.acl_roles


def visible(states: Mapping[str, DocState], records: Mapping[str, ManifestRecord], role: str) -> frozenset[str]:
    """Documents a role may be shown from the committed state (see :func:`shown`)."""
    return frozenset(
        doc_id for doc_id, state in states.items() if (record := records.get(doc_id)) and shown(state, record, role)
    )


def validate_events(events: Sequence[DocEvent], records: Sequence[ManifestRecord]) -> None:
    """Ids unique and ordered, times non-decreasing, every document known, and the lifecycle respected throughout."""
    known = {r.doc_id for r in records}
    if len({e.event_id for e in events}) != len(events):
        raise UpdateError("duplicate event id")
    times = [parse_ts(e.at) for e in events]
    if times != sorted(times):
        raise UpdateError("events run backwards in time")
    states: dict[str, DocState] = {}
    for event in events:
        if event.doc_id not in known or (event.kind is EventKind.SUPERSEDE and event.detail.get("by") not in known):
            raise UpdateError(f"{event.event_id}: unknown document")
        apply(states, event)


def snapshot_times(events: Sequence[DocEvent], count: int) -> tuple[str, ...]:
    """``count`` evenly spaced index snapshot instants across the stream, after its first event and at its last."""
    if count < 1 or not events:
        raise UpdateError("snapshots need events and a positive count")
    first, last = parse_ts(events[0].at), parse_ts(events[-1].at)
    step = (last - first) / count
    return tuple(iso(first + step * (i + 1)) for i in range(count))


def stream_digest(events: Sequence[DocEvent]) -> str:
    return digest_of([{"id": e.event_id, "at": e.at, "kind": e.kind.value, "doc": e.doc_id, "detail": dict(e.detail)}
                      for e in events])  # fmt: skip
