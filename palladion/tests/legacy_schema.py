"""Helpers that turn a current database into the older one a migration test starts from."""
from __future__ import annotations

import sqlite3


def without_v8(connection: sqlite3.Connection) -> None:
    """A version-7 database had neither chunk heading paths nor alias roles (ADR-0105, 0106): remove them."""
    if "heading_path_json" in {row[1] for row in connection.execute("PRAGMA table_info(p02_chunks)")}:
        connection.execute("ALTER TABLE p02_chunks DROP COLUMN heading_path_json")
    if "defining" in {row[1] for row in connection.execute("PRAGMA table_info(exact_aliases)")}:
        connection.execute("DROP INDEX IF EXISTS exact_alias_order_idx")
        connection.execute("ALTER TABLE exact_aliases DROP COLUMN defining")
    connection.execute("DELETE FROM schema_versions WHERE version=8")
