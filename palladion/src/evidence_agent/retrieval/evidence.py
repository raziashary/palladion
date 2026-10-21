"""Canonical authorization, publication, time and original-byte citation reader."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from evidence_agent.core.errors import PermissionDenied, ResourceConflict
from evidence_agent.core.models import Principal, VersionedModel
from evidence_agent.core.retrieval import Chunk
from evidence_agent.memory.hotcache import HotCache
from evidence_agent.storage.catalog import Catalog


class Passage(VersionedModel):
    citation_id: str
    revision_id: str
    generation: str
    section_id: str
    start_byte: int
    end_byte: int
    line_start: int
    line_end: int
    text: str
    sha256: str
    pdf_provenance: dict[str, Any] | None = None


class EvidenceResolver:
    def __init__(self, catalog: Catalog, fingerprint: str) -> None:
        self.catalog = catalog
        self.registry = catalog.registry
        self.fingerprint = fingerprint

    def resolve(self, principal: Principal, case_id: str, chunk_id: str, *,
                generation: str | None = None, as_of: datetime | None = None) -> Passage:
        chunk = self.catalog.get_chunk(principal, chunk_id)
        if chunk.case_id != case_id:
            raise PermissionDenied
        instant = as_of or self.registry.clock()
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError("Source applicability requires an aware instant")
        # One SQLite transaction holds source/ACL/version metadata stable through byte read.
        with self.registry.database.transaction() as connection:
            self.registry.access.authorize(principal, tenant_id=chunk.tenant_id,
                                           case_id=case_id, grant="source:read")
            row = connection.execute("SELECT * FROM document_revisions WHERE tenant_id=? "
                                     "AND revision_id=?", (chunk.tenant_id, chunk.revision_id)).fetchone()
            if row is None or row["approval_status"] != "APPROVED" or row["index_state"] != "READY":
                raise PermissionDenied
            metadata = self.catalog.eligible_generation_metadata(principal, chunk.revision_id)
            if (metadata is None or metadata.get("state") != "READY" or
                    metadata.get("fingerprint") != self.fingerprint):
                raise PermissionDenied
            if generation is not None and row["index_generation"] != generation:
                raise PermissionDenied
            for field, lower in (("valid_from", True), ("valid_to", False)):
                if row[field] is not None:
                    boundary = datetime.fromisoformat(row[field])
                    if (lower and instant < boundary) or (not lower and instant >= boundary):
                        raise PermissionDenied
            approval = connection.execute("SELECT status FROM approval_records WHERE "
                                          "approval_record_id=? AND tenant_id=? AND revision_id=?",
                                          (row["approval_record_id"], chunk.tenant_id,
                                           chunk.revision_id)).fetchone()
            if approval is None or approval["status"] != "APPROVED":
                raise PermissionDenied
            acl = json.loads(row["acl_json"])
            if acl.get("allowed_principal_ids") and principal.principal_id not in acl["allowed_principal_ids"]:
                raise PermissionDenied
            for edge in connection.execute("SELECT applicability_scope_json,valid_from FROM "
                                           "supersession_edges WHERE tenant_id=? AND "
                                           "predecessor_revision_id=?", (chunk.tenant_id, chunk.revision_id)):
                scope = json.loads(edge[0])
                if scope.get("case_id") == case_id and datetime.fromisoformat(edge[1]) <= instant:
                    raise PermissionDenied
            original = self.registry.originals.read(row["content_sha256"])
            text_bytes = original[chunk.start_byte:chunk.end_byte]
            if (chunk.end_byte > len(original) or not text_bytes or
                    hashlib.sha256(text_bytes).hexdigest() != chunk.content_sha256 or
                    hashlib.sha256(original).hexdigest() != chunk.source_sha256):
                raise ResourceConflict
            provenance = self.registry.extraction_provenance(principal, chunk.revision_id)
            if provenance is not None:
                provenance["pages"] = [page for page in provenance["pages"]
                    if page["start_byte"] < chunk.end_byte and page["end_byte"] > chunk.start_byte]
        return Passage(citation_id=chunk.chunk_id, revision_id=chunk.revision_id,
                       generation=str(row["index_generation"]), section_id=chunk.section_id,
                       start_byte=chunk.start_byte, end_byte=chunk.end_byte,
                       line_start=chunk.line_start, line_end=chunk.line_end,
                       text=text_bytes.decode("utf-8"), sha256=chunk.content_sha256,
                       pdf_provenance=provenance)

    def chunk(self, principal: Principal, passage: Passage) -> Chunk:
        return self.catalog.get_chunk(principal, passage.citation_id)


class RequestLedger:
    """Current-request handles; every release re-reads the original domain authority."""

    def __init__(self, search: object, principal: Principal, case_id: str, trace_id: str,
                 freshness_seconds: dict[str, int] | None = None, hotcache: HotCache | None = None) -> None:
        # Local import avoids making retrieval's domain types depend on the orchestrator.
        from evidence_agent.retrieval.hybrid import HybridSearch
        if not isinstance(search, HybridSearch):
            raise TypeError("Canonical search owner required")
        self.search, self.principal, self.case_id, self.trace_id = search, principal, case_id, trace_id
        self.hotcache = hotcache
        self.freshness_seconds = freshness_seconds or {}
        self.records: dict[str, dict[str, Any]] = {}
        from evidence_agent.core.models import EvidenceRecord
        self.envelopes: dict[str, EvidenceRecord] = {}
        self.failures: list[str] = []
        self.tool_status: dict[str, str] = {}

    def read(self, identifier: str) -> dict[str, Any]:
        def load() -> dict[str, Any]:
            return read_runtime_evidence(self.search, self.principal, self.case_id, identifier,
                freshness_seconds=self.freshness_seconds)
        if self.hotcache is not None and identifier.startswith("chunk_"):
            from evidence_agent.memory.store import CaseStore
            epoch = CaseStore(self.search.registry, self.principal, self.case_id).memory().epoch()
            return self.hotcache.read(load, principal=self.principal, case_id=self.case_id, epoch=epoch)
        return load()

    def add(self, identifier: str) -> dict[str, Any]:
        if identifier not in self.records and len(self.records) >= 32:
            raise ValueError("Ledger bound exceeded")
        data = self.read(identifier)
        if (data["kind"] == "DOCUMENT" and identifier not in self.records and
                sum(d["kind"] == "DOCUMENT" for d in self.records.values()) >= 12):
            raise ValueError("Source passage bound exceeded")
        from evidence_agent.core.models import (
            AccessScope,
            EvidenceAuthority,
            EvidenceKind,
            EvidenceRecord,
            EvidenceVerificationState,
            SourceKind,
            SourceRef,
        )
        kind = EvidenceKind(data["kind"])
        source_kind = {EvidenceKind.DOCUMENT: SourceKind.DOCUMENT_REVISION,
            EvidenceKind.LIVE_OBSERVATION: SourceKind.LIVE_LOOKUP,
            EvidenceKind.POLICY_DECISION: SourceKind.POLICY_DECISION,
            EvidenceKind.CASE_EVENT: SourceKind.CASE_EVENT}[kind]
        authority = {EvidenceKind.DOCUMENT: EvidenceAuthority.CANONICAL_SOURCE,
            EvidenceKind.LIVE_OBSERVATION: EvidenceAuthority.OPERATIONAL_OBSERVATION,
            EvidenceKind.POLICY_DECISION: EvidenceAuthority.APPROVED_POLICY,
            EvidenceKind.CASE_EVENT: EvidenceAuthority.NONE}[kind]
        extra = ({"revision_id": data["revision_id"], "chunk_id": identifier,
                  "span_start": data["start_byte"], "span_end": data["end_byte"]}
                 if kind is EvidenceKind.DOCUMENT else {})
        now = self.search.registry.clock()
        self.envelopes[identifier] = EvidenceRecord(evidence_id=identifier, kind=kind,
            source_identity=str(data.get("revision_id") or identifier),
            content_hash=data.get("content_sha256") or hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest(),
            source_ref=SourceRef(source_kind=source_kind, tenant_id=self.principal.tenant_id,
                source_id=str(data.get("revision_id") or identifier), **extra),
            provenance=(identifier,), authority=authority,
            authority_record=identifier if authority is not EvidenceAuthority.NONE else None,
            occurred_at=now,
            observed_at=datetime.fromisoformat(data["observed_at"]) if data.get("observed_at") else None,
            acl=AccessScope(tenant_id=self.principal.tenant_id, allowed_case_ids=(self.case_id,)),
            verification=EvidenceVerificationState.VALID if data.get("valid", True) else EvidenceVerificationState.UNKNOWN,
            run_trace_id=self.trace_id)
        self.records[identifier] = data
        return data

    def refresh(self) -> bool:
        changed = False
        from evidence_agent.core.errors import EvidenceAgentError
        for identifier in tuple(self.records):
            try:
                current = self.read(identifier)
            except (EvidenceAgentError, ValueError):
                self.records.pop(identifier)
                self.envelopes.pop(identifier, None)
                changed = True
            else:
                changed |= current != self.records[identifier]
                self.records[identifier] = current
        return changed

    def snapshot(self, cited: set[str] | None = None) -> dict[str, object]:
        selected = {key: model_view(value) for key, value in self.records.items()
                    if cited is None or key in cited or value["kind"] != "DOCUMENT"}
        return {"evidence": selected, "omitted_document_count": len(self.records)-len(selected), "failures": self.failures,
                "tool_status": self.tool_status, "searched_scope": "current authorized case and supplied index"}


def read_runtime_evidence(search: object, principal: Principal, case_id: str,
                          identifier: str, *, freshness_seconds: dict[str, int] | None = None) -> dict[str, Any]:
    """Canonical citation reader for all P04 kinds; no caller-supplied payloads."""
    from evidence_agent.core.models import LiveOperationStatus, PolicyDecisionStatus
    from evidence_agent.live.gateway import read_observation, read_scope
    from evidence_agent.policy.engine import PolicyEngine
    from evidence_agent.policy.registry import PolicyRegistry, PolicySpec
    from evidence_agent.policy.temporal import TemporalResolver
    from evidence_agent.retrieval.hybrid import HybridSearch

    if not isinstance(search, HybridSearch):
        raise TypeError("Canonical search required")
    registry = search.registry
    registry.access.authorize(principal, tenant_id=principal.tenant_id,
                              case_id=case_id, grant="case:read")
    if identifier.startswith("mem_"):
        from evidence_agent.memory.store import CaseStore
        memory_item = CaseStore(registry, principal, case_id).memory().read(identifier)
        return {"evidence_id": identifier, "kind": "CASE_EVENT", "event": memory_item,
                "valid": False, "authority": "NONE", "occurred_at": memory_item["set_at"]}
    if identifier.startswith("evt_"):
        from evidence_agent.memory.store import CaseStore
        event = CaseStore(registry, principal, case_id).read_event(identifier)
        return {"evidence_id": identifier, "kind": "CASE_EVENT", "event": event,
                "valid": False, "authority": "NONE", "occurred_at": event["at"]}
    if identifier.startswith("chunk_"):
        item = search.resolver.resolve(principal, case_id, identifier)
        return {"evidence_id": identifier, "kind": "DOCUMENT", "text": item.text,
            "revision_id": item.revision_id, "section_id": item.section_id,
            "generation": item.generation, "start_byte": item.start_byte, "end_byte": item.end_byte,
            "content_sha256": item.sha256,
            **({"pdf_provenance": item.pdf_provenance} if item.pdf_provenance is not None else {})}
    if identifier.startswith("live_"):
        observation = read_observation(registry, principal, case_id, identifier)
        # The operation owner controls freshness; a prior successful read is not current forever.
        maximum = (freshness_seconds or {}).get(observation.operation_id)
        current = registry.clock()
        fresh = maximum is not None and 0 <= (current-observation.observed_at).total_seconds() <= maximum
        if observation.data_as_of is not None and maximum is not None:
            fresh &= 0 <= (current-observation.data_as_of).total_seconds() <= maximum
        return {"evidence_id": identifier, "kind": "LIVE_OBSERVATION",
            "operation": observation.operation_id, "status": observation.operation_status.value,
            "data": observation.data, "observed_at": observation.observed_at.isoformat(),
            "data_as_of": observation.data_as_of.isoformat() if observation.data_as_of else None,
            "source_event_at": observation.source_event_at.isoformat() if observation.source_event_at else None,
            "source_system": observation.source_system,
            "valid": observation.operation_status is LiveOperationStatus.OK and fresh}
    if identifier.startswith("policy_"):
        policies = PolicyRegistry(registry)
        decision = PolicyEngine(policies).replay(principal, case_id, identifier)
        if decision.evaluation_mode != "current":
            raise PermissionDenied
        temporal_inputs = decision.temporal_input_refs or decision.input_evidence_refs
        selected = TemporalResolver(policies).resolve(principal, case_id,
            decision.policy_family_id, temporal_inputs)
        if decision.version_id and (selected.spec is None or selected.spec.version_id != decision.version_id):
            raise PermissionDenied
        if not decision.version_id:
            expected = {"INCOMPLETE_INPUT": "MISSING_TIME_INPUT",
                        "UNVERIFIED_INPUT": "UNVERIFIED_TIME_SOURCE"}.get(decision.status.value, decision.status.value)
            if selected.status != expected:
                raise PermissionDenied  # A historical conflict/absence is not a fresh result after registry changes.
        texts = []
        clause_refs: list[dict[str, Any]] = []
        if selected.spec:
            spec = PolicySpec.model_validate_json(selected.spec.model_dump_json())
            texts = [policies.read_clause(principal, c) for c in spec.clauses]
            clause_refs = [{"version_id": spec.version_id, "clause_index": number,
                "revision_id": c.revision_id, "section_id": c.section_id,
                "start_byte": c.start_byte, "end_byte": c.end_byte,
                "applicability": "SELECTED"} for number, c in enumerate(spec.clauses)]
            for field in spec.required_facts:
                for evidence_id in decision.input_evidence_refs:
                    observation = read_observation(registry, principal, case_id, evidence_id)
                    if observation.operation_id != field.operation:
                        continue
                    instant = observation.data_as_of or observation.observed_at
                    if not 0 <= (registry.clock()-instant).total_seconds() <= field.max_age_seconds:
                        raise PermissionDenied
        elif decision.status is PolicyDecisionStatus.POLICY_CONFLICT:
            scope = read_scope(registry, principal, case_id)
            rows = registry.database.connection.execute(
                "SELECT decision_table_json FROM policy_versions WHERE tenant_id=? AND family_id=? "
                "AND status='APPROVED' LIMIT 129", (principal.tenant_id, decision.policy_family_id)).fetchall()
            for row in rows[:128]:
                candidate = PolicySpec.model_validate_json(row[0])
                if (case_id not in candidate.allowed_case_ids or candidate.product != scope.product or
                        candidate.transaction_class != scope.transaction_class):
                    continue
                try:
                    for clause in candidate.clauses:
                        policies.clause(principal, clause)
                except PermissionDenied:
                    continue
                for number, clause in enumerate(candidate.clauses):
                    if len(clause_refs) >= 12:
                        break
                    clause_refs.append({"version_id": candidate.version_id, "clause_index": number,
                        "revision_id": clause.revision_id, "section_id": clause.section_id,
                        "start_byte": clause.start_byte, "end_byte": clause.end_byte,
                        "applicability": "UNRESOLVED_CANDIDATE"})
        return {"evidence_id": identifier, "kind": "POLICY_DECISION",
            "status": decision.status.value, "family_id": decision.policy_family_id,
            "version_id": decision.version_id, "time_basis": decision.time_basis.value if decision.time_basis else None,
            "as_of": decision.as_of.isoformat() if decision.as_of else None,
            "outcome": decision.outcome, "required_fields": list(decision.required_fields),
            "missing_fields": list(decision.missing_fields), "rule_trace": list(decision.rule_trace),
            "input_evidence_refs": list(decision.input_evidence_refs), "temporal_input_refs": list(temporal_inputs), "clauses": texts,
            "clause_refs": clause_refs,
            "valid": decision.status is PolicyDecisionStatus.DETERMINED}
    raise PermissionDenied


def public_citation(item: dict[str, Any]) -> dict[str, Any]:
    """Operator metadata, not raw policy internals or rejected diagnostics."""
    fields = {"evidence_id", "kind", "revision_id", "section_id", "start_byte", "end_byte",
              "generation", "operation", "observed_at", "source_event_at", "data_as_of",
              "source_system", "status", "family_id", "version_id", "time_basis", "as_of"}
    fields.add("clause_refs")
    fields.add("pdf_provenance")
    return {k: v for k, v in item.items() if k in fields}


def model_view(item: dict[str, Any]) -> dict[str, Any]:
    """Bound model context without truncating canonical storage or hiding that a view is partial."""
    view = dict(item)
    view.pop("content_sha256", None)
    if item.get("kind") == "DOCUMENT":
        view = {k: v for k, v in item.items() if k in {"evidence_id", "kind", "section_id"}}
        text = str(item["text"])
        view.update(text_preview=text[:800], text_truncated=len(text) > 800)
    elif item.get("kind") == "POLICY_DECISION":
        clauses = view.pop("clauses")
        view.update(clause_previews=[text[:400] for text in clauses[:4]],
                    clauses_truncated=len(clauses) > 4 or any(len(text) > 400 for text in clauses))
    elif item.get("kind") == "CASE_EVENT":
        event = item["event"]
        payload = event.get("payload", {})
        view["event"] = {"event_id": event["event_id"], "kind": event["kind"], "at": event.get("at", event.get("set_at")),
            "status": payload.get("status") or payload.get("disposition"),
            "reported_statement_preview": str(event.get("content", payload.get("query", "")))[:400],
            "authority": "NONE", "verification": "REQUIRES_RECHECK"}
    return view
