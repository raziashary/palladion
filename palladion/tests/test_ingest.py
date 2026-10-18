from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import pytest

from evidence_agent.core.errors import PermissionDenied, ResourceConflict, ValidationFailure
from evidence_agent.core.ids import digest_bytes
from evidence_agent.core.models import Principal
from evidence_agent.ingest.chunking import chunk_blocks
from evidence_agent.ingest.metadata import validate_supersession_scope, validate_upload_metadata
from evidence_agent.ingest.parsing import parse_document
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
        for table in (
            "context_links",
            "exact_aliases",
            "index_backend_manifests",
            "index_generation_chunks",
            "index_generations",
            "p02_chunks",
        ):
            connection.execute(f"DROP TABLE IF EXISTS {table}")
        connection.execute("DROP INDEX case_events_scope_idx")
        connection.execute("DELETE FROM schema_versions WHERE version > 1")
        connection.execute("PRAGMA user_version = 1")
        connection.commit()
    finally:
        connection.close()


def _downgrade_to_v2(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        for table in (
            "context_links",
            "exact_aliases",
            "index_backend_manifests",
            "index_generation_chunks",
            "index_generations",
            "p02_chunks",
        ):
            connection.execute(f"DROP TABLE IF EXISTS {table}")
        connection.execute("DELETE FROM schema_versions WHERE version = 3")
        connection.execute("PRAGMA user_version = 2")
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
        assert [row["version"] for row in rows] == [1, 2, 3]
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
        assert upgraded.connection.execute("PRAGMA user_version").fetchone()[0] == 3
        assert [
            row[0]
            for row in upgraded.connection.execute("SELECT tenant_id FROM tenants ORDER BY tenant_id")
        ] == ["tenant-original", "tenant-preserved"]
        assert [
            row[0]
            for row in upgraded.connection.execute("SELECT version FROM schema_versions ORDER BY version")
        ] == [1, 2, 3]
        assert upgraded.connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = 'case_events_scope_idx'"
        ).fetchone() is not None
        assert upgraded.connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'p02_chunks'"
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


def test_failed_v3_migration_rolls_back_additive_catalog_and_preserves_v2_rows(
    tmp_path: Path,
) -> None:
    path = tmp_path / "rollback-v3.sqlite"
    with Database(path) as database:
        database.connection.execute("INSERT INTO tenants(tenant_id) VALUES ('kept-v2')")
    _downgrade_to_v2(path)
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "CREATE TRIGGER fail_v3_record BEFORE INSERT ON schema_versions "
            "WHEN NEW.version = 3 BEGIN SELECT RAISE(ABORT, 'injected v3 migration failure'); END"
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(sqlite3.IntegrityError, match="injected v3 migration failure"):
        Database(path).open()

    connection = sqlite3.connect(path)
    try:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
        assert connection.execute("SELECT version FROM schema_versions ORDER BY version").fetchall() == [
            (1,),
            (2,),
        ]
        assert connection.execute("SELECT tenant_id FROM tenants").fetchall() == [("kept-v2",)]
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name IN ('index_generations', 'index_generation_chunks', 'index_backend_manifests')"
        ).fetchall() == []
        assert connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'p02_chunks'"
        ).fetchone() is None
    finally:
        connection.close()

@pytest.mark.parametrize("version,application_id", [(0, 0), (4, Database.APPLICATION_ID), (1, 42)])
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


def test_markdown_parser_keeps_exact_unicode_offsets_lines_headings_and_tables() -> None:
    content = (
        "# Café\r\n\r\nRule ✓ applies.\r\nException: unless status is pending.\r\n\r\n"
        "| field | value |\r\n| --- | --- |\r\n| state | ready |\r\n"
    ).encode("utf-8")
    blocks = parse_document(content, filename="policy.md", content_type="text/markdown; charset=utf-8")

    assert blocks[0].kind == "heading"
    assert blocks[0].heading_path == ("Café",)
    assert any(block.kind == "table" for block in blocks)
    assert all(content[block.start_byte : block.end_byte].decode("utf-8") == block.text for block in blocks)
    assert [block.line_start for block in blocks] == sorted(block.line_start for block in blocks)
    assert blocks[1].section_id == "café"


@pytest.mark.parametrize(
    ("filename", "content_type", "content"),
    [
        ("policy.pdf", "application/pdf", b"unsupported"),
        ("policy.md", "text/plain", b"# Wrong MIME\n"),
        ("policy.txt", "text/plain", b"bad\xffutf8"),
        ("policy.txt", "text/plain", b""),
    ],
)
def test_parser_rejects_unsupported_or_malformed_uploads(
    filename: str, content_type: str, content: bytes
) -> None:
    with pytest.raises(ValidationFailure):
        parse_document(content, filename=filename, content_type=content_type)


def test_chunking_is_deterministic_exact_and_keeps_exception_with_rule() -> None:
    content = (
        "# Refund\n\nThe normal rule is to hold settlement.\n\n"
        "Exception: unless duplicate capture is confirmed.\n\n"
        "A separate unrelated paragraph follows.\n"
    ).encode("utf-8")
    blocks = parse_document(content, filename="sop.md", content_type="text/markdown")
    args = {
        "source_bytes": content,
        "tenant_id": "tenant-a",
        "case_id": "case-1",
        "revision_id": "rev-test",
        "source_sha256": digest_bytes(content),
        "max_chars": 100,
    }
    first = chunk_blocks(blocks, **args)
    second = chunk_blocks(blocks, **args)

    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]
    linked = next(chunk for chunk in first if "Exception:" in chunk.text)
    assert "The normal rule is to hold settlement." in linked.text
    for chunk in first:
        assert content[chunk.start_byte : chunk.end_byte].decode("utf-8") == chunk.text
        assert chunk.content_sha256 == digest_bytes(chunk.text.encode("utf-8"))
        assert chunk.source_sha256 == digest_bytes(content)
    assert all(chunk.parent_id is None or chunk.parent_id in {item.chunk_id for item in first} for chunk in first)


def test_chunking_splits_oversized_unicode_block_at_exact_character_boundaries() -> None:
    content = ("Café ✓ " * 9 + "tail\n").encode("utf-8")
    blocks = parse_document(content, filename="long.md", content_type="text/markdown")
    chunks = chunk_blocks(
        blocks,
        source_bytes=content,
        tenant_id="tenant-a",
        case_id="case-1",
        revision_id="rev-long",
        source_sha256=digest_bytes(content),
        max_chars=13,
    )

    assert len(chunks) > 1
    assert all(len(chunk.text) <= 13 for chunk in chunks)
    assert "".join(chunk.text for chunk in chunks) == content.decode("utf-8")
    assert all(content[chunk.start_byte : chunk.end_byte].decode("utf-8") == chunk.text for chunk in chunks)
    assert all(chunk.line_start == chunk.line_end == 1 for chunk in chunks)
    assert all(
        right.chunk_id in left.neighbor_ids and left.chunk_id in right.neighbor_ids
        for left, right in zip(chunks, chunks[1:])
    )


def test_chunking_does_not_attach_exception_when_pair_exceeds_max_chars() -> None:
    content = (
        "A sufficiently long rule that consumes most of the available limit.\n\n"
        "Exception: an oversized exception clause remains a separate bounded chunk.\n"
    ).encode("utf-8")
    blocks = parse_document(content, filename="exception.md", content_type="text/markdown")
    chunks = chunk_blocks(
        blocks,
        source_bytes=content,
        tenant_id="tenant-a",
        case_id="case-1",
        revision_id="rev-exception",
        source_sha256=digest_bytes(content),
        max_chars=45,
    )

    assert all(len(chunk.text) <= 45 for chunk in chunks)
    assert any("sufficiently long rule" in chunk.text for chunk in chunks)
    exception_chunks = [chunk for chunk in chunks if "Exception:" in chunk.text]
    assert exception_chunks
    assert all("sufficiently long rule" not in chunk.text for chunk in exception_chunks)
    assert all(content[chunk.start_byte : chunk.end_byte].decode("utf-8") == chunk.text for chunk in chunks)


def _approved_source(tmp_path: Path) -> tuple[Database, Registry, Principal, Principal, str, bytes]:
    database, registry = _registry(tmp_path)
    uploader = registry.bootstrap_principal(
        _principal("uploader", grants=("document:upload", "source:read"))
    )
    approver = registry.bootstrap_principal(
        _principal("approver", roles=("admin",), grants=("document:approve", "source:read"))
    )
    registry.bootstrap_case("tenant-a", "case-1")
    uploader = registry.bootstrap_membership(uploader, "case-1")
    approver = registry.bootstrap_membership(approver, "case-1")
    content = b"# Approved\n\nSynthetic policy text.\n"
    revision = registry.register_source(
        uploader,
        tenant_id="tenant-a",
        case_id="case-1",
        family_id="DEMO.POLICY",
        content=content,
        source_path="demo/policy.md",
        owner_id="uploader",
    )
    registry.approve_source(approver, revision)
    return database, registry, uploader, approver, revision, content


def test_upload_metadata_checks_mime_hash_and_current_trusted_scope(tmp_path: Path) -> None:
    database, registry, uploader, _, _, content = _approved_source(tmp_path)
    checked = validate_upload_metadata(
        registry,
        uploader,
        tenant_id="tenant-a",
        case_id="case-1",
        family_id="DEMO.NEW",
        content=content,
        filename="new.md",
        content_type="text/markdown",
        expected_sha256=digest_bytes(content),
        source_path="demo/new.md",
        owner_id="uploader",
    )
    assert checked.content_sha256 == digest_bytes(content)
    assert checked.content_type == "text/markdown"

    with pytest.raises(ValidationFailure):
        validate_upload_metadata(
            registry,
            uploader,
            tenant_id="tenant-a",
            case_id="case-1",
            family_id="DEMO.NEW",
            content=content,
            filename="new.md",
            content_type="text/plain",
            expected_sha256=digest_bytes(content),
            source_path="demo/new.md",
            owner_id="uploader",
        )
    with pytest.raises(ValidationFailure):
        validate_upload_metadata(
            registry,
            uploader,
            tenant_id="tenant-a",
            case_id="case-1",
            family_id="DEMO.NEW",
            content=content,
            filename="new.md",
            content_type="text/markdown",
            expected_sha256="0" * 64,
            source_path="demo/new.md",
            owner_id="uploader",
        )
    database.close()


def test_supersession_scope_requires_approver_and_exact_case_family_scope(tmp_path: Path) -> None:
    database, registry, uploader, approver, revision, _ = _approved_source(tmp_path)
    validate_supersession_scope(
        registry,
        approver,
        predecessor_revision_id=revision,
        successor_tenant_id="tenant-a",
        successor_case_id="case-1",
        successor_family_id="DEMO.POLICY",
        applicability_scope={"tenant_id": "tenant-a", "case_id": "case-1"},
    )
    with pytest.raises(PermissionDenied):
        validate_supersession_scope(
            registry,
            approver,
            predecessor_revision_id=revision,
            successor_tenant_id="tenant-a",
            successor_case_id="case-1",
            successor_family_id="DEMO.POLICY",
            applicability_scope={"tenant_id": "tenant-a", "case_id": "case-other"},
        )
    with pytest.raises(PermissionDenied):
        validate_supersession_scope(
            registry,
            approver,
            predecessor_revision_id=revision,
            successor_tenant_id="tenant-a",
            successor_case_id="case-1",
            successor_family_id="DEMO.UNRELATED",
            applicability_scope={"tenant_id": "tenant-a", "case_id": "case-1"},
        )
    successor = registry.register_source(
        uploader,
        tenant_id="tenant-a",
        case_id="case-1",
        family_id="DEMO.POLICY",
        content=b"# Successor\n\nApproved successor content.\n",
        source_path="demo/policy-successor.md",
        owner_id="uploader",
    )
    with pytest.raises(ValidationFailure):
        registry.approve_source(
            approver,
            successor,
            supersedes_revision_id=revision,
            applicability_scope={"tenant_id": "tenant-a", "case_id": "case-other"},
        )
    assert database.connection.execute(
        "SELECT approval_status FROM document_revisions WHERE revision_id = ?", (successor,)
    ).fetchone()[0] == "DRAFT"
    registry.approve_source(
        approver,
        successor,
        supersedes_revision_id=revision,
        applicability_scope={"tenant_id": "tenant-a", "case_id": "case-1"},
    )
    edge = database.connection.execute(
        "SELECT approved_by, predecessor_revision_id, successor_revision_id "
        "FROM supersession_edges WHERE successor_revision_id = ?",
        (successor,),
    ).fetchone()
    assert tuple(edge) == ("approver", revision, successor)
    database.close()


def test_source_revocation_is_audited_and_cannot_be_resurrected_by_seed(tmp_path: Path) -> None:
    database, registry, uploader, approver, revision, _ = _approved_source(tmp_path)
    registry.revoke_source(approver, revision)
    with pytest.raises(PermissionDenied):
        registry.read_source(uploader, revision)
    with pytest.raises(ResourceConflict):
        registry.approve_source(approver, revision)
    registry.bootstrap_principal(approver)
    assert database.connection.execute(
        "SELECT approval_status FROM document_revisions WHERE revision_id = ?", (revision,)
    ).fetchone()[0] == "REVOKED"
    assert database.connection.execute(
        "SELECT status FROM approval_records WHERE revision_id = ?", (revision,)
    ).fetchone()[0] == "APPROVED"
    assert database.connection.execute(
        "SELECT event_kind FROM audit_events WHERE event_kind = 'SOURCE_REVOKED'"
    ).fetchone()[0] == "SOURCE_REVOKED"
    database.close()
