"""Bounded discovery, exact union, canonical resolution and rechecked expansion."""
from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Any, Literal, Protocol, Sequence

from evidence_agent.core.errors import DependencyUnavailable, PermissionDenied, ResourceConflict
from evidence_agent.core.models import Principal, VersionedModel
from evidence_agent.core.retrieval import Candidate, Chunk, SearchIndex
from evidence_agent.graph.relations import GraphPath
from evidence_agent.retrieval.coverage import Coverage, source_coverage
from evidence_agent.retrieval.evidence import EvidenceResolver, Passage
from evidence_agent.retrieval.graph_expand import GraphExpansion
from evidence_agent.storage.catalog import Catalog
from evidence_agent.storage.exact import ExactIndex
from evidence_agent.telemetry.audit import AuditLog


class Ranker(Protocol):
    @property
    def max_candidates(self) -> int: ...

    def rank(self, query: str, chunks: Sequence[Chunk]) -> tuple[Chunk, ...]: ...


class SearchResult(VersionedModel):
    trace_id: str
    status: Literal["OK", "DEGRADED", "UNAVAILABLE"]
    mode: str
    passages: tuple[Passage, ...]
    coverage: Coverage
    warnings: tuple[str, ...]
    stage_counts: dict[str, int]
    elapsed_ms: float
    graph_paths: tuple[GraphPath, ...] = ()
    evidence_budget: dict[str, Any] | None = None


class HybridSearch:
    def __init__(self, catalog: Catalog, index: SearchIndex, ranker: Ranker | None = None,
                 graph: GraphExpansion | None = None) -> None:
        self.catalog = catalog
        self.registry = catalog.registry
        self.index = index
        self.resolver = EvidenceResolver(catalog, index.fingerprint)
        self.exact = ExactIndex(catalog)
        self.ranker = ranker
        self.graph = graph

    def search(self, principal: Principal, case_id: str, query: str, *,
               mode: Literal["lexical", "dense", "hybrid", "reranked"] = "hybrid",
               limit: int = 12, as_of: datetime | None = None,
               require_graph: bool = False,
               token_budget: int | None = None,
               reuse_physical_audit: bool = False,
               evaluator_candidates: tuple[Candidate, ...] | None = None) -> SearchResult:
        if not query.strip() or len(query) > 2048 or not 1 <= limit <= 40:
            raise ValueError("Search bounds exceeded")
        if as_of is not None and (as_of.tzinfo is None or as_of.utcoffset() is None):
            raise ValueError("Document cutoff must be timezone-aware")
        if token_budget is not None and not 1 <= token_budget <= 65536:
            raise ValueError("Token budget bounds exceeded")
        self.registry.access.authorize(principal, tenant_id=principal.tenant_id,
                                       case_id=case_id, grant="source:read")
        started = time.perf_counter()
        warnings: list[str] = []
        candidates: list[tuple[str, str | None]] = []
        try:
            if evaluator_candidates is not None and len(evaluator_candidates)>100:
                raise ValueError("Frozen evaluator candidate bound exceeded")
            discovered = (evaluator_candidates if evaluator_candidates is not None else
                self.index.query(query, principal, case_id,
                                 "hybrid" if mode == "reranked" else mode, limit=40))
            candidates.extend((hit.chunk_id, hit.generation) for hit in discovered)
        except DependencyUnavailable:
            warnings.append("INDEX_UNAVAILABLE")
        exact_ids = self.exact.lookup(principal, case_id, query)
        if self.exact.truncated:
            warnings.append("EXACT_CANDIDATES_TRUNCATED")
        # A recognized but unknown structured code cannot silently return a near identifier.
        if self.exact.identifiers(query) and not exact_ids:
            warnings.append("EXACT_IDENTIFIER_NOT_FOUND")
            candidates = []
        candidates = [(chunk_id, None) for chunk_id in exact_ids] + candidates
        resolved: dict[str, Passage] = {}
        excluded = 0
        for chunk_id, generation in candidates:
            if chunk_id in resolved:
                continue
            try:
                resolved[chunk_id] = self.resolver.resolve(principal, case_id, chunk_id,
                                                         generation=generation, as_of=as_of)
            except (PermissionDenied, ResourceConflict):
                excluded += 1
        ordered = list(resolved.values())
        resolved_count = len(ordered)
        if mode == "reranked":
            if self.ranker is None:
                warnings.append("RERANK_UNAVAILABLE")
            else:
                try:
                    chunks = tuple(self.resolver.chunk(principal, passage) for passage in ordered[:self.ranker.max_candidates])
                    ordered = [resolved[chunk.chunk_id] for chunk in self.ranker.rank(query, chunks)]
                except DependencyUnavailable:
                    warnings.append("RERANK_UNAVAILABLE")
        selected = ordered[:limit]
        # Every expanded reference is independently resolved; no adjacent payload text is trusted.
        if mode == "reranked":
            expanded: dict[str, Passage] = {}
            for passage in selected:
                expanded[passage.citation_id] = passage
                chunk = self.resolver.chunk(principal, passage)
                neighbors = self.catalog.context_links(principal, chunk.chunk_id) + chunk.neighbor_ids
                for neighbor in neighbors[:4]:
                    if len(expanded) >= limit:
                        break
                    try:
                        item = self.resolver.resolve(principal, case_id, neighbor, as_of=as_of)
                        expanded[item.citation_id] = item
                    except (PermissionDenied, ResourceConflict):
                        excluded += 1
            selected = list(expanded.values())[:limit]
        graph_paths: tuple[GraphPath,...] = ()
        if self.graph is not None:
            try:
                expansion=self.graph.expand(self.resolver,principal,case_id,tuple(selected),as_of=as_of)
                # Preserve the primary anchor; source-linked neighbors get the next slots.
                # This explicit treatment ordering is measured against unchanged B2.
                combined=selected[:1]+list(expansion.passages)+selected[1:]
                selected=list({p.citation_id:p for p in combined}.values())[:limit]
                returned={p.citation_id for p in selected}
                graph_paths=tuple(p for p in expansion.paths if p.target_chunk_id in returned)
                if expansion.bounded:
                    warnings.append("GRAPH_BOUNDED")
            except (DependencyUnavailable,PermissionDenied,ResourceConflict):
                warnings.append("GRAPH_UNAVAILABLE")
        elif require_graph:
            warnings.append("GRAPH_UNAVAILABLE")
        if require_graph and "GRAPH_UNAVAILABLE" in warnings:
            warnings.append("GRAPH_REQUIRED_UNAVAILABLE")
        # Recheck again at release, including references fetched before a mid-request revocation.
        selected = [self.resolver.resolve(principal, case_id, p.citation_id,
                                         generation=p.generation, as_of=as_of) for p in selected]
        budget_info = None
        if token_budget is not None:
            from evidence_agent.retrieval.embeddings import PassageTokenizer
            tokenizer = PassageTokenizer(cache_dir=getattr(self.index, "model_cache_dir", None))
            kept: list[Passage] = []
            used = 0
            for passage in selected:
                count = tokenizer.count("\n\n".join(p.text for p in (*kept, passage)))
                if count > token_budget:
                    break  # Ranked prefix only; never rewrite canonical text/spans.
                kept.append(passage)
                used = count
            budget_info = {"limit_tokens": token_budget, "used_tokens": used,
                "requested_limit": limit, "available_passages": len(selected),
                "returned_passages": len(kept), "truncated": len(kept) < len(selected),
                "tokenizer": tokenizer.manifest, "separator": "\n\n", "special_tokens": False}
            selected = kept
            returned = {p.citation_id for p in selected}
            graph_paths = tuple(p for p in graph_paths if p.target_chunk_id in returned
                and set(p.evidence_ids).issubset(returned))
        coverage = source_coverage(self.registry, principal, case_id, self.index, as_of=as_of,
                                   reuse_physical_audit=reuse_physical_audit)
        warnings.extend(coverage.warnings)
        elapsed = (time.perf_counter() - started) * 1000
        stages = {"discovered": len(candidates), "resolved": resolved_count,
                  "reranked": len(ordered), "expanded": len(selected), "graph_paths":len(graph_paths)}
        trace_id = f"retrieval_{uuid.uuid4().hex}"
        AuditLog(self.registry).append(principal, trace_id, {
            "generations": tuple(sorted({passage.generation for passage in selected})),
            "fingerprint": self.index.fingerprint,
            "mode": mode, "candidate_count": len(candidates), "returned_count": len(selected),
            "excluded_count": excluded, "elapsed_ms": elapsed, "stage_counts": stages,
            "failure": "INDEX_UNAVAILABLE" if "INDEX_UNAVAILABLE" in warnings else
                       "RERANK_UNAVAILABLE" if "RERANK_UNAVAILABLE" in warnings else
                       "GRAPH_UNAVAILABLE" if "GRAPH_UNAVAILABLE" in warnings else "NONE",
            "index_coverage": coverage.index_coverage,
        })
        status: Literal["OK", "DEGRADED", "UNAVAILABLE"] = "OK"
        if warnings:
            status = "UNAVAILABLE" if (not selected and "INDEX_UNAVAILABLE" in warnings or
                                        "GRAPH_REQUIRED_UNAVAILABLE" in warnings) else "DEGRADED"
        return SearchResult(trace_id=trace_id, status=status, mode=mode, passages=tuple(selected),
                            coverage=coverage, warnings=tuple(dict.fromkeys(warnings)),
                            stage_counts=stages, elapsed_ms=elapsed,graph_paths=graph_paths,
                            evidence_budget=budget_info)
