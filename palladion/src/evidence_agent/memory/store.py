"""Append-only runtime events and explicitly controlled scoped memory."""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import Field, model_validator

from evidence_agent.core.errors import EvidenceAgentError, PermissionDenied
from evidence_agent.core.models import Principal, ReportedFact, SourceRef, VersionedModel
from evidence_agent.storage.registry import Registry
from evidence_agent.storage.sqlite import utc_now


class CaseStore:
    def __init__(self, registry: Registry, principal: Principal, case_id: str) -> None:
        self.registry, self.principal, self.case_id = registry, principal, case_id

    def memory(self) -> MemoryStore:
        return MemoryStore(self)

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
                "evidence_handles": self._handles(payload.get("citations", [])),
                "missing_requirements": [v for v in payload.get("missing_requirements", [])[:32]
                    if isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9_]{1,100}", v)],
                "hypotheses": [h for h in payload.get("hypotheses", [])[:4]
                    if h.get("verification_status") == "UNVERIFIED" and
                    h.get("text") == "A reconciliation delay is possible; this is unverified."]}
        if kind == "RUNTIME_TOOL_RESULT":
            return {k: v for k, v in payload.items() if k in {
                "trace_id", "schema_version", "tool", "status", "error_code"}}
        # Request text and internal prompts never escape via event evidence/recall.
        return {k: v for k, v in payload.items() if k in {
            "trace_id", "schema_version", "attempt", "role", "stage", "status", "usage",
            "main_used", "tools_used"}}

    def unresolved_questions(self) -> tuple[str, ...]:
        """An empty/outage reply cannot resolve a prior executed incomplete policy."""
        from evidence_agent.core.models import PolicyDecisionStatus
        from evidence_agent.policy.engine import PolicyEngine
        from evidence_agent.policy.registry import PolicyRegistry, PolicySpec

        self.authorize()
        rows = self.registry.database.connection.execute(
            "SELECT event_id FROM (SELECT event_id, row_number() OVER ("
            "PARTITION BY json_extract(payload_json,'$.policy_family_id') "
            "ORDER BY occurred_at DESC,event_id DESC) AS rank FROM case_events "
            "WHERE tenant_id=? AND case_id=? AND event_kind='POLICY_DECISION' "
            "AND json_extract(payload_json,'$.evaluation_mode')='current' "
            "AND json_extract(payload_json,'$.status') IN ('INCOMPLETE_INPUT','DETERMINED')) "
            "WHERE rank=1 LIMIT 128", (self.principal.tenant_id, self.case_id)).fetchall()
        questions: set[str] = set()
        policy_fields: set[str] = set()
        for row in rows:
            try:
                decision = PolicyEngine(PolicyRegistry(self.registry)).replay(
                    self.principal, self.case_id, row[0])
            except (EvidenceAgentError, ValueError):
                continue
            if decision.version_id:
                spec_row = self.registry.database.connection.execute(
                    "SELECT decision_table_json FROM policy_versions WHERE tenant_id=? AND version_id=?",
                    (self.principal.tenant_id, decision.version_id)).fetchone()
                if spec_row:
                    policy_fields.update(f.name for f in PolicySpec.model_validate_json(spec_row[0]).required_facts)
            if decision.status is PolicyDecisionStatus.INCOMPLETE_INPUT:
                questions.update(decision.missing_fields)
        # Case questions not covered by an executed policy remain open until explicit case closure.
        row = self.registry.database.connection.execute(
            "SELECT payload_json FROM case_events WHERE tenant_id=? AND case_id=? "
            "AND event_kind='RUNTIME_RELEASE' "
            "AND json_array_length(json_extract(payload_json,'$.missing_requirements'))>0 "
            "ORDER BY occurred_at DESC,event_id DESC LIMIT 1",
            (self.principal.tenant_id, self.case_id)).fetchone()
        if row:
            previous = self._safe_payload("RUNTIME_RELEASE", json.loads(row[0]))["missing_requirements"]
            questions.update(set(previous) - policy_fields)
        return tuple(sorted(questions)[:5])

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
                    from evidence_agent.retrieval.evidence import EvidenceResolver
                    from evidence_agent.storage.catalog import Catalog
                    catalog = Catalog(self.registry)
                    generation = catalog.eligible_generation_metadata(self.principal, citation["revision_id"])
                    if generation is None:
                        continue
                    EvidenceResolver(catalog, str(generation["fingerprint"])).resolve(
                        self.principal, self.case_id, identifier, generation=citation.get("generation"))
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


class MemorySpec(VersionedModel):
    memory_kind: Literal["EPISODIC", "SEMANTIC", "PROCEDURAL"] = "SEMANTIC"
    scope_kind: Literal["USER", "CASE", "TEAM", "ORGANIZATION"] = "USER"
    scope_id: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=2048)
    claim_kind: Literal["REPORTED", "HYPOTHESIS", "PROCEDURE"] = "REPORTED"
    validity_policy_id: str = Field(default="UNSPECIFIED", min_length=1, max_length=100)
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    source_ref: SourceRef | None = None

    @model_validator(mode="after")
    def valid_dates(self) -> MemorySpec:
        for instant in (self.valid_from, self.valid_until):
            if instant is not None and (instant.tzinfo is None or instant.utcoffset() is None):
                raise ValueError("Memory validity requires aware timestamps")
        if self.valid_from and self.valid_until and self.valid_until <= self.valid_from:
            raise ValueError("Invalid memory validity interval")
        return self


class MemoryStore:
    """Application-only writes. The model's recall tool has no reference to mutations."""

    def __init__(self, case: CaseStore) -> None:
        self.case, self.registry = case, case.registry
        self.last_recall_incomplete = False

    def _admin(self) -> None:
        self.case.authorize()
        self.registry.access.authorize(self.case.principal, tenant_id=self.case.principal.tenant_id,
            case_id=self.case.case_id, role="admin", grant="document:approve")

    def team_membership(self, team_id: str, principal_id: str, *, revoke: bool = False) -> None:
        self._admin()
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", team_id):
            raise ValueError("Invalid team identifier")
        member = self.registry.access.authenticate(principal_id)
        if member.tenant_id != self.case.principal.tenant_id:
            raise PermissionDenied
        now = utc_now()
        with self.registry.database.transaction() as db:
            self._admin()
            db.execute("INSERT OR IGNORE INTO memory_teams VALUES(?,?)", (member.tenant_id, team_id))
            db.execute("INSERT INTO memory_team_memberships VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(tenant_id,team_id,principal_id) DO UPDATE SET "
                "set_by=excluded.set_by,set_at=excluded.set_at,revoked_at=excluded.revoked_at",
                (member.tenant_id, team_id, principal_id, self.case.principal.principal_id,
                 now, now if revoke else None))
            self._event(db, "TEAM_CHANGED", {"team_id": team_id, "principal_id": principal_id, "revoked": revoke})

    def _event(self, db: Any, kind: str, payload: dict[str, Any]) -> str:
        identifier = "evt_" + uuid.uuid4().hex
        db.execute("INSERT INTO case_events VALUES(?,?,?,?,?,?,?)", (identifier,
            self.case.principal.tenant_id, self.case.case_id, self.case.principal.principal_id,
            "MEMORY_" + kind, json.dumps(payload), utc_now()))
        return identifier

    def _source(self, ref: SourceRef | None, origin: str | None) -> None:
        if ref is None:
            return
        from evidence_agent.core.models import SourceKind
        from evidence_agent.live.gateway import read_observation
        from evidence_agent.policy.engine import PolicyEngine
        from evidence_agent.policy.registry import PolicyRegistry
        from evidence_agent.retrieval.evidence import EvidenceResolver
        from evidence_agent.storage.catalog import Catalog
        if ref.tenant_id != self.case.principal.tenant_id or origin is None:
            raise PermissionDenied
        if ref.source_kind is SourceKind.DOCUMENT_REVISION:
            catalog = Catalog(self.registry)
            metadata = catalog.eligible_generation_metadata(self.case.principal, ref.revision_id or "")
            if metadata is None:
                raise PermissionDenied
            passage = EvidenceResolver(catalog, str(metadata["fingerprint"])).resolve(
                self.case.principal, origin, ref.chunk_id or "")
            if (passage.revision_id != ref.revision_id or ref.source_id != ref.revision_id or
                    ref.span_start is not None and (ref.span_start, ref.span_end) != (passage.start_byte, passage.end_byte)):
                raise PermissionDenied
        elif ref.source_kind is SourceKind.LIVE_LOOKUP:
            read_observation(self.registry, self.case.principal, origin, ref.source_id)
        elif ref.source_kind is SourceKind.POLICY_DECISION:
            PolicyEngine(PolicyRegistry(self.registry)).replay(self.case.principal, origin, ref.source_id)
        else:
            CaseStore(self.registry, self.case.principal, origin).read_event(ref.source_id)

    def write(self, spec: MemorySpec, *, supersedes_id: str | None = None,
              general: bool = False) -> str:
        self.case.authorize()
        if self.closed():
            raise PermissionDenied
        principal = self.case.principal
        origin = None if general else self.case.case_id
        owner = principal.principal_id
        if spec.scope_kind in {"TEAM", "ORGANIZATION"} or general or spec.claim_kind == "PROCEDURE":
            self._admin()
        if supersedes_id:
            previous = self.read(supersedes_id, for_control=True)
            owner = previous["owner_id"]
            origin = previous["origin_case_id"]
            if owner != principal.principal_id:
                self._admin()
            # Corrections/promotion cannot erase an originating private case/source.
            old_ref = previous["source_ref"]
            if old_ref != (spec.source_ref.model_dump(mode="json") if spec.source_ref else None):
                raise ValueError("Correction must preserve source provenance")
        if spec.scope_kind == "USER" and owner != principal.principal_id:
            self._admin()
            if spec.scope_id != owner:
                raise PermissionDenied
            if origin:
                self.registry.access.authorize(principal, tenant_id=principal.tenant_id,
                    case_id=origin, grant="case:read")
        else:
            self.registry.access.memory_scope(principal, tenant_id=principal.tenant_id,
                origin_case=origin, current_case=self.case.case_id, kind=spec.scope_kind,
                scope_id=spec.scope_id, owner_id=owner)
        self._source(spec.source_ref, origin)
        now = utc_now()
        start = spec.valid_from or datetime.now(timezone.utc)
        if spec.valid_until and spec.valid_until <= start:
            raise ValueError("Invalid memory validity interval")
        identifier = "mem_" + uuid.uuid4().hex
        with self.registry.database.transaction() as db:
            self.case.authorize()
            if supersedes_id and db.execute("SELECT 1 FROM memory_provenance WHERE supersedes_id=?",
                                           (supersedes_id,)).fetchone():
                raise ValueError("Memory already superseded")
            event = self._event(db, "WRITTEN", {"memory_id": identifier, "supersedes_id": supersedes_id,
                "scope_kind": spec.scope_kind, "validity_policy_id": spec.validity_policy_id})
            db.execute("INSERT INTO memory_entries VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                identifier, spec.memory_kind, principal.tenant_id, spec.scope_kind, spec.scope_id,
                event, spec.source_ref.source_id if spec.source_ref else None, "UNVERIFIED",
                spec.content, spec.validity_policy_id, spec.valid_until.isoformat() if spec.valid_until else None,
                None, now))
            db.execute("INSERT INTO memory_provenance VALUES(?,?,?,?,?,?,?,?,?)", (
                identifier, owner, origin, principal.principal_id, now, start.isoformat(),
                supersedes_id, spec.claim_kind, spec.source_ref.model_dump_json() if spec.source_ref else None))
        return identifier

    def read(self, identifier: str, *, for_control: bool = False) -> dict[str, Any]:
        self.case.authorize()
        row = self.registry.database.connection.execute(
            "SELECT e.*,p.* FROM memory_entries e JOIN memory_provenance p USING(memory_id) "
            "WHERE memory_id=? AND tenant_id=?", (identifier, self.case.principal.tenant_id)).fetchone()
        if row is None:
            raise PermissionDenied
        if for_control and row["owner_id"] != self.case.principal.principal_id:
            self._admin()
            if row["origin_case_id"]:
                self.registry.access.authorize(self.case.principal, tenant_id=row["tenant_id"],
                    case_id=row["origin_case_id"], grant="case:read")
        else:
            self.registry.access.memory_scope(self.case.principal, tenant_id=row["tenant_id"],
            origin_case=row["origin_case_id"], current_case=self.case.case_id,
            kind=row["scope_kind"], scope_id=row["scope_id"], owner_id=row["owner_id"])
        db = self.registry.database.connection
        if not for_control and db.execute("SELECT 1 FROM memory_provenance WHERE supersedes_id=?", (identifier,)).fetchone():
            raise PermissionDenied
        if not for_control and db.execute("SELECT 1 FROM case_events WHERE tenant_id=? AND event_kind='MEMORY_REVOKED' "
                      "AND json_extract(payload_json,'$.memory_id')=?", (row["tenant_id"], identifier)).fetchone():
            raise PermissionDenied
        now = datetime.now(timezone.utc)
        if not for_control and (now < datetime.fromisoformat(row["valid_from"]) or (
                row["user_valid_until"] and now >= datetime.fromisoformat(row["user_valid_until"]))):
            raise PermissionDenied
        if self.closed(row["origin_case_id"]):
            raise PermissionDenied
        ref = SourceRef.model_validate_json(row["source_ref_json"]) if row["source_ref_json"] else None
        self._source(ref, row["origin_case_id"])
        return {"memory_id": identifier, "event_id": identifier, "kind": row["memory_kind"],
            "scope_kind": row["scope_kind"], "scope_id": row["scope_id"], "owner_id": row["owner_id"],
            "origin_case_id": row["origin_case_id"], "content": row["content"],
            "claim_kind": row["claim_kind"], "verification_status": "UNVERIFIED", "authority": "NONE",
            "source_event_id": row["source_event_id"], "source_ref": ref.model_dump(mode="json") if ref else None,
            "validity_policy_id": row["validity_policy_id"], "valid_from": row["valid_from"],
            "valid_until": row["user_valid_until"], "set_by": row["set_by"], "set_at": row["set_at"]}

    def recall(self, *, query: str | None = None, memory_id: str | None = None,
               category: str | None = None, limit: int = 8) -> list[dict[str, Any]]:
        self.case.authorize()
        self.last_recall_incomplete = False
        if not 1 <= limit <= 20 or query is not None and len(query) > 256:
            raise ValueError("Memory recall bounds exceeded")
        if category not in {None, "EPISODIC", "SEMANTIC", "PROCEDURAL"}:
            raise ValueError("Unknown memory category")
        if memory_id:
            candidates = [(memory_id,)]
        else:
            sql = "SELECT e.memory_id FROM memory_entries e JOIN memory_provenance p USING(memory_id) "
            params: list[Any] = [self.case.principal.tenant_id]
            if query:
                words = re.findall(r"\w+", query, flags=re.UNICODE)[:16]
                if not words:
                    return []
                sql += "JOIN memory_fts f ON f.memory_id=e.memory_id "
                condition = " AND memory_fts MATCH ?"
                params.append(" AND ".join('"' + word + '"' for word in words))
            else:
                condition = ""
            sql += "WHERE e.tenant_id=?" + condition
            # Scope before ranking/windowing: denied users/cases must not starve eligible memories.
            sql += """
                AND ((e.scope_kind='USER' AND e.scope_id=? AND p.owner_id=?)
                  OR (e.scope_kind='CASE' AND e.scope_id=?)
                  OR (e.scope_kind='TEAM' AND EXISTS(
                      SELECT 1 FROM memory_team_memberships t WHERE t.tenant_id=e.tenant_id
                      AND t.team_id=e.scope_id AND t.principal_id=? AND t.revoked_at IS NULL))
                  OR (e.scope_kind='ORGANIZATION' AND e.scope_id=e.tenant_id))
                AND (p.origin_case_id IS NULL OR (
                    p.origin_case_id IN (SELECT value FROM json_each(?)) AND EXISTS(
                    SELECT 1 FROM case_memberships c WHERE c.tenant_id=e.tenant_id
                    AND c.case_id=p.origin_case_id AND c.principal_id=? AND c.revoked_at IS NULL)))
                AND julianday(p.valid_from)<=julianday(?)
                AND (e.user_valid_until IS NULL OR julianday(e.user_valid_until)>julianday(?))
                AND NOT EXISTS(SELECT 1 FROM memory_provenance next WHERE next.supersedes_id=e.memory_id)
                AND NOT EXISTS(SELECT 1 FROM case_events v WHERE v.tenant_id=e.tenant_id
                    AND v.event_kind='MEMORY_REVOKED' AND json_extract(v.payload_json,'$.memory_id')=e.memory_id)
                AND NOT EXISTS(SELECT 1 FROM case_events v WHERE v.tenant_id=e.tenant_id
                    AND v.event_kind='MEMORY_CLOSED' AND v.case_id=coalesce(p.origin_case_id,?))
            """
            actor = self.case.principal
            now = utc_now()
            params.extend([actor.principal_id, actor.principal_id, self.case.case_id,
                actor.principal_id, json.dumps(actor.allowed_case_ids), actor.principal_id, now, now, self.case.case_id])
            if category:
                sql += " AND e.memory_kind=?"
                params.append(category)
            sql += " ORDER BY e.created_at DESC,e.memory_id DESC LIMIT 501"
            candidates = self.registry.database.connection.execute(sql, params).fetchall()
        self.last_recall_incomplete = len(candidates) > 500
        found = []
        for row in candidates[:500]:
            try:
                item = self.read(row[0])
            except (EvidenceAgentError, ValueError):
                continue
            if category is None or item["kind"] == category:
                found.append(item)
            if len(found) == limit:
                break
        return found

    def revoke(self, identifier: str) -> None:
        item = self.read(identifier, for_control=True)
        if item["owner_id"] != self.case.principal.principal_id:
            self._admin()
        with self.registry.database.transaction() as db:
            self.case.authorize()
            self._event(db, "REVOKED", {"memory_id": identifier})

    def close_case(self) -> None:
        self._admin()
        with self.registry.database.transaction() as db:
            self._admin()
            self._event(db, "CLOSED", {"case_id": self.case.case_id})

    def closed(self, case_id: str | None = None) -> bool:
        return self.registry.database.connection.execute(
            "SELECT 1 FROM case_events WHERE tenant_id=? AND case_id=? AND event_kind='MEMORY_CLOSED' LIMIT 1",
            (self.case.principal.tenant_id, case_id or self.case.case_id)).fetchone() is not None

    def epoch(self) -> str:
        """Canonical invalidation token, not a duplicate permission/authority cache."""
        self.case.authorize()
        row = self.registry.database.connection.execute(
            "SELECT count(*),max(occurred_at) FROM case_events WHERE tenant_id=? AND event_kind LIKE 'MEMORY_%'",
            (self.case.principal.tenant_id,)).fetchone()
        return str(tuple(row))
