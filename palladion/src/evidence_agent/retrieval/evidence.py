"""Canonical authorization, publication, time and original-byte citation reader."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from evidence_agent.core.errors import PermissionDenied, ResourceConflict
from evidence_agent.core.models import Principal, VersionedModel
from evidence_agent.core.retrieval import Chunk
from evidence_agent.storage.catalog import Catalog


class Passage(VersionedModel):
    citation_id: str
    revision_id: str
    generation: str
    section_id: str
    start_byte: int
    end_byte: int
    line_start: int
    line_end: int
    text: str
    sha256: str


class EvidenceResolver:
    def __init__(self, catalog: Catalog, fingerprint: str) -> None:
        self.catalog = catalog
        self.registry = catalog.registry
        self.fingerprint = fingerprint

    def resolve(self, principal: Principal, case_id: str, chunk_id: str, *,
                generation: str | None = None, as_of: datetime | None = None) -> Passage:
        chunk = self.catalog.get_chunk(principal, chunk_id)
        if chunk.case_id != case_id:
            raise PermissionDenied
        instant = as_of or datetime.now(timezone.utc)
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError("Source applicability requires an aware instant")
        # One SQLite transaction holds source/ACL/version metadata stable through byte read.
        with self.registry.database.transaction() as connection:
            self.registry.access.authorize(principal, tenant_id=chunk.tenant_id,
                                           case_id=case_id, grant="source:read")
            row = connection.execute("SELECT * FROM document_revisions WHERE tenant_id=? "
                                     "AND revision_id=?", (chunk.tenant_id, chunk.revision_id)).fetchone()
            if row is None or row["approval_status"] != "APPROVED" or row["index_state"] != "READY":
                raise PermissionDenied
            metadata = self.catalog.eligible_generation_metadata(principal, chunk.revision_id)
            if (metadata is None or metadata.get("state") != "READY" or
                    metadata.get("fingerprint") != self.fingerprint):
                raise PermissionDenied
            if generation is not None and row["index_generation"] != generation:
                raise PermissionDenied
            for field, lower in (("valid_from", True), ("valid_to", False)):
                if row[field] is not None:
                    boundary = datetime.fromisoformat(row[field])
                    if (lower and instant < boundary) or (not lower and instant >= boundary):
                        raise PermissionDenied
            approval = connection.execute("SELECT status FROM approval_records WHERE "
                                          "approval_record_id=? AND tenant_id=? AND revision_id=?",
                                          (row["approval_record_id"], chunk.tenant_id,
                                           chunk.revision_id)).fetchone()
            if approval is None or approval["status"] != "APPROVED":
                raise PermissionDenied
            acl = json.loads(row["acl_json"])
            if acl.get("allowed_principal_ids") and principal.principal_id not in acl["allowed_principal_ids"]:
                raise PermissionDenied
            for edge in connection.execute("SELECT applicability_scope_json,valid_from FROM "
                                           "supersession_edges WHERE tenant_id=? AND "
                                           "predecessor_revision_id=?", (chunk.tenant_id, chunk.revision_id)):
                scope = json.loads(edge[0])
                if scope.get("case_id") == case_id and datetime.fromisoformat(edge[1]) <= instant:
                    raise PermissionDenied
            original = self.registry.originals.read(row["content_sha256"])
            text_bytes = original[chunk.start_byte:chunk.end_byte]
            if (chunk.end_byte > len(original) or not text_bytes or
                    hashlib.sha256(text_bytes).hexdigest() != chunk.content_sha256 or
                    hashlib.sha256(original).hexdigest() != chunk.source_sha256):
                raise ResourceConflict
        return Passage(citation_id=chunk.chunk_id, revision_id=chunk.revision_id,
                       generation=str(row["index_generation"]), section_id=chunk.section_id,
                       start_byte=chunk.start_byte, end_byte=chunk.end_byte,
                       line_start=chunk.line_start, line_end=chunk.line_end,
                       text=text_bytes.decode("utf-8"), sha256=chunk.content_sha256)

    def chunk(self, principal: Principal, passage: Passage) -> Chunk:
        return self.catalog.get_chunk(principal, passage.citation_id)
