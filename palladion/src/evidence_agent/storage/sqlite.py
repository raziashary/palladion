"""SQLite connection ownership and forward-only, transactional schema upgrades."""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


class DatabaseSchemaError(RuntimeError):
    """The database is foreign, incomplete, newer, or cannot be upgraded safely."""


class Database:
    """Own one SQLite connection and initialize only recognized Palladion schemas.

    Use as ``with Database(path) as database`` or call ``open()`` and ``close()``.
    Opening an uninitialized file creates the current schema. Existing recognized
    schemas are upgraded in forward-only transactions; unknown schemas are rejected
    and never reset. ``connection`` is available only while open.
    """

    APPLICATION_ID = 0x50414C4C  # ASCII "PALL"
    SCHEMA_VERSION = 8

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._connection: sqlite3.Connection | None = None
        self.backup_path: Path | None = None

    @property
    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise RuntimeError("database is closed; call open() first")
        return self._connection

    def open(self) -> Database:
        """Open and initialize/upgrade the database, returning this owner."""
        if self._connection is not None:
            return self
        if self.path != ":memory:":
            Path(self.path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, isolation_level=None)
        connection.row_factory = sqlite3.Row
        self._connection = connection
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
                raise DatabaseSchemaError("SQLite foreign key enforcement is unavailable")
            previous = self._preflight_schema()
            if self.path != ":memory:" and 0 < previous < self.SCHEMA_VERSION:
                # Preserve the exact old persistent state before any forward schema mutation.
                backup_path = Path(self.path).with_name(Path(self.path).name + ".pre-v" +
                    str(self.SCHEMA_VERSION) + "-" + uuid.uuid4().hex + ".sqlite")
                with backup_path.open("xb"):
                    pass
                with closing(sqlite3.connect(backup_path)) as backup:
                    connection.backup(backup)
                    if backup.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise DatabaseSchemaError("Pre-migration backup integrity check failed")
                self.backup_path = backup_path
            journal = connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]
            if self.path != ":memory:" and str(journal).lower() != "wal":
                raise DatabaseSchemaError("SQLite WAL mode could not be enabled")
            self._initialize_or_upgrade()
        except BaseException:
            self.close()
            raise
        return self

    def close(self) -> None:
        """Close the owned connection; safe to call more than once."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def __enter__(self) -> Database:
        return self.open()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Run a write transaction with immediate lock acquisition and rollback."""
        connection = self.connection
        if connection.in_transaction:
            raise RuntimeError("nested database transactions are not supported")
        connection.execute("BEGIN IMMEDIATE")
        try:
            yield connection
        except BaseException:
            connection.rollback()
            raise
        else:
            connection.commit()

    @contextmanager
    def read_transaction(self) -> Iterator[sqlite3.Connection]:
        """Read one stable snapshot without taking the write lock, so readers never queue behind writers."""
        connection = self.connection
        if connection.in_transaction:
            raise RuntimeError("nested database transactions are not supported")
        connection.execute("BEGIN")
        try:
            yield connection
        finally:
            connection.rollback()

    def _initialize_or_upgrade(self) -> None:
        user_version = self._preflight_schema()
        if user_version == 0:
            self._create_fresh_schema()
            user_version = self.SCHEMA_VERSION

        while user_version < self.SCHEMA_VERSION:
            next_version = user_version + 1
            self._apply_migration(user_version, next_version)
            user_version = next_version
        self._validate_schema_shape(user_version)

    def _preflight_schema(self) -> int:
        """Reject unrecognized files before WAL or schema pragmas can mutate them."""
        connection = self.connection
        user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        application_id = int(connection.execute("PRAGMA application_id").fetchone()[0])
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }

        if user_version == 0:
            if application_id != 0 or tables:
                raise DatabaseSchemaError("refusing to initialize a non-empty or foreign database")
            return 0

        if application_id != self.APPLICATION_ID:
            raise DatabaseSchemaError("database application_id does not identify Palladion")

        if user_version > self.SCHEMA_VERSION:
            raise DatabaseSchemaError(
                f"database schema version {user_version} is newer than supported version "
                f"{self.SCHEMA_VERSION}"
            )
        if user_version < 1:
            raise DatabaseSchemaError(f"unsupported database schema version {user_version}")
        self._validate_schema_shape(user_version)
        return user_version

    def _create_fresh_schema(self) -> None:
        schema_path = Path(__file__).with_name("schema.sql")
        statements = _read_sql_statements(schema_path.read_text(encoding="utf-8"))
        with self.transaction() as connection:
            if int(connection.execute("PRAGMA user_version").fetchone()[0]) != 0:
                return  # another opener created the schema between our check and this write lock
            connection.execute(f"PRAGMA application_id = {self.APPLICATION_ID}")
            for statement in statements:
                connection.execute(statement)
            connection.execute(
                "INSERT INTO schema_versions(version, applied_at) VALUES (?, ?)",
                (1, utc_now()),
            )
            connection.execute("PRAGMA user_version = 1")
            self._migration_1_to_2(connection)
            connection.execute(
                "INSERT INTO schema_versions(version, applied_at) VALUES (?, ?)",
                (2, utc_now()),
            )
            connection.execute("PRAGMA user_version = 2")
            self._migration_2_to_3(connection)
            connection.execute(
                "INSERT INTO schema_versions(version, applied_at) VALUES (?, ?)",
                (3, utc_now()),
            )
            connection.execute("PRAGMA user_version = 3")
            self._migration_3_to_4(connection)
            connection.execute("INSERT INTO schema_versions VALUES (?, ?)", (4, utc_now()))
            connection.execute("PRAGMA user_version = 4")
            self._migration_4_to_5(connection)
            connection.execute("INSERT INTO schema_versions VALUES (?, ?)", (5, utc_now()))
            connection.execute("PRAGMA user_version = 5")
            self._migration_5_to_6(connection)
            connection.execute("INSERT INTO schema_versions VALUES (?, ?)", (6, utc_now()))
            connection.execute("PRAGMA user_version = 6")
            self._migration_6_to_7(connection)
            connection.execute("INSERT INTO schema_versions VALUES (?, ?)", (7, utc_now()))
            connection.execute("PRAGMA user_version = 7")
            self._migration_7_to_8(connection)
            connection.execute("INSERT INTO schema_versions VALUES (?, ?)", (8, utc_now()))
            connection.execute("PRAGMA user_version = 8")

    def _apply_migration(self, current: int, target: int) -> None:
        if (current, target) not in {(1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (7, 8)}:
            raise DatabaseSchemaError(f"no forward migration from version {current} to {target}")
        with self.transaction() as connection:
            if int(connection.execute("PRAGMA user_version").fetchone()[0]) != current:
                return  # another opener already applied this step
            if (current, target) == (1, 2):
                self._migration_1_to_2(connection)
            elif target == 3:
                self._migration_2_to_3(connection)
            elif target == 4:
                self._migration_3_to_4(connection)
            elif target == 5:
                self._migration_4_to_5(connection)
            elif target == 6:
                self._migration_5_to_6(connection)
            elif target == 7:
                self._migration_6_to_7(connection)
            else:
                self._migration_7_to_8(connection)
            connection.execute(
                "INSERT INTO schema_versions(version, applied_at) VALUES (?, ?)",
                (target, utc_now()),
            )
            connection.execute(f"PRAGMA user_version = {target}")

    @staticmethod
    def _migration_1_to_2(connection: sqlite3.Connection) -> None:
        connection.execute(
            "CREATE INDEX case_events_scope_idx "
            "ON case_events(tenant_id, case_id, occurred_at)"
        )

    @staticmethod
    def _migration_2_to_3(connection: sqlite3.Connection) -> None:
        """Add P02's generation catalog without altering the published P01 tables."""
        statements = (
            """CREATE TABLE p02_chunks (
                chunk_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                revision_id TEXT NOT NULL,
                case_id TEXT NOT NULL,
                section_id TEXT NOT NULL,
                start_byte INTEGER NOT NULL CHECK (start_byte >= 0),
                end_byte INTEGER NOT NULL CHECK (end_byte > start_byte),
                line_start INTEGER NOT NULL CHECK (line_start > 0),
                line_end INTEGER NOT NULL CHECK (line_end >= line_start),
                text TEXT NOT NULL,
                content_sha256 TEXT NOT NULL CHECK (
                    length(content_sha256) = 64 AND content_sha256 NOT GLOB '*[^0-9a-f]*'
                ),
                source_sha256 TEXT NOT NULL CHECK (
                    length(source_sha256) = 64 AND source_sha256 NOT GLOB '*[^0-9a-f]*'
                ),
                parent_id TEXT,
                neighbor_ids_json TEXT NOT NULL,
                parser_version TEXT NOT NULL,
                UNIQUE (tenant_id, revision_id, start_byte, end_byte),
                FOREIGN KEY (tenant_id, revision_id)
                    REFERENCES document_revisions(tenant_id, revision_id)
            )""",
            """CREATE TABLE index_generations (
                tenant_id TEXT NOT NULL,
                revision_id TEXT NOT NULL,
                generation TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                parser_version TEXT NOT NULL,
                graph_enabled INTEGER NOT NULL CHECK (graph_enabled IN (0, 1)),
                required_backends_json TEXT NOT NULL,
                state TEXT NOT NULL CHECK (state IN ('INDEXING', 'READY', 'FAILED')),
                expected_count INTEGER NOT NULL CHECK (expected_count >= 0),
                expected_manifest_sha256 TEXT NOT NULL CHECK (
                    length(expected_manifest_sha256) = 64 AND
                    expected_manifest_sha256 NOT GLOB '*[^0-9a-f]*'
                ),
                created_at TEXT NOT NULL,
                ready_at TEXT,
                PRIMARY KEY (tenant_id, revision_id, generation),
                FOREIGN KEY (tenant_id, revision_id)
                    REFERENCES document_revisions(tenant_id, revision_id)
            )""",
            """CREATE TABLE index_generation_chunks (
                tenant_id TEXT NOT NULL,
                revision_id TEXT NOT NULL,
                generation TEXT NOT NULL,
                chunk_id TEXT NOT NULL REFERENCES p02_chunks(chunk_id),
                content_sha256 TEXT NOT NULL CHECK (
                    length(content_sha256) = 64 AND content_sha256 NOT GLOB '*[^0-9a-f]*'
                ),
                PRIMARY KEY (tenant_id, revision_id, generation, chunk_id),
                FOREIGN KEY (tenant_id, revision_id, generation)
                    REFERENCES index_generations(tenant_id, revision_id, generation)
            )""",
            """CREATE TABLE index_backend_manifests (
                tenant_id TEXT NOT NULL,
                revision_id TEXT NOT NULL,
                generation TEXT NOT NULL,
                backend TEXT NOT NULL,
                expected_count INTEGER NOT NULL CHECK (expected_count >= 0),
                expected_manifest_sha256 TEXT NOT NULL CHECK (
                    length(expected_manifest_sha256) = 64 AND
                    expected_manifest_sha256 NOT GLOB '*[^0-9a-f]*'
                ),
                confirmed_count INTEGER NOT NULL CHECK (confirmed_count >= 0),
                confirmed_manifest_sha256 TEXT NOT NULL CHECK (
                    length(confirmed_manifest_sha256) = 64 AND
                    confirmed_manifest_sha256 NOT GLOB '*[^0-9a-f]*'
                ),
                acknowledged_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, revision_id, generation, backend),
                FOREIGN KEY (tenant_id, revision_id, generation)
                    REFERENCES index_generations(tenant_id, revision_id, generation)
            )""",
            """CREATE TABLE exact_aliases (
                tenant_id TEXT NOT NULL,
                case_id TEXT NOT NULL,
                normalized_alias TEXT NOT NULL,
                alias TEXT NOT NULL,
                revision_id TEXT NOT NULL,
                chunk_id TEXT NOT NULL REFERENCES p02_chunks(chunk_id),
                PRIMARY KEY (tenant_id, case_id, normalized_alias, revision_id, chunk_id),
                FOREIGN KEY (tenant_id, case_id) REFERENCES cases(tenant_id, case_id),
                FOREIGN KEY (tenant_id, revision_id)
                    REFERENCES document_revisions(tenant_id, revision_id)
            )""",
            """CREATE TABLE context_links (
                tenant_id TEXT NOT NULL,
                case_id TEXT NOT NULL,
                from_chunk_id TEXT NOT NULL REFERENCES p02_chunks(chunk_id),
                to_chunk_id TEXT NOT NULL REFERENCES p02_chunks(chunk_id),
                relation TEXT NOT NULL CHECK (relation = 'EXCEPTION_TO'),
                actor_id TEXT NOT NULL REFERENCES principals(principal_id),
                created_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, from_chunk_id, to_chunk_id, relation),
                FOREIGN KEY (tenant_id, case_id) REFERENCES cases(tenant_id, case_id),
                CHECK (from_chunk_id <> to_chunk_id)
            )""",
            "CREATE INDEX p02_chunks_revision_idx ON p02_chunks(tenant_id, revision_id, start_byte)",
            "CREATE INDEX exact_alias_lookup_idx ON exact_aliases(tenant_id, case_id, normalized_alias)",
            "CREATE INDEX context_links_from_idx ON context_links(tenant_id, case_id, from_chunk_id)",
        )
        for statement in statements:
            connection.execute(statement)

    @staticmethod
    def _migration_3_to_4(connection: sqlite3.Connection) -> None:
        script = Path(__file__).with_name("memory_schema.sql").read_text(encoding="utf-8")
        for statement in _read_sql_statements(script):
            connection.execute(statement)

    @staticmethod
    def _migration_4_to_5(connection: sqlite3.Connection) -> None:
        script = Path(__file__).with_name("graph_schema.sql").read_text(encoding="utf-8")
        for statement in _read_sql_statements(script):
            connection.execute(statement)

    @staticmethod
    def _migration_5_to_6(connection: sqlite3.Connection) -> None:
        script = Path(__file__).with_name("promotion_schema.sql").read_text(encoding="utf-8")
        for statement in _read_sql_statements(script):
            connection.execute(statement)

    @staticmethod
    def _migration_6_to_7(connection: sqlite3.Connection) -> None:
        script = Path(__file__).with_name("extraction_schema.sql").read_text(encoding="utf-8")
        for statement in _read_sql_statements(script):
            connection.execute(statement)

    @staticmethod
    def _migration_7_to_8(connection: sqlite3.Connection) -> None:
        """Chunks keep their heading path, and an alias records whether it names its own revision (ADR-0105, 0106).

        Existing chunks get an empty path. Their generations were indexed without that context; the search
        representation fingerprint changed with it, so they are not served until indexed again. Existing aliases
        are classified here with the same normalisation (strip, casefold) the catalog applies when it writes one.
        """
        connection.execute("ALTER TABLE p02_chunks ADD COLUMN heading_path_json TEXT NOT NULL DEFAULT '[]'")
        connection.execute(
            "ALTER TABLE exact_aliases ADD COLUMN defining INTEGER NOT NULL DEFAULT 0 CHECK (defining IN (0, 1))")
        names = connection.execute(
            "SELECT aliases.rowid, aliases.normalized_alias, revisions.family_id, revisions.revision_id "
            "FROM exact_aliases AS aliases JOIN document_revisions AS revisions "
            "ON revisions.tenant_id = aliases.tenant_id AND revisions.revision_id = aliases.revision_id").fetchall()
        for rowid, key, family_id, revision_id in names:
            if key in (family_id.strip().casefold(), revision_id.strip().casefold()):
                connection.execute("UPDATE exact_aliases SET defining = 1 WHERE rowid = ?", (rowid,))
        connection.execute(
            "CREATE INDEX exact_alias_order_idx ON exact_aliases(tenant_id, case_id, normalized_alias, defining)")

    def _validate_schema_shape(self, version: int) -> None:
        expected = {
            "schema_versions",
            "tenants",
            "principals",
            "principal_roles",
            "principal_grants",
            "cases",
            "case_memberships",
            "document_families",
            "document_revisions",
            "approval_records",
            "supersession_edges",
            "chunks",
            "policy_versions",
            "policy_source_clauses",
            "case_events",
            "memory_entries",
            "index_manifest",
            "audit_events",
        }
        actual = {
            row[0]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        if not expected.issubset(actual):
            missing = ", ".join(sorted(expected - actual))
            raise DatabaseSchemaError(f"Palladion schema is incomplete; missing tables: {missing}")
        recorded = {
            int(row[0]) for row in self.connection.execute("SELECT version FROM schema_versions")
        }
        if recorded != set(range(1, version + 1)):
            raise DatabaseSchemaError("schema_versions does not match PRAGMA user_version")
        if version >= 2:
            indexes = {
                row[0]
                for row in self.connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'index'"
                )
            }
            if "case_events_scope_idx" not in indexes:
                raise DatabaseSchemaError("Palladion schema version 2 is missing its migration index")
        if version >= 3:
            p02_tables = {
                "p02_chunks",
                "index_generations",
                "index_generation_chunks",
                "index_backend_manifests",
                "exact_aliases",
                "context_links",
            }
            if not p02_tables.issubset(actual):
                missing = ", ".join(sorted(p02_tables - actual))
                raise DatabaseSchemaError(f"Palladion schema version 3 is missing tables: {missing}")
        if version >= 4:
            if not {"memory_provenance", "memory_teams", "memory_team_memberships", "memory_fts"}.issubset(actual):
                raise DatabaseSchemaError("Palladion schema version 4 is missing memory tables")
        if version >= 5:
            if not {"index_graph_expectations", "graph_entity_attestations", "graph_relations", "graph_relation_reviews",
                    "graph_merge_decisions"}.issubset(actual):
                raise DatabaseSchemaError("Palladion schema version 5 is missing graph tables")
        if version >= 6 and not {"memory_sessions","memory_event_sessions","memory_event_chunks",
                "memory_promotion_decisions","memory_promotion_links"}.issubset(actual):
            raise DatabaseSchemaError("Palladion schema version 6 is missing promotion tables")
        if version >= 7 and "source_extractions" not in actual:
            raise DatabaseSchemaError("Palladion schema version 7 is missing extraction provenance")
        if version >= 8 and (
            "heading_path_json" not in {row[1] for row in self.connection.execute("PRAGMA table_info(p02_chunks)")}
            or "defining" not in {row[1] for row in self.connection.execute("PRAGMA table_info(exact_aliases)")}
        ):
            raise DatabaseSchemaError("Palladion schema version 8 is missing chunk heading paths or alias roles")



def iso_stamp(moment: datetime) -> str:
    """Fixed-precision UTC ISO-8601 text of an instant, suitable for lexical ordering."""
    return moment.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def utc_now() -> str:
    """The wall clock as fixed-precision UTC ISO-8601 text."""
    return iso_stamp(datetime.now(timezone.utc))


def _read_sql_statements(script: str) -> list[str]:
    statements: list[str] = []
    pending = ""
    for line in script.splitlines():
        pending += line + "\n"
        if sqlite3.complete_statement(pending):
            statement = pending.strip()
            if statement:
                statements.append(statement)
            pending = ""
    if pending.strip():
        raise DatabaseSchemaError("schema.sql contains an incomplete SQL statement")
    return statements
