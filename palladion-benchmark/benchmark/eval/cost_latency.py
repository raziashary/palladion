"""Latency and cost accounting from ledger records (B03-T05.01, protocol 8.5 and 10, BADR-0024).

Two rules hold throughout. A timed-out call is censored: its duration is "at least the deadline", never an observed
latency, so percentiles are computed over completed calls and the timeouts are reported beside them. A missing cost
stays missing: nothing is summed as zero unless the system reported zero. Offline (index build) cost comes from the
index record an arm writes and is spread over an amortization horizon the caller states.

The last section measures update consistency (B07-T05.03): how long a *reader* kept answering differently from the
committed source state after an event. It lives here because it is time accounting, but it is scored against the
update stream's committed state, never against retrieval gold, and it never looks inside an index.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from benchmark.contracts import RunStatus
from benchmark.eval.observable import NotObservable
from benchmark.eval.statistics import StatisticsError, quantile
from benchmark.fixtures.knowledge import parse_ts
from benchmark.fixtures.manifest import ManifestRecord
from benchmark.fixtures.updates import DocEvent, DocState, EventKind, UpdateError, apply, shown
from benchmark.runner import LedgerRecord

LATENCY_LEVELS = (0.50, 0.90, 0.95, 0.99)


@dataclass(frozen=True)
class LatencySummary:
    """Percentiles over completed calls, and the censored timeouts reported beside them."""

    completed: int
    percentiles: Mapping[str, float]
    timeouts: int
    deadline_ms: float | None
    percentiles_with_timeouts_at_deadline: Mapping[str, float] | None  # a lower bound, not an observation


@dataclass(frozen=True)
class CostSummary:
    """Self-reported cost over the records that reported one. ``total_usd`` is None when no record did."""

    observed: int
    missing: int
    total_usd: float | None
    mean_usd: float | None


def level_name(level: float) -> str:
    return f"p{round(level * 100)}"


def _percentiles(values: Sequence[float]) -> dict[str, float]:
    return {level_name(level): quantile(values, level) for level in LATENCY_LEVELS}


def final_records(records: Sequence[LedgerRecord]) -> list[LedgerRecord]:
    return [r for r in records if r.is_final]


def latency_summary(records: Sequence[LedgerRecord], *, deadline_ms: float | None) -> LatencySummary:
    """Latency of the final records: completed calls give percentiles; a TIMEOUT is counted, never read as a latency."""
    finals = final_records(records)
    completed = [r.duration_ms for r in finals if r.status is RunStatus.OK and r.duration_ms is not None]
    timeouts = sum(r.status is RunStatus.TIMEOUT for r in finals)
    with_deadline: dict[str, float] | None = None
    if timeouts:
        if deadline_ms is None:
            raise StatisticsError("timed-out calls cannot be reported without the deadline that cut them off")
        with_deadline = _percentiles([*completed, *([deadline_ms] * timeouts)])
    return LatencySummary(
        completed=len(completed),
        percentiles=_percentiles(completed) if completed else {},
        timeouts=timeouts,
        deadline_ms=deadline_ms,
        percentiles_with_timeouts_at_deadline=with_deadline,
    )


def _reported_cost(record: LedgerRecord) -> float | None:
    payload = record.payload
    if not isinstance(payload, Mapping):
        return None
    value = payload.get("cost_usd")
    return None if value is None else float(value)


def online_cost(records: Sequence[LedgerRecord]) -> CostSummary:
    """Cost reported across the final records, whatever their state: spend on a failed call is still spend.

    A record that reported no cost is counted as missing, never as zero, so a run state cannot hide unknown cost.
    """
    costs = [_reported_cost(r) for r in final_records(records)]
    seen = [c for c in costs if c is not None]
    total = sum(seen) if seen else None
    return CostSummary(
        observed=len(seen),
        missing=len(costs) - len(seen),
        total_usd=total,
        mean_usd=None if total is None else total / len(seen),
    )


@dataclass(frozen=True)
class OfflineCost:
    """What an arm recorded about building its index. Either value may be unknown."""

    build_ms: float | None
    cost_usd: float | None
    extraction_calls: float | None = None
    extraction_prompt_tokens: float | None = None
    extraction_completion_tokens: float | None = None
    storage_bytes: float | None = None

    @classmethod
    def from_index_stats(cls, stats: Mapping[str, object]) -> OfflineCost:
        def number(key: str) -> float | None:
            value = stats.get(key)
            if value is None:
                return None
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise StatisticsError(f"index record field {key} must be a number or null")
            return float(value)

        return cls(
            number("build_ms"),
            number("build_cost_usd"),
            number("extraction_calls"),
            number("extraction_prompt_tokens"),
            number("extraction_completion_tokens"),
            number("storage_bytes"),
        )


def amortized_cost_per_query(
    offline: OfflineCost, online_mean_usd: float | None, *, amortization_queries: int
) -> float | None:
    """Online mean plus the build cost spread over the stated number of queries; unknown if either part is unknown."""
    if amortization_queries < 1:
        raise StatisticsError("an amortization horizon needs at least one query")
    if offline.cost_usd is None or online_mean_usd is None:
        return None
    return online_mean_usd + offline.cost_usd / amortization_queries


# --------------------------------------------------------------------------- update consistency (B07-T05.03)

INDEX_REASON = "index-internal staleness is not observed; only what the reader returned is"
CLASSIFICATION_REASON = "a search result does not show a document's classification, so a reclassification is not seen"
NO_PROBE_REASON = "no probe of the document was taken between this event and the next change to it"
NO_REVISION_REASON = "the reader's probes carry no revision, so an amendment cannot be seen"


@dataclass(frozen=True)
class ReaderProbe:
    """One search that must or must not return a document, taken at ``at`` for ``role``.

    ``returned`` is whether the reader gave the document back; ``revision`` is the amendment count of the text it gave
    back, when the reader exposes one.
    """

    at: str
    doc_id: str
    role: str
    returned: bool
    revision: int | None = None


@dataclass(frozen=True)
class ExposureWindow:
    """How long the reader disagreed with the committed state after one event, as bounds from the probes taken.

    ``lower_s`` is the time to the last probe that disagreed (0 when none did); ``upper_s`` is the time to the first
    probe after which every probe agreed, or None when the reader never settled within the probes (censored: at least
    ``lower_s``). The bounds are never negative.
    """

    event_id: str
    kind: EventKind
    doc_id: str
    probes: int
    lower_s: float
    upper_s: float | None

    @property
    def exposed(self) -> bool:
        return self.lower_s > 0 or self.upper_s is None


@dataclass(frozen=True)
class KindSummary:
    measured: int
    exposed: int
    censored: int
    max_lower_s: float
    mean_lower_s: float


@dataclass(frozen=True)
class UpdateConsistency:
    windows: tuple[ExposureWindow, ...]
    by_kind: Mapping[str, KindSummary]
    unmeasured: Mapping[str, NotObservable]  # event id -> why no window exists
    index_internal: NotObservable


def update_consistency(
    events: Sequence[DocEvent], records: Mapping[str, ManifestRecord], probes: Sequence[ReaderProbe]
) -> UpdateConsistency:
    """Exposure windows of a reader against the committed source state of ``events``.

    Each probe is compared with the state its document had when the probe was taken (the as-of rule), so a reader that
    returns a document that was withdrawn or superseded, or hides one that was approved, disagrees. An event is
    measured over the probes of its document up to the next change to that document; an event that changes nothing a
    search can show gets no window and the reason is recorded.
    """
    timeline: dict[str, list[tuple[DocEvent, DocState, DocState]]] = defaultdict(list)
    states: dict[str, DocState] = {}
    for event in sorted(events, key=lambda e: parse_ts(e.at)):
        if event.doc_id not in records:
            raise StatisticsError(f"an event names a document the records do not hold: {event.doc_id}")
        before = states.get(event.doc_id, DocState())
        try:
            apply(states, event)
        except UpdateError as exc:
            raise StatisticsError(f"the events are not a valid stream: {exc}") from exc
        timeline[event.doc_id].append((event, before, states[event.doc_id]))
    by_doc: dict[str, list[ReaderProbe]] = defaultdict(list)
    for probe in sorted(probes, key=lambda p: parse_ts(p.at)):
        if probe.doc_id not in records:
            raise StatisticsError(f"a probe names a document the records do not hold: {probe.doc_id}")
        by_doc[probe.doc_id].append(probe)

    windows: list[ExposureWindow] = []
    unmeasured: dict[str, NotObservable] = {}
    for doc_id, steps in timeline.items():
        record = records[doc_id]
        for position, (event, before, after) in enumerate(steps):
            if event.kind is EventKind.RECLASSIFY:
                unmeasured[event.event_id] = NotObservable(CLASSIFICATION_REASON)
                continue
            if event.kind is EventKind.AMEND and not any(p.revision is not None for p in by_doc[doc_id]):
                unmeasured[event.event_id] = NotObservable(NO_REVISION_REASON)
                continue
            start = parse_ts(event.at)
            end = parse_ts(steps[position + 1][0].at) if position + 1 < len(steps) else None
            taken = [
                p
                for p in by_doc[doc_id]
                if parse_ts(p.at) >= start
                and (end is None or parse_ts(p.at) < end)
                and _affected(event, before, after, record, p)
            ]
            if taken:
                windows.append(_window(event, after, record, taken))
            else:
                unmeasured[event.event_id] = NotObservable(NO_PROBE_REASON)
    return UpdateConsistency(tuple(windows), _summaries(windows), unmeasured, NotObservable(INDEX_REASON))


def _affected(event: DocEvent, before: DocState, after: DocState, record: ManifestRecord, probe: ReaderProbe) -> bool:
    """Whether the event changes what this probe must see."""
    if event.kind is EventKind.AMEND:
        return probe.revision is not None
    return shown(before, record, probe.role) != shown(after, record, probe.role)


def _agrees(event: DocEvent, after: DocState, record: ManifestRecord, probe: ReaderProbe) -> bool:
    if probe.returned != shown(after, record, probe.role):
        return False
    return event.kind is not EventKind.AMEND or not probe.returned or probe.revision == after.revision


def _window(event: DocEvent, after: DocState, record: ManifestRecord, probes: Sequence[ReaderProbe]) -> ExposureWindow:
    start = parse_ts(event.at)
    verdicts = [(parse_ts(p.at), _agrees(event, after, record, p)) for p in probes]
    last_bad = max((at for at, ok in verdicts if not ok), default=None)
    settled: float | None
    if last_bad is None:
        lower, settled = 0.0, (verdicts[0][0] - start).total_seconds()
    else:
        later = [at for at, _ in verdicts if at > last_bad]
        lower = (last_bad - start).total_seconds()
        settled = (min(later) - start).total_seconds() if later else None
    return ExposureWindow(event.event_id, event.kind, event.doc_id, len(probes), lower, settled)


def _summaries(windows: Sequence[ExposureWindow]) -> dict[str, KindSummary]:
    grouped: dict[str, list[ExposureWindow]] = defaultdict(list)
    for window in windows:
        grouped[window.kind.value].append(window)
    return {
        kind: KindSummary(
            measured=len(items),
            exposed=sum(w.exposed for w in items),
            censored=sum(w.upper_s is None for w in items),
            max_lower_s=max(w.lower_s for w in items),
            mean_lower_s=sum(w.lower_s for w in items) / len(items),
        )
        for kind, items in sorted(grouped.items())
    }
