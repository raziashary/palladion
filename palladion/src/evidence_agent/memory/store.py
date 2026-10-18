"""P04 append-only request state; full memory promotion/validity belongs to P05."""
from __future__ import annotations

import json
import uuid
from typing import Any

from evidence_agent.core.errors import PermissionDenied
from evidence_agent.core.models import Principal, ReportedFact
from evidence_agent.storage.registry import Registry
from evidence_agent.storage.sqlite import utc_now


class CaseStore:
    def __init__(self, registry: Registry, principal: Principal, case_id: str) -> None:
        self.registry, self.principal, self.case_id = registry, principal, case_id

    def authorize(self) -> None:
        self.registry.access.authorize(self.principal, tenant_id=self.principal.tenant_id,
                                       case_id=self.case_id, grant="case:read")

    def append(self, kind: str, trace_id: str, payload: dict[str, Any]) -> str:
        self.authorize()
        if kind not in {"REQUEST", "ATTEMPT", "TOOL_RESULT", "RELEASE", "CANCELLED", "DIAGNOSTIC"}:
            raise ValueError("Unknown runtime event")
        envelope = {**payload, "schema_version": "1.0", "trace_id": trace_id}
        encoded = json.dumps(envelope, ensure_ascii=False)
        if len(encoded.encode()) > 65536:
            raise ValueError("Event exceeds bound")
        identifier = "evt_" + uuid.uuid4().hex
        with self.registry.database.transaction() as connection:
            self.authorize()
            connection.execute("INSERT INTO case_events VALUES(?,?,?,?,?,?,?)", (
                identifier, self.principal.tenant_id, self.case_id, self.principal.principal_id,
                "RUNTIME_" + kind, encoded, utc_now()))
        return identifier

    def recent(self, *, limit: int = 12) -> list[dict[str, Any]]:
        self.authorize()
        if not 1 <= limit <= 20:
            raise ValueError("Recall limit exceeded")
        rows = self.registry.database.connection.execute(
            "SELECT event_id,event_kind,payload_json,occurred_at FROM case_events "
            "WHERE tenant_id=? AND case_id=? AND event_kind IN "
            "('RUNTIME_REQUEST','RUNTIME_ATTEMPT','RUNTIME_TOOL_RESULT','RUNTIME_RELEASE','RUNTIME_CANCELLED') "
            "ORDER BY occurred_at DESC,event_id DESC LIMIT ?",
            (self.principal.tenant_id, self.case_id, limit)).fetchall()
        results = []
        for row in reversed(rows):
            payload = self._safe_payload(row[1], json.loads(row[2]))
            results.append({"event_id": row[0], "kind": row[1], "payload": payload, "at": row[3],
                            "authority": "NONE", "verification": "REQUIRES_RECHECK"})
        return results

    def _safe_payload(self, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        if kind == "RUNTIME_RELEASE":
            return {"trace_id": payload["trace_id"], "schema_version": "1.0",
                "disposition": payload["disposition"], "budget": payload.get("budget", {}),
                "evidence_handles": self._handles(payload.get("citations", []))}
        if kind == "RUNTIME_TOOL_RESULT":
            return {k: v for k, v in payload.items() if k in {
                "trace_id", "schema_version", "tool", "status", "error_code"}}
        # Request text and internal prompts never escape via event evidence/recall.
        return {k: v for k, v in payload.items() if k in {
            "trace_id", "schema_version", "attempt", "role", "stage", "status", "usage",
            "main_used", "tools_used"}}

    def own_reported_facts(self) -> tuple[ReportedFact, ...]:
        """Internal packet input: only this operator's prior reports, never verified facts."""
        self.authorize()
        rows = self.registry.database.connection.execute(
            "SELECT event_id,payload_json FROM case_events WHERE tenant_id=? AND case_id=? "
            "AND actor_id=? AND event_kind='RUNTIME_REQUEST' "
            "ORDER BY occurred_at DESC,event_id DESC LIMIT 4",
            (self.principal.tenant_id, self.case_id, self.principal.principal_id)).fetchall()
        reports = []
        for row in reversed(rows):
            query = json.loads(row[1]).get("query")
            if isinstance(query, str):
                reports.append(ReportedFact(fact_id=row[0], statement=query[:2048],
                    source="authenticated_operator", validity_policy_id="UNSPECIFIED",
                    provenance=(row[0],)))
        return tuple(reports)

    def _handles(self, citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        from evidence_agent.core.errors import EvidenceAgentError
        from evidence_agent.core.models import SourceKind, SourceRef
        from evidence_agent.live.gateway import read_observation
        from evidence_agent.policy.engine import PolicyEngine
        from evidence_agent.policy.registry import PolicyRegistry
        handles = []
        for citation in citations[:12]:
            identifier = citation.get("evidence_id", "")
            try:
                if citation.get("kind") == "DOCUMENT":
                    metadata = self.registry.source_metadata(self.principal, citation["revision_id"])
                    if metadata["approval_status"] != "APPROVED" or metadata["index_state"] != "READY":
                        continue
                    reference = SourceRef(source_kind=SourceKind.DOCUMENT_REVISION,
                        tenant_id=self.principal.tenant_id, source_id=citation["revision_id"],
                        revision_id=citation["revision_id"], chunk_id=identifier,
                        span_start=citation["start_byte"], span_end=citation["end_byte"])
                elif citation.get("kind") == "LIVE_OBSERVATION":
                    reference = read_observation(self.registry, self.principal, self.case_id, identifier).source_ref
                elif citation.get("kind") == "POLICY_DECISION":
                    PolicyEngine(PolicyRegistry(self.registry)).replay(self.principal, self.case_id, identifier)
                    reference = SourceRef(source_kind=SourceKind.POLICY_DECISION,
                        tenant_id=self.principal.tenant_id, source_id=identifier)
                else:
                    continue
                handles.append(reference.model_dump(mode="json"))
            except (EvidenceAgentError, ValueError, KeyError):
                continue  # No existence or stale-text leak from revoked/unavailable prior handles.
        return handles

    def read_event(self, identifier: str) -> dict[str, Any]:
        self.authorize()
        row = self.registry.database.connection.execute(
            "SELECT event_kind,payload_json,occurred_at FROM case_events WHERE tenant_id=? AND case_id=? "
            "AND event_id=? AND event_kind IN ('RUNTIME_REQUEST','RUNTIME_ATTEMPT','RUNTIME_TOOL_RESULT','RUNTIME_RELEASE','RUNTIME_CANCELLED')",
            (self.principal.tenant_id, self.case_id, identifier)).fetchone()
        if row is None:
            raise PermissionDenied
        payload = self._safe_payload(row[0], json.loads(row[1]))
        return {"event_id": identifier, "kind": row[0], "payload": payload, "at": row[2],
                "authority": "NONE", "verification": "REQUIRES_RECHECK"}
