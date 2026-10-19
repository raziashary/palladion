"""The deterministic read-only live operational mock (B02-T05.01)."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from benchmark.fixtures import live_api
from benchmark.fixtures.entities import Principal
from benchmark.fixtures.live_api import (
    MAX_AGE_SECONDS,
    STALE_FACTOR,
    LiveApiError,
    LiveMock,
    LiveResponse,
    LiveStatus,
    Mode,
)
from benchmark.fixtures.operations import LIVE_OPERATIONS, in_outage, replay
from benchmark.fixtures.world import World, build_world

EVAL = "2026-10-05T12:00:00Z"


@pytest.fixture(scope="module")
def world() -> World:
    return build_world(7)


def principal(world: World, role: str, tenant: str | None = None) -> Principal:
    return next(p for p in world.entities.principals if p.role_id == role and (tenant is None or p.tenant_id == tenant))


def settled_txn(world: World) -> str:
    return next(t.txn_id for t in world.operations.transactions if t.events[-1].kind.value == "settled")


def quiet_instant(world: World, operation: str) -> str:
    """An instant outside every outage of the operation, so the mode under test is the only fault."""
    for hour in range(24 * 30):
        candidate = f"2026-09-{1 + hour // 24:02d}T{hour % 24:02d}:30:00Z"
        if not in_outage(world.operations, operation, candidate):
            return candidate
    raise AssertionError("no quiet instant")


def mock(world: World, **modes: Mode) -> LiveMock:
    return LiveMock(world.entities, world.operations, {("CASE-1", op): m for op, m in modes.items()})


# --------------------------------------------------------------------------- read-only surface


def test_the_public_surface_has_no_write_operation(world: World) -> None:
    surface = {n for n, _ in inspect.getmembers(LiveMock, callable) if not n.startswith("_")}
    assert surface == {"operations", "read", "mode_for"}
    assert not any(w in name for name in surface for w in ("write", "update", "delete", "set", "create", "post", "put"))
    assert LiveMock.operations() == LIVE_OPERATIONS == tuple(MAX_AGE_SECONDS)


def test_an_unknown_operation_fails_and_so_does_a_mode_for_one(world: World) -> None:
    l2 = principal(world, "support_l2")
    with pytest.raises(LiveApiError, match="unknown operation"):
        mock(world).read("CASE-1", "refund_transaction", "TXN-X", l2, EVAL)
    with pytest.raises(LiveApiError, match="unknown operation"):
        LiveMock(world.entities, world.operations, {("CASE-1", "delete_transaction"): Mode.OK})


def test_reading_never_changes_the_world(world: World) -> None:
    before = world.operations.digest()
    live = mock(world)
    txn = settled_txn(world)
    for operation in LIVE_OPERATIONS:
        subject = world.operations.transaction(txn).merchant_id if operation == "merchant_status" else txn
        live.read("CASE-1", operation, subject, principal(world, "engineer"), EVAL)
    assert world.operations.digest() == before


def test_the_module_never_reads_the_wall_clock() -> None:
    source = Path(inspect.getsourcefile(live_api) or "").read_text(encoding="utf-8")
    assert "datetime.now" not in source and "time.time" not in source and "utcnow" not in source


# --------------------------------------------------------------------------- determinism and payloads


def test_the_same_case_returns_the_same_state_every_time(world: World) -> None:
    txn = settled_txn(world)
    engineer = principal(world, "engineer")
    instant = quiet_instant(world, "transaction_status")
    first = mock(world).read("CASE-1", "transaction_status", txn, engineer, instant)
    again = mock(world).read("CASE-1", "transaction_status", txn, engineer, instant)
    assert first == again and first.payload == again.payload


def test_an_ok_read_matches_the_timeline_at_the_evaluation_time(world: World) -> None:
    engineer = principal(world, "engineer")
    instant = quiet_instant(world, "transaction_status")
    state = replay(world.operations, instant)
    for txn in world.operations.transactions[:40]:
        got = mock(world).read("CASE-1", "transaction_status", txn.txn_id, engineer, instant)
        assert got.status is LiveStatus.OK and got.payload is not None
        assert got.payload["state"] == state[txn.txn_id]["state"]
        assert got.read_at == instant and got.observed_at == instant and got.fresh and got.age_seconds == 0


def test_read_timestamps_come_from_the_case_not_the_clock(world: World) -> None:
    engineer = principal(world, "engineer")
    got = mock(world).read(
        "CASE-1", "merchant_status", world.entities.merchants[0].merchant_id, engineer, "2026-07-01T09:00:00+07:00"
    )
    assert got.read_at == "2026-07-01T02:00:00Z"


# --------------------------------------------------------------------------- the failure modes


def test_each_failure_mode_is_distinguishable(world: World) -> None:
    txn = settled_txn(world)
    engineer = principal(world, "engineer")
    instant = quiet_instant(world, "settlement_state")
    seen = {}
    for mode in Mode:
        got = mock(world, settlement_state=mode).read("CASE-1", "settlement_state", txn, engineer, instant)
        seen[mode] = (got.status, got.http_status, got.payload is not None, got.fresh)
    assert seen == {
        Mode.OK: (LiveStatus.OK, 200, True, True),
        Mode.STALE: (LiveStatus.OK, 200, True, False),
        Mode.OUTAGE: (LiveStatus.UNAVAILABLE, 503, False, False),
        Mode.UNAUTHORIZED: (LiveStatus.UNAUTHORIZED, 403, False, False),
    }
    assert len(set(seen.values())) == 4


def test_stale_differs_from_fresh_only_by_the_declared_bound(world: World) -> None:
    txn = settled_txn(world)
    engineer = principal(world, "engineer")
    instant = quiet_instant(world, "settlement_state")
    fresh = mock(world).read("CASE-1", "settlement_state", txn, engineer, instant)
    stale = mock(world, settlement_state=Mode.STALE).read("CASE-1", "settlement_state", txn, engineer, instant)
    bound = MAX_AGE_SECONDS["settlement_state"]
    assert fresh.age_seconds == 0 and stale.age_seconds == bound * STALE_FACTOR > bound
    assert fresh.max_age_seconds == stale.max_age_seconds == bound
    assert (fresh.status, fresh.http_status) == (stale.status, stale.http_status)


def test_a_stale_answer_can_disagree_with_the_current_state(world: World) -> None:
    engineer = principal(world, "engineer")
    bound = MAX_AGE_SECONDS["transaction_status"]
    differing = 0
    for txn in world.operations.transactions:
        probe = txn.events[-1].time
        if in_outage(world.operations, "transaction_status", probe):
            continue
        fresh = mock(world).read("CASE-1", "transaction_status", txn.txn_id, engineer, probe)
        stale = mock(world, transaction_status=Mode.STALE).read(
            "CASE-1", "transaction_status", txn.txn_id, engineer, probe
        )
        assert stale.age_seconds == bound * STALE_FACTOR
        if fresh.payload and stale.payload and fresh.payload["state"] != stale.payload["state"]:
            differing += 1
    assert differing >= 5  # stale data is not merely relabelled fresh data


def test_a_modeled_outage_applies_to_one_case_only(world: World) -> None:
    txn = settled_txn(world)
    engineer = principal(world, "engineer")
    instant = quiet_instant(world, "transaction_status")
    live = mock(world, transaction_status=Mode.OUTAGE)
    assert live.read("CASE-1", "transaction_status", txn, engineer, instant).status is LiveStatus.UNAVAILABLE
    assert live.read("CASE-2", "transaction_status", txn, engineer, instant).status is LiveStatus.OK
    assert (
        live.mode_for("CASE-1", "transaction_status") is Mode.OUTAGE
        and live.mode_for("CASE-2", "transaction_status") is Mode.OK
    )


def test_a_timeline_outage_gives_a_503_even_in_ok_mode_and_ends_at_the_exclusive_bound(world: World) -> None:
    outage = next(o for o in world.operations.outages if o.operation == "transaction_status" and o.period.end)
    txn = world.operations.transactions[0]
    engineer = principal(world, "engineer")
    inside = mock(world).read("CASE-1", "transaction_status", txn.txn_id, engineer, outage.period.start)
    assert inside.status is LiveStatus.UNAVAILABLE and inside.payload is None
    assert outage.period.end is not None
    overlapping = [
        o
        for o in world.operations.outages
        if o.operation == "transaction_status" and o.period.contains(outage.period.end)
    ]
    after = mock(world).read("CASE-1", "transaction_status", txn.txn_id, engineer, outage.period.end)
    assert (after.status is LiveStatus.UNAVAILABLE) == bool(overlapping)


def test_authorization_follows_role_tenant_and_grant_dates(world: World) -> None:
    txn = next(t for t in world.operations.transactions if t.tenant_id == "T-NORTHWAVE")
    instant = quiet_instant(world, "settlement_state")
    l1 = principal(world, "support_l1", "T-NORTHWAVE")
    l2 = principal(world, "support_l2", "T-NORTHWAVE")
    other_tenant = principal(world, "support_l2", "T-KESTREL")
    engineer = principal(world, "engineer")
    live = mock(world)
    assert live.read("CASE-1", "settlement_state", txn.txn_id, l1, instant).status is LiveStatus.UNAUTHORIZED
    assert live.read("CASE-1", "settlement_state", txn.txn_id, other_tenant, instant).status is LiveStatus.UNAUTHORIZED
    assert live.read("CASE-1", "settlement_state", txn.txn_id, l2, instant).status is LiveStatus.OK
    assert live.read("CASE-1", "settlement_state", txn.txn_id, engineer, instant).status is LiveStatus.OK
    assert (
        live.read("CASE-1", "settlement_state", txn.txn_id, l2, "2024-06-01T00:00:00Z").status
        is LiveStatus.UNAUTHORIZED
    )
    quiet_l1 = quiet_instant(world, "transaction_status")
    assert live.read("CASE-1", "transaction_status", txn.txn_id, l1, quiet_l1).status is LiveStatus.OK


def test_unknown_subjects_are_not_found(world: World) -> None:
    got = mock(world).read("CASE-1", "transaction_status", "TXN-NOPE-00000", principal(world, "engineer"), EVAL)
    assert got.status is LiveStatus.NOT_FOUND and got.http_status == 404 and got.payload is None and not got.fresh


def test_the_freshness_bound_is_inclusive() -> None:
    exact = LiveResponse(
        "c", "transaction_status", "t", LiveStatus.OK, 200, {}, "2026-10-05T12:00:00Z", "2026-10-05T11:45:00Z", 900
    )
    over = LiveResponse(
        "c", "transaction_status", "t", LiveStatus.OK, 200, {}, "2026-10-05T12:00:00Z", "2026-10-05T11:44:59Z", 900
    )
    assert exact.age_seconds == 900 and exact.fresh
    assert over.age_seconds == 901 and not over.fresh


def test_a_missing_subject_looks_the_same_as_another_tenants_to_an_outsider(world: World) -> None:
    outsider = principal(world, "support_l2", "T-KESTREL")
    other_tenants_txn = next(t.txn_id for t in world.operations.transactions if t.tenant_id == "T-NORTHWAVE")
    instant = quiet_instant(world, "transaction_status")
    missing = mock(world).read("CASE-1", "transaction_status", "TXN-NOPE-00000", outsider, instant)
    foreign = mock(world).read("CASE-1", "transaction_status", other_tenants_txn, outsider, instant)
    assert missing.status is foreign.status is LiveStatus.UNAUTHORIZED
