"""Typed extraction of source-linked candidates; no arbitrary model graph writes."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from evidence_agent.core.errors import PermissionDenied
from evidence_agent.core.ids import canonical_entity_key
from evidence_agent.core.retrieval import Chunk
from evidence_agent.graph.registry import GraphRegistry
from evidence_agent.graph.relations import ProjectedRelation, RelationCandidate, projection_digest
from evidence_agent.storage.neo4j import Neo4jIndex


def extract_candidates(
    registry: GraphRegistry, records: Sequence[dict[str, Any]]
) -> tuple[str, ...]:
    """Consume bounded typed extractor output under current scoped-admin authority.

    Explicitly structured source statements may use EXPLICIT_SOURCE; natural-language
    or model-inferred associations must use EXTRACTED_UNREVIEWED. Neither is authority.
    """
    registry.authorize(write=True)
    if len(records) > 128:
        raise ValueError("Relation extraction bound")
    return tuple(registry.relation(RelationCandidate.model_validate(row)) for row in records)


def extract_registered_links(registry: GraphRegistry) -> tuple[str, ...]:
    """Project existing authenticated structural links through the typed producer."""
    registry.authorize(write=True)
    rows = registry.registry.database.connection.execute(
        "SELECT from_chunk_id,to_chunk_id FROM context_links "
        "WHERE tenant_id=? AND case_id=? AND relation='EXCEPTION_TO' ORDER BY from_chunk_id,to_chunk_id LIMIT 129",
        (registry.principal.tenant_id, registry.case_id),
    ).fetchall()
    if len(rows) > 128:
        raise ValueError("Registered graph extraction bound")
    candidates = []
    for row in rows:
        source = registry.chunk(row["from_chunk_id"])
        target = registry.chunk(row["to_chunk_id"])
        source_key = registry.attest(
            source.chunk_id, kind="source_span", display_name=source.section_id[:200]
        )
        target_key = registry.attest(
            target.chunk_id, kind="source_span", display_name=target.section_id[:200]
        )
        candidates.append(
            RelationCandidate(
                from_key=target_key,
                to_key=source_key,
                relation_type="EXCEPTION_TO",
                evidence_chunk_id=target.chunk_id,
                evidence_kind="EXPLICIT_SOURCE",
            ).model_dump(mode="json")
        )
    return extract_candidates(registry, candidates)


@dataclass(frozen=True)
class GraphProjection:
    chunks: tuple[Chunk, ...]
    entities: dict[str, tuple[str, ...]]
    edges: tuple[dict[str, Any], ...]
    manifest: dict[str, str]
    family_id: str

    def publish(self, registry: GraphRegistry, backend: Neo4jIndex, generation: str) -> None:
        registry.authorize(write=True)
        backend.ensure_constraints()
        for chunk in self.chunks:
            source = registry.registry.source_metadata(registry.principal, chunk.revision_id)
            allowed = source["allowed_principal_ids"]
            if not isinstance(allowed, tuple) or any(not isinstance(p, str) for p in allowed):
                raise ValueError("Invalid graph source ACL")
            # Approved registry family identity is attested by the explicit indexing admin.
            registry.attest(
                chunk.chunk_id,
                kind="document_family",
                display_name=self.family_id,
                external_id=self.family_id,
            )
            backend.upsert_chunk(
                chunk.tenant_id,
                chunk.case_id,
                chunk.revision_id,
                generation,
                chunk.chunk_id,
                chunk.content_sha256,
                self.entities[chunk.chunk_id],
                allowed_principal_ids=allowed,
            )
        for edge in self.edges:
            # Re-read the canonical authority after preparation; no stale approvals.
            current = registry.edge(edge["edge_id"])
            if current != edge:
                raise ValueError("Graph relation changed during publication")
            backend.upsert_edge(
                str(edge["tenant_id"]),
                str(edge["case_id"]),
                str(edge["edge_id"]),
                registry.canonical_key(str(edge["from_key"])),
                registry.canonical_key(str(edge["to_key"])),
                str(edge["relation_type"]),
                str(edge["evidence_chunk_id"]),
                str(edge["evidence_kind"]),
                revision=self.chunks[0].revision_id,
                generation=generation,
            )


def prepare_projection(
    registry: GraphRegistry, chunks: Sequence[Chunk], family_id: str
) -> GraphProjection:
    registry.authorize(write=True)
    if not chunks or len(chunks) > 4096:
        raise ValueError("Graph chunk projection bound")
    family_key = canonical_entity_key(
        registry.principal.tenant_id, "source_registry", "document_family", family_id
    )
    entities: dict[str, tuple[str, ...]] = {}
    manifest: dict[str, str] = {}
    for chunk in chunks:
        rows = registry.registry.database.connection.execute(
            "SELECT entity_key FROM graph_entity_attestations "
            "WHERE tenant_id=? AND case_id=? AND evidence_chunk_id=? ORDER BY entity_key LIMIT 33",
            (chunk.tenant_id, chunk.case_id, chunk.chunk_id),
        ).fetchall()
        keys = tuple(sorted({family_key, *(registry.canonical_key(r[0]) for r in rows)}))
        if len(keys) > 32:
            raise ValueError("Graph mention bound")
        for key in keys:
            if key != family_key:
                registry.entity(key)
        entities[chunk.chunk_id] = keys
        manifest["c:" + chunk.chunk_id] = projection_digest([chunk.content_sha256, keys])
    identifiers = {c.chunk_id for c in chunks}
    rows = registry.registry.database.connection.execute(
        "SELECT r.edge_id FROM graph_relations r "
        "JOIN p02_chunks c ON c.chunk_id=r.evidence_chunk_id WHERE r.tenant_id=? AND r.case_id=? "
        "AND c.revision_id=? ORDER BY r.edge_id LIMIT 4097",
        (registry.principal.tenant_id, registry.case_id, chunks[0].revision_id),
    ).fetchall()
    if len(rows) > 4096:
        raise ValueError("Graph edge projection bound")
    edges = []
    for row in rows:
        try:
            edge = registry.edge(row[0])
        except PermissionDenied:
            continue
        if edge["evidence_chunk_id"] not in identifiers:
            raise ValueError("Graph relation source span not in generation")
        edges.append(edge)
        physical = ProjectedRelation.model_validate(
            {
                k: edge[k]
                for k in (
                    "edge_id",
                    "from_key",
                    "to_key",
                    "relation_type",
                    "evidence_chunk_id",
                    "evidence_kind",
                )
            }
        )
        physical = physical.model_copy(
            update={
                "from_key": registry.canonical_key(physical.from_key),
                "to_key": registry.canonical_key(physical.to_key),
            }
        )
        manifest["r:" + edge["edge_id"]] = projection_digest(physical.model_dump(mode="json"))
    return GraphProjection(tuple(chunks), entities, tuple(edges), manifest, family_id)
