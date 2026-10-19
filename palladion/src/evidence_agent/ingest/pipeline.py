"""Authenticated, retry-safe source-to-index publication pipeline."""

from __future__ import annotations

import hashlib
from pathlib import PurePath
from typing import TYPE_CHECKING

from evidence_agent.core.errors import PermissionDenied, ResourceConflict
from evidence_agent.core.models import Principal
from evidence_agent.core.retrieval import SearchIndex
from evidence_agent.storage.catalog import Catalog

from .chunking import chunk_blocks
from .parsing import PARSER_VERSION, parse_document

if TYPE_CHECKING:
    from evidence_agent.storage.neo4j import Neo4jIndex


class IngestPipeline:
    """Parse approved originals, upsert Qdrant, and publish after exact readback."""

    def __init__(self, catalog: Catalog, index: SearchIndex, graph: Neo4jIndex | None = None) -> None:
        self.catalog = catalog
        self.registry = catalog.registry
        self._index = index
        self.graph = graph

    def index(self, principal: Principal, revision_id: str) -> str:
        """Index an authorized, approved revision; incomplete attempts remain unavailable."""
        source = self.registry.source_metadata(principal, revision_id)
        if source["approval_status"] != "APPROVED":
            raise PermissionDenied
        content = self.registry.read_source(principal, revision_id)
        source_hash = hashlib.sha256(content).hexdigest()
        if source_hash != source["content_sha256"]:
            raise ResourceConflict
        filename = str(source["source_path"])
        suffix = PurePath(filename.replace("\\", "/")).suffix.lower()
        content_type = "text/markdown" if suffix in {".md", ".markdown"} else "text/plain"
        blocks = parse_document(content, filename=filename, content_type=content_type)
        chunks = chunk_blocks(
            blocks,
            source_bytes=content,
            tenant_id=str(source["tenant_id"]),
            case_id=str(source["case_id"]),
            revision_id=revision_id,
            source_sha256=source_hash,
        )
        projection = None
        if self.graph is not None:
            from evidence_agent.graph.registry import GraphRegistry
            from evidence_agent.ingest.graph_extract import prepare_projection
            projection = prepare_projection(GraphRegistry(self.catalog,principal,str(source["case_id"])),
                                            chunks,str(source["family_id"]))
        generation = self.catalog.stage_generation(
            principal,
            revision_id,
            chunks,
            source_bytes=content,
            fingerprint=self._index.fingerprint,
            parser_version=PARSER_VERSION,
            graph_enabled=self.graph is not None,
            graph_manifest=projection.manifest if projection else None,
        )
        try:
            self._index.ensure_collection()
            allowed_principal_ids = source["allowed_principal_ids"]
            if not isinstance(allowed_principal_ids, tuple) or not all(
                isinstance(principal_id, str) for principal_id in allowed_principal_ids
            ):
                raise ResourceConflict
            self._index.upsert(
                chunks,
                generation,
                allowed_principal_ids,
            )
            readback = self._index.readback(str(source["tenant_id"]), revision_id, generation)
            acknowledged = self.catalog.reconcile(principal, revision_id, generation, readback)
            if self.graph is not None and projection is not None:
                from evidence_agent.graph.registry import GraphRegistry
                projection.publish(GraphRegistry(self.catalog,principal,str(source["case_id"])),
                                   self.graph,generation)
                acknowledged = self.catalog.reconcile(principal,revision_id,generation,
                    self.graph.projection_readback(str(source["tenant_id"]),revision_id,generation),
                    backend="neo4j")
            if not acknowledged:
                raise ResourceConflict
        except Exception:
            self.catalog.mark_failed(principal, revision_id, generation)
            raise
        ready = self.catalog.eligible_generation_metadata(principal, revision_id)
        if ready is None or ready["generation"] != generation or ready["state"] != "READY":
            raise ResourceConflict
        return generation
