"""Validation of untrusted upload fields against persisted registry authority."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from evidence_agent.core.errors import PermissionDenied, ValidationFailure
from evidence_agent.core.models import Principal
from evidence_agent.storage.registry import Registry

from .parsing import MAX_SOURCE_BYTES, validate_source


@dataclass(frozen=True, slots=True)
class ValidatedUpload:
    """Upload values checked against bytes and current persisted grants."""

    tenant_id: str
    case_id: str
    family_id: str
    content: bytes
    source_path: str
    owner_id: str
    allowed_principal_ids: tuple[str, ...]
    valid_from: str | None
    valid_to: str | None
    content_type: str
    content_sha256: str


def validate_upload(content: bytes, filename: str, mime_type: str) -> None:
    """Validate source size, UTF-8 encoding, extension, and declared MIME type."""
    validate_source(content, filename, mime_type)


def validate_upload_metadata(
    registry: Registry,
    uploader: Principal,
    *,
    tenant_id: str,
    case_id: str,
    family_id: str,
    content: bytes,
    filename: str,
    content_type: str,
    expected_sha256: str,
    source_path: str,
    owner_id: str,
    allowed_principal_ids: tuple[str, ...] = (),
    valid_from: str | None = None,
    valid_to: str | None = None,
) -> ValidatedUpload:
    """Reject spoofed MIME/hash/scope and metadata outside current registry grants.

    This function validates only; `Registry.register_source` remains the sole
    writer and repeats authorization within its transaction.
    """
    if not isinstance(content, bytes) or not content or len(content) > MAX_SOURCE_BYTES:
        raise ValidationFailure
    media_type = validate_source(content, filename, content_type)
    actual_hash = hashlib.sha256(content).hexdigest()
    if expected_sha256 != actual_hash:
        raise ValidationFailure
    if not family_id or not source_path or tenant_id != uploader.tenant_id:
        raise ValidationFailure
    registry.access.authorize(
        uploader,
        tenant_id=tenant_id,
        case_id=case_id,
        grant="document:upload",
    )
    owner = registry.get_principal(owner_id)
    if owner is None or owner.tenant_id != tenant_id:
        raise ValidationFailure
    if len(allowed_principal_ids) != len(set(allowed_principal_ids)):
        raise ValidationFailure
    for principal_id in allowed_principal_ids:
        allowed = registry.get_principal(principal_id)
        if (
            allowed is None
            or allowed.tenant_id != tenant_id
            or not registry.is_member(tenant_id, case_id, principal_id)
        ):
            raise ValidationFailure
    # Registration owns the canonical timestamp parser/normalizer. This check
    # is intentionally delegated there instead of maintaining a second policy.
    return ValidatedUpload(
        tenant_id,
        case_id,
        family_id,
        content,
        source_path,
        owner_id,
        allowed_principal_ids,
        valid_from,
        valid_to,
        media_type,
        actual_hash,
    )


def validate_supersession_scope(
    registry: Registry,
    approver: Principal,
    *,
    predecessor_revision_id: str,
    successor_tenant_id: str,
    successor_case_id: str,
    successor_family_id: str,
    applicability_scope: dict[str, str],
) -> None:
    """Validate a same-family, same-case supersession under an approver grant."""
    registry.access.authorize(
        approver,
        tenant_id=successor_tenant_id,
        case_id=successor_case_id,
        grant="document:approve",
        role="admin",
    )
    predecessor = registry.source_metadata(approver, predecessor_revision_id)
    expected_scope = {"case_id": successor_case_id, "tenant_id": successor_tenant_id}
    if (
        predecessor["tenant_id"] != successor_tenant_id
        or predecessor["case_id"] != successor_case_id
        or predecessor["family_id"] != successor_family_id
        or applicability_scope != expected_scope
    ):
        raise PermissionDenied
