"""Explicit five-second reuse of complete physical audits, never source authority."""
from __future__ import annotations

import math
import sqlite3
import time
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Iterator

TTL_SECONDS = 5.0
MAX_ENTRIES = 32
MAX_BYTES = 1024 * 1024
_APPLICATION_ID = 0x50414348


@contextmanager
def _open(path: Path) -> Iterator[sqlite3.Connection]:
    if path.exists() and path.stat().st_size > MAX_BYTES:
        raise ValueError("Audit cache exceeds its size bound")
    with closing(sqlite3.connect(path, timeout=0.05, isolation_level=None)) as connection:
        identifier = connection.execute("PRAGMA application_id").fetchone()[0]
        tables = {r[0] for r in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if identifier not in (0, _APPLICATION_ID) or tables - {"audits"} or (tables and identifier == 0):
            raise ValueError("Unrecognized audit cache")
        page_size = connection.execute("PRAGMA page_size").fetchone()[0]
        connection.execute(f"PRAGMA max_page_count={MAX_BYTES // page_size}")
        connection.execute(f"PRAGMA application_id={_APPLICATION_ID}")
        connection.execute("CREATE TABLE IF NOT EXISTS audits "
                           "(key TEXT PRIMARY KEY, wall REAL NOT NULL, monotonic REAL NOT NULL)")
        if connection.execute("SELECT COUNT(*) FROM audits").fetchone()[0] > MAX_ENTRIES:
            raise ValueError("Audit cache exceeds its entry bound")
        yield connection


def is_fresh(wall: float, monotonic: float) -> bool:
    return (all(isinstance(v, (float, int)) and math.isfinite(v) for v in (wall, monotonic))
            and 0 <= time.time() - wall <= TTL_SECONDS
            and 0 <= time.monotonic() - monotonic <= TTL_SECONDS)


def read_audit(path: Path, key: str) -> tuple[float, float] | None:
    """Return the original audit-start timestamp only while both clocks are fresh."""
    with _open(path) as connection:
        row = connection.execute("SELECT wall,monotonic FROM audits WHERE key=?", (key,)).fetchone()
        if row is None:
            return None
        wall, monotonic = row
        if not is_fresh(wall, monotonic):
            return None
        return float(wall), float(monotonic)


def write_audit(path: Path, key: str, wall: float, monotonic: float) -> None:
    """Publish a complete successful audit; reuse never refreshes its original age."""
    if not is_fresh(wall, monotonic):
        return
    with _open(path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute("INSERT OR REPLACE INTO audits VALUES(?,?,?)", (key, wall, monotonic))
            connection.execute("DELETE FROM audits WHERE key NOT IN "
                               "(SELECT key FROM audits ORDER BY wall DESC,key LIMIT ?)", (MAX_ENTRIES,))
            connection.commit()
        except BaseException:
            connection.rollback()
            raise


def invalidate_audits(path: Path) -> None:
    """A newly observed failed fresh audit invalidates prior successes immediately."""
    with _open(path) as connection:
        connection.execute("DELETE FROM audits")
