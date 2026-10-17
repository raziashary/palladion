"""Stable, namespace-scoped identifiers derived from immutable inputs."""

from __future__ import annotations

import hashlib
import json


def digest_bytes(data: bytes) -> str:
    if not isinstance(data, bytes):
        raise TypeError("data must be bytes")
    return hashlib.sha256(data).hexdigest()


def _stable_id(prefix: str, *parts: str | int) -> str:
    payload = json.dumps(parts, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()}"


def revision_id(tenant_id: str, family_id: str, content_hash: str) -> str:
    """Identify one immutable revision within a tenant and source family."""
    if not tenant_id or not family_id:
        raise ValueError("tenant_id and family_id are required")
    if len(content_hash) != 64 or any(c not in "0123456789abcdef" for c in content_hash):
        raise ValueError("content_hash must be a lowercase SHA-256 hex digest")
    return _stable_id("rev", tenant_id, family_id, content_hash)


def chunk_id(tenant_id: str, revision: str, start: int, end: int) -> str:
    """Identify an exact half-open byte span inside an immutable revision."""
    if not tenant_id or not revision:
        raise ValueError("tenant_id and revision are required")
    if isinstance(start, bool) or isinstance(end, bool) or start < 0 or end < start:
        raise ValueError("chunk spans must be non-negative half-open ranges")
    return _stable_id("chunk", tenant_id, revision, start, end)


def evidence_ref_id(tenant_id: str, revision: str, start: int, end: int, content_hash: str) -> str:
    """Identify a tenant-scoped citation to a hash-checked source span."""
    if len(content_hash) != 64 or any(c not in "0123456789abcdef" for c in content_hash):
        raise ValueError("content_hash must be a lowercase SHA-256 hex digest")
    span_id = chunk_id(tenant_id, revision, start, end)
    return _stable_id("evidence", tenant_id, span_id, content_hash)


def canonical_entity_key(
    tenant_id: str,
    source_system: str,
    entity_kind: str,
    verified_external_id: str,
) -> str:
    """Key an attested external ID; display labels are not accepted as identity inputs."""
    if not tenant_id or not source_system or not entity_kind or not verified_external_id:
        raise ValueError("tenant, source system, entity kind and verified external ID are required")
    return _stable_id("entity", tenant_id, source_system, entity_kind, verified_external_id)


def provisional_entity_key(tenant_id: str, revision: str, start: int, end: int) -> str:
    """Keep unresolved identities separate and anchored to an immutable source span."""
    if not tenant_id or not revision:
        raise ValueError("tenant_id and revision are required")
    if isinstance(start, bool) or isinstance(end, bool) or start < 0 or end < start:
        raise ValueError("provisional source spans must be non-negative half-open ranges")
    return _stable_id("provisional", tenant_id, revision, start, end)
