"""Update consistency and stale-index exposure (B07-T05.03): a lagging reader is exposed, a consistent one is not."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import timedelta
from pathlib import Path

import pytest

from benchmark.adapters.common import PublishedView
from benchmark.eval.cost_latency import ReaderProbe, update_consistency
from benchmark.eval.observable import NotObservable
from benchmark.eval.statistics import StatisticsError
from benchmark.fixtures.knowledge import iso, parse_ts
from benchmark.fixtures.manifest import ManifestRecord
from benchmark.fixtures.updates import DocEvent, EventKind, build_events, replay, shown

ROLE = "support_l1"
T0 = "2026-06-01T00:00:00Z"


def record(doc_id: str, roles: tuple[str, ...] = ("support_l1", "support_l2")) -> ManifestRecord:
    return ManifestRecord(
        doc_id=doc_id, path=f"p/{doc_id}", sha256="0" * 64, title=doc_id, source_type="sop", registry_state="approved",
        version_id=f"{doc_id}@v1", family_id="F", approved_by="A", valid_from=None, valid_to=None, recorded_from=None,
        supersedes=None, acl_tenants=("T",), acl_roles=roles, tokens=10,
    )  # fmt: skip


def at(seconds: int) -> str:
    return iso(parse_ts(T0) + timedelta(seconds=seconds))


def event(number: int, seconds: int, kind: EventKind, doc: str = "D1", **detail: str) -> DocEvent:
    return DocEvent(f"ev-{number:04d}", at(seconds), kind, doc, detail)


def probe(seconds: int, returned: bool, doc: str = "D1", role: str = ROLE, revision: int | None = None) -> ReaderProbe:
    return ReaderProbe(at(seconds), doc, role, returned, revision)


LIFE = (event(1, 0, EventKind.CREATE), event(2, 100, EventKind.APPROVE), event(3, 1000, EventKind.WITHDRAW))
RECORDS = {"D1": record("D1"), "D2": record("D2")}


def test_a_consistent_reader_has_a_zero_window_and_a_lagging_one_a_positive_window() -> None:
    consistent = [probe(110, True), probe(500, True), probe(1010, False), probe(2000, False)]
    lagging = [probe(110, False), probe(500, True), probe(1010, True), probe(1300, True), probe(2000, False)]
    ok = update_consistency(LIFE, RECORDS, consistent)
    late = update_consistency(LIFE, RECORDS, lagging)
    assert {w.kind: (w.lower_s, w.upper_s) for w in ok.windows} == {
        EventKind.APPROVE: (0.0, 10.0),
        EventKind.WITHDRAW: (0.0, 10.0),
    }
    assert {w.kind: (w.lower_s, w.upper_s) for w in late.windows} == {
        EventKind.APPROVE: (10.0, 400.0),
        EventKind.WITHDRAW: (300.0, 1000.0),
    }
    assert not any(w.exposed for w in ok.windows) and all(w.exposed for w in late.windows)
    assert late.by_kind["withdraw"].max_lower_s == 300.0 and ok.by_kind["withdraw"].exposed == 0


def test_a_reader_that_never_settles_is_censored_not_given_an_invented_end() -> None:
    result = update_consistency(LIFE, RECORDS, [probe(1010, True), probe(5000, True)])
    withdraw = next(w for w in result.windows if w.kind is EventKind.WITHDRAW)
    assert withdraw.lower_s == 4000.0 and withdraw.upper_s is None and withdraw.exposed
    assert result.by_kind["withdraw"].censored == 1


def test_a_window_is_never_negative_and_probes_before_the_event_do_not_count() -> None:
    early = [probe(50, True), probe(60, True), probe(100, True), probe(1000, False)]
    result = update_consistency(LIFE, RECORDS, early)
    approve = next(w for w in result.windows if w.kind is EventKind.APPROVE)
    assert approve.probes == 1 and approve.lower_s == 0.0 and approve.upper_s == 0.0, "a probe at the instant counts"
    assert all(w.lower_s >= 0 and (w.upper_s is None or w.upper_s >= w.lower_s) for w in result.windows)


def test_a_probe_after_the_next_change_belongs_to_that_change() -> None:
    result = update_consistency(LIFE, RECORDS, [probe(110, True), probe(1100, True)])
    approve = next(w for w in result.windows if w.kind is EventKind.APPROVE)
    assert approve.probes == 1, "the probe after the withdrawal is not a measure of the approval"


def test_supersede_and_revocation_and_delete_expose_what_they_hide() -> None:
    stream = (
        event(1, 0, EventKind.CREATE, "D2"), event(2, 10, EventKind.APPROVE, "D2"),
        event(3, 100, EventKind.REVOKE_ACL, "D2", role="support_l1"),
        event(4, 500, EventKind.SUPERSEDE, "D2", by="D1"),
        event(5, 900, EventKind.DELETE, "D2"),
    )  # fmt: skip
    probes = [
        probe(150, True, "D2", "support_l1"), probe(150, True, "D2", "support_l2"),
        probe(550, True, "D2", "support_l2"), probe(950, True, "D2", "support_l2"),
    ]  # fmt: skip
    result = update_consistency(stream, RECORDS, probes)
    kinds = {w.kind: w for w in result.windows}
    assert kinds[EventKind.REVOKE_ACL].lower_s == 50.0, "only the revoked role's probe was affected"
    assert kinds[EventKind.SUPERSEDE].lower_s == 50.0
    assert EventKind.DELETE not in kinds and "ev-0005" in result.unmeasured, "a superseded document is already hidden"
    plain = (*LIFE[:2], event(3, 900, EventKind.DELETE))
    deleted = update_consistency(plain, RECORDS, [probe(950, True), probe(990, False)])
    assert [(w.kind, w.lower_s, w.upper_s) for w in deleted.windows if w.kind is EventKind.DELETE] == [
        (EventKind.DELETE, 50.0, 90.0)
    ]
    assert EventKind.APPROVE not in kinds and result.unmeasured["ev-0002"].reason.startswith("no probe")


def test_an_amendment_needs_revisions_and_reclassification_is_never_seen() -> None:
    stream = (
        event(1, 0, EventKind.CREATE), event(2, 10, EventKind.APPROVE), event(3, 100, EventKind.AMEND),
        event(4, 300, EventKind.RECLASSIFY, classification="public"),
    )  # fmt: skip
    plain = update_consistency(stream, RECORDS, [probe(120, True), probe(200, True)])
    assert "ev-0003" in plain.unmeasured and "revision" in plain.unmeasured["ev-0003"].reason
    assert "classification" in plain.unmeasured["ev-0004"].reason
    seen = update_consistency(stream, RECORDS, [probe(120, True, revision=0), probe(200, True, revision=1)])
    amend = next(w for w in seen.windows if w.kind is EventKind.AMEND)
    assert amend.lower_s == 20.0 and amend.upper_s == 100.0


def test_index_internal_staleness_is_declared_not_observed() -> None:
    result = update_consistency(LIFE, RECORDS, [probe(110, True)])
    assert isinstance(result.index_internal, NotObservable) and "not observed" in result.index_internal.reason


def test_unknown_documents_and_invalid_streams_are_refused() -> None:
    with pytest.raises(StatisticsError, match="probe names a document"):
        update_consistency(LIFE, RECORDS, [probe(10, True, doc="D9")])
    with pytest.raises(StatisticsError, match="event names a document"):
        update_consistency((event(1, 0, EventKind.CREATE, "D9"),), RECORDS, [])
    with pytest.raises(StatisticsError, match="not a valid stream"):
        update_consistency((event(1, 0, EventKind.APPROVE),), RECORDS, [])


# ------------------------------------------------------------------ over the 1,000-event stream


@pytest.fixture(scope="module")
def stream(s_published: Path) -> tuple[tuple[DocEvent, ...], dict[str, ManifestRecord]]:
    records = tuple(PublishedView.load(s_published).records)
    return build_events(records, 7), {r.doc_id: r for r in records}


def probes_after_each_event(
    events: Sequence[DocEvent], records: dict[str, ManifestRecord], reader: Callable[[DocEvent, str, bool], bool]
) -> list[ReaderProbe]:
    out = []
    for e in events:
        for delay in (1, 30):
            when = iso(parse_ts(e.at) + timedelta(seconds=delay))
            for role in ("support_l1", "support_l2"):
                truth = e.doc_id in {
                    d for d in replay(events, when) if shown(replay(events, when)[d], records[d], role)
                }
                out.append(ReaderProbe(when, e.doc_id, role, reader(e, when, truth)))
    return out


def test_a_reader_that_follows_the_committed_state_is_never_exposed_on_the_real_stream(
    stream: tuple[tuple[DocEvent, ...], dict[str, ManifestRecord]],
) -> None:
    events, records = stream
    subset = events[:120]
    result = update_consistency(subset, records, probes_after_each_event(subset, records, lambda e, when, truth: truth))
    assert result.windows and not any(w.exposed for w in result.windows)


def test_a_reader_frozen_at_the_start_is_exposed_on_the_real_stream(
    stream: tuple[tuple[DocEvent, ...], dict[str, ManifestRecord]],
) -> None:
    events, records = stream
    subset = events[:120]
    result = update_consistency(subset, records, probes_after_each_event(subset, records, lambda e, when, truth: False))
    assert any(w.exposed for w in result.windows)
    assert result.by_kind["approve"].exposed == result.by_kind["approve"].measured > 0
