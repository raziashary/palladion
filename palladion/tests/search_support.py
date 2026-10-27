"""Shared fixtures for the search tests: a ranked in-memory index and a corpus that drives the real registry,
catalog, ingest pipeline, resolver and exact lane (P11)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from evidence_agent.core.retrieval import Candidate
from evidence_agent.ingest.pipeline import IngestPipeline
from evidence_agent.retrieval.hybrid import HybridSearch
from evidence_agent.retrieval.rerank import FastEmbedReranker
from evidence_agent.storage.exact import ExactIndex

from .test_pipeline import MemoryIndex, _setup


def at(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)


NOW = at("2026-10-18T00:00:00")


class RankedIndex(MemoryIndex):
    """Ranks indexed chunks by shared words with the query; honours the revision filter like the Qdrant index."""

    def __init__(self) -> None:
        super().__init__()
        self.fingerprint = "a" * 64
        self.texts: dict[str, str] = {}
        self.generation_filters: list[object] = []

    def upsert(self, chunks, generation, allowed_principal_ids):  # type: ignore[no-untyped-def]
        """Store the points; a real index filters on `allowed_principal_ids`, this one leaves that to the resolver."""
        assert self.collection_ready and generation
        if chunks:
            self.points.setdefault((chunks[0].revision_id, generation), {}).update(
                {chunk.chunk_id: chunk.content_sha256 for chunk in chunks})
            self.texts.update({chunk.chunk_id: chunk.text for chunk in chunks})

    def query(self, query, principal, case_id, mode="hybrid", limit=20, exact=False, generations=None):  # type: ignore[no-untyped-def]
        self.generation_filters.append(generations)
        words = set(query.casefold().split())
        scored = []
        for (revision, generation), chunks in self.points.items():
            if generations is not None and generation not in generations:
                continue
            for chunk_id in chunks:
                overlap = len(words & set(self.texts[chunk_id].casefold().split()))
                if overlap:
                    scored.append((-overlap, chunk_id, generation))
        return tuple(Candidate(chunk_id=c, generation=g, score=-s, channel="ranked")
                     for s, c, g in sorted(scored)[:limit])


class LeakyIndex(RankedIndex):
    """An index that ignores the generation filter, as a stale one would: the resolver must still be the authority."""

    def query(self, query, principal, case_id, mode="hybrid", limit=20, exact=False, generations=None):  # type: ignore[no-untyped-def]
        return super().query(query, principal, case_id, mode, limit, exact, None)


class Corpus:
    def __init__(self, tmp_path: Path, index: RankedIndex | None = None) -> None:
        self.database, self.registry, self.catalog, self.uploader, first, _ = _setup(tmp_path)
        self.registry.clock = lambda: NOW  # the registry's injected evaluation clock (ADR-0101), not the wall clock
        self.admin = self.registry.access.authenticate("approver")
        self.reader = self.registry.bootstrap_membership(self.registry.bootstrap_principal(
            self.uploader.model_copy(update={"principal_id": "reader-a", "grants": ("source:read", "case:read")})),
            "case-1")
        self.registry.bootstrap_case("tenant-a", "case-2")
        self.uploader = self.registry.bootstrap_membership(self.uploader, "case-2")
        self.admin = self.registry.bootstrap_membership(self.admin, "case-2")
        self.index = index or RankedIndex()
        self.pipeline = IngestPipeline(self.catalog, self.index)
        self.search = HybridSearch(self.catalog, self.index, FastEmbedReranker(enabled=False))
        self.first = first

    def add(self, family: str, text: str, *, valid_from: str | None = None, valid_to: str | None = None,
            supersedes: str | None = None, register_aliases: bool = False, allowed: tuple[str, ...] = (),
            case_id: str = "case-1", index: bool = True) -> str:
        """Register, approve and (unless `index` is false) index one revision, as the owning principals would."""
        revision = self.registry.register_source(
            self.uploader, tenant_id="tenant-a", case_id=case_id, family_id=family, content=text.encode(),
            source_path=f"{family}-{len(self.index.points)}.md", owner_id="uploader",
            allowed_principal_ids=allowed, valid_from=valid_from, valid_to=valid_to)
        scope = {"tenant_id": "tenant-a", "case_id": case_id} if supersedes else None
        self.registry.approve_source(self.admin, revision, supersedes_revision_id=supersedes,
                                     applicability_scope=scope)
        if not index:
            return revision
        self.pipeline.index(self.admin if allowed else self.uploader, revision)  # only a named principal may read it
        if register_aliases:
            ExactIndex(self.catalog).register_approved(self.admin, revision)
        return revision

    def generation_of(self, revision: str) -> str:
        return str(self.catalog.generation_for_revision(self.admin, revision)["generation"])  # type: ignore[index]

    def revisions_of(self, result) -> list[str]:  # type: ignore[no-untyped-def]
        return [p.revision_id for p in result.passages]

    def close(self) -> None:
        self.database.close()
