"""Bounded discovery, exact union, canonical resolution and rechecked expansion."""
from __future__ import annotations

import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Protocol, Sequence

from evidence_agent.core.errors import DependencyUnavailable, PermissionDenied, ResourceConflict
from evidence_agent.core.models import Principal, VersionedModel
from evidence_agent.core.retrieval import Candidate, Chunk, SearchIndex
from evidence_agent.graph.relations import GraphPath
from evidence_agent.retrieval.coverage import Coverage, counted_coverage, source_coverage
from evidence_agent.retrieval.evidence import EvidenceResolver, Passage
from evidence_agent.retrieval.graph_expand import GraphExpansion
from evidence_agent.storage.applicability import Applicability
from evidence_agent.storage.catalog import Catalog
from evidence_agent.storage.exact import ExactIndex
from evidence_agent.telemetry.audit import AuditLog

CONTEXT_SHARE = 4  # at most one slot in four of the limit may hold context rather than a ranked passage (ADR-0104)
CONTEXT_REFERENCES = 4  # linked and adjacent references considered for each ranked passage
CANDIDATE_POOL = 40  # candidates asked of the index before the canonical checks and the rerank
FROZEN_CANDIDATE_LIMIT = 100  # an evaluator's frozen candidate list may not exceed this


@dataclass
class _Exclusions:
    """Why candidates were dropped by the canonical checks; owned by one search and counted only through `record`."""

    not_eligible: int = 0
    integrity_conflict: int = 0

    def record(self, error: PermissionDenied | ResourceConflict) -> None:
        if isinstance(error, ResourceConflict):
            self.integrity_conflict += 1
        else:
            self.not_eligible += 1

    @property
    def total(self) -> int:
        return self.not_eligible + self.integrity_conflict

    def as_dict(self) -> dict[str, int]:
        return {"NOT_ELIGIBLE": self.not_eligible, "INTEGRITY_CONFLICT": self.integrity_conflict}


@dataclass
class _Stopwatch:
    """Wall time per search stage in milliseconds, so a slow stage names itself; owned by one search."""

    stages: dict[str, float] = field(default_factory=dict)

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        started = time.perf_counter()
        try:
            yield
        finally:
            self.stages[name] = self.stages.get(name, 0.0) + (time.perf_counter() - started) * 1000


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
    excluded: dict[str, int] = {}  # candidates dropped by canonical checks, by reason
    unmatched_identifiers: tuple[str, ...] = ()  # code-shaped query tokens with no registered alias
    stage_ms: dict[str, float] = {}  # wall time of each search stage


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
               also_at: Sequence[datetime] = (),
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
        # Validity is judged at the evaluation instant and at each trusted case instant (ADR-0102).
        applicability = Applicability.at(as_of or self.registry.clock(), also_at)
        watch = _Stopwatch()
        warnings: list[str] = []
        candidates: list[tuple[str, str | None]] = []
        eligible: tuple[str, ...] | None = None  # None: no prefilter, from a frozen list or a bounded case
        try:
            if evaluator_candidates is not None and len(evaluator_candidates) > FROZEN_CANDIDATE_LIMIT:
                raise ValueError("Frozen evaluator candidate bound exceeded")
            if evaluator_candidates is not None:
                discovered: Sequence[Candidate] = evaluator_candidates
            else:
                # The index may only offer index generations that can apply, so stale near-duplicates and the leftover points
                # of earlier generations never take a slot (ADR-0103).
                with watch.stage("eligibility"):
                    eligible = self.catalog.eligible_generations(principal, case_id, applicability,
                                                                  fingerprint=self.index.fingerprint)
                if eligible is None:
                    warnings.append("ELIGIBILITY_PREFILTER_BOUNDED")
                elif not eligible:
                    warnings.append("NO_ELIGIBLE_SOURCES")  # nothing could apply, so the index is not asked
                with watch.stage("index"):
                    discovered = () if eligible == () else self.index.query(
                        query, principal, case_id, "hybrid" if mode == "reranked" else mode,
                        limit=CANDIDATE_POOL, generations=eligible)
            candidates.extend((hit.chunk_id, hit.generation) for hit in discovered)
        except DependencyUnavailable:
            warnings.append("INDEX_UNAVAILABLE")
            eligible = None
        with watch.stage("exact"):
            exact = self.exact.hits(principal, case_id, query, eligible)
        if exact.truncated:
            warnings.append("EXACT_CANDIDATES_TRUNCATED")
        # An unknown structured code is labelled, never silently replaced by a near identifier (ADR-0105).
        if exact.unmatched:
            warnings.append("EXACT_IDENTIFIER_NOT_FOUND")
        if exact.unknown_lookup:
            candidates = []  # a bare unknown code asks for that code; similar-looking neighbours would substitute it
        candidates = ([(chunk_id, None) for chunk_id in exact.leading] + candidates
                      + [(chunk_id, None) for chunk_id in exact.trailing])
        resolved: dict[str, Passage] = {}
        exclusions = _Exclusions()
        with watch.stage("resolve"):
            tried: set[tuple[str, str | None]] = set()  # an offer made twice is judged, and counted, once
            for chunk_id, generation in candidates:
                if chunk_id in resolved or (chunk_id, generation) in tried:
                    continue
                tried.add((chunk_id, generation))
                passage = self._release(principal, case_id, chunk_id, applicability, exclusions, generation)
                if passage is not None:
                    resolved[chunk_id] = passage
        ordered = list(resolved.values())
        resolved_count = len(ordered)
        if mode == "reranked":
            if self.ranker is None:
                warnings.append("RERANK_UNAVAILABLE")
            else:
                try:
                    with watch.stage("rerank"):
                        chunks = tuple(self.resolver.chunk(principal, passage)
                                       for passage in ordered[:self.ranker.max_candidates])
                        ordered = [resolved[chunk.chunk_id] for chunk in self.ranker.rank(query, chunks)]
                except DependencyUnavailable:
                    warnings.append("RERANK_UNAVAILABLE")
        selected = ordered[:limit]
        if mode == "reranked":
            with watch.stage("context"):
                selected = self._with_context(principal, case_id, ordered, limit, applicability, exclusions)
        graph_paths: tuple[GraphPath,...] = ()
        if self.graph is not None:
            try:
                with watch.stage("graph"):
                    expansion = self.graph.expand(self.resolver, principal, case_id, tuple(selected),
                                                  applicability=applicability)
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
        with watch.stage("release"):
            selected = [released for released in (
                self._release(principal, case_id, passage.citation_id, applicability, exclusions, passage.generation)
                for passage in selected) if released is not None]
        budget_info = None
        if token_budget is not None:
            from evidence_agent.retrieval.embeddings import PassageTokenizer
            tokenizer = PassageTokenizer(cache_dir=getattr(self.index, "model_cache_dir", None))
            kept: list[Passage] = []
            used = 0
            for passage in selected:
                with watch.stage("budget"):
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
        with watch.stage("coverage"):
            coverage = (source_coverage(self.registry, principal, case_id, self.index, as_of=applicability.primary,
                                        reuse_physical_audit=True) if reuse_physical_audit else
                        counted_coverage(self.registry, principal, case_id, self.index, as_of=applicability.primary))
        warnings.extend(coverage.warnings)
        if exclusions.integrity_conflict:
            warnings.append("INTEGRITY_CONFLICT")
        if not selected and exclusions.total:
            warnings.append("ALL_CANDIDATES_EXCLUDED")
        elapsed = (time.perf_counter() - started) * 1000
        stages = {"discovered": len(candidates), "resolved": resolved_count, "excluded": exclusions.total,
                  "reranked": len(ordered), "expanded": len(selected), "graph_paths":len(graph_paths)}
        trace_id = f"retrieval_{uuid.uuid4().hex}"
        AuditLog(self.registry).append(principal, trace_id, {
            "generations": tuple(sorted({passage.generation for passage in selected})),
            "fingerprint": self.index.fingerprint,
            "mode": mode, "candidate_count": len(candidates), "returned_count": len(selected),
            "excluded_count": exclusions.total, "elapsed_ms": elapsed, "stage_counts": stages,
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
                            evidence_budget=budget_info, excluded=exclusions.as_dict(),
                            unmatched_identifiers=exact.unmatched,
                            stage_ms={name: round(ms, 3) for name, ms in watch.stages.items()})

    def _release(self, principal: Principal, case_id: str, chunk_id: str, applicability: Applicability,
                 exclusions: _Exclusions, generation: str | None = None) -> Passage | None:
        """The passage if the canonical checks release it now; otherwise None, with the reason counted."""
        try:
            return self.resolver.resolve(principal, case_id, chunk_id, generation=generation,
                                         applicability=applicability)
        except (PermissionDenied, ResourceConflict) as error:
            exclusions.record(error)
            return None

    def _with_context(self, principal: Principal, case_id: str, ordered: Sequence[Passage], limit: int,
                      applicability: Applicability, exclusions: _Exclusions) -> list[Passage]:
        """Ranked passages first, then a bounded share of context, never displacing a ranked passage (ADR-0104).

        Context is the exception-linked chunks of the best passages and their same-section neighbours; each is
        resolved independently, so no adjacent payload text is trusted. A reserved slot with no context goes to
        the next ranked passage.
        """
        reserve = limit // CONTEXT_SHARE
        primaries = list(ordered[:limit - reserve])
        taken = {passage.citation_id for passage in primaries}
        context: list[Passage] = []
        for passage in primaries:
            if len(context) >= reserve:
                break
            try:
                chunk = self.resolver.chunk(principal, passage)
                linked = self.catalog.context_links(principal, chunk.chunk_id)
            except PermissionDenied as error:  # revoked since it was ranked
                exclusions.record(error)
                continue
            for neighbor in (*linked, *chunk.neighbor_ids)[:CONTEXT_REFERENCES]:
                if len(context) >= reserve:
                    break
                if neighbor in taken:
                    continue
                try:
                    section_id = self.catalog.get_chunk(principal, neighbor).section_id
                except PermissionDenied as error:
                    exclusions.record(error)
                    continue
                if neighbor not in linked and section_id != passage.section_id:
                    continue  # position alone does not make another section relevant
                item = self._release(principal, case_id, neighbor, applicability, exclusions)
                if item is not None:
                    taken.add(item.citation_id)
                    context.append(item)
        refill = [p for p in ordered[len(primaries):] if p.citation_id not in taken][:reserve - len(context)]
        return primaries + refill + context
