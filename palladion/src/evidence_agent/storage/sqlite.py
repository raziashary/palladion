"""SQLite connection ownership and forward-only, transactional schema upgrades."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
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
    SCHEMA_VERSION = 2

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._connection: sqlite3.Connection | None = None

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
            self._preflight_schema()
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

    def _apply_migration(self, current: int, target: int) -> None:
        if (current, target) != (1, 2):
            raise DatabaseSchemaError(f"no forward migration from version {current} to {target}")
        with self.transaction() as connection:
            self._migration_1_to_2(connection)
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


def utc_now() -> str:
    """Return fixed-precision UTC ISO-8601 text suitable for lexical ordering."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


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
