"""Live-event timelines and case histories (B02-T01.03): what the operational systems said, and when.

Reported and verified facts stay apart (protocol 4.4). Timelines replay identically for a given instant.
"""

from __future__ import annotations

import random
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import Any

from benchmark.fixtures import FICTIONAL_NOTICE, digest_of, to_plain
from benchmark.fixtures.entities import Principal, WorldEntities, WorldError, lookup, rng_for
from benchmark.fixtures.knowledge import Interval, iso, parse_ts

LIVE_OPERATIONS = ("transaction_status", "settlement_state", "merchant_status", "reconciliation_status")
_L1_OPERATIONS = ("transaction_status", "merchant_status")


class TxnEventKind(StrEnum):
    INITIATED = "initiated"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    PENDING_SETTLEMENT = "pending_settlement"
    SETTLED = "settled"
    REVERSED = "reversed"
    CHARGEBACK_OPENED = "disputed"


class ReconStatus(StrEnum):
    PENDING = "pending"
    MATCHED = "matched"
    UNMATCHED = "unmatched"


class MerchantStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class Provenance(StrEnum):
    """Where a case fact came from. A user report is never a verified observation, whatever it claims."""

    USER_REPORTED = "user_reported"
    VERIFIED = "verified"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class TransactionEvent:
    time: str
    kind: TxnEventKind


@dataclass(frozen=True)
class Transaction:
    txn_id: str
    tenant_id: str
    merchant_id: str
    txn_type_id: str
    amount: int
    initiated_at: str
    events: tuple[TransactionEvent, ...]


@dataclass(frozen=True)
class ReconciliationEvent:
    txn_id: str
    time: str
    status: ReconStatus


@dataclass(frozen=True)
class MerchantStatusPeriod:
    merchant_id: str
    status: MerchantStatus
    period: Interval


@dataclass(frozen=True)
class Outage:
    operation: str
    period: Interval


@dataclass(frozen=True)
class AuthorizationGrant:
    principal_id: str
    operation: str
    period: Interval


@dataclass(frozen=True)
class CaseEvent:
    seq: int
    time: str
    provenance: Provenance
    fact_key: str
    value: str | None
    corrects_seq: int | None


@dataclass(frozen=True)
class CaseHistory:
    case_id: str
    tenant_id: str
    principal_id: str
    merchant_id: str
    txn_id: str
    case_type_id: str
    opened_at: str
    events: tuple[CaseEvent, ...]


@dataclass(frozen=True)
class Operations:
    transactions: tuple[Transaction, ...]
    reconciliations: tuple[ReconciliationEvent, ...]
    merchant_periods: tuple[MerchantStatusPeriod, ...]
    outages: tuple[Outage, ...]
    grants: tuple[AuthorizationGrant, ...]
    cases: tuple[CaseHistory, ...]

    def transaction(self, txn_id: str) -> Transaction:
        return lookup(self.transactions, "txn_id", txn_id)

    def case(self, case_id: str) -> CaseHistory:
        return lookup(self.cases, "case_id", case_id)

    def records(self) -> Iterator[dict[str, Any]]:
        for kind in ("transactions", "reconciliations", "merchant_periods", "outages", "grants", "cases"):
            for item in getattr(self, kind):
                yield {"kind": kind, "fictional": FICTIONAL_NOTICE, **to_plain(item)}

    def digest(self) -> str:
        return digest_of(list(self.records()))


def transaction_state(txn: Transaction, as_of: str) -> str | None:
    """The state after every event at or before ``as_of`` (point events are visible from their own instant)."""
    state = None
    for event in txn.events:
        if parse_ts(event.time) <= parse_ts(as_of):
            state = event.kind.value
    return state


def reconciliation_status(ops: Operations, txn_id: str, as_of: str) -> str | None:
    latest = None
    for event in ops.reconciliations:
        if event.txn_id == txn_id and parse_ts(event.time) <= parse_ts(as_of):
            latest = event.status.value
    return latest


def merchant_status(ops: Operations, merchant_id: str, as_of: str) -> str | None:
    for period in ops.merchant_periods:
        if period.merchant_id == merchant_id and period.period.contains(as_of):
            return period.status.value
    return None


def in_outage(ops: Operations, operation: str, as_of: str) -> bool:
    return any(o.operation == operation and o.period.contains(as_of) for o in ops.outages)


def granted(ops: Operations, principal_id: str, operation: str, as_of: str) -> bool:
    return any(
        g.principal_id == principal_id and g.operation == operation and g.period.contains(as_of) for g in ops.grants
    )


def replay(ops: Operations, as_of: str) -> dict[str, dict[str, str | None]]:
    """The full operational state at an instant, as plain data. Same operations and instant, same result."""
    return {
        txn.txn_id: {
            "state": transaction_state(txn, as_of),
            "reconciliation": reconciliation_status(ops, txn.txn_id, as_of),
            "merchant": merchant_status(ops, txn.merchant_id, as_of),
        }
        for txn in ops.transactions
    }


@dataclass(frozen=True)
class CaseView:
    """What is known about a case at an instant, keeping reported and verified facts apart."""

    reported: Mapping[str, str | None]
    verified: Mapping[str, str | None]
    unresolved: tuple[str, ...]

    @property
    def disputed(self) -> tuple[str, ...]:
        """Keys where a user report and a verified observation disagree."""
        return tuple(sorted(k for k, v in self.reported.items() if k in self.verified and self.verified[k] != v))


def case_view(case: CaseHistory, as_of: str) -> CaseView:
    """Fold a case history up to ``as_of``. A correction demotes the report it corrects; verified facts are kept."""
    seen = [e for e in case.events if parse_ts(e.time) <= parse_ts(as_of)]
    demoted = {e.corrects_seq for e in seen if e.corrects_seq is not None}
    reported: dict[str, str | None] = {}
    verified: dict[str, str | None] = {}
    open_keys: dict[str, None] = {}
    for event in sorted(seen, key=lambda e: e.seq):
        if event.provenance is Provenance.USER_REPORTED and event.seq not in demoted:
            reported[event.fact_key] = event.value
        elif event.provenance is Provenance.VERIFIED:
            verified[event.fact_key] = event.value
            open_keys.pop(event.fact_key, None)
        elif event.provenance is Provenance.UNRESOLVED:
            open_keys[event.fact_key] = None
    unresolved = tuple(sorted(k for k in open_keys if k not in verified))
    return CaseView(reported, verified, unresolved)


def validate_operations(entities: WorldEntities, ops: Operations) -> None:
    merchants = {m.merchant_id: m for m in entities.merchants}
    txns = {t.txn_id: t for t in ops.transactions}
    principals = {p.principal_id: p for p in entities.principals}
    txn_types = {t.txn_type_id for t in entities.transaction_types}
    if len(txns) != len(ops.transactions) or len({c.case_id for c in ops.cases}) != len(ops.cases):
        raise WorldError("duplicate transaction or case id")
    for txn in ops.transactions:
        merchant = merchants.get(txn.merchant_id)
        if merchant is None or merchant.tenant_id != txn.tenant_id or txn.txn_type_id not in txn_types:
            raise WorldError(f"{txn.txn_id}: merchant, tenant or type mismatch")
        times = [parse_ts(e.time) for e in txn.events]
        if times != sorted(times) or not txn.events or txn.events[0].kind is not TxnEventKind.INITIATED:
            raise WorldError(f"{txn.txn_id}: events must start with initiation and never run backwards")
    for case in ops.cases:
        owner = txns.get(case.txn_id)
        if owner is None or owner.tenant_id != case.tenant_id or owner.merchant_id != case.merchant_id:
            raise WorldError(f"{case.case_id}: transaction does not belong to the case tenant and merchant")
        principal = principals.get(case.principal_id)
        if principal is None or principal.tenant_id != case.tenant_id:
            raise WorldError(f"{case.case_id}: principal is not in the case tenant")
        seqs = [e.seq for e in case.events]
        if seqs != sorted(set(seqs)) or any(
            e.corrects_seq is not None and e.corrects_seq >= e.seq for e in case.events
        ):
            raise WorldError(f"{case.case_id}: event sequence is not strictly increasing or a correction looks ahead")
        if any(e.provenance is Provenance.UNRESOLVED and e.value is not None for e in case.events):
            raise WorldError(f"{case.case_id}: an unresolved fact cannot carry a value")
    if any(r.txn_id not in txns for r in ops.reconciliations) or any(
        p.merchant_id not in merchants for p in ops.merchant_periods
    ):
        raise WorldError("reconciliation or merchant status references an unknown id")
    if any(o.operation not in LIVE_OPERATIONS for o in ops.outages) or any(
        g.operation not in LIVE_OPERATIONS or g.principal_id not in principals for g in ops.grants
    ):
        raise WorldError("outage or grant references an unknown operation or principal")


def build_operations(entities: WorldEntities, seed: int, *, transactions: int, cases: int) -> Operations:
    """Generate transactions, reconciliation, merchant status, outages, grants and case histories from the seed."""
    rng = rng_for(seed, "operations")
    txn_types = {t.txn_type_id: t for t in entities.transaction_types}
    begin, end = parse_ts("2026-02-01T00:00:00Z"), parse_ts("2026-10-01T00:00:00Z")
    span = int((end - begin) / timedelta(minutes=1))
    txns: list[Transaction] = []
    recon: list[ReconciliationEvent] = []
    for number in range(transactions):
        merchant = rng.choice(entities.merchants)
        txn_type = rng.choice(entities.transaction_types)
        start = begin + timedelta(minutes=rng.randrange(span))
        events = [TransactionEvent(iso(start), TxnEventKind.INITIATED)]
        clock = start + timedelta(seconds=rng.randint(1, 20))
        events.append(TransactionEvent(iso(clock), TxnEventKind.AUTHORIZED))
        txn_id = f"TXN-{merchant.tenant_id[2:5]}-{number + 1:05d}"
        outcome = rng.random()
        if outcome < 0.2:
            events.append(TransactionEvent(iso(clock + timedelta(seconds=rng.randint(1, 60))), TxnEventKind.FAILED))
        else:
            clock += timedelta(minutes=rng.randint(1, 90))
            events.append(TransactionEvent(iso(clock), TxnEventKind.CAPTURED))
            if txn_types[txn_type.txn_type_id].settles:
                clock += timedelta(hours=rng.randint(6, 40))
                final = rng.random()
                if final < 0.6:
                    events.append(TransactionEvent(iso(clock), TxnEventKind.SETTLED))
                    matched = rng.random() < 0.9
                    recon.append(
                        ReconciliationEvent(
                            txn_id,
                            iso(clock + timedelta(hours=20)),
                            ReconStatus.MATCHED if matched else ReconStatus.UNMATCHED,
                        )
                    )
                elif final < 0.75:
                    events.append(TransactionEvent(iso(clock), TxnEventKind.REVERSED))
                elif final < 0.85:
                    events.append(TransactionEvent(iso(clock), TxnEventKind.CHARGEBACK_OPENED))
                else:
                    events.append(TransactionEvent(iso(clock), TxnEventKind.PENDING_SETTLEMENT))
                    recon.append(ReconciliationEvent(txn_id, iso(clock), ReconStatus.PENDING))
        amount = rng.choice((75_000, 150_000, 480_000, 1_250_000, 3_900_000, 5_000_000, 7_800_000, 21_000_000))
        txns.append(
            Transaction(
                txn_id,
                merchant.tenant_id,
                merchant.merchant_id,
                txn_type.txn_type_id,
                amount,
                iso(start),
                tuple(events),
            )
        )
    periods: list[MerchantStatusPeriod] = []
    horizon = parse_ts("2025-01-01T00:00:00Z")
    for merchant in entities.merchants:
        roll = rng.random()
        if roll < 0.15:
            gap_start = begin + timedelta(days=rng.randint(10, 200))
            gap_end = gap_start + timedelta(days=rng.randint(3, 30))
            periods.append(
                MerchantStatusPeriod(
                    merchant.merchant_id, MerchantStatus.ACTIVE, Interval(iso(horizon), iso(gap_start))
                )
            )
            periods.append(
                MerchantStatusPeriod(
                    merchant.merchant_id, MerchantStatus.SUSPENDED, Interval(iso(gap_start), iso(gap_end))
                )
            )
            periods.append(
                MerchantStatusPeriod(merchant.merchant_id, MerchantStatus.ACTIVE, Interval(iso(gap_end), None))
            )
        elif roll < 0.18:
            closed = begin + timedelta(days=rng.randint(30, 220))
            periods.append(
                MerchantStatusPeriod(merchant.merchant_id, MerchantStatus.ACTIVE, Interval(iso(horizon), iso(closed)))
            )
            periods.append(
                MerchantStatusPeriod(merchant.merchant_id, MerchantStatus.CLOSED, Interval(iso(closed), None))
            )
        else:
            periods.append(
                MerchantStatusPeriod(merchant.merchant_id, MerchantStatus.ACTIVE, Interval(iso(horizon), None))
            )
    outages: list[Outage] = []
    for operation in LIVE_OPERATIONS:
        for _ in range(4):
            outage_start = begin + timedelta(minutes=rng.randrange(span))
            outages.append(
                Outage(operation, Interval(iso(outage_start), iso(outage_start + timedelta(hours=rng.randint(1, 18)))))
            )
    grants: list[AuthorizationGrant] = []
    for principal in entities.principals:
        operations = _L1_OPERATIONS if principal.role_id == "support_l1" else LIVE_OPERATIONS
        for operation in operations:
            grants.append(AuthorizationGrant(principal.principal_id, operation, Interval(iso(horizon), None)))
    case_list = _build_cases(rng, entities, txns, cases)
    ops = Operations(tuple(txns), tuple(recon), tuple(periods), tuple(outages), tuple(grants), tuple(case_list))
    validate_operations(entities, ops)
    return ops


def _build_cases(rng: random.Random, entities: WorldEntities, txns: list[Transaction], count: int) -> list[CaseHistory]:
    by_tenant: dict[str, list[Principal]] = {}
    for principal in entities.principals:
        if principal.role_id in ("support_l1", "support_l2", "risk_analyst"):
            by_tenant.setdefault(principal.tenant_id, []).append(principal)
    case_types = {c.txn_type_id: c for c in entities.case_types}
    out: list[CaseHistory] = []
    for number in range(count):
        txn = rng.choice(txns)
        opened = parse_ts(txn.events[-1].time) + timedelta(hours=rng.randint(1, 160))
        case_type = case_types.get(txn.txn_type_id) or rng.choice(entities.case_types)
        true_state = txn.events[-1].kind.value
        claimed = true_state if rng.random() < 0.6 else rng.choice(("settled", "failed", "captured", "reversed"))
        events = [
            CaseEvent(1, iso(opened), Provenance.USER_REPORTED, "txn_state", claimed, None),
            CaseEvent(2, iso(opened), Provenance.USER_REPORTED, "amount", str(txn.amount), None),
        ]
        seq = 3
        if rng.random() < 0.5:
            events.append(
                CaseEvent(
                    seq,
                    iso(opened + timedelta(hours=rng.randint(1, 12))),
                    Provenance.VERIFIED,
                    "txn_state",
                    true_state,
                    None,
                )
            )
            seq += 1
        else:
            events.append(
                CaseEvent(seq, iso(opened + timedelta(hours=1)), Provenance.UNRESOLVED, "txn_state", None, None)
            )
            seq += 1
        if rng.random() < 0.3:
            events.append(
                CaseEvent(
                    seq,
                    iso(opened + timedelta(hours=rng.randint(13, 30))),
                    Provenance.USER_REPORTED,
                    "txn_state",
                    true_state,
                    1,
                )
            )
        out.append(
            CaseHistory(
                f"CASE-{number + 1:05d}",
                txn.tenant_id,
                rng.choice(by_tenant[txn.tenant_id]).principal_id,
                txn.merchant_id,
                txn.txn_id,
                case_type.case_type_id,
                iso(opened),
                tuple(events),
            )
        )
    return out
