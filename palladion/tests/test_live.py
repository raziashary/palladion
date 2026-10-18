import asyncio
import json
from datetime import timedelta

import pytest
from pydantic import ValidationError

from evidence_agent.core.errors import PermissionDenied
from evidence_agent.core.models import LiveOperationStatus
from evidence_agent.live.contracts import LookupRequest, Snapshot
from evidence_agent.live.gateway import LiveGateway, read_observation
from evidence_agent.live.mock import MockAdapter


def request(operation="get_transaction_status", target="TX-DEMO-102"):
    return LookupRequest(operation=operation, case_id="case-42", target_id=target)


def transaction(state="FAILED"):
    return Snapshot(status="OK", data={"transaction_id": "TX-DEMO-102", "state": state,
        "transaction_occurred_at": "2026-08-15T10:20:00+00:00"})


def gateway(p03, snapshots, **kwargs):
    adapter = MockAdapter(snapshots, **kwargs)
    return LiveGateway(p03.registry, adapter, p03.config, clock=lambda: p03.now), adapter


def test_named_reads_persist_reopenable_scope_bound_observations(p03):
    service, adapter = gateway(p03, {("get_transaction_status", "TX-DEMO-102"): (transaction(),)})
    result = asyncio.run(service.lookup(p03.reader, request()))
    assert result.operation_status is LiveOperationStatus.OK
    assert result.data["state"] == "FAILED"
    assert read_observation(p03.registry, p03.reader, "case-42", result.lookup_id) == result
    assert sum(adapter.calls.values()) == 1
    with pytest.raises(PermissionDenied):
        read_observation(p03.registry, p03.uploader, "case-43", result.lookup_id)
    audit = p03.registry.database.connection.execute(
        "SELECT safe_payload_json FROM audit_events WHERE event_kind='LIVE_READ'").fetchone()[0]
    assert "target_sha256" in audit and "TX-DEMO-102" not in audit and '"state"' not in audit


@pytest.mark.parametrize("status", ["NOT_FOUND", "FORBIDDEN", "INVALID_ARGUMENT", "RATE_LIMITED",
                                    "TIMEOUT", "UNAVAILABLE", "SCHEMA_MISMATCH"])
def test_all_failure_statuses_are_explicit_not_facts(p03, status):
    service, adapter = gateway(p03, {("get_transaction_status", "TX-DEMO-102"):
                                    (Snapshot(status=status, data={"secret": "CANARY"}),)})
    result = asyncio.run(service.lookup(p03.reader, request()))
    assert result.operation_status.value == status
    assert result.data == {} and result.error is not None
    expected = 2 if status in {"TIMEOUT", "UNAVAILABLE", "RATE_LIMITED"} else 1
    assert sum(adapter.calls.values()) == expected
    assert "CANARY" not in result.model_dump_json()


def test_authorization_before_call_and_at_reader_no_existence_leak(p03):
    service, adapter = gateway(p03, {})
    for target in ("TX-DEMO-143", "TX-DEMO-999", "TX-DEMO-288"):
        with pytest.raises(PermissionDenied, match="Access denied"):
            asyncio.run(service.lookup(p03.reader, request(target=target)))
    assert sum(adapter.calls.values()) == 0
    assert p03.registry.database.connection.execute(
        "SELECT count(*) FROM case_events WHERE event_kind='LIVE_OBSERVATION'").fetchone()[0] == 0


@pytest.mark.parametrize("extra", [{"url": "https://bad.example"}, {"sql": "DROP TABLE cases"},
                                   {"principal_id": "admin-a"}, {"operation_version": "2.0"}])
def test_dynamic_privileges_endpoints_and_versions_rejected(extra):
    with pytest.raises(ValidationError):
        LookupRequest.model_validate({"operation": "get_transaction_status", "case_id": "case-42",
                                       "target_id": "TX-DEMO-102", **extra})
    with pytest.raises(ValidationError):
        request(target="../other")


def test_old_bi_cutoff_stays_stale_despite_current_observation(p03):
    snapshot = Snapshot(status="OK", data={"merchant_id": "MERCHANT-DEMO-102", "result": "NOT_FOUND"},
                        data_as_of=p03.now-timedelta(days=1))
    service, _ = gateway(p03, {("get_merchant_summary", "MERCHANT-DEMO-102"): (snapshot,)})
    result = asyncio.run(service.lookup(p03.reader, request("get_merchant_summary", "MERCHANT-DEMO-102")))
    assert result.operation_status is LiveOperationStatus.STALE_DATA
    assert result.observed_at == p03.now and result.data_as_of == snapshot.data_as_of
    assert result.data["result"] == "NOT_FOUND"  # Scoped BI result, never transaction nonexistence.


def test_schema_extra_target_and_oversized_output_fail_closed(p03):
    for data in ({**transaction().data, "raw_secret": "CANARY"},
                 {**transaction().data, "transaction_id": "TX-DEMO-143"},
                 {**transaction().data, "state": "CANARY"*4000}):
        service, _ = gateway(p03, {("get_transaction_status", "TX-DEMO-102"):
                                  (Snapshot(status="OK", data=data),)})
        result = asyncio.run(service.lookup(p03.reader, request()))
        assert result.operation_status is LiveOperationStatus.SCHEMA_MISMATCH
        assert result.data == {} and "CANARY" not in result.model_dump_json()


def test_deduplicate_inflight_but_refresh_finished_reads(p03):
    service, adapter = gateway(p03, {("get_transaction_status", "TX-DEMO-102"):
                                    (transaction(), transaction("SUCCEEDED"))}, delay_seconds=.01)

    async def run():
        one, two = await asyncio.gather(service.lookup(p03.reader, request()), service.lookup(p03.reader, request()))
        assert one.lookup_id == two.lookup_id
        three = await service.lookup(p03.reader, request())
        assert three.lookup_id != one.lookup_id and three.data["state"] == "SUCCEEDED"
    asyncio.run(run())
    assert sum(adapter.calls.values()) == 2


def test_deadline_cancellation_and_rate_budget_are_bounded(p03):
    operation = p03.config.operations["get_transaction_status"].model_copy(update={"timeout_ms": 20})
    config = p03.config.model_copy(update={"operations": {"get_transaction_status": operation}, "calls_per_minute": 1})
    adapter = MockAdapter({("get_transaction_status", "TX-DEMO-102"): (transaction(),)}, delay_seconds=.1)
    service = LiveGateway(p03.registry, adapter, config, clock=lambda: p03.now)
    assert asyncio.run(service.lookup(p03.reader, request())).operation_status is LiveOperationStatus.TIMEOUT
    assert adapter.cancelled == 1
    assert asyncio.run(service.lookup(p03.reader, request())).operation_status is LiveOperationStatus.RATE_LIMITED
    service, adapter = gateway(p03, {}, delay_seconds=1)

    async def cancel():
        task = asyncio.create_task(service.lookup(p03.reader, request()))
        await asyncio.sleep(.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not service._pending
    asyncio.run(cancel())
    assert adapter.cancelled == 1
    audits = [json.loads(r[0]) for r in p03.registry.database.connection.execute(
        "SELECT safe_payload_json FROM audit_events WHERE event_kind='LIVE_READ'")]
    assert any(a["status"] == "CANCELLED" for a in audits)


def test_mid_read_membership_revocation_prevents_persistence(p03):
    service, _ = gateway(p03, {("get_transaction_status", "TX-DEMO-102"): (transaction(),)}, delay_seconds=.03)

    async def run():
        task = asyncio.create_task(service.lookup(p03.reader, request()))
        await asyncio.sleep(.01)
        p03.registry.revoke_membership(p03.admin, p03.reader.principal_id, "case-42")
        with pytest.raises(PermissionDenied):
            await task
    asyncio.run(run())
    assert p03.registry.database.connection.execute(
        "SELECT count(*) FROM case_events WHERE event_kind='LIVE_OBSERVATION'").fetchone()[0] == 0


def test_fanout_cap_and_incident_timestamp_contract(p03):
    snapshots = {("get_transaction_status", "TX-DEMO-102"): (transaction(),),
                 ("get_incident_status", "INC-DEMO-102"): (Snapshot(status="OK",
                  data={"incident_id": "INC-DEMO-102", "state": "OPEN"}, source_event_at=p03.now),)}
    service, adapter = gateway(p03, snapshots, delay_seconds=.03)
    service.config = service.config.model_copy(update={"max_pending": 1})

    async def run():
        task = asyncio.create_task(service.lookup(p03.reader, request()))
        await asyncio.sleep(.01)
        denied = await service.lookup(p03.reader, request("get_incident_status", "INC-DEMO-102"))
        assert denied.operation_status is LiveOperationStatus.RATE_LIMITED
        await task
        incident = await service.lookup(p03.reader, request("get_incident_status", "INC-DEMO-102"))
        assert incident.operation_status is LiveOperationStatus.OK
        assert incident.source_event_at == p03.now
        audit = p03.registry.database.connection.execute(
            "SELECT safe_payload_json FROM audit_events WHERE trace_id=?", (incident.lookup_id,)).fetchone()[0]
        assert json.loads(audit)["source_event_at"] == p03.now.isoformat()
    asyncio.run(run())
    assert sum(adapter.calls.values()) == 2


def test_single_retry_owner_can_recover_transient_failure(p03):
    service, adapter = gateway(p03, {("get_transaction_status", "TX-DEMO-102"):
                                    (Snapshot(status="RATE_LIMITED"), transaction())})
    observation = asyncio.run(service.lookup(p03.reader, request()))
    assert observation.operation_status is LiveOperationStatus.OK
    assert sum(adapter.calls.values()) == 2
    audit = p03.registry.database.connection.execute(
        "SELECT safe_payload_json FROM audit_events WHERE trace_id=?", (observation.lookup_id,)).fetchone()[0]
    assert json.loads(audit)["attempts"] == 2


def test_max_concurrent_reads_is_enforced(p03):
    class TrackingAdapter(MockAdapter):
        active = maximum = 0

        async def read(self, req):
            self.active += 1
            self.maximum = max(self.maximum, self.active)
            try:
                return await super().read(req)
            finally:
                self.active -= 1

    adapter = TrackingAdapter({("get_transaction_status", "TX-DEMO-102"): (transaction(),),
        ("get_incident_status", "INC-DEMO-102"): (Snapshot(status="OK",
            data={"incident_id": "INC-DEMO-102", "state": "OPEN"}),)}, delay_seconds=.02)
    service = LiveGateway(p03.registry, adapter, p03.config.model_copy(update={"max_concurrent": 1}),
                          clock=lambda: p03.now)

    async def run():
        results = await asyncio.gather(service.lookup(p03.reader, request()),
            service.lookup(p03.reader, request("get_incident_status", "INC-DEMO-102")))
        assert all(r.operation_status is LiveOperationStatus.OK for r in results)
    asyncio.run(run())
    assert adapter.maximum == 1 and adapter.active == 0
