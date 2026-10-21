"""Authenticated policy approval, immutable definitions and source-bound audit replay."""
from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from evidence_agent.core.errors import PermissionDenied, ResourceConflict
from evidence_agent.core.models import Principal, SourceKind, SourceRef, TimeBasis, VersionedModel
from evidence_agent.live.gateway import iso
from evidence_agent.storage.registry import Registry


class Clause(VersionedModel):
    revision_id: str = Field(min_length=1)
    section_id: str = Field(min_length=1)
    start_byte: int = Field(ge=0)
    end_byte: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RequiredFact(VersionedModel):
    name: str = Field(min_length=1, max_length=100)
    type: Literal["enum", "bool", "int", "float", "string"]
    operation: Literal["get_transaction_status", "get_settlement_status",
                       "get_incident_status", "get_merchant_summary"]
    field: str = Field(min_length=1, max_length=100)
    allowed_values: tuple[str, ...] = ()
    max_age_seconds: int = Field(gt=0, le=86400)


class Rule(VersionedModel):
    id: str = Field(min_length=1, max_length=100)
    predicate: dict[str, Any]
    outcome: str = Field(min_length=1, max_length=100)
    clause: Clause


class PolicySpec(VersionedModel):
    version_id: str = Field(min_length=1, max_length=100)
    family_id: str = Field(min_length=1, max_length=100)
    author_id: str = Field(min_length=1)
    product: str = Field(min_length=1)
    transaction_class: str = Field(min_length=1)
    allowed_case_ids: tuple[str, ...] = Field(min_length=1, max_length=100)
    time_basis: TimeBasis
    timestamp_source: str
    domain_event: str | None = None
    timestamp_max_age_seconds: int = Field(default=300, gt=0, le=86400)
    valid_from: datetime
    valid_to: datetime | None = None
    clauses: tuple[Clause, ...] = Field(min_length=1, max_length=16)
    required_facts: tuple[RequiredFact, ...] = Field(default=(), max_length=32)
    rules: tuple[Rule, ...] = Field(default=(), max_length=64)
    default_outcome: str = Field(min_length=1, max_length=100)

    @field_validator("valid_from", "valid_to")
    @classmethod
    def aware(cls, value: datetime | None) -> datetime | None:
        if value is not None:
            iso(value)
        return value

    @model_validator(mode="after")
    def coherent(self) -> PolicySpec:
        sources = {TimeBasis.TRANSACTION_OCCURRED_AT: "verified_live.transaction_occurred_at",
                   TimeBasis.CASE_OPENED_AT: "case_event.opened_at",
                   TimeBasis.EVALUATION_AT: "server_clock.evaluation_time",
                   TimeBasis.DOMAIN_EVENT_AT: "verified_case.domain_event_at"}
        if self.timestamp_source != sources[self.time_basis]:
            raise ValueError("Time basis requires its approved producer")
        if (self.time_basis is TimeBasis.DOMAIN_EVENT_AT) != bool(self.domain_event):
            raise ValueError("Domain event must be explicitly named")
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("Invalid half-open validity interval")
        if len(set(self.allowed_case_ids)) != len(self.allowed_case_ids):
            raise ValueError("Duplicate case scope")
        if len({f.name for f in self.required_facts}) != len(self.required_facts):
            raise ValueError("Duplicate required fact")
        if len({r.id for r in self.rules}) != len(self.rules):
            raise ValueError("Duplicate rule ID")
        if any(r.clause not in self.clauses for r in self.rules):
            raise ValueError("Rule clause must be in the approved source set")
        return self


class PolicyRegistry:
    def __init__(self, registry: Registry, *, clock: Callable[[], datetime] | None = None) -> None:
        self.registry, self.clock = registry, clock or registry.clock

    def _event(self, actor: Principal, version: str, kind: str,
                extra: dict[str, Any] | None = None) -> None:
        at = self.clock()
        self.registry.database.connection.execute("INSERT INTO audit_events VALUES(?,?,?,?,?,?,?)",
            ("audit_"+uuid.uuid4().hex, version, actor.principal_id, actor.tenant_id, kind,
             json.dumps({"version_id": version, **(extra or {})}), iso(at)))

    def clause(self, principal: Principal, clause: Clause, *,
               knowledge_cutoff: datetime | None = None) -> SourceRef:
        if knowledge_cutoff is not None:
            iso(knowledge_cutoff)
            self.registry.access.authorize(principal, tenant_id=principal.tenant_id,
                                            role="admin", grant="document:approve")
        source = self.registry.source_metadata(principal, clause.revision_id)
        current = source["approval_status"] == source["approval_record_status"] == "APPROVED"
        if not current:
            if knowledge_cutoff is None:
                raise PermissionDenied
            self.registry.access.authorize(principal, tenant_id=principal.tenant_id,
                                            role="admin", grant="document:approve")
            approval = self.registry.database.connection.execute(
                "SELECT recorded_at,status FROM approval_records WHERE tenant_id=? AND revision_id=?",
                (principal.tenant_id, clause.revision_id)).fetchone()
            revoked = self.registry.database.connection.execute(
                "SELECT occurred_at,safe_payload_json FROM audit_events WHERE tenant_id=? "
                "AND event_kind='SOURCE_REVOKED'", (principal.tenant_id,)).fetchall()
            if approval is None or approval["status"] != "APPROVED" or datetime.fromisoformat(
                    approval["recorded_at"]) > knowledge_cutoff or any(
                    json.loads(r["safe_payload_json"]).get("revision_id") == clause.revision_id
                    and datetime.fromisoformat(r["occurred_at"]) <= knowledge_cutoff for r in revoked):
                raise PermissionDenied
        elif knowledge_cutoff is not None:
            approval = self.registry.database.connection.execute(
                "SELECT recorded_at FROM approval_records WHERE tenant_id=? AND revision_id=?",
                (principal.tenant_id, clause.revision_id)).fetchone()
            if approval is None or datetime.fromisoformat(approval[0]) > knowledge_cutoff:
                raise PermissionDenied
        original = self.registry.originals.read(str(source["content_sha256"]))
        raw = original[clause.start_byte:clause.end_byte]
        if clause.end_byte > len(original) or not raw or hashlib.sha256(raw).hexdigest() != clause.sha256:
            raise ResourceConflict
        return SourceRef(source_kind=SourceKind.DOCUMENT_REVISION, tenant_id=principal.tenant_id,
                         source_id=clause.revision_id, revision_id=clause.revision_id,
                         chunk_id=clause.section_id, span_start=clause.start_byte, span_end=clause.end_byte)

    def read_clause(self, principal: Principal, clause: Clause, *,
                    knowledge_cutoff: datetime | None = None) -> str:
        """Historical bytes require explicit admin audit; current reads retain current approval."""
        from contextlib import nullcontext
        database = self.registry.database
        with nullcontext() if database.connection.in_transaction else database.transaction():
            self.clause(principal, clause, knowledge_cutoff=knowledge_cutoff)
            source = self.registry.source_metadata(principal, clause.revision_id)
            return self.registry.originals.read(str(source["content_sha256"]))[
                clause.start_byte:clause.end_byte].decode("utf-8")

    def register(self, actor: Principal, spec: PolicySpec) -> None:
        spec = PolicySpec.model_validate_json(spec.model_dump_json())
        # No policy string in a document grants execution authority.
        from evidence_agent.policy.engine import validate_predicate

        self.registry.access.authorize(actor, tenant_id=actor.tenant_id,
                                        role="admin", grant="document:approve")
        author = self.registry.access.authenticate(spec.author_id)
        if author.tenant_id != actor.tenant_id or actor.principal_id == spec.author_id:
            raise PermissionDenied
        for case_id in spec.allowed_case_ids:
            self.registry.access.authorize(actor, tenant_id=actor.tenant_id,
                                            case_id=case_id, grant="case:read")
        for rule in spec.rules:
            validate_predicate(rule.predicate, {f.name for f in spec.required_facts})
        with self.registry.database.transaction() as connection:
            for clause in spec.clauses:
                self.clause(actor, clause)
                source_author = connection.execute(
                    "SELECT uploader_id FROM document_revisions WHERE tenant_id=? AND revision_id=?",
                    (actor.tenant_id, clause.revision_id)).fetchone()[0]
                if source_author != spec.author_id:
                    raise PermissionDenied
            existing = connection.execute("SELECT decision_table_json FROM policy_versions WHERE version_id=?",
                                           (spec.version_id,)).fetchone()
            if existing:
                if PolicySpec.model_validate_json(existing[0]) != spec:
                    raise ResourceConflict
                return
            approval = self.registry.source_metadata(actor, spec.clauses[0].revision_id)
            approval_id = connection.execute(
                "SELECT approval_record_id FROM document_revisions WHERE tenant_id=? AND revision_id=?",
                (actor.tenant_id, spec.clauses[0].revision_id)).fetchone()[0]
            assert approval["approval_status"] == "APPROVED"
            connection.execute("INSERT OR IGNORE INTO document_families VALUES(?,?,?,?)",
                               (actor.tenant_id, spec.family_id, spec.author_id, iso(self.clock())))
            connection.execute("INSERT INTO policy_versions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (spec.version_id, actor.tenant_id, spec.family_id, approval_id, spec.time_basis.value,
                 spec.timestamp_source, iso(spec.valid_from), iso(spec.valid_to) if spec.valid_to else None,
                 iso(self.clock()), "APPROVED", json.dumps({"cases": spec.allowed_case_ids}),
                 spec.model_dump_json()))
            for clause in spec.clauses:
                connection.execute("INSERT INTO policy_source_clauses VALUES(?,?,?,?)",
                    (actor.tenant_id, spec.version_id, clause.revision_id, clause.section_id))
            self._event(actor, spec.version_id, "POLICY_APPROVED")

    def revoke(self, actor: Principal, version_id: str) -> None:
        self.registry.access.authorize(actor, tenant_id=actor.tenant_id,
                                        role="admin", grant="document:approve")
        with self.registry.database.transaction() as connection:
            row = connection.execute("SELECT decision_table_json,status FROM policy_versions "
                                     "WHERE tenant_id=? AND version_id=?", (actor.tenant_id, version_id)).fetchone()
            if row is None or row["status"] != "APPROVED":
                raise PermissionDenied
            spec = PolicySpec.model_validate_json(row[0])
            for case in spec.allowed_case_ids:
                self.registry.access.authorize(actor, tenant_id=actor.tenant_id, case_id=case)
            connection.execute("UPDATE policy_versions SET status='REVOKED' WHERE version_id=?", (version_id,))
            self._event(actor, version_id, "POLICY_REVOKED")

    def supersede(self, actor: Principal, predecessor: str, successor: str, *,
                   case_id: str, valid_from: datetime, reason: str) -> None:
        self.registry.access.authorize(actor, tenant_id=actor.tenant_id, case_id=case_id,
                                        role="admin", grant="document:approve")
        iso(valid_from)
        if not reason.strip() or len(reason) > 200 or predecessor == successor:
            raise ValueError("Explicit bounded reason and distinct versions required")
        with self.registry.database.transaction() as connection:
            specs = []
            for version in (predecessor, successor):
                row = connection.execute("SELECT decision_table_json FROM policy_versions "
                    "WHERE tenant_id=? AND version_id=? AND status='APPROVED'", (actor.tenant_id, version)).fetchone()
                if not row:
                    raise PermissionDenied
                spec = PolicySpec.model_validate_json(row[0])
                if case_id not in spec.allowed_case_ids:
                    raise PermissionDenied
                specs.append(spec)
            if (specs[0].family_id, specs[0].time_basis, specs[0].product, specs[0].transaction_class) != (
                    specs[1].family_id, specs[1].time_basis, specs[1].product, specs[1].transaction_class):
                raise ResourceConflict
            self._event(actor, successor, "POLICY_SUPERSEDES", {
                "predecessor": predecessor, "case_id": case_id, "valid_from": iso(valid_from),
                "reason_sha256": hashlib.sha256(reason.encode()).hexdigest()})
