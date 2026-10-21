"""Target-authorized mock reads, bounded work and persisted admissible observations."""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import ValidationError

from evidence_agent.core.errors import PermissionDenied, ResourceConflict
from evidence_agent.core.models import (
    AccessScope,
    ErrorCode,
    ErrorEnvelope,
    FreshnessState,
    LiveObservation,
    LiveOperationStatus,
    Principal,
    SourceKind,
    SourceRef,
)
from evidence_agent.live.contracts import (
    DATA_MODELS,
    TARGET_FIELDS,
    AdapterConfig,
    CaseScope,
    LookupRequest,
    OperationConfig,
    Snapshot,
)
from evidence_agent.live.mock import ReadAdapter
from evidence_agent.storage.registry import Registry


def iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Aware backend time required")
    return value.astimezone(timezone.utc).isoformat()


def load_config(path: Path) -> AdapterConfig:
    return AdapterConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def append_case_event(registry: Registry, principal: Principal, case_id: str,
                      kind: str, payload: str, at: datetime, event_id: str) -> None:
    with registry.database.transaction() as connection:
        registry.access.authorize(principal, tenant_id=principal.tenant_id,
                                  case_id=case_id, grant="case:read")
        connection.execute("INSERT INTO case_events VALUES(?,?,?,?,?,?,?)",
                           (event_id, principal.tenant_id, case_id, principal.principal_id,
                            kind, payload, iso(at)))


def register_scope(registry: Registry, actor: Principal, case_id: str, scope: CaseScope,
                   at: datetime) -> None:
    """Authenticated fixture/owner producer; request arguments cannot create target grants."""
    registry.access.authorize(actor, tenant_id=actor.tenant_id, case_id=case_id,
                              role="admin", grant="document:approve")
    scope = CaseScope.model_validate_json(scope.model_dump_json())
    if any(event > at for event in scope.domain_events.values()):
        raise ValueError("Future domain event cannot be registered as observed")
    for operation, target in scope.targets.items():
        LookupRequest(operation=operation, case_id=case_id, target_id=target)
    existing = registry.database.connection.execute(
        "SELECT payload_json FROM case_events WHERE tenant_id=? AND case_id=? "
        "AND event_kind='LIVE_SCOPE_REGISTERED' ORDER BY occurred_at DESC,event_id DESC LIMIT 1",
        (actor.tenant_id, case_id)).fetchone()
    if existing:
        if CaseScope.model_validate_json(existing[0]) != scope:
            raise ResourceConflict
        return
    append_case_event(registry, actor, case_id, "LIVE_SCOPE_REGISTERED", scope.model_dump_json(),
                      at, "scope_" + uuid.uuid4().hex)


def read_scope(registry: Registry, principal: Principal, case_id: str) -> CaseScope:
    registry.access.authorize(principal, tenant_id=principal.tenant_id,
                              case_id=case_id, grant="case:read")
    row = registry.database.connection.execute(
        "SELECT payload_json FROM case_events WHERE tenant_id=? AND case_id=? "
        "AND event_kind='LIVE_SCOPE_REGISTERED' ORDER BY occurred_at DESC,event_id DESC LIMIT 1",
        (principal.tenant_id, case_id)).fetchone()
    if row is None:
        raise PermissionDenied
    return CaseScope.model_validate_json(row[0])


def read_observation(registry: Registry, principal: Principal, case_id: str,
                     lookup_id: str) -> LiveObservation:
    scope = read_scope(registry, principal, case_id)
    row = registry.database.connection.execute(
        "SELECT payload_json FROM case_events WHERE event_id=? AND tenant_id=? AND case_id=? "
        "AND event_kind='LIVE_OBSERVATION'", (lookup_id, principal.tenant_id, case_id)).fetchone()
    if row is None:
        raise PermissionDenied
    observation = LiveObservation.model_validate_json(row[0])
    data = observation.data
    operation = observation.operation_id
    if (operation not in scope.targets or observation.scope.tenant_id != principal.tenant_id or
            observation.scope.allowed_case_ids != (case_id,) or observation.lookup_id != lookup_id or
            observation.source_ref.source_id != lookup_id):
        raise PermissionDenied
    field = TARGET_FIELDS[operation]
    if observation.operation_status in {LiveOperationStatus.OK, LiveOperationStatus.STALE_DATA}:
        if data.get(field) != scope.targets[operation]:
            raise PermissionDenied
    return observation


class LiveGateway:
    def __init__(self, registry: Registry, adapter: ReadAdapter, config: AdapterConfig, *,
                 clock: Callable[[], datetime] | None = None) -> None:
        self.registry, self.adapter, self.config = registry, adapter, config
        self.clock = clock or registry.clock
        self._semaphore = asyncio.Semaphore(config.max_concurrent)
        self._pending: dict[tuple[str, str, str, str], asyncio.Task[LiveObservation]] = {}
        self._waiters: dict[tuple[str, str, str, str], int] = defaultdict(int)
        self._rates: dict[str, deque[float]] = defaultdict(deque)

    def _authorize(self, principal: Principal, request: LookupRequest) -> None:
        scope = read_scope(self.registry, principal, request.case_id)
        if scope.targets.get(request.operation) != request.target_id:
            raise PermissionDenied

    async def lookup(self, principal: Principal, request: LookupRequest) -> LiveObservation:
        self._authorize(principal, request)  # Before lookup; never leak target existence.
        config = self.config.operations.get(request.operation)
        if config is None:
            raise ValueError("Operation not configured")
        key = (principal.principal_id, request.case_id, request.operation, request.target_id)
        if key not in self._pending:
            now = time.monotonic()
            rates = self._rates[principal.principal_id]
            while rates and rates[0] <= now - 60:
                rates.popleft()
            if len(rates) >= self.config.calls_per_minute or len(self._pending) >= self.config.max_pending:
                return self._record(principal, request, Snapshot(status="RATE_LIMITED"), config, 0)
            rates.append(now)
            self._pending[key] = asyncio.create_task(self._read(principal, request, config))
        task = self._pending[key]
        self._waiters[key] += 1
        try:
            result = await asyncio.shield(task)
            self._authorize(principal, request)  # Again after any awaited work.
            return result
        finally:
            self._waiters[key] -= 1
            if not self._waiters[key]:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                self._pending.pop(key, None)
                self._waiters.pop(key, None)

    async def _read(self, principal: Principal, request: LookupRequest,
                    config: OperationConfig) -> LiveObservation:
        attempts = 0
        snapshot = Snapshot(status="UNAVAILABLE")
        try:
            # Includes queueing, every attempt and backoff; one retry owner.
            async with asyncio.timeout(config.timeout_ms / 1000):
                async with self._semaphore:
                    for attempts in range(1, config.max_attempts + 1):
                        try:
                            snapshot = await self.adapter.read(request)
                            if not isinstance(snapshot, Snapshot):
                                raise TypeError("Adapter contract mismatch")
                        except (TimeoutError, ConnectionError, OSError):
                            snapshot = Snapshot(status="UNAVAILABLE")
                        except (ValidationError, ValueError, TypeError):
                            snapshot = Snapshot(status="SCHEMA_MISMATCH")
                        if snapshot.status not in {"TIMEOUT", "UNAVAILABLE", "RATE_LIMITED"}:
                            break
                        if attempts < config.max_attempts:
                            await asyncio.sleep(config.backoff_ms / 1000)
        except TimeoutError:
            snapshot = Snapshot(status="TIMEOUT")
        except asyncio.CancelledError:
            self._audit(principal, request, "CANCELLED", attempts, self.clock())
            raise
        self._authorize(principal, request)
        return self._record(principal, request, snapshot, config, attempts)

    def _record(self, principal: Principal, request: LookupRequest, snapshot: Snapshot,
                config: OperationConfig, attempts: int) -> LiveObservation:
        now = self.clock()
        iso(now)
        status = LiveOperationStatus(snapshot.status)
        freshness = FreshnessState.UNKNOWN
        data = {}
        if snapshot.status == "OK":
            try:
                if len(snapshot.model_dump_json().encode()) > config.max_response_bytes:
                    raise ValueError("Oversized response")
                validated = DATA_MODELS[request.operation].model_validate_json(json.dumps(snapshot.data))
                data = validated.model_dump(mode="json", exclude={"schema_version"})
                if (request.operation == "get_transaction_status" and
                        datetime.fromisoformat(str(data["transaction_occurred_at"])) > now):
                    raise ValueError("Future transaction event")
                if data[TARGET_FIELDS[request.operation]] != request.target_id:
                    raise ValueError("Mismatched upstream target")
                cutoff = snapshot.data_as_of if config.freshness_field == "data_as_of" else now
                if snapshot.source_event_at is not None and snapshot.source_event_at > now:
                    raise ValueError("Future source event")
                if cutoff is None or cutoff > now:
                    raise ValueError("Missing or future snapshot cutoff")
                freshness = (FreshnessState.STALE if (now-cutoff).total_seconds() > config.max_age_seconds
                             else FreshnessState.FRESH)
                if freshness is FreshnessState.STALE:
                    status = LiveOperationStatus.STALE_DATA
            except (ValidationError, ValueError, KeyError, TypeError):
                status, data = LiveOperationStatus.SCHEMA_MISMATCH, {}
        lookup_id = "live_" + uuid.uuid4().hex
        observation = LiveObservation(
            lookup_id=lookup_id, operation_id=request.operation, operation_status=status,
            source_system=config.source_system, data=data, observed_at=now,
            source_event_at=snapshot.source_event_at, data_as_of=snapshot.data_as_of,
            freshness_state=freshness, scope=AccessScope(tenant_id=principal.tenant_id,
                                                       allowed_case_ids=(request.case_id,)),
            source_ref=SourceRef(source_kind=SourceKind.LIVE_LOOKUP,
                                 tenant_id=principal.tenant_id, source_id=lookup_id),
            error=None if status in {LiveOperationStatus.OK, LiveOperationStatus.STALE_DATA} else
            ErrorEnvelope(error_code={LiveOperationStatus.FORBIDDEN: ErrorCode.PERMISSION_DENIED,
                LiveOperationStatus.NOT_FOUND: ErrorCode.NOT_FOUND,
                LiveOperationStatus.INVALID_ARGUMENT: ErrorCode.VALIDATION_ERROR,
                LiveOperationStatus.SCHEMA_MISMATCH: ErrorCode.VALIDATION_ERROR}.get(status, ErrorCode.UNAVAILABLE), retryable=status in {
                LiveOperationStatus.TIMEOUT, LiveOperationStatus.UNAVAILABLE, LiveOperationStatus.RATE_LIMITED},
                correlation_id=lookup_id, user_summary="Scoped operational observation unavailable"))
        append_case_event(self.registry, principal, request.case_id, "LIVE_OBSERVATION",
                          observation.model_dump_json(), now, lookup_id)
        self._audit(principal, request, status.value, attempts, now, observation)
        return observation

    def _audit(self, principal: Principal, request: LookupRequest, status: str,
               attempts: int, at: datetime, observation: LiveObservation | None = None) -> None:
        payload = {"operation": request.operation, "case_id": request.case_id,
                   "target_sha256": hashlib.sha256(request.target_id.encode()).hexdigest(),
                   "status": status, "attempts": attempts, "observed_at": iso(at),
                   "operation_version": request.operation_version}
        if observation is not None:
            payload.update({"source_system": observation.source_system,
                "source_event_at": iso(observation.source_event_at) if observation.source_event_at else None,
                "data_as_of": iso(observation.data_as_of) if observation.data_as_of else None})
        with self.registry.database.transaction() as connection:
            connection.execute("INSERT INTO audit_events VALUES(?,?,?,?,?,?,?)",
                               ("audit_"+uuid.uuid4().hex, observation.lookup_id if observation else "live_"+uuid.uuid4().hex,
                                principal.principal_id, principal.tenant_id,
                                "LIVE_READ", json.dumps(payload), iso(at)))
