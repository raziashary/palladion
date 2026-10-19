"""Explicitly enabled derived sqlite-vec memory experiment; canonical readers own access."""
from __future__ import annotations

import hashlib
import math
import sqlite3
from pathlib import Path
from typing import Any

import sqlite_vec  # type: ignore[import-untyped]  # Packaged extension has no typing marker.

from evidence_agent.core.errors import PermissionDenied, ResourceConflict
from evidence_agent.memory.store import MemoryStore
from evidence_agent.retrieval.embeddings import DenseEncoder


class VectorMemory:
    """A bounded exact cosine sidecar, not an ANN or another memory authority store.

    The extension supplies vector arithmetic. At most 512 owner-scoped candidates are
    inspected; every candidate is revalidated before content reaches the caller. No
    automatic rebuild, deletion, or canonical registry migration is performed.
    """
    def __init__(self, path: Path, encoder: DenseEncoder, *, enabled: bool = False) -> None:
        if not enabled:
            raise PermissionError("Explicit vector-memory experiment enablement required")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.encoder = encoder
        self.connection = sqlite3.connect(path)
        application_id = self.connection.execute("PRAGMA application_id").fetchone()[0]
        tables = self.connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        if (tables and application_id != 0x50303856) or application_id not in {0,0x50303856}:
            self.connection.close()
            raise ValueError("Refusing to modify an unrecognized vector sidecar")
        try:
            self.connection.enable_load_extension(True)
            sqlite_vec.load(self.connection)
        except Exception:
            self.connection.close()
            raise
        finally:
            # Loading arbitrary extensions is never exposed to model/user input.
            try:
                self.connection.enable_load_extension(False)
            except sqlite3.ProgrammingError:
                pass  # Connection was closed on an extension-load failure.
        self.connection.execute("CREATE TABLE IF NOT EXISTS memory_vectors ("
            "memory_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, owner_id TEXT NOT NULL, "
            "fingerprint TEXT NOT NULL, content_sha256 TEXT NOT NULL, embedding BLOB NOT NULL)")
        self.connection.execute("PRAGMA application_id=1345337430")
        self.connection.commit()
        self.last_candidate_count = 0
        self.last_truncated = False

    def _vector(self, text: str, *, query: bool = False) -> bytes:
        vectors = [self.encoder.embed_query(text)] if query else self.encoder.embed_documents((text,))
        if len(vectors) != 1 or len(vectors[0]) != self.encoder.dimension or any(
                not math.isfinite(value) or abs(value)>3.4e38 for value in vectors[0]) or not any(vectors[0]):
            raise ValueError("Invalid pinned memory embedding")
        return bytes(sqlite_vec.serialize_float32(vectors[0]))

    def index(self, memory: MemoryStore, identifiers: tuple[str, ...]) -> int:
        if not 1 <= len(identifiers) <= 64 or len(set(identifiers)) != len(identifiers):
            raise ValueError("Bounded unique memory IDs required")
        memory.case.authorize()
        principal = memory.case.principal
        rows = []
        for identifier in identifiers:
            record = memory.read(identifier)
            # Initial experiment is private owner memory; wider sharing is not inferred.
            if record["owner_id"] != principal.principal_id or record["scope_kind"] != "USER":
                raise PermissionDenied
            text = record["content"]
            if len(text) > 4096:
                raise ValueError("Memory embedding text bound exceeded")
            rows.append((identifier,principal.tenant_id,principal.principal_id,
                         self.encoder.fingerprint,hashlib.sha256(text.encode()).hexdigest(),
                         self._vector(text)))
        with self.connection:
            self.connection.executemany("INSERT INTO memory_vectors VALUES(?,?,?,?,?,?) "
                "ON CONFLICT(memory_id) DO UPDATE SET fingerprint=excluded.fingerprint, "
                "content_sha256=excluded.content_sha256,embedding=excluded.embedding",rows)
        for row in rows:
            actual = self.connection.execute("SELECT fingerprint,content_sha256,embedding "
                "FROM memory_vectors WHERE memory_id=?",(row[0],)).fetchone()
            if actual != (row[3],row[4],row[5]):
                raise ResourceConflict
        return len(rows)

    def recall(self, memory: MemoryStore, query: str, *, limit: int = 8) -> list[dict[str, Any]]:
        if not query.strip() or len(query)>256 or not 1<=limit<=20:
            raise ValueError("Vector recall bounds exceeded")
        memory.case.authorize()
        principal = memory.case.principal
        # Scope before candidate window; distance is computed only after canonical read.
        rows = self.connection.execute("SELECT memory_id,content_sha256,embedding FROM "
            "memory_vectors WHERE tenant_id=? AND owner_id=? AND fingerprint=? "
            "ORDER BY memory_id LIMIT 513",(principal.tenant_id,principal.principal_id,
                                           self.encoder.fingerprint)).fetchall()
        self.last_candidate_count = min(len(rows),512)
        self.last_truncated = len(rows)>512
        vector = self._vector(query,query=True)
        scored = []
        for identifier, digest, embedding in rows[:512]:
            try:
                record = memory.read(identifier)
            except (PermissionDenied,ResourceConflict):
                continue
            if record["owner_id"] != principal.principal_id or record["scope_kind"] != "USER":
                continue
            if hashlib.sha256(record["content"].encode()).hexdigest()!=digest:
                continue
            distance = self.connection.execute("SELECT vec_distance_cosine(?,?)",
                                                (embedding,vector)).fetchone()[0]
            if distance is not None and math.isfinite(distance):
                scored.append((float(distance),identifier,record))
        return [record for _,_,record in sorted(scored,key=lambda item:(item[0],item[1]))[:limit]]

    def close(self) -> None:
        self.connection.close()
