"""Authorized supplied-source coverage is distinct from external inventory attestation."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from evidence_agent.core.errors import DependencyUnavailable, ResourceConflict
from evidence_agent.core.models import (
    InvestigationRequirement,
    Principal,
    RequirementOrigin,
    VersionedModel,
)
from evidence_agent.core.retrieval import SearchIndex
from evidence_agent.retrieval.audit_cache import (
    invalidate_audits,
    is_fresh,
    read_audit,
    write_audit,
)
from evidence_agent.storage.applicability import Applicability
from evidence_agent.storage.catalog import MAX_COVERAGE_CHUNKS, MAX_COVERAGE_SOURCES, Catalog
from evidence_agent.storage.qdrant import IndexConsistencyError
from evidence_agent.storage.registry import Registry, acl_allows


class Coverage(VersionedModel):
    index_coverage: bool
    inventory_attested: bool = False
    requirements_assessed: bool = False
    source_counts_complete: bool = True
    accepted_source_count: int
    indexed_source_count: int
    warnings: tuple[str, ...] = ()
    physical_audit_mode: Literal["FRESH", "CACHED", "COUNTS", "NOT_CHECKED"] = "NOT_CHECKED"
    physical_verified_at: datetime | None = None
    physical_cache_status: Literal["DISABLED", "HIT", "MISS", "UNAVAILABLE"] = "DISABLED"


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


READBACK_BATCH = 64  # revisions read back in one physical scroll (the index accepts up to this many)


def _verdict(accepted: int, indexed: int, warnings: list[str]) -> bool:
    """True when every accepted source is indexed and nothing was warned; says so in `warnings` otherwise."""
    if accepted != indexed:
        warnings.append("ACCEPTED_BUT_UNINDEXED")
    return accepted == indexed and not warnings


def _invalidate_cached_audits(registry: Registry) -> bool:
    """Forget every cached healthy audit of this database; False when the cache could not be cleared."""
    if registry.database.path == ":memory:":
        return True
    existing_cache = Path(registry.database.path + ".coverage-cache.sqlite")
    if not existing_cache.exists():
        return True
    try:
        invalidate_audits(existing_cache)
    except (OSError, sqlite3.Error, ValueError):
        return False
    return True


def _accepted_sources(registry: Registry, principal: Principal, case_id: str,
                      as_of: datetime | None) -> tuple[list[sqlite3.Row], bool]:
    """The approved revisions the caller may read that apply at the evaluation instant, and whether the case held more
    than the bound. Both depths of coverage count against this one list."""
    registry.access.authorize(principal, tenant_id=principal.tenant_id, case_id=case_id, grant="source:read")
    at_now = Applicability.at(as_of or registry.clock())
    rows = registry.database.connection.execute(
        "SELECT * FROM document_revisions WHERE tenant_id=? AND case_id=? AND "
        "approval_status='APPROVED' AND (json_array_length(json_extract(acl_json,'$.allowed_principal_ids'))=0 "
        "OR EXISTS(SELECT 1 FROM json_each(document_revisions.acl_json,'$.allowed_principal_ids') "
        "WHERE value=?)) ORDER BY revision_id LIMIT ?",
        (principal.tenant_id, case_id, principal.principal_id, MAX_COVERAGE_SOURCES + 1)).fetchall()
    visible = [row for row in rows[:MAX_COVERAGE_SOURCES]
               if acl_allows(row["acl_json"], principal.principal_id)
               and at_now.admits(row["valid_from"], row["valid_to"], ())]
    return visible, len(rows) > MAX_COVERAGE_SOURCES


def counted_coverage(registry: Registry, principal: Principal, case_id: str, index: SearchIndex, *,
                     as_of: datetime | None = None) -> Coverage:
    """The coverage a search can afford on every call (ADR-0109): the canonical manifest of every READY source against
    the number of points the index holds for its generation, from one call and without reading a vector back.

    `source_coverage` reads every point back and validates it; that audit belongs to `/index-health` and to explicit
    requests. A count that differs from the manifest is a mismatch as a differing readback is, but a point with the
    right count and the wrong content is not seen here, which is why `physical_audit_mode` says COUNTS. Access that
    changes between the two canonical reads raises PermissionDenied, as it does in the full audit. A healthy cached
    full audit is dropped when this one finds a mismatch.
    """
    visible, truncated = _accepted_sources(registry, principal, case_id, as_of)
    warnings = ["COVERAGE_SCOPE_TRUNCATED"] if truncated else []
    catalog = Catalog(registry)
    ready = {row["revision_id"]: row["index_generation"] for row in visible if row["index_state"] == "READY"}
    failed: set[str] = set()
    counts: dict[str, int] = {}
    expected: dict[tuple[str, str], dict[str, str]] = {}
    if ready:  # a case with nothing indexed has nothing to count, and the index is not asked
        try:
            expected = catalog.coverage_manifests(principal, case_id, ready)
            counts = index.generation_counts(principal.tenant_id, case_id, list(ready.values()))
            if catalog.coverage_manifests(principal, case_id, ready) != expected:  # changed while we were counting
                failed.update(ready)
                warnings.append("INDEX_MANIFEST_MISMATCH")
        except ResourceConflict:
            failed.update(ready)
            warnings.append("CANONICAL_MANIFEST_UNAVAILABLE")
        except DependencyUnavailable:
            failed.update(ready)
            warnings.append("INDEX_UNAVAILABLE")
        except IndexConsistencyError:
            failed.update(ready)
            warnings.append("INDEX_MANIFEST_MISMATCH")
    indexed = 0
    for row in visible:
        if row["index_state"] != "READY":
            continue
        if row["revision_id"] in failed:
            continue
        if len(expected[(row["revision_id"], row["index_generation"])]) != counts.get(row["index_generation"], 0):
            warnings.append("INDEX_MANIFEST_MISMATCH")
            continue
        indexed += 1
    healthy = _verdict(len(visible), indexed, warnings)
    if not healthy:
        _invalidate_cached_audits(registry)
    return Coverage(index_coverage=healthy, source_counts_complete=not truncated,
                    accepted_source_count=len(visible), indexed_source_count=indexed,
                    warnings=tuple(dict.fromkeys(warnings)), physical_audit_mode="COUNTS")


def source_coverage(registry: Registry, principal: Principal, case_id: str,
                    index: SearchIndex | None = None, *, as_of: datetime | None = None,
                    reuse_physical_audit: bool = False) -> Coverage:
    """The full audit: every point of every READY source read back and validated (the default of `/index-health`)."""
    indexed = 0
    now = as_of or registry.clock()
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Document cutoff must be timezone-aware")
    warnings: list[str] = []
    catalog = Catalog(registry)
    visible, truncated = _accepted_sources(registry, principal, case_id, now)
    if truncated:
        warnings.append("COVERAGE_SCOPE_TRUNCATED")
    accepted = len(visible)
    physical: dict[tuple[str, str], dict[str, str]] = {}
    failed_batches: set[str] = set()
    batch_readback = getattr(index, "readback_many", None)
    requested = {row["revision_id"]: row["index_generation"] for row in visible
                 if row["index_state"] == "READY"}

    def expected_snapshot() -> dict[tuple[str, str], dict[str, str]]:
        try:
            return catalog.coverage_manifests(principal, case_id, requested) if index is not None else {}
        except ResourceConflict:
            failed_batches.update(requested)
            warnings.append("CANONICAL_MANIFEST_UNAVAILABLE")
            return {}

    expected_manifests = expected_snapshot() if reuse_physical_audit else {}
    audit_wall, audit_monotonic = time.time(), time.monotonic()
    cached_at: float | None = None
    cached_times: tuple[float, float] | None = None
    cache_status: Literal["DISABLED", "HIT", "MISS", "UNAVAILABLE"] = "DISABLED"
    cache_path: Path | None = None
    cache_key: str | None = None
    if reuse_physical_audit:
        cache_status = "UNAVAILABLE"
        try:
            identity = getattr(index, "audit_cache_identity", None)
            if (isinstance(identity, str) and identity and callable(batch_readback)
                    and registry.database.path != ":memory:" and requested and not warnings
                    and len(requested) == accepted):
                cache_path = Path(registry.database.path + ".coverage-cache.sqlite")
                key_input = [principal.tenant_id, principal.principal_id, case_id, identity,
                    [(revision, generation, sorted(chunks.items()))
                     for (revision, generation), chunks in sorted(expected_manifests.items())]]
                cache_key = hashlib.sha256(json.dumps(key_input, separators=(",", ":")).encode()).hexdigest()
                cached_times = read_audit(cache_path, cache_key)
                cached_at = cached_times[0] if cached_times is not None else None
                cache_status = "HIT" if cached_at is not None else "MISS"
        except (OSError, sqlite3.Error, ValueError, DependencyUnavailable):
            cache_status = "UNAVAILABLE"
    if callable(batch_readback) and cached_at is None and not failed_batches:
        ready = [row for row in visible if row["index_state"] == "READY"]
        for start in range(0, len(ready), READBACK_BATCH):
            batch = {row["revision_id"]: row["index_generation"] for row in ready[start:start + READBACK_BATCH]}
            try:
                readback = batch_readback(principal.tenant_id, batch)
                if sum(map(len, physical.values())) + sum(map(len, readback.values())) > MAX_COVERAGE_CHUNKS:
                    physical.clear()
                    failed_batches.update(row["revision_id"] for row in ready)
                    warnings.append("COVERAGE_POINT_LIMIT")
                    break
                physical.update(readback)
            except DependencyUnavailable:
                failed_batches.update(batch)
                warnings.append("INDEX_UNAVAILABLE")
            except IndexConsistencyError:
                failed_batches.update(batch)
                warnings.append("INDEX_MANIFEST_MISMATCH")
    # Recheck after physical work/cache lookup; a changed canonical snapshot invalidates reuse.
    current_manifests = expected_snapshot()
    if not reuse_physical_audit:
        expected_manifests = current_manifests
    elif current_manifests != expected_manifests:
        failed_batches.update(requested)
        warnings.append("INDEX_MANIFEST_MISMATCH")
    if cached_times is not None and not is_fresh(*cached_times):
        failed_batches.update(requested)
        warnings.append("PHYSICAL_AUDIT_EXPIRED")
    for row in visible:
        if row["index_state"] != "READY":
            continue
        if index is not None:
            generation = row["index_generation"]
            try:
                if row["revision_id"] in failed_batches:
                    continue
                expected = expected_manifests[(row["revision_id"], generation)]
                # Existing custom/test adapters retain their declared single-read contract.
                actual = (expected if cached_at is not None else
                    physical.get((row["revision_id"], generation), {}) if callable(batch_readback)
                    else index.readback(principal.tenant_id, row["revision_id"], generation))
            except DependencyUnavailable:
                warnings.append("INDEX_UNAVAILABLE")
                continue
            except IndexConsistencyError:
                warnings.append("INDEX_MANIFEST_MISMATCH")
                continue
            if expected != actual:
                warnings.append("INDEX_MANIFEST_MISMATCH")
                continue
        indexed += 1
    healthy = _verdict(accepted, indexed, warnings)
    if not healthy and cached_at is None and not _invalidate_cached_audits(registry):
        cache_status = "UNAVAILABLE"
    if (healthy and cached_at is None and cache_key is not None and cache_path is not None
            and cache_status == "MISS"):
        try:
            write_audit(cache_path, cache_key, audit_wall, audit_monotonic)
        except (OSError, sqlite3.Error, ValueError):
            cache_status = "UNAVAILABLE"
    return Coverage(index_coverage=healthy,
                    source_counts_complete=not truncated, accepted_source_count=accepted,
                    indexed_source_count=indexed,
                    warnings=tuple(dict.fromkeys(warnings)),
                    physical_audit_mode="NOT_CHECKED" if index is None else "CACHED" if cached_at is not None else "FRESH",
                    physical_verified_at=(datetime.fromtimestamp(cached_at or audit_wall, timezone.utc)
                        if healthy and index is not None else None),
                    physical_cache_status=cache_status)
