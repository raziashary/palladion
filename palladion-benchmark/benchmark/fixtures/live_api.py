"""Deterministic, read-only mock of the live operational systems (B02-T05.01).

Four named read operations answer from the world's timelines at the case's evaluation time. A case can be given a
failure mode per operation: a 503 outage, a stale answer older than the operation's freshness bound, or an
unauthorized read. The four outcomes differ in status and timestamps, so a system that ignores the failure cannot be
mistaken for one that handles it. There is no write operation and no wall clock: read times come from the case.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import Any, Final

from benchmark.fixtures.entities import Principal, WorldEntities, WorldError
from benchmark.fixtures.knowledge import iso, parse_ts
from benchmark.fixtures.operations import (
    LIVE_OPERATIONS,
    Operations,
    granted,
    in_outage,
    merchant_status,
    reconciliation_status,
    transaction_state,
)


class LiveApiError(WorldError):
    """The caller asked for something the mock does not offer, such as a write or an unknown operation."""


class Mode(StrEnum):
    OK = "ok"
    OUTAGE = "outage"
    STALE = "stale"
    UNAUTHORIZED = "unauthorized"


class LiveStatus(StrEnum):
    OK = "ok"
    UNAVAILABLE = "unavailable"
    UNAUTHORIZED = "unauthorized"
    NOT_FOUND = "not_found"


HTTP_STATUS: Final = {
    LiveStatus.OK: 200,
    LiveStatus.UNAVAILABLE: 503,
    LiveStatus.UNAUTHORIZED: 403,
    LiveStatus.NOT_FOUND: 404,
}
# Per-operation freshness bounds in seconds (BADR-0020 rule 8): how old an answer may be and still be used.
MAX_AGE_SECONDS: Final = {
    "transaction_status": 900,
    "settlement_state": 3_600,
    "merchant_status": 86_400,
    "reconciliation_status": 21_600,
}
STALE_FACTOR: Final = 4  # a stale answer is observed this many freshness bounds before the read


@dataclass(frozen=True)
class LiveResponse:
    case_id: str
    operation: str
    subject_id: str
    status: LiveStatus
    http_status: int
    payload: Mapping[str, Any] | None
    read_at: str
    observed_at: str | None
    max_age_seconds: int

    @property
    def age_seconds(self) -> float | None:
        if self.observed_at is None:
            return None
        return (parse_ts(self.read_at) - parse_ts(self.observed_at)).total_seconds()

    @property
    def fresh(self) -> bool:
        """True only for an answer that exists and is no older than the operation's bound."""
        age = self.age_seconds
        return self.status is LiveStatus.OK and age is not None and age <= self.max_age_seconds


class LiveMock:
    """Read-only operations over a world's timelines with per-case failure modes."""

    def __init__(
        self, entities: WorldEntities, ops: Operations, modes: Mapping[tuple[str, str], Mode] | None = None
    ) -> None:
        self._entities = entities
        self._ops = ops
        self._modes = dict(modes or {})
        for (_, operation), _mode in self._modes.items():
            if operation not in LIVE_OPERATIONS:
                raise LiveApiError(f"unknown operation {operation}")

    @staticmethod
    def operations() -> tuple[str, ...]:
        return LIVE_OPERATIONS

    def mode_for(self, case_id: str, operation: str) -> Mode:
        return self._modes.get((case_id, operation), Mode.OK)

    def read(
        self, case_id: str, operation: str, subject_id: str, principal: Principal, evaluation_time: str
    ) -> LiveResponse:
        """Answer one read. The same arguments always give the same response."""
        if operation not in LIVE_OPERATIONS:
            raise LiveApiError(f"unknown operation {operation}")
        read_at = iso(parse_ts(evaluation_time))
        bound = MAX_AGE_SECONDS[operation]

        def respond(
            status: LiveStatus, payload: Mapping[str, Any] | None = None, seen: str | None = None
        ) -> LiveResponse:
            return LiveResponse(
                case_id, operation, subject_id, status, HTTP_STATUS[status], payload, read_at, seen, bound
            )

        mode = self.mode_for(case_id, operation)
        subject = self._subject_tenant(operation, subject_id)
        internal = next(t.tenant_id for t in self._entities.tenants if t.internal)
        if subject is None:  # an outsider gets the same answer for a missing subject as for another tenant's
            return respond(LiveStatus.NOT_FOUND if principal.tenant_id == internal else LiveStatus.UNAUTHORIZED)
        allowed = granted(self._ops, principal.principal_id, operation, read_at) and principal.tenant_id in (
            subject,
            internal,
        )
        if mode is Mode.UNAUTHORIZED or not allowed:
            return respond(LiveStatus.UNAUTHORIZED)
        if mode is Mode.OUTAGE or in_outage(self._ops, operation, read_at):
            return respond(LiveStatus.UNAVAILABLE)
        seen = iso(parse_ts(read_at) - timedelta(seconds=bound * STALE_FACTOR)) if mode is Mode.STALE else read_at
        return respond(LiveStatus.OK, self._payload(operation, subject_id, seen), seen)

    def _subject_tenant(self, operation: str, subject_id: str) -> str | None:
        if operation == "merchant_status":
            found = [m.tenant_id for m in self._entities.merchants if m.merchant_id == subject_id]
        else:
            found = [t.tenant_id for t in self._ops.transactions if t.txn_id == subject_id]
        return found[0] if found else None

    def _payload(self, operation: str, subject_id: str, observed_at: str) -> Mapping[str, Any]:
        if operation == "merchant_status":
            return {"merchant_id": subject_id, "status": merchant_status(self._ops, subject_id, observed_at)}
        txn = self._ops.transaction(subject_id)
        state = transaction_state(txn, observed_at)
        if operation == "transaction_status":
            return {"txn_id": subject_id, "state": state, "amount": txn.amount}
        if operation == "reconciliation_status":
            return {"txn_id": subject_id, "reconciliation": reconciliation_status(self._ops, subject_id, observed_at)}
        return {"txn_id": subject_id, "settled": state == "settled", "state": state}
