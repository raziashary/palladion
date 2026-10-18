"""Authorized supplied-source coverage is distinct from external inventory attestation."""
from __future__ import annotations

import json
import re
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from evidence_agent.core.errors import DependencyUnavailable
from evidence_agent.core.models import (
    InvestigationRequirement,
    Principal,
    RequirementOrigin,
    VersionedModel,
)
from evidence_agent.core.retrieval import SearchIndex
from evidence_agent.storage.catalog import Catalog
from evidence_agent.storage.registry import Registry


class Coverage(VersionedModel):
    index_coverage: bool
    inventory_attested: bool = False
    requirements_assessed: bool = False
    accepted_source_count: int
    indexed_source_count: int
    warnings: tuple[str, ...] = ()


def claim_requirements(records: Iterable[dict[str, Any]], suggested: tuple[str, ...] = ()) -> tuple[InvestigationRequirement, ...]:
    """Approved schema fields cannot be erased or replaced by model suggestions."""
    origins: dict[str, InvestigationRequirement] = {}
    for record in records:
        if record.get("kind") == "POLICY_DECISION":
            for name in record["required_fields"]:
                origins[name] = InvestigationRequirement(slot=name, origin=RequirementOrigin.POLICY_SCHEMA)
    for name in suggested[:32]:
        if re.fullmatch(r"[a-z][a-z0-9_]{0,63}", name) and name not in origins:
            origins[name] = InvestigationRequirement(slot=name, origin=RequirementOrigin.MODEL_SUGGESTION, required=False)
    return tuple(origins.values())


def quote_policy_families(registry: Registry, principal: Principal, case_id: str,
                           passage: dict[str, Any], quote: str) -> set[str]:
    """Risk follows approved clause bindings, never a model's answer-kind label."""
    from evidence_agent.core.errors import PermissionDenied
    from evidence_agent.live.gateway import read_scope
    from evidence_agent.policy.registry import PolicyRegistry, PolicySpec
    scope = read_scope(registry, principal, case_id)
    position = str(passage["text"]).find(quote)
    if position < 0:
        return set()
    start = int(passage["start_byte"]) + len(str(passage["text"])[:position].encode())
    end = start + len(quote.encode())
    rows = registry.database.connection.execute(
        "SELECT DISTINCT p.decision_table_json FROM policy_versions p JOIN policy_source_clauses c "
        "ON p.tenant_id=c.tenant_id AND p.version_id=c.version_id "
        "WHERE p.tenant_id=? AND p.status='APPROVED' AND c.revision_id=? LIMIT 129",
        (principal.tenant_id, passage["revision_id"])).fetchall()
    if len(rows) > 128:
        return {"UNRESOLVED_POLICY_SCOPE"}
    families = set()
    for row in rows:
        spec = PolicySpec.model_validate_json(row[0])
        if (case_id not in spec.allowed_case_ids or spec.product != scope.product or
                spec.transaction_class != scope.transaction_class):
            continue
        for clause in spec.clauses:
            if clause.revision_id == passage["revision_id"] and clause.start_byte < end and start < clause.end_byte:
                try:
                    PolicyRegistry(registry).clause(principal, clause)
                except PermissionDenied:
                    continue
                families.add(spec.family_id)
    return families


def source_coverage(registry: Registry, principal: Principal, case_id: str,
                    index: SearchIndex | None = None) -> Coverage:
    registry.access.authorize(principal, tenant_id=principal.tenant_id,
                              case_id=case_id, grant="source:read")
    accepted = indexed = 0
    now = datetime.now(timezone.utc)
    warnings: list[str] = []
    catalog = Catalog(registry)
    rows = registry.database.connection.execute(
            "SELECT * FROM document_revisions WHERE tenant_id=? AND case_id=? AND "
            "approval_status='APPROVED' ORDER BY revision_id LIMIT 101", (principal.tenant_id, case_id)).fetchall()
    if len(rows) > 100:
        warnings.append("COVERAGE_SCOPE_TRUNCATED")
    for row in rows[:100]:
        allowed = json.loads(row["acl_json"]).get("allowed_principal_ids", [])
        if allowed and principal.principal_id not in allowed:
            continue
        if row["valid_from"] and now < datetime.fromisoformat(row["valid_from"]):
            continue
        if row["valid_to"] and now >= datetime.fromisoformat(row["valid_to"]):
            continue
        accepted += 1
        if row["index_state"] != "READY":
            continue
        if index is not None:
            generation = row["index_generation"]
            expected = catalog.manifest_for_generation(principal, row["revision_id"], generation)
            try:
                actual = index.readback(principal.tenant_id, row["revision_id"], generation)
            except DependencyUnavailable:
                warnings.append("INDEX_UNAVAILABLE")
                continue
            if expected != actual:
                warnings.append("INDEX_MANIFEST_MISMATCH")
                continue
        indexed += 1
    if accepted != indexed:
        warnings.append("ACCEPTED_BUT_UNINDEXED")
    return Coverage(index_coverage=accepted == indexed and not warnings, accepted_source_count=accepted,
                    indexed_source_count=indexed,
                    warnings=tuple(dict.fromkeys(warnings)))
