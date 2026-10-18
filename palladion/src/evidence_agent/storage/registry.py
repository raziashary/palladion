"""Persisted source registry with authorization at every operation boundary."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone

from evidence_agent.core.errors import PermissionDenied, ResourceConflict, ValidationFailure
from evidence_agent.core.ids import digest_bytes, revision_id
from evidence_agent.core.models import Principal
from evidence_agent.security.access import AccessController

from .originals import OriginalStore
from .sqlite import Database, utc_now

_GRANTS = {"document:upload", "document:approve", "source:read", "case:read"}


class Registry:
    """Persist identities, case scope, source registration and approval evidence.

    ``bootstrap_*`` methods are trusted synthetic-fixture setup APIs. Runtime
    operations use persisted principals, grants and memberships, then read exact
    original bytes only after current authorization and approval checks.
    """

    def __init__(self, database: Database, originals: OriginalStore) -> None:
        self.database = database
        self.originals = originals
        self.access = AccessController(self.get_principal, self.is_member)

    def bootstrap_principal(self, principal: Principal) -> Principal:
        """Persist one trusted synthetic profile; repeated calls never restore grants."""
        connection = self.database.connection
        existing = connection.execute(
            "SELECT tenant_id FROM principals WHERE principal_id = ?",
            (principal.principal_id,),
        ).fetchone()
        if existing is not None:
            if existing["tenant_id"] != principal.tenant_id:
                raise ResourceConflict
            current = self.get_principal(principal.principal_id)
            if current is None:
                raise ResourceConflict
            return current

        profile_json = principal.model_dump_json()
        with self.database.transaction() as transaction:
            transaction.execute("INSERT OR IGNORE INTO tenants(tenant_id) VALUES (?)", (principal.tenant_id,))
            transaction.execute(
                "INSERT INTO principals(principal_id, tenant_id, profile_json, created_at) "
                "VALUES (?, ?, ?, ?)",
                (principal.principal_id, principal.tenant_id, profile_json, utc_now()),
            )
            transaction.executemany(
                "INSERT INTO principal_roles(principal_id, role) VALUES (?, ?)",
                ((principal.principal_id, role) for role in principal.roles),
            )
            invalid_grants = set(principal.grants) - _GRANTS
            if invalid_grants:
                raise ValidationFailure
            transaction.executemany(
                "INSERT INTO principal_grants(principal_id, grant_name) VALUES (?, ?)",
                ((principal.principal_id, grant_name) for grant_name in principal.grants),
            )
        return self.get_principal(principal.principal_id) or principal

    def bootstrap_case(self, tenant_id: str, case_id: str) -> None:
        """Create a synthetic case; intended only for trusted fixture setup."""
        if not tenant_id or not case_id:
            raise ValidationFailure
        with self.database.transaction() as connection:
            connection.execute("INSERT OR IGNORE INTO tenants(tenant_id) VALUES (?)", (tenant_id,))
            connection.execute(
                "INSERT OR IGNORE INTO cases(tenant_id, case_id, created_at) VALUES (?, ?, ?)",
                (tenant_id, case_id, utc_now()),
            )

    def bootstrap_membership(self, principal: Principal, case_id: str) -> Principal:
        """Create a synthetic membership for a previously persisted principal."""
        current = self.get_principal(principal.principal_id)
        if current is None or current.tenant_id != principal.tenant_id:
            raise PermissionDenied
        with self.database.transaction() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO case_memberships "
                "(tenant_id, case_id, principal_id, granted_at) VALUES (?, ?, ?, ?)",
                (current.tenant_id, case_id, current.principal_id, utc_now()),
            )
        updated = self.get_principal(principal.principal_id)
        if updated is None:
            raise PermissionDenied
        return updated

    def get_principal(self, principal_id: str) -> Principal | None:
        """Load a typed principal with currently persisted roles, grants and cases."""
        row = self.database.connection.execute(
            "SELECT principal_id, tenant_id, profile_json FROM principals WHERE principal_id = ?",
            (principal_id,),
        ).fetchone()
        if row is None:
            return None
        principal = Principal.model_validate_json(row["profile_json"])
        if principal.principal_id != row["principal_id"] or principal.tenant_id != row["tenant_id"]:
            raise ResourceConflict
        roles = tuple(
            record[0]
            for record in self.database.connection.execute(
                "SELECT role FROM principal_roles WHERE principal_id = ? ORDER BY role",
                (principal_id,),
            )
        )
        grants = tuple(
            record[0]
            for record in self.database.connection.execute(
                "SELECT grant_name FROM principal_grants WHERE principal_id = ? ORDER BY grant_name",
                (principal_id,),
            )
        )
        cases = tuple(
            record[0]
            for record in self.database.connection.execute(
                "SELECT case_id FROM case_memberships "
                "WHERE principal_id = ? AND tenant_id = ? AND revoked_at IS NULL ORDER BY case_id",
                (principal_id, principal.tenant_id),
            )
        )
        return principal.model_copy(
            update={"roles": roles, "grants": grants, "allowed_case_ids": cases}
        )

    def is_member(self, tenant_id: str, case_id: str, principal_id: str) -> bool:
        """Return whether a current, non-revoked membership exists."""
        return (
            self.database.connection.execute(
                "SELECT 1 FROM case_memberships "
                "WHERE tenant_id = ? AND case_id = ? AND principal_id = ? AND revoked_at IS NULL",
                (tenant_id, case_id, principal_id),
            ).fetchone()
            is not None
        )

    def revoke_grant(self, actor: Principal, principal_id: str, grant_name: str) -> None:
        """Revoke a persisted grant under a current synthetic administrator."""
        if grant_name not in _GRANTS:
            raise ValidationFailure
        target = self.get_principal(principal_id)
        if target is None:
            raise PermissionDenied
        self.access.authorize(
            actor,
            tenant_id=target.tenant_id,
            grant="document:approve",
            role="admin",
        )
        with self.database.transaction() as connection:
            self.access.authorize(
                actor,
                tenant_id=target.tenant_id,
                grant="document:approve",
                role="admin",
            )
            connection.execute(
                "DELETE FROM principal_grants WHERE principal_id = ? AND grant_name = ?",
                (principal_id, grant_name),
            )
            self._audit(
                connection,
                actor,
                "GRANT_REVOKED",
                {"principal_id": principal_id, "grant": grant_name},
            )

    def revoke_membership(self, actor: Principal, principal_id: str, case_id: str) -> None:
        """Revoke a current case membership under a current synthetic administrator."""
        target = self.get_principal(principal_id)
        if target is None:
            raise PermissionDenied
        self.access.authorize(
            actor,
            tenant_id=target.tenant_id,
            grant="document:approve",
            role="admin",
        )
        with self.database.transaction() as connection:
            self.access.authorize(
                actor,
                tenant_id=target.tenant_id,
                grant="document:approve",
                role="admin",
            )
            cursor = connection.execute(
                "UPDATE case_memberships SET revoked_at = ? "
                "WHERE tenant_id = ? AND case_id = ? AND principal_id = ? AND revoked_at IS NULL",
                (utc_now(), target.tenant_id, case_id, principal_id),
            )
            if cursor.rowcount:
                self._audit(
                    connection,
                    actor,
                    "CASE_MEMBERSHIP_REVOKED",
                    {"principal_id": principal_id, "case_id": case_id},
                )

    def source_metadata(self, principal: Principal, revision_id: str) -> dict[str, object]:
        """Read source scope and status under current source authorization."""
        row = self.database.connection.execute(
            "SELECT revision.revision_id, revision.tenant_id, revision.case_id, revision.family_id, "
            "revision.content_sha256, revision.source_path, revision.owner_id, "
            "revision.approval_status, revision.index_state, revision.index_generation, "
            "revision.valid_from, revision.valid_to, revision.acl_json, approval.status "
            "AS approval_record_status FROM document_revisions AS revision "
            "LEFT JOIN approval_records AS approval ON approval.approval_record_id = revision.approval_record_id "
            "AND approval.tenant_id = revision.tenant_id AND approval.revision_id = revision.revision_id "
            "WHERE revision.tenant_id = ? AND revision.revision_id = ?",
            (principal.tenant_id, revision_id),
        ).fetchone()
        if row is None:
            raise PermissionDenied
        self.access.authorize(
            principal,
            tenant_id=row["tenant_id"],
            case_id=row["case_id"],
            grant="source:read",
        )
        acl = json.loads(row["acl_json"])
        allowed = acl.get("allowed_principal_ids", [])
        if allowed and principal.principal_id not in allowed:
            raise PermissionDenied
        metadata: dict[str, object] = dict(row)
        metadata["allowed_principal_ids"] = tuple(allowed)
        return metadata

    def revoke_source(self, actor: Principal, revision_id: str) -> None:
        """Immediately revoke source authority and append an audit event atomically."""
        with self.database.transaction() as connection:
            self.access.authorize(
                actor,
                tenant_id=actor.tenant_id,
                grant="document:approve",
                role="admin",
            )
            row = connection.execute(
                "SELECT tenant_id, case_id, approval_status FROM document_revisions "
                "WHERE tenant_id = ? AND revision_id = ?",
                (actor.tenant_id, revision_id),
            ).fetchone()
            if row is None:
                raise PermissionDenied
            self.access.authorize(
                actor,
                tenant_id=row["tenant_id"],
                case_id=row["case_id"],
                grant="document:approve",
                role="admin",
            )
            if row["approval_status"] != "APPROVED":
                raise ResourceConflict
            connection.execute(
                "UPDATE document_revisions SET approval_status = 'REVOKED' "
                "WHERE tenant_id = ? AND revision_id = ? AND approval_status = 'APPROVED'",
                (actor.tenant_id, revision_id),
            )
            self._audit(connection, actor, "SOURCE_REVOKED", {"revision_id": revision_id})

    def register_source(
        self,
        principal: Principal,
        *,
        tenant_id: str,
        case_id: str,
        family_id: str,
        content: bytes,
        source_path: str,
        owner_id: str,
        allowed_principal_ids: tuple[str, ...] = (),
        valid_from: str | None = None,
        valid_to: str | None = None,
    ) -> str:
        """Store and register a new immutable source revision in STORED state."""
        self.access.authorize(
            principal,
            tenant_id=tenant_id,
            case_id=case_id,
            grant="document:upload",
        )
        if not family_id or not source_path or not isinstance(content, bytes):
            raise ValidationFailure
        owner = self.get_principal(owner_id)
        if owner is None or owner.tenant_id != tenant_id:
            raise ValidationFailure
        if len(allowed_principal_ids) != len(set(allowed_principal_ids)):
            raise ValidationFailure
        for allowed_id in allowed_principal_ids:
            allowed = self.get_principal(allowed_id)
            if (
                allowed is None
                or allowed.tenant_id != tenant_id
                or not self.is_member(tenant_id, case_id, allowed_id)
            ):
                raise ValidationFailure
        valid_from = _normalize_utc(valid_from)
        valid_to = _normalize_utc(valid_to)
        if valid_from is not None and valid_to is not None and valid_from >= valid_to:
            raise ValidationFailure

        content_hash = digest_bytes(content)
        revision = revision_id(tenant_id, family_id, content_hash)
        # A content hash is the only filesystem path input. The supplied source_path
        # is persisted as descriptive provenance and never opened or resolved.
        self.originals.put(content)

        with self.database.transaction() as connection:
            self.access.authorize(
                principal,
                tenant_id=tenant_id,
                case_id=case_id,
                grant="document:upload",
            )
            connection.execute(
                "INSERT OR IGNORE INTO document_families(tenant_id, family_id, owner_id, created_at) "
                "VALUES (?, ?, ?, ?)",
                (tenant_id, family_id, owner_id, utc_now()),
            )
            family = connection.execute(
                "SELECT owner_id FROM document_families WHERE tenant_id = ? AND family_id = ?",
                (tenant_id, family_id),
            ).fetchone()
            if family["owner_id"] != owner_id:
                raise ResourceConflict
            inserted = connection.execute(
                "INSERT OR IGNORE INTO document_revisions "
                "(revision_id, tenant_id, family_id, case_id, content_sha256, source_path, "
                "approval_status, uploader_id, owner_id, valid_from, valid_to, registered_at, "
                "index_state, index_generation, acl_json) "
                "VALUES (?, ?, ?, ?, ?, ?, 'DRAFT', ?, ?, ?, ?, ?, 'STORED', 'unindexed', ?)",
                (
                    revision,
                    tenant_id,
                    family_id,
                    case_id,
                    content_hash,
                    source_path,
                    principal.principal_id,
                    owner_id,
                    valid_from,
                    valid_to,
                    utc_now(),
                    json.dumps(
                        {
                            "case_id": case_id,
                            "tenant_id": tenant_id,
                            "allowed_principal_ids": sorted(allowed_principal_ids),
                        },
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                ),
            ).rowcount == 1
            row = connection.execute(
                "SELECT content_sha256, uploader_id, family_id, case_id, source_path, owner_id, "
                "acl_json, "
                "valid_from, valid_to FROM document_revisions "
                "WHERE tenant_id = ? AND revision_id = ?",
                (tenant_id, revision),
            ).fetchone()
            existing = (
                row["content_sha256"],
                row["uploader_id"],
                row["family_id"],
                row["case_id"],
                row["source_path"],
                row["owner_id"],
                row["acl_json"],
                row["valid_from"],
                row["valid_to"],
            )
            requested = (
                content_hash,
                principal.principal_id,
                family_id,
                case_id,
                source_path,
                owner_id,
                json.dumps(
                    {
                        "case_id": case_id,
                        "tenant_id": tenant_id,
                        "allowed_principal_ids": sorted(allowed_principal_ids),
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                ),
                valid_from,
                valid_to,
            )
            if existing != requested:
                raise ResourceConflict
            if inserted:
                self._audit(
                    connection,
                    principal,
                    "SOURCE_REGISTERED",
                    {"revision_id": revision, "family_id": family_id, "content_sha256": content_hash},
                )
        return revision

    def approve_source(
        self,
        principal: Principal,
        revision_id: str,
        *,
        supersedes_revision_id: str | None = None,
        applicability_scope: dict[str, str] | None = None,
    ) -> str:
        """Record external approval; uploader self-approval is forbidden."""
        if (supersedes_revision_id is None) != (applicability_scope is None):
            raise ValidationFailure
        with self.database.transaction() as connection:
            self.access.authorize(
                principal,
                tenant_id=principal.tenant_id,
                grant="document:approve",
                role="admin",
            )
            row = connection.execute(
                "SELECT * FROM document_revisions WHERE tenant_id = ? AND revision_id = ?",
                (principal.tenant_id, revision_id),
            ).fetchone()
            if row is None or row["approval_status"] != "DRAFT":
                raise ResourceConflict
            self.access.authorize(
                principal,
                tenant_id=row["tenant_id"],
                case_id=row["case_id"],
                grant="document:approve",
                role="admin",
            )
            if row["uploader_id"] == principal.principal_id:
                raise PermissionDenied
            if row["index_state"] != "STORED":
                raise ResourceConflict

            predecessor = None
            scope_json = None
            if supersedes_revision_id is not None and applicability_scope is not None:
                expected_scope = {"tenant_id": row["tenant_id"], "case_id": row["case_id"]}
                if applicability_scope != expected_scope:
                    raise ValidationFailure
                predecessor = connection.execute(
                    "SELECT tenant_id, case_id, family_id, approval_status FROM document_revisions "
                    "WHERE tenant_id = ? AND revision_id = ?",
                    (row["tenant_id"], supersedes_revision_id),
                ).fetchone()
                if (
                    predecessor is None
                    or predecessor["approval_status"] != "APPROVED"
                    or predecessor["case_id"] != row["case_id"]
                    or predecessor["family_id"] != row["family_id"]
                    or supersedes_revision_id == revision_id
                ):
                    raise ValidationFailure
                scope_json = json.dumps(applicability_scope, separators=(",", ":"), sort_keys=True)

            approval_id = f"approval_{uuid.uuid4().hex}"
            recorded_at = utc_now()
            scope = json.dumps(
                {"case_id": row["case_id"], "tenant_id": principal.tenant_id},
                separators=(",", ":"),
            )
            connection.execute(
                "INSERT INTO approval_records "
                "(approval_record_id, revision_id, tenant_id, approver_id, status, "
                "approval_scope_json, recorded_at) VALUES (?, ?, ?, ?, 'APPROVED', ?, ?)",
                (approval_id, revision_id, principal.tenant_id, principal.principal_id, scope, recorded_at),
            )
            connection.execute(
                "UPDATE document_revisions SET approval_status = 'APPROVED', approval_record_id = ? "
                "WHERE tenant_id = ? AND revision_id = ?",
                (approval_id, principal.tenant_id, revision_id),
            )
            if predecessor is not None and supersedes_revision_id is not None and scope_json is not None:
                edge_identity = "\0".join(
                    (principal.tenant_id, supersedes_revision_id, revision_id, scope_json)
                ).encode("utf-8")
                connection.execute(
                    "INSERT OR IGNORE INTO supersession_edges "
                    "(edge_id, tenant_id, predecessor_revision_id, successor_revision_id, "
                    "applicability_scope_json, valid_from, recorded_at, approved_by) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        "edge_" + hashlib.sha256(edge_identity).hexdigest(),
                        principal.tenant_id,
                        supersedes_revision_id,
                        revision_id,
                        scope_json,
                        row["valid_from"] or recorded_at,
                        recorded_at,
                        principal.principal_id,
                    ),
                )
                self._audit(
                    connection,
                    principal,
                    "SOURCE_SUPERSESSION_RECORDED",
                    {
                        "revision_id": revision_id,
                        "predecessor_revision_id": supersedes_revision_id,
                    },
                )
            self._audit(
                connection,
                principal,
                "SOURCE_APPROVED",
                {"revision_id": revision_id, "approval_record_id": approval_id},
            )
        return approval_id

    def read_source(
        self,
        principal: Principal,
        revision_id: str,
        *,
        start_byte: int | None = None,
        end_byte: int | None = None,
    ) -> bytes:
        """Recheck current persisted access and approval, then return exact bytes."""
        with self.database.transaction() as connection:
            self.access.authorize(
                principal,
                tenant_id=principal.tenant_id,
                grant="source:read",
            )
            row = connection.execute(
                "SELECT revision.tenant_id, revision.case_id, revision.content_sha256, "
                "revision.approval_status, revision.acl_json, approval.status AS record_status "
                "FROM document_revisions AS revision "
                "LEFT JOIN approval_records AS approval "
                "ON approval.approval_record_id = revision.approval_record_id "
                "AND approval.tenant_id = revision.tenant_id "
                "AND approval.revision_id = revision.revision_id "
                "WHERE revision.tenant_id = ? AND revision.revision_id = ?",
                (principal.tenant_id, revision_id),
            ).fetchone()
            if row is None:
                raise PermissionDenied
            self.access.authorize(
                principal,
                tenant_id=row["tenant_id"],
                case_id=row["case_id"],
                grant="source:read",
            )
            if row["approval_status"] != "APPROVED" or row["record_status"] != "APPROVED":
                raise PermissionDenied
            acl = json.loads(row["acl_json"])
            allowed_principal_ids = acl.get("allowed_principal_ids", [])
            if allowed_principal_ids and principal.principal_id not in allowed_principal_ids:
                raise PermissionDenied

            if start_byte is None:
                if end_byte is not None:
                    raise ValidationFailure
                content = self.originals.read(row["content_sha256"])
            else:
                if end_byte is None:
                    raise ValidationFailure
                content = self.originals.read_range(row["content_sha256"], start_byte, end_byte)
            self._audit(
                connection,
                principal,
                "SOURCE_READ",
                {"revision_id": revision_id, "content_sha256": row["content_sha256"]},
            )
        return content

    def _audit(
        self,
        connection: sqlite3.Connection,
        principal: Principal,
        event_kind: str,
        safe_payload: dict[str, str],
    ) -> None:
        trace_id = f"trace_{uuid.uuid4().hex}"
        connection.execute(
            "INSERT INTO audit_events "
            "(audit_id, trace_id, principal_id, tenant_id, event_kind, safe_payload_json, occurred_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                f"audit_{uuid.uuid4().hex}",
                trace_id,
                principal.principal_id,
                principal.tenant_id,
                event_kind,
                json.dumps(safe_payload, separators=(",", ":"), sort_keys=True),
                utc_now(),
            ),
        )


__all__ = ["Registry"]


def _normalize_utc(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationFailure
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationFailure from exc
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValidationFailure
    return instant.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
