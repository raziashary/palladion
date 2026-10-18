"""Authorized supplied-source coverage is distinct from external inventory attestation."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from evidence_agent.core.errors import DependencyUnavailable
from evidence_agent.core.models import Principal, VersionedModel
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
