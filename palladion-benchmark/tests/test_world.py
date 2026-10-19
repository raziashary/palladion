"""Hidden world entities (B02-T01.01): determinism, fictional marking, identity separation, referential integrity."""

from __future__ import annotations

import dataclasses
import itertools
import os
import subprocess
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from benchmark.contracts import require_ident, screen_arm_visible
from benchmark.fixtures import FICTIONAL_NOTICE, canonical_json
from benchmark.fixtures.entities import (
    ERROR_CODE_COUNT,
    MERCHANTS_PER_TENANT,
    SHARED_MERCHANT_NAMES,
    WorldEntities,
    WorldError,
    build_entities,
    validate_entities,
)
from benchmark.fixtures.knowledge import Interval
from benchmark.fixtures.operations import (
    CaseEvent,
    CaseHistory,
    Operations,
    Outage,
    Provenance,
    ReconciliationEvent,
    ReconStatus,
    Transaction,
    TransactionEvent,
    TxnEventKind,
    build_operations,
    case_view,
    granted,
    in_outage,
    replay,
    transaction_state,
    validate_operations,
)
from benchmark.fixtures.world import build_world

ROOT = Path(__file__).resolve().parents[1]


def test_the_same_seed_gives_byte_identical_output() -> None:
    first, second = build_entities(7), build_entities(7)
    assert canonical_json(first) == canonical_json(second)
    assert first.digest() == second.digest()


def test_a_different_seed_gives_a_different_world() -> None:
    assert build_entities(7).digest() != build_entities(8).digest()


def test_output_does_not_depend_on_the_hash_randomisation_seed() -> None:
    code = "from benchmark.fixtures.world import build_entities; print(build_entities(7).digest())"
    digests = set()
    for hash_seed in ("0", "12345"):
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        out = subprocess.run(
            [sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, check=True
        )
        digests.add(out.stdout.strip())
    assert digests == {build_entities(7).digest()}


def test_every_record_carries_the_fictional_notice() -> None:
    records = list(build_entities(7).records())
    assert len(records) > 100
    assert all(record["fictional"] == FICTIONAL_NOTICE for record in records)
    assert "is an actual operating procedure" in FICTIONAL_NOTICE and "Nothing here" in FICTIONAL_NOTICE


def test_the_vocabulary_has_the_documented_shape() -> None:
    world = build_entities(7)
    assert len(world.tenants) == 4 and sum(t.internal for t in world.tenants) == 1
    assert len(world.transaction_types) == 10 and len(world.case_types) == 10
    assert len(world.error_codes) == ERROR_CODE_COUNT == len({e.code for e in world.error_codes})
    assert {r.role_id for r in world.roles} >= {"support_l1", "support_l2", "approver", "auditor"}
    assert len(world.merchants) == 3 * MERCHANTS_PER_TENANT


def test_same_named_merchants_exist_across_tenants_under_distinct_ids() -> None:
    world = build_entities(7)
    by_name: dict[str, list[tuple[str, str]]] = {}
    for merchant in world.merchants:
        by_name.setdefault(merchant.display_name, []).append((merchant.tenant_id, merchant.merchant_id))
    collisions = {name: held for name, held in by_name.items() if len(held) > 1}
    assert len(collisions) == SHARED_MERCHANT_NAMES
    for held in collisions.values():
        assert len({tenant for tenant, _ in held}) == len(held) >= 2  # each copy lives in a different tenant
        assert len({merchant_id for _, merchant_id in held}) == len(held)
    assert len({m.merchant_id for m in world.merchants}) == len(world.merchants)


def test_references_resolve_and_ids_are_usable_as_arm_visible_identifiers() -> None:
    world = build_entities(7)
    tenants = {t.tenant_id for t in world.tenants}
    roles = {r.role_id for r in world.roles}
    classes = {c.class_id for c in world.merchant_classes}
    txn_types = {t.txn_type_id for t in world.transaction_types}
    assert all(p.tenant_id in tenants and p.role_id in roles for p in world.principals)
    assert all(m.tenant_id in tenants and m.class_id in classes for m in world.merchants)
    assert all(e.txn_type_id in txn_types for e in world.error_codes)
    assert all(c.txn_type_id in txn_types for c in world.case_types)
    for principal in world.principals:
        require_ident("principal_id", principal.principal_id)  # the contract regex accepts the world's ids
    internal = {t.tenant_id for t in world.tenants if t.internal}
    internal_roles = {r.role_id for r in world.roles if r.internal_only}
    for principal in world.principals:  # internal roles live only in the internal tenant
        assert (principal.role_id in internal_roles) == (principal.tenant_id in internal)


def test_at_least_two_independent_approvers_exist() -> None:
    approvers = [p for p in build_entities(7).principals if p.role_id == "approver"]
    assert len(approvers) >= 2 and len({p.principal_id for p in approvers}) == len(approvers)


def test_error_codes_are_not_sequential_keywords() -> None:
    numbers = sorted(int(e.code.split("-")[1]) for e in build_entities(7).error_codes)
    gaps = Counter(b - a for a, b in itertools.pairwise(numbers))
    assert max(gaps) > 20  # codes are scattered, not a counting run a keyword scan could guess


def test_lookup_of_an_unknown_id_is_refused() -> None:
    world = build_entities(7)
    assert world.merchant(world.merchants[0].merchant_id) == world.merchants[0]
    with pytest.raises(WorldError, match="unknown merchant_id"):
        world.merchant("MRC-NOPE-0000")


def test_the_world_holds_no_arm_visible_or_gold_marker() -> None:
    text = canonical_json(build_entities(7)).lower()
    assert "answerability" not in text and "expected_answer" not in text


def replaced(world: WorldEntities, **changes: Any) -> WorldEntities:
    return dataclasses.replace(world, **changes)


def test_a_clean_world_passes_validation() -> None:
    validate_entities(build_entities(7))


def test_planted_defects_are_refused() -> None:
    world = build_entities(7)
    merchant = world.merchants[0]
    cases = {
        "duplicate id in merchants": replaced(world, merchants=(*world.merchants, merchant)),
        "unknown tenant or role": replaced(
            world, principals=(dataclasses.replace(world.principals[0], role_id="nope"),)
        ),
        "unknown tenant or class": replaced(world, merchants=(dataclasses.replace(merchant, class_id="MC-NOPE"),)),
        "unknown transaction type": replaced(
            world, error_codes=(dataclasses.replace(world.error_codes[0], txn_type_id="x"),)
        ),
    }
    for message, broken in cases.items():
        with pytest.raises(WorldError, match=message):
            validate_entities(broken)


# ----- live events and case histories (B02-T01.03)

ENTITIES = build_entities(7)
SNAPSHOT = "2026-10-18T03:00:00Z"


@pytest.fixture(scope="module")
def ops() -> Operations:
    return build_operations(ENTITIES, 7, transactions=240, cases=120)


def planted_case(**changes: Any) -> CaseHistory:
    txn = build_operations(ENTITIES, 7, transactions=20, cases=1).transactions[0]
    principal = next(p for p in ENTITIES.principals if p.tenant_id == txn.tenant_id and p.role_id == "support_l2")
    base: dict[str, Any] = {
        "case_id": "CASE-X",
        "tenant_id": txn.tenant_id,
        "principal_id": principal.principal_id,
        "merchant_id": txn.merchant_id,
        "txn_id": txn.txn_id,
        "case_type_id": "CT-X",
        "opened_at": "2026-05-01T00:00:00Z",
        "events": (),
    }
    return CaseHistory(**{**base, **changes})


def event(
    seq: int, hour: int, provenance: Provenance, key: str, value: str | None, corrects: int | None = None
) -> CaseEvent:
    return CaseEvent(seq, f"2026-05-01T{hour:02d}:00:00Z", provenance, key, value, corrects)


def test_operations_are_deterministic_and_seed_sensitive(ops: Operations) -> None:
    assert build_operations(ENTITIES, 7, transactions=240, cases=120).digest() == ops.digest()
    other = build_operations(build_entities(8), 8, transactions=240, cases=120)
    assert other.digest() != ops.digest()


def test_timelines_replay_identically_at_every_probed_instant(ops: Operations) -> None:
    rebuilt = build_operations(ENTITIES, 7, transactions=240, cases=120)
    for instant in ("2026-03-01T00:00:00Z", "2026-06-15T12:30:00Z", SNAPSHOT):
        assert replay(ops, instant) == replay(rebuilt, instant)
    assert replay(ops, "2026-03-01T00:00:00Z") != replay(ops, SNAPSHOT)  # time actually moves the state


def test_a_transaction_event_is_visible_from_its_own_instant() -> None:
    txn = Transaction(
        "TXN-X",
        "T-NORTHWAVE",
        "m",
        "refund",
        1,
        "2026-05-01T00:00:00Z",
        (
            TransactionEvent("2026-05-01T00:00:00Z", TxnEventKind.INITIATED),
            TransactionEvent("2026-05-01T00:00:10Z", TxnEventKind.CAPTURED),
        ),
    )
    assert transaction_state(txn, "2026-04-30T23:59:59Z") is None
    assert transaction_state(txn, "2026-05-01T00:00:00Z") == "initiated"
    assert transaction_state(txn, "2026-05-01T00:00:09Z") == "initiated"
    assert transaction_state(txn, "2026-05-01T00:00:10Z") == "captured"


def test_reported_and_verified_facts_stay_distinguishable() -> None:
    case = planted_case(
        events=(
            event(1, 1, Provenance.USER_REPORTED, "txn_state", "settled"),
            event(2, 2, Provenance.VERIFIED, "txn_state", "failed"),
        )
    )
    view = case_view(case, "2026-05-01T05:00:00Z")
    assert view.reported == {"txn_state": "settled"} and view.verified == {"txn_state": "failed"}
    assert view.disputed == ("txn_state",)  # the user's claim is kept, not overwritten by the verified value
    before = case_view(case, "2026-05-01T01:30:00Z")
    assert before.verified == {} and before.reported == {"txn_state": "settled"}


def test_a_user_correction_demotes_the_earlier_report_without_touching_verified_facts() -> None:
    case = planted_case(
        events=(
            event(1, 1, Provenance.USER_REPORTED, "txn_state", "settled"),
            event(2, 2, Provenance.VERIFIED, "amount", "100"),
            event(3, 3, Provenance.USER_REPORTED, "txn_state", "failed", corrects=1),
        )
    )
    view = case_view(case, SNAPSHOT)
    assert view.reported == {"txn_state": "failed"} and view.verified == {"amount": "100"}


def test_an_unresolved_fact_stays_open_until_verified() -> None:
    case = planted_case(events=(event(1, 1, Provenance.UNRESOLVED, "settlement_state", None),))
    assert case_view(case, SNAPSHOT).unresolved == ("settlement_state",)
    closed = planted_case(
        events=(
            event(1, 1, Provenance.UNRESOLVED, "settlement_state", None),
            event(2, 2, Provenance.VERIFIED, "settlement_state", "settled"),
        )
    )
    assert case_view(closed, SNAPSHOT).unresolved == ()


def test_generated_cases_include_disputed_unresolved_and_corrected_facts(ops: Operations) -> None:
    views = [case_view(c, SNAPSHOT) for c in ops.cases]
    assert sum(1 for v in views if v.disputed) >= 5
    assert sum(1 for v in views if v.unresolved) >= 5
    assert sum(1 for c in ops.cases if any(e.corrects_seq is not None for e in c.events)) >= 5
    assert all(v.reported.get("txn_state") is not None for v in views)


def test_outage_windows_are_half_open_and_grants_follow_role(ops: Operations) -> None:
    lone = Operations(
        (), (), (), (Outage("transaction_status", Interval("2026-05-01T00:00:00Z", "2026-05-01T02:00:00Z")),), (), ()
    )
    assert in_outage(lone, "transaction_status", "2026-05-01T00:00:00Z")
    assert in_outage(lone, "transaction_status", "2026-05-01T01:59:59Z")
    assert not in_outage(lone, "transaction_status", "2026-05-01T02:00:00Z")
    assert not in_outage(lone, "settlement_state", "2026-05-01T01:00:00Z")  # another operation is unaffected
    l1 = next(p for p in ENTITIES.principals if p.role_id == "support_l1")
    l2 = next(p for p in ENTITIES.principals if p.role_id == "support_l2")
    assert granted(ops, l1.principal_id, "transaction_status", SNAPSHOT)
    assert not granted(ops, l1.principal_id, "settlement_state", SNAPSHOT)
    assert granted(ops, l2.principal_id, "settlement_state", SNAPSHOT)
    assert not granted(ops, l2.principal_id, "settlement_state", "2024-01-01T00:00:00Z")  # before the grant began


def test_every_merchant_has_exactly_one_status_at_any_instant(ops: Operations) -> None:
    for merchant in ENTITIES.merchants:
        for instant in ("2026-03-01T00:00:00Z", "2026-07-01T00:00:00Z", SNAPSHOT):
            held = [
                p for p in ops.merchant_periods if p.merchant_id == merchant.merchant_id and p.period.contains(instant)
            ]
            assert len(held) == 1


def test_operations_validation_catches_planted_defects(ops: Operations) -> None:
    validate_operations(ENTITIES, ops)
    txn, case = ops.transactions[0], ops.cases[0]
    other_tenant = next(t.tenant_id for t in ENTITIES.tenants if t.tenant_id != txn.tenant_id and not t.internal)
    foreign_txn = next(t.txn_id for t in ops.transactions if t.tenant_id != case.tenant_id)
    no_value = CaseEvent(1, case.opened_at, Provenance.UNRESOLVED, "k", "v", None)
    disorder = CaseEvent(0, case.opened_at, Provenance.VERIFIED, "k", "v", None)
    rest = ops.transactions[1:]
    cases = {
        "mismatch": replace(ops, transactions=(replace(txn, tenant_id=other_tenant), *rest)),
        "never run backwards": replace(ops, transactions=(replace(txn, events=txn.events[::-1]), *rest)),
        "duplicate transaction or case id": replace(ops, cases=(case, case)),
        "principal is not in the case tenant": replace(
            ops, cases=(replace(case, principal_id="meridian.engineer.01"),)
        ),
        "does not belong to the case tenant": replace(ops, cases=(replace(case, txn_id=foreign_txn),)),
        "strictly increasing": replace(ops, cases=(replace(case, events=(*case.events, disorder)),)),
        "cannot carry a value": replace(ops, cases=(replace(case, events=(no_value,)),)),
        "unknown id": replace(ops, reconciliations=(ReconciliationEvent("TXN-NOPE", SNAPSHOT, ReconStatus.PENDING),)),
        "unknown operation or principal": replace(ops, outages=(Outage("not_an_operation", Interval(SNAPSHOT, None)),)),
    }
    for message, broken in cases.items():
        with pytest.raises(WorldError, match=message):
            validate_operations(ENTITIES, broken)


def test_the_world_aggregate_is_reproducible_across_processes_and_environments() -> None:
    code = "from benchmark.fixtures.world import build_world; print(build_world(7).digest())"
    digests = set()
    for hash_seed, tz in (("0", "UTC"), ("999", "Asia/Jakarta")):
        env = {**os.environ, "PYTHONHASHSEED": hash_seed, "TZ": tz, "LANG": "C"}
        out = subprocess.run(
            [sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, check=True
        )
        digests.add(out.stdout.strip())
    assert digests == {build_world(7).digest()}


def test_every_world_record_is_marked_fictional_and_carries_no_gold_vocabulary() -> None:
    world = build_world(7)
    records = list(world.records())
    assert len(records) > 1_000 and all(r["fictional"] == FICTIONAL_NOTICE for r in records)
    text = canonical_json(records).lower()
    for forbidden in ("answerability", "expected_answer", "required_evidence", "forbidden_claim", "outcome_label"):
        assert forbidden not in text
    assert world.digest() == build_world(7).digest() != build_world(8).digest()


def test_no_name_in_the_world_trips_the_arm_visible_screen() -> None:
    """A fictional merchant or product must never be refused as a gold-like word when it reaches a filter."""
    world = build_entities(7)
    names = (
        [m.display_name for m in world.merchants] + [p.name for p in world.products] + [t.name for t in world.tenants]
    )
    for name in names:
        screen_arm_visible("name", {"language": name})
