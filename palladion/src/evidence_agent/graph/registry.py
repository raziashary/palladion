"""Canonical scoped graph attestations, candidates, reviews and immutable merge audit."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import Any

from evidence_agent.core.errors import PermissionDenied, ResourceConflict
from evidence_agent.core.ids import canonical_entity_key, provisional_entity_key
from evidence_agent.core.models import Principal
from evidence_agent.core.retrieval import Chunk
from evidence_agent.graph.relations import RelationCandidate
from evidence_agent.storage.catalog import Catalog
from evidence_agent.storage.sqlite import utc_now


class GraphRegistry:
    def __init__(self, catalog: Catalog, principal: Principal, case_id: str) -> None:
        self.catalog, self.registry = catalog, catalog.registry
        self.principal, self.case_id = principal, case_id

    def authorize(self, *, write: bool = False) -> None:
        self.registry.access.authorize(
            self.principal,
            tenant_id=self.principal.tenant_id,
            case_id=self.case_id,
            grant="document:approve" if write else "source:read",
            role="admin" if write else None,
        )

    def _invalidate_projection(self, db: Any, chunk_ids: tuple[str, ...]) -> None:
        for identifier in set(chunk_ids):
            row = db.execute(
                "SELECT revision_id FROM p02_chunks WHERE chunk_id=? AND tenant_id=? AND case_id=?",
                (identifier, self.principal.tenant_id, self.case_id),
            ).fetchone()
            if row is not None:
                db.execute(
                    "UPDATE index_generations SET state='INDEXING',ready_at=NULL WHERE tenant_id=? "
                    "AND revision_id=? AND graph_enabled=1 AND state='READY'",
                    (self.principal.tenant_id, row[0]),
                )
                db.execute(
                    "UPDATE document_revisions SET index_state='INDEXING' WHERE tenant_id=? "
                    "AND revision_id=? AND index_generation IN (SELECT generation FROM index_generations "
                    "WHERE tenant_id=? AND revision_id=? AND graph_enabled=1 AND state='INDEXING')",
                    (self.principal.tenant_id, row[0], self.principal.tenant_id, row[0]),
                )

    def chunk(self, identifier: str) -> Chunk:
        self.authorize()
        chunk = self.catalog.get_chunk(self.principal, identifier)
        if chunk.case_id != self.case_id:
            raise PermissionDenied
        # Catalog owns current source approval/ACL; OriginalStore owns byte hashes.
        # Composing these readers also works inside an atomic merge transaction.
        original = self.registry.originals.read(chunk.source_sha256)
        if (
            hashlib.sha256(original[chunk.start_byte : chunk.end_byte]).hexdigest()
            != chunk.content_sha256
        ):
            raise ResourceConflict
        return chunk

    def attest(
        self,
        chunk_id: str,
        *,
        kind: str,
        display_name: str,
        external_id: str | None = None,
        source_system: str = "source_registry",
    ) -> str:
        self.authorize(write=True)
        chunk = self.chunk(chunk_id)
        if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,80}", kind) or not re.fullmatch(
            r"[a-zA-Z0-9_.-]{1,80}", source_system
        ):
            raise ValueError("Invalid namespace")
        if (
            not display_name
            or len(display_name) > 200
            or external_id is not None
            and not 1 <= len(external_id) <= 200
        ):
            raise ValueError("Invalid identity attributes")
        key = (
            canonical_entity_key(chunk.tenant_id, source_system, kind, external_id)
            if external_id
            else (
                provisional_entity_key(
                    chunk.tenant_id, chunk.revision_id, chunk.start_byte, chunk.end_byte
                )
            )
        )
        with self.registry.database.transaction() as db:
            self.authorize(write=True)
            self.chunk(chunk_id)
            cursor = db.execute(
                "INSERT OR IGNORE INTO graph_entity_attestations VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "att_" + uuid.uuid4().hex,
                    chunk.tenant_id,
                    self.case_id,
                    key,
                    source_system,
                    kind,
                    external_id,
                    "VERIFIED" if external_id else "PROVISIONAL",
                    display_name,
                    chunk_id,
                    self.principal.principal_id,
                    utc_now(),
                ),
            )
            if cursor.rowcount:
                self._invalidate_projection(db, (chunk_id,))
        return key

    def entity(self, key: str) -> tuple[dict[str, Any], ...]:
        self.authorize()
        rows = self.registry.database.connection.execute(
            "SELECT * FROM graph_entity_attestations WHERE tenant_id=? AND case_id=? AND entity_key=? LIMIT 129",
            (self.principal.tenant_id, self.case_id, key),
        ).fetchall()
        if not rows or len(rows) > 128:
            raise PermissionDenied
        # All origin proofs are necessary: a merge cannot launder private provenance.
        for row in rows:
            self.chunk(row["evidence_chunk_id"])
        return tuple(dict(row) for row in rows)

    def relation(self, candidate: RelationCandidate) -> str:
        self.authorize(write=True)
        self.entity(candidate.from_key)
        self.entity(candidate.to_key)
        self.chunk(candidate.evidence_chunk_id)
        edge_id = (
            "edge_"
            + hashlib.sha256(
                json.dumps(
                    [self.principal.tenant_id, self.case_id, candidate.model_dump(mode="json")],
                    sort_keys=True,
                ).encode()
            ).hexdigest()
        )
        with self.registry.database.transaction() as db:
            self.authorize(write=True)
            self.entity(candidate.from_key)
            self.entity(candidate.to_key)
            self.chunk(candidate.evidence_chunk_id)
            cursor = db.execute(
                "INSERT OR IGNORE INTO graph_relations VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    edge_id,
                    self.principal.tenant_id,
                    self.case_id,
                    candidate.from_key,
                    candidate.to_key,
                    candidate.relation_type,
                    candidate.evidence_chunk_id,
                    candidate.evidence_kind,
                    self.principal.principal_id,
                    utc_now(),
                ),
            )
            if cursor.rowcount:
                self._invalidate_projection(db, (candidate.evidence_chunk_id,))
        return edge_id

    def keys_for_chunk(self, identifier: str) -> tuple[str, ...]:
        self.chunk(identifier)
        rows = self.registry.database.connection.execute(
            "SELECT entity_key FROM graph_entity_attestations "
            "WHERE tenant_id=? AND case_id=? AND evidence_chunk_id=? ORDER BY entity_key LIMIT 33",
            (self.principal.tenant_id, self.case_id, identifier),
        ).fetchall()
        if len(rows) > 32:
            raise ValueError("Entity mention bound")
        keys = tuple(r[0] for r in rows)
        for key in keys:
            self.entity(key)
        return tuple(sorted({*keys, *(self.canonical_key(key) for key in keys)}))

    def canonical_key(self, key: str) -> str:
        return self.resolve_identity(key)[0]

    def resolve_identity(self, key: str) -> tuple[str, tuple[str, ...]]:
        seen: set[str] = set()
        proofs: set[str] = set()
        for _ in range(8):
            if key in seen:
                raise ValueError("Cyclic identity equivalence")
            seen.add(key)
            proofs.update(row["evidence_chunk_id"] for row in self.entity(key))
            row = self.registry.database.connection.execute(
                "SELECT to_key,evidence_chunk_id FROM graph_merge_decisions "
                "WHERE tenant_id=? AND case_id=? AND from_key=? AND decision='ACCEPTED' "
                "ORDER BY occurred_at DESC,decision_id DESC LIMIT 1",
                (self.principal.tenant_id, self.case_id, key),
            ).fetchone()
            if row is None:
                return key, tuple(sorted(proofs))
            self.chunk(row["evidence_chunk_id"])
            proofs.add(row["evidence_chunk_id"])
            key = row["to_key"]
        raise ValueError("Identity equivalence depth exceeded")

    def edge(self, identifier: str, *, include_rejected: bool = False) -> dict[str, Any]:
        self.authorize()
        row = self.registry.database.connection.execute(
            "SELECT * FROM graph_relations WHERE edge_id=? AND tenant_id=? AND case_id=?",
            (identifier, self.principal.tenant_id, self.case_id),
        ).fetchone()
        if row is None:
            raise PermissionDenied
        self.entity(row["from_key"])
        self.entity(row["to_key"])
        self.chunk(row["evidence_chunk_id"])
        result = dict(row)
        review = self.registry.database.connection.execute(
            "SELECT decision,reviewer_id FROM graph_relation_reviews WHERE edge_id=? ORDER BY occurred_at DESC,review_id DESC LIMIT 1",
            (identifier,),
        ).fetchone()
        if review:
            result["evidence_kind"] = review["decision"]
        if result["evidence_kind"] == "REJECTED" and not include_rejected:
            raise PermissionDenied
        return result

    def review(self, edge_id: str, *, accepted: bool, reason: str) -> str:
        self.authorize(write=True)
        self.edge(edge_id, include_rejected=True)
        if not 1 <= len(reason) <= 512:
            raise ValueError("Review reason required")
        identifier = "grev_" + uuid.uuid4().hex
        with self.registry.database.transaction() as db:
            self.authorize(write=True)
            self.edge(edge_id, include_rejected=True)
            db.execute(
                "INSERT INTO graph_relation_reviews VALUES(?,?,?,?,?,?)",
                (
                    identifier,
                    edge_id,
                    "HUMAN_VERIFIED" if accepted else "REJECTED",
                    self.principal.principal_id,
                    reason,
                    utc_now(),
                ),
            )
            row = db.execute(
                "SELECT evidence_chunk_id FROM graph_relations WHERE edge_id=?", (edge_id,)
            ).fetchone()
            self._invalidate_projection(db, (row[0],))
        return identifier

    def merge(
        self, from_key: str, to_key: str, *, evidence_chunk_id: str, accepted: bool, reason: str
    ) -> str:
        self.authorize(write=True)
        self.entity(from_key)
        self.entity(to_key)
        self.chunk(evidence_chunk_id)
        if from_key == to_key or not 1 <= len(reason) <= 512:
            raise ValueError("Distinct identities and explicit equivalence reason required")
        identifier = "merge_" + uuid.uuid4().hex
        with self.registry.database.transaction() as db:
            self.authorize(write=True)
            self.entity(from_key)
            self.entity(to_key)
            self.chunk(evidence_chunk_id)
            if accepted and self.canonical_key(to_key) == from_key:
                raise ValueError("Cyclic identity equivalence")
            if accepted:
                # The reader permits eight visited identities. Reject a new edge
                # before committing if it would create a chain the reader cannot open.
                target = to_key
                for _ in range(7):
                    next_row = db.execute(
                        "SELECT to_key FROM graph_merge_decisions WHERE tenant_id=? AND case_id=? "
                        "AND from_key=? AND decision='ACCEPTED' ORDER BY occurred_at DESC,decision_id DESC LIMIT 1",
                        (self.principal.tenant_id,self.case_id,target)).fetchone()
                    if next_row is None:
                        break
                    target = next_row[0]
                else:
                    raise ValueError("Identity equivalence depth exceeded")
            db.execute(
                "INSERT INTO graph_merge_decisions VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    identifier,
                    self.principal.tenant_id,
                    self.case_id,
                    from_key,
                    to_key,
                    "ACCEPTED" if accepted else "REJECTED",
                    evidence_chunk_id,
                    self.principal.principal_id,
                    reason,
                    utc_now(),
                ),
            )
            if accepted:
                proofs = tuple(
                    r["evidence_chunk_id"] for key in (from_key, to_key) for r in self.entity(key)
                )
                self._invalidate_projection(db, (*proofs, evidence_chunk_id))
        return identifier

    def merge_history(self, key: str) -> tuple[dict[str, Any], ...]:
        self.entity(key)
        rows = self.registry.database.connection.execute(
            "SELECT * FROM graph_merge_decisions "
            "WHERE tenant_id=? AND case_id=? AND (from_key=? OR to_key=?) ORDER BY occurred_at,decision_id LIMIT 129",
            (self.principal.tenant_id, self.case_id, key, key),
        ).fetchall()
        if len(rows) > 128:
            raise ValueError("Merge audit exceeds bounded reader")
        for row in rows:
            self.entity(row["from_key"])
            self.entity(row["to_key"])
            self.chunk(row["evidence_chunk_id"])
        return tuple(dict(row) for row in rows)
