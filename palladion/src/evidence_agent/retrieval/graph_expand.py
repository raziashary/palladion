"""Bounded graph navigation with canonical authorization of every path proof."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

from evidence_agent.core.errors import DependencyUnavailable, PermissionDenied, ResourceConflict
from evidence_agent.core.models import Principal
from evidence_agent.graph.registry import GraphRegistry
from evidence_agent.graph.relations import GraphPath, TraversalLimits
from evidence_agent.retrieval.evidence import EvidenceResolver, Passage
from evidence_agent.storage.applicability import Applicability
from evidence_agent.storage.neo4j import Neo4jIndex


@dataclass(frozen=True)
class Expansion:
    passages: tuple[Passage, ...]
    paths: tuple[GraphPath, ...]
    bounded: bool


class GraphExpansion:
    def __init__(self, backend: Neo4jIndex, limits: TraversalLimits | None = None) -> None:
        self.backend, self.limits = backend, limits or TraversalLimits()

    def expand(
        self,
        resolver: EvidenceResolver,
        principal: Principal,
        case_id: str,
        anchors: tuple[Passage, ...],
        *,
        applicability: Applicability | None = None,
    ) -> Expansion:
        control = GraphRegistry(resolver.catalog, principal, case_id)
        control.authorize()
        started = time.monotonic()
        frontier: list[tuple[Passage, tuple[str, ...]]] = [
            (p, ()) for p in anchors[: min(12, self.limits.nodes)]
        ]
        seen_nodes = {p.citation_id for p, _ in frontier}
        seen_edges: set[str] = set()
        admitted: dict[str, Passage] = {}
        paths: list[GraphPath] = []
        bounded = len(frontier) < len(anchors)
        fanout_reached = False
        for _ in range(self.limits.hops):
            next_frontier: list[tuple[Passage, tuple[str, ...]]] = []
            for anchor, prior in frontier:
                metadata=resolver.catalog.eligible_generation_metadata(principal,anchor.revision_id)
                if metadata is None or not metadata["graph_enabled"] or metadata["generation"]!=anchor.generation:
                    raise DependencyUnavailable("Graph projection is not published for this anchor")
                if time.monotonic() - started >= self.limits.timeout_seconds:
                    raise DependencyUnavailable("Graph traversal deadline exceeded")
                rows = self.backend.neighbors(
                    principal.tenant_id,
                    case_id,
                    (anchor.citation_id,),
                    fanout=self.limits.fanout,
                    principal_id=principal.principal_id,
                    timeout_seconds=max(
                        0.001, self.limits.timeout_seconds - (time.monotonic() - started)
                    ),
                )
                fanout_reached |= len(rows) >= self.limits.fanout
                if time.monotonic() - started >= self.limits.timeout_seconds:
                    raise DependencyUnavailable("Graph traversal deadline exceeded")
                for row in rows:
                    edge_id, identifier = row.get("edge_id"), row.get("chunk_id")
                    if (
                        not isinstance(edge_id, str)
                        or not isinstance(identifier, str)
                        or max(len(edge_id), len(identifier)) > 100
                    ):
                        raise DependencyUnavailable("Invalid graph projection reference")
                    if identifier == anchor.citation_id or edge_id in seen_edges:
                        continue
                    previously_seen = identifier in seen_nodes
                    if len(seen_edges) >= self.limits.edges or len(seen_nodes) >= self.limits.nodes:
                        bounded = True
                        break
                    seen_edges.add(edge_id)
                    try:
                        current_edge = control.edge(edge_id)
                        from_key = control.canonical_key(current_edge["from_key"])
                        to_key = control.canonical_key(current_edge["to_key"])
                        origin_keys = control.keys_for_chunk(anchor.citation_id)
                        target_keys = control.keys_for_chunk(identifier)
                        if not (
                            (from_key in origin_keys and to_key in target_keys)
                            or (to_key in origin_keys and from_key in target_keys)
                        ):
                            continue
                        chain = (*prior, edge_id)
                        evidence = {anchor.citation_id, identifier}
                        unreviewed = False
                        for link in chain:
                            edge = control.edge(link)
                            evidence.add(edge["evidence_chunk_id"])
                            for key in (edge["from_key"], edge["to_key"]):
                                evidence.update(control.resolve_identity(key)[1])
                            unreviewed |= edge["evidence_kind"] == "EXTRACTED_UNREVIEWED"
                        if len(evidence) > 12:
                            bounded = True
                            continue
                        # No Neo4j payload text or inferred assertion enters evidence.
                        for proof in evidence:
                            resolver.resolve(principal, case_id, proof, applicability=applicability)
                        passage = resolver.resolve(
                            principal,
                            case_id,
                            identifier,
                            generation=row.get("generation"),
                            applicability=applicability,
                        )
                    except (PermissionDenied, ResourceConflict):
                        continue
                    paths.append(
                        GraphPath(
                            path_id="path_"
                            + hashlib.sha256(("|".join(chain) + identifier).encode()).hexdigest(),
                            edge_ids=chain,
                            evidence_ids=tuple(sorted(evidence)),
                            includes_unreviewed=unreviewed,
                            target_chunk_id=identifier,
                        )
                    )
                    if not previously_seen:
                        seen_nodes.add(identifier)
                        admitted[identifier] = passage
                        next_frontier.append((passage, chain))
                if bounded:
                    break
            frontier = next_frontier
            if not frontier or bounded:
                break
        # Revalidate again after traversal, including any mid-request ACL tightening.
        for path in paths:
            for identifier in path.evidence_ids:
                resolver.resolve(principal, case_id, identifier, applicability=applicability)
        if time.monotonic() - started >= self.limits.timeout_seconds:
            raise DependencyUnavailable("Graph traversal deadline exceeded")
        return Expansion(tuple(admitted.values()), tuple(paths), bounded or fanout_reached)
