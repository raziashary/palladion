from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from evidence_agent.core.errors import PermissionDenied, ResourceConflict, ValidationFailure
from evidence_agent.core.ids import digest_bytes
from evidence_agent.core.models import Principal
from evidence_agent.storage.originals import OriginalIntegrityError, OriginalStore
from evidence_agent.storage.registry import Registry
from evidence_agent.storage.sqlite import Database, DatabaseSchemaError


def _principal(
    principal_id: str,
    *,
    roles: tuple[str, ...] = (),
    grants: tuple[str, ...] = (),
) -> Principal:
    return Principal(
        principal_id=principal_id,
        tenant_id="tenant-a",
        roles=roles,
        grants=grants,
    )


def _registry(tmp_path: Path) -> tuple[Database, Registry]:
    database = Database(tmp_path / "registry.sqlite").open()
    originals = OriginalStore(tmp_path / "originals")
    return database, Registry(database, originals)


def _downgrade_to_v1(path: Path, *, populated: bool) -> None:
    connection = sqlite3.connect(path)
    try:
        if populated:
            connection.execute("INSERT INTO tenants(tenant_id) VALUES ('tenant-preserved')")
        connection.execute("DROP INDEX case_events_scope_idx")
        connection.execute("DELETE FROM schema_versions WHERE version = 2")
        connection.execute("PRAGMA user_version = 1")
        connection.commit()
    finally:
        connection.close()


def test_fresh_schema_enforces_foreign_keys_status_and_utc_records(tmp_path: Path) -> None:
    with Database(tmp_path / "fresh.sqlite") as database:
        connection = database.connection
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert connection.execute("PRAGMA user_version").fetchone()[0] == Database.SCHEMA_VERSION
        rows = connection.execute("SELECT version, applied_at FROM schema_versions ORDER BY version").fetchall()
        assert [row["version"] for row in rows] == [1, 2]
        assert all(row["applied_at"].endswith("Z") for row in rows)

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO cases(tenant_id, case_id, created_at) VALUES ('missing', 'c1', '2026-01-01T00:00:00Z')"
            )
        connection.execute("INSERT INTO tenants(tenant_id) VALUES ('tenant-a')")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO document_revisions "
                "(revision_id, tenant_id, family_id, case_id, content_sha256, source_path, "
                "approval_status, uploader_id, owner_id, registered_at, index_state, index_generation, acl_json) "
                "VALUES ('r1', 'tenant-a', 'f1', 'missing', ?, 'x', 'INVALID', 'p1', 'p1', "
                "'2026-01-01T00:00:00Z', 'STORED', 'unindexed', '{}')",
                ("0" * 64,),
            )
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_populated_forward_upgrade_preserves_rows_and_reopens(tmp_path: Path) -> None:
    path = tmp_path / "upgrade.sqlite"
    with Database(path) as database:
        database.connection.execute(
            "INSERT INTO tenants(tenant_id) VALUES ('tenant-original')"
        )
    _downgrade_to_v1(path, populated=True)

    with Database(path) as upgraded:
        assert upgraded.connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert [
            row[0]
            for row in upgraded.connection.execute("SELECT tenant_id FROM tenants ORDER BY tenant_id")
        ] == ["tenant-original", "tenant-preserved"]
        assert [
            row[0]
            for row in upgraded.connection.execute("SELECT version FROM schema_versions ORDER BY version")
        ] == [1, 2]
        assert upgraded.connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = 'case_events_scope_idx'"
        ).fetchone() is not None
    with Database(path) as reopened:
        assert reopened.connection.execute(
            "SELECT tenant_id FROM tenants WHERE tenant_id = 'tenant-preserved'"
        ).fetchone()[0] == "tenant-preserved"


def test_failed_migration_rolls_back_ddl_data_and_version(tmp_path: Path) -> None:
    path = tmp_path / "rollback.sqlite"
    with Database(path) as database:
        database.connection.execute("INSERT INTO tenants(tenant_id) VALUES ('kept')")
    _downgrade_to_v1(path, populated=False)
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "CREATE TRIGGER fail_v2_record BEFORE INSERT ON schema_versions "
            "WHEN NEW.version = 2 BEGIN SELECT RAISE(ABORT, 'injected migration failure'); END"
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(sqlite3.IntegrityError, match="injected migration failure"):
        Database(path).open()

    connection = sqlite3.connect(path)
    try:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert connection.execute("SELECT version FROM schema_versions").fetchall() == [(1,)]
        assert connection.execute("SELECT tenant_id FROM tenants").fetchall() == [("kept",)]
        assert connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = 'case_events_scope_idx'"
        ).fetchone() is None
    finally:
        connection.close()


@pytest.mark.parametrize("version,application_id", [(0, 0), (3, Database.APPLICATION_ID), (1, 42)])
def test_unknown_newer_or_foreign_schemas_are_rejected(
    tmp_path: Path, version: int, application_id: int
) -> None:
    path = tmp_path / f"unknown-{version}-{application_id}.sqlite"
    connection = sqlite3.connect(path)
    try:
        if version == 0:
            connection.execute("CREATE TABLE foreign_table(value TEXT)")
        else:
            connection.execute(f"PRAGMA user_version = {version}")
            connection.execute(f"PRAGMA application_id = {application_id}")
    finally:
        connection.close()
    original_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(DatabaseSchemaError):
        Database(path).open()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == original_hash
    assert not Path(f"{path}-wal").exists()
    assert not Path(f"{path}-shm").exists()


def test_registry_reopens_typed_profiles_and_enforces_approval_and_current_acl(
    tmp_path: Path,
) -> None:
    database, registry = _registry(tmp_path)
    uploader = registry.bootstrap_principal(
        _principal("uploader", grants=("document:upload", "source:read"))
    )
    approver = registry.bootstrap_principal(
        _principal("approver", roles=("admin",), grants=("document:approve", "source:read"))
    )
    reader = registry.bootstrap_principal(
        _principal("reader", grants=("source:read", "case:read"))
    )
    limited_reader = registry.bootstrap_principal(
        _principal("limited-reader", grants=("source:read", "case:read"))
    )
    registry.bootstrap_case("tenant-a", "case-1")
    uploader = registry.bootstrap_membership(uploader, "case-1")
    approver = registry.bootstrap_membership(approver, "case-1")
    reader = registry.bootstrap_membership(reader, "case-1")
    limited_reader = registry.bootstrap_membership(limited_reader, "case-1")

    # The authoritative Principal is reconstructed from typed JSON plus current tables.
    database.close()
    database = Database(tmp_path / "registry.sqlite").open()
    registry = Registry(database, OriginalStore(tmp_path / "originals"))
    uploader = registry.get_principal("uploader")
    approver = registry.get_principal("approver")
    reader = registry.get_principal("reader")
    assert uploader == registry.access.authenticate("uploader")
    assert uploader.allowed_case_ids == ("case-1",)

    content = "Approved in prose does not approve itself: café ✓\n".encode("utf-8")
    revision = registry.register_source(
        uploader,
        tenant_id="tenant-a",
        case_id="case-1",
        family_id="DEMO.SOP",
        content=content,
        source_path=r"..\untrusted\source.md",
        owner_id="uploader",
        allowed_principal_ids=("reader",),
    )
    assert digest_bytes(registry.originals.read(digest_bytes(content))) == digest_bytes(content)
    row = database.connection.execute(
        "SELECT approval_status, index_state, source_path FROM document_revisions WHERE revision_id = ?",
        (revision,),
    ).fetchone()
    assert tuple(row) == ("DRAFT", "STORED", r"..\untrusted\source.md")
    with pytest.raises(PermissionDenied):
        registry.approve_source(uploader, revision)
    approval_id = registry.approve_source(approver, revision)
    approval = database.connection.execute(
        "SELECT approver_id, status FROM approval_records WHERE approval_record_id = ?",
        (approval_id,),
    ).fetchone()
    assert tuple(approval) == ("approver", "APPROVED")

    assert registry.read_source(reader, revision) == content
    assert registry.read_source(reader, revision, start_byte=39, end_byte=45) == content[39:45]
    with pytest.raises(PermissionDenied):
        registry.read_source(limited_reader, revision)
    registry.revoke_grant(approver, "reader", "source:read")
    with pytest.raises(PermissionDenied):
        registry.read_source(reader, revision)
    current_reader = registry.get_principal("reader")
    assert current_reader is not None and "source:read" not in current_reader.grants

    registry.bootstrap_principal(
        _principal("reader-2", grants=("source:read",))
    )
    reader_2 = registry.get_principal("reader-2")
    reader_2 = registry.bootstrap_membership(reader_2, "case-1")
    registry.revoke_membership(approver, "reader-2", "case-1")
    with pytest.raises(PermissionDenied):
        registry.read_source(reader_2, revision)

    events = database.connection.execute(
        "SELECT event_kind FROM audit_events ORDER BY occurred_at, rowid"
    ).fetchall()
    assert [row[0] for row in events] == [
        "SOURCE_REGISTERED",
        "SOURCE_APPROVED",
        "SOURCE_READ",
            "SOURCE_READ",
        "GRANT_REVOKED",
        "CASE_MEMBERSHIP_REVOKED",
    ]
    database.close()
    with Database(tmp_path / "registry.sqlite") as reopened:
        assert reopened.connection.execute(
            "SELECT index_state FROM document_revisions WHERE revision_id = ?", (revision,)
        ).fetchone()[0] == "STORED"


def test_registration_rejects_revision_metadata_aliases_and_normalizes_utc(tmp_path: Path) -> None:
    database, registry = _registry(tmp_path)
    uploader = registry.bootstrap_principal(
        _principal("uploader", grants=("document:upload",))
    )
    registry.bootstrap_case("tenant-a", "case-1")
    registry.bootstrap_case("tenant-a", "case-2")
    reader = registry.bootstrap_principal(_principal("reader", grants=("source:read",)))
    uploader = registry.bootstrap_membership(uploader, "case-1")
    uploader = registry.bootstrap_membership(uploader, "case-2")
    registry.bootstrap_membership(reader, "case-1")
    registry.bootstrap_membership(reader, "case-2")
    metadata = {
        "tenant_id": "tenant-a",
        "family_id": "DEMO.UTC",
        "content": b"versioned metadata",
        "source_path": "demo/source.md",
        "owner_id": "uploader",
        "allowed_principal_ids": ("reader",),
        "valid_from": "2026-01-01T03:00:00+03:00",
        "valid_to": "2027-01-01T00:00:00Z",
    }
    revision = registry.register_source(
        uploader, case_id="case-1", **metadata
    )
    row = database.connection.execute(
        "SELECT valid_from, valid_to FROM document_revisions WHERE revision_id = ?", (revision,)
    ).fetchone()
    assert tuple(row) == ("2026-01-01T00:00:00.000000Z", "2027-01-01T00:00:00.000000Z")

    with pytest.raises(ResourceConflict):
        registry.register_source(uploader, case_id="case-2", **metadata)
    with pytest.raises(ResourceConflict):
        registry.register_source(
            uploader, case_id="case-1", **{**metadata, "source_path": "different-name.md"}
        )
    with pytest.raises(ResourceConflict):
        registry.register_source(
            uploader,
            case_id="case-1",
            **{**metadata, "allowed_principal_ids": ()},
        )
    with pytest.raises(ValidationFailure):
        registry.register_source(
            uploader,
            case_id="case-1",
            **{**metadata, "content": b"naive", "valid_from": "2026-01-01T00:00:00"},
        )
    with pytest.raises(ValidationFailure):
        registry.register_source(
            uploader,
            case_id="case-1",
            **{**metadata, "content": b"malformed", "valid_from": "not-a-time"},
        )
    database.close()


def test_original_store_preserves_exact_utf8_bytes_and_half_open_ranges(tmp_path: Path) -> None:
    store = OriginalStore(tmp_path / "objects")
    content = "A café marker ✓ at the end\n".encode("utf-8")
    digest = store.put(content)
    assert digest == digest_bytes(content)
    assert store.put(content) == digest
    assert store.read(digest) == content
    marker = content.index("✓".encode("utf-8"))
    assert store.read_range(digest, marker, marker + len("✓".encode("utf-8"))) == "✓".encode("utf-8")
    assert store.read_range(digest, len(content), len(content)) == b""
    with pytest.raises(ValueError):
        store.read_range(digest, -1, 2)
    with pytest.raises(ValueError):
        store.read_range(digest, 0, len(content) + 1)
    with pytest.raises(ValueError):
        store.read("../outside")
    with pytest.raises(TypeError):
        store.read_range(digest, True, 1)


def test_original_store_detects_corruption_without_replacing_content(tmp_path: Path) -> None:
    store = OriginalStore(tmp_path / "objects")
    content = b"immutable original"
    digest = store.put(content)
    path = store.path_for(digest)
    path.write_bytes(b"tampered bytes")
    corrupted = path.read_bytes()
    with pytest.raises(OriginalIntegrityError):
        store.read(digest)
    with pytest.raises(OriginalIntegrityError):
        store.put(content)
    assert path.read_bytes() == corrupted
