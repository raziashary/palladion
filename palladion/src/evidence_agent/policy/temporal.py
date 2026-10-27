"""Policy-declared trusted time, valid/record time and explicit scoped precedence."""
from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime

from evidence_agent.core.errors import PermissionDenied
from evidence_agent.core.models import LiveOperationStatus, Principal, SourceRef, TimeBasis
from evidence_agent.live.gateway import iso, read_observation, read_scope
from evidence_agent.policy.registry import PolicyRegistry, PolicySpec


@dataclass(frozen=True)
class Selection:
    status: str
    spec: PolicySpec | None = None
    as_of: datetime | None = None
    sources: tuple[SourceRef, ...] = ()
    trace: tuple[str, ...] = ()


class TemporalResolver:
    def __init__(self, policies: PolicyRegistry, *, clock: Callable[[], datetime] | None = None) -> None:
        self.policies, self.registry, self.clock = policies, policies.registry, clock or policies.clock

    def resolve(self, principal: Principal, case_id: str, family_id: str,
                 evidence_ids: Sequence[str] = (), *, knowledge_cutoff: datetime | None = None,
                 evaluation_time: datetime | None = None) -> Selection:
        database = self.registry.database
        with nullcontext() if database.connection.in_transaction else database.transaction():
            return self._resolve(principal, case_id, family_id, evidence_ids, knowledge_cutoff, evaluation_time)

    def _resolve(self, principal: Principal, case_id: str, family_id: str,
                  evidence_ids: Sequence[str], cutoff: datetime | None, evaluation_time: datetime | None) -> Selection:
        scope = read_scope(self.registry, principal, case_id)
        now = self.clock()
        iso(now)
        if len(evidence_ids) > 32 or not family_id or len(family_id) > 100:
            raise ValueError("Selection bounds exceeded")
        if cutoff is not None:
            iso(cutoff)
            self.registry.access.authorize(principal, tenant_id=principal.tenant_id,
                                            role="admin", grant="document:approve")
            if cutoff > now:
                raise ValueError("Knowledge cutoff cannot be in the future")
        if evaluation_time is not None:
            iso(evaluation_time)
            if cutoff is None:
                raise PermissionDenied
            if evaluation_time > now:
                raise ValueError("Audit simulation time cannot be in the future")
        rows = self.registry.database.connection.execute(
            "SELECT * FROM policy_versions WHERE tenant_id=? AND family_id=? LIMIT 129",
            (principal.tenant_id, family_id)).fetchall()
        if len(rows) > 128:
            return Selection("POLICY_CONFLICT", trace=("CANDIDATE_BOUND_EXCEEDED",))
        candidates: list[tuple[PolicySpec, tuple[SourceRef, ...]]] = []
        scope_matches = 0
        for row in rows:
            spec = PolicySpec.model_validate_json(row["decision_table_json"])
            if (case_id not in spec.allowed_case_ids or spec.product != scope.product or
                    spec.transaction_class != scope.transaction_class):
                continue
            scope_matches += 1
            if cutoff is not None and datetime.fromisoformat(row["registered_at"]) > cutoff:
                continue
            events = self.registry.database.connection.execute(
                "SELECT event_kind,occurred_at FROM audit_events WHERE tenant_id=? AND trace_id=? "
                "AND event_kind IN ('POLICY_APPROVED','POLICY_REVOKED') ORDER BY occurred_at,audit_id",
                (principal.tenant_id, spec.version_id)).fetchall()
            known = [e for e in events if cutoff is None or datetime.fromisoformat(e[1]) <= cutoff]
            if (not any(e[0] == "POLICY_APPROVED" for e in known) or
                    any(e[0] == "POLICY_REVOKED" for e in known) or
                    (cutoff is None and row["status"] != "APPROVED")):
                continue
            try:
                sources = tuple(self.policies.clause(principal, c, knowledge_cutoff=cutoff) for c in spec.clauses)
            except PermissionDenied:
                continue
            candidates.append((spec, sources))
        if not candidates:
            return Selection("NOT_APPLICABLE" if rows and not scope_matches else "NO_APPLICABLE_POLICY",
                             trace=("NO_ACCESSIBLE_APPROVED_CANDIDATE",))
        if len({spec.time_basis for spec, _ in candidates}) != 1:
            return Selection("POLICY_CONFLICT", trace=("MIXED_TIME_BASIS_WITHOUT_APPROVED_MIGRATION",))
        instants: dict[str, datetime] = {}
        for spec, _ in candidates:
            if spec.time_basis is TimeBasis.EVALUATION_AT:
                instant = evaluation_time or now
            elif spec.time_basis is TimeBasis.CASE_OPENED_AT:
                instant = self.registry.case_opened_at(principal, case_id)
            elif spec.time_basis is TimeBasis.DOMAIN_EVENT_AT:
                if spec.domain_event not in scope.domain_events:
                    return Selection("MISSING_TIME_INPUT", trace=("NAMED_DOMAIN_EVENT_MISSING",))
                instant = scope.domain_events[spec.domain_event]
            else:
                times = set()
                attempted = False
                for evidence_id in evidence_ids:
                    observation = read_observation(self.registry, principal, case_id, evidence_id)
                    attempted |= observation.operation_id == "get_transaction_status"
                    if (observation.operation_id == "get_transaction_status" and
                            observation.operation_status is LiveOperationStatus.OK and
                            0 <= (now-observation.observed_at).total_seconds() <= spec.timestamp_max_age_seconds):
                        value = observation.data.get("transaction_occurred_at")
                        if isinstance(value, str):
                            times.add(datetime.fromisoformat(value))
                if not times:
                    return Selection("UNVERIFIED_TIME_SOURCE" if attempted else "MISSING_TIME_INPUT",
                                     trace=("PERSISTED_FRESH_TRANSACTION_TIME_REQUIRED",))
                if len(times) != 1:
                    return Selection("POLICY_CONFLICT", trace=("CONFLICTING_TRANSACTION_TIMES",))
                instant = times.pop()
            iso(instant)
            instants[spec.version_id] = instant
        eligible = []
        for spec, sources in candidates:
            instant = instants[spec.version_id]
            if instant < spec.valid_from or spec.valid_to is not None and instant >= spec.valid_to:
                continue
            valid_sources = True
            for clause in spec.clauses:
                metadata = self.registry.source_metadata(principal, clause.revision_id)
                lower, upper = metadata["valid_from"], metadata["valid_to"]
                if (isinstance(lower, str) and instant < datetime.fromisoformat(lower) or
                        isinstance(upper, str) and instant >= datetime.fromisoformat(upper)):
                    valid_sources = False
            if valid_sources:
                eligible.append((spec, sources))
        identifiers = {spec.version_id for spec, _ in eligible}
        superseded = set()
        edges = self.registry.database.connection.execute(
            "SELECT trace_id,safe_payload_json,occurred_at FROM audit_events WHERE tenant_id=? "
            "AND event_kind='POLICY_SUPERSEDES'", (principal.tenant_id,)).fetchall()
        for edge in edges:
            metadata = json.loads(edge["safe_payload_json"])
            successor = edge["trace_id"]
            if (successor in identifiers and metadata["predecessor"] in identifiers and
                    metadata["case_id"] == case_id and
                    (cutoff is None or datetime.fromisoformat(edge["occurred_at"]) <= cutoff) and
                    datetime.fromisoformat(metadata["valid_from"]) <= instants[successor]):
                superseded.add(metadata["predecessor"])
        maximal = [(spec, sources) for spec, sources in eligible if spec.version_id not in superseded]
        if not eligible:
            return Selection("NO_APPLICABLE_POLICY", trace=("NO_VALID_INTERVAL",))
        if len(maximal) != 1:
            return Selection("POLICY_CONFLICT", trace=("INCOMPARABLE_OR_CYCLIC_PRECEDENCE",))
        spec, sources = maximal[0]
        return Selection("SELECTED", spec, instants[spec.version_id], sources,
                         ("CURRENT_ACL_RECHECKED", "APPROVAL_AND_CLAUSES_VERIFIED",
                          "AUDIT_SIMULATION_TIME" if evaluation_time else "DECLARED_BACKEND_TIME_SOURCE",
                          "KNOWLEDGE_CUTOFF=" + (iso(cutoff) if cutoff else "CURRENT"),
                          "BASIS="+spec.time_basis.value, "AS_OF="+iso(instants[spec.version_id])))
