"""R2 hybrid fusion and R3 reranking over the shared chunks (B04-T02.01, B04-T02.02).

R2 fuses R0's lexical ranking and R1's dense ranking by reciprocal-rank fusion with a pinned constant. Exact
identifiers named in the query are found by the lexical index and reported separately: a fused candidate that holds one
carries ``exact_key_match`` in its metadata, and the notes list every exact-key chunk. R3 reranks the fused top
candidates with Palladion's pinned cross-encoder. Both arms apply the shared access filter before ranking (through the
two underlying arms) and the shared evidence budget after it.

The cross-encoder is English-trained and about 30 percent of queries are Bahasa, so every R3 result carries
``RERANKER_LANGUAGE_NOTE`` in its description (BR23).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

from benchmark.adapters.bm25 import Bm25Arm, identifiers
from benchmark.adapters.common import (
    AdapterError,
    Chunk,
    Condition,
    candidate_from_chunk,
    enforce_budget,
    flags_from_notes,
)
from benchmark.adapters.dense import DenseArm
from benchmark.adapters.eligibility import Eligibility
from benchmark.adapters.models import ModelSpec, verify
from benchmark.contracts import EvidenceCandidate, RetrievalRequest

RRF_K = 60
DEPTH = 50
MAX_RERANK_DEPTH = 30
# Mirrors Palladion's default (its rerank.py, ADR-0109): measured on this arm, 20 found as much as 30.
RERANK_DEPTH = 20
RERANKER_NAME = "Xenova/ms-marco-MiniLM-L-6-v2"
# The same CPU budget as Palladion's reranker (its rerank.py, measured in P11-T05): copied, not imported (BADR-0002).
RERANKER_THREADS = min(4, os.cpu_count() or 2)
RERANK_BATCH = 8
RERANKER_LANGUAGE_NOTE = "English-trained cross-encoder; about 30 percent of queries are Bahasa (BR23)"


def reciprocal_rank_fusion(rankings: Sequence[Sequence[str]], k: int = RRF_K) -> list[tuple[str, float]]:
    """Fuse ranked id lists: each id scores the sum of 1 / (k + rank) over the lists that hold it. Ties order by id."""
    if k < 1:
        raise AdapterError("the fusion constant is at least 1")
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] += 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))


class Reranker(Protocol):
    @property
    def fingerprint(self) -> str: ...

    def rerank(self, query: str, texts: Sequence[str]) -> list[float]: ...


class FastEmbedReranker:
    """The pinned cross-encoder through fastembed, loaded from a local snapshot whose files match their digests."""

    def __init__(self, snapshot: Path, spec: ModelSpec) -> None:
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        verify(snapshot, spec)
        self._model = TextCrossEncoder(
            model_name=RERANKER_NAME,
            specific_model_path=str(snapshot),
            local_files_only=True,
            cuda=False,
            threads=RERANKER_THREADS,
        )
        manifest = {
            "model": RERANKER_NAME,
            "repository": spec.repository,
            "revision": spec.revision,
            "files": dict(spec.digests),
        }
        self._fingerprint = hashlib.sha256(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    @property
    def fingerprint(self) -> str:
        return self._fingerprint

    def rerank(self, query: str, texts: Sequence[str]) -> list[float]:
        scores = [float(s) for s in self._model.rerank(query, list(texts), batch_size=RERANK_BATCH)]
        if len(scores) != len(texts):
            raise AdapterError("the cross-encoder returned a different number of scores than candidates")
        return scores


class HybridArm:
    """The R2 arm: reciprocal-rank fusion of the lexical and dense rankings."""

    arm_id = "R2"

    def __init__(
        self,
        lexical: Bm25Arm,
        dense: DenseArm,
        *,
        rrf_k: int = RRF_K,
        depth: int = DEPTH,
        eligibility: Eligibility | None = None,
    ) -> None:
        if lexical.view is not dense.view and lexical.view.root != dense.view.root:
            raise AdapterError("the lexical and dense arms must read the same published namespace")
        if lexical.condition is not dense.condition or lexical.chunk_words != dense.chunk_words:
            raise AdapterError("the lexical and dense arms must share the metadata condition and chunking")
        if rrf_k < 1 or depth < 1:
            raise AdapterError("the fusion constant and depth are at least 1")
        self.lexical, self.dense = lexical, dense
        self.view = lexical.view
        self.condition: Condition = lexical.condition
        self.rrf_k, self.depth = rrf_k, depth
        self.eligibility = eligibility  # R3f only: the approval, window and supersession rule applied before ranking
        self.last_notes: dict[str, Any] = {}
        self._stats: dict[str, Any] = {}

    def call_flags(self) -> tuple[str, ...]:
        return flags_from_notes(self.last_notes)

    def build_index(self, source_manifest_uri: str, index_namespace: str) -> None:
        started = time.perf_counter()
        self.lexical.build_index(source_manifest_uri, index_namespace)
        self.dense.build_index(source_manifest_uri, index_namespace)
        self._stats = {
            "arm": self.arm_id,
            "lexical": self.lexical.index_stats(),
            "dense": self.dense.index_stats(),
            "rrf_k": self.rrf_k,
            "depth": self.depth,
            "build_ms": (time.perf_counter() - started) * 1000,
        }

    def adopt_built_indexes(self) -> None:
        """Use the lexical and dense indexes that were already built, so arms sharing them do not build them twice."""
        self._stats = {
            "arm": self.arm_id,
            "lexical": self.lexical.index_stats(),
            "dense": self.dense.index_stats(),
            "rrf_k": self.rrf_k,
            "depth": self.depth,
            "build_ms": 0.0,
        }

    def index_stats(self) -> dict[str, Any]:
        return dict(self._stats)

    def describe(self) -> dict[str, Any]:
        described = {
            "arm": self.arm_id,
            "rrf_k": self.rrf_k,
            "depth": self.depth,
            "condition": self.condition.value,
            "lexical": self.lexical.describe(),
            "dense": self.dense.describe(),
        }
        return described if self.eligibility is None else {**described, "eligibility": self.eligibility.describe()}

    def eligible_for(self, request: RetrievalRequest) -> frozenset[str] | None:
        """The documents the request may be answered from, or None when this arm ranks the whole namespace."""
        return None if self.eligibility is None else self.eligibility.documents(request)

    def fused(
        self, query: str, principal_id: str, eligible: frozenset[str] | None = None
    ) -> tuple[list[tuple[Chunk, float]], dict[str, dict[str, int]], list[Chunk]]:
        """Fused (chunk, score) best first, the per-channel ranks of each chunk, and the exact-key chunks."""
        lexical = [s.chunk for s in self.lexical.rank(query, principal_id, eligible)[: self.depth]]
        dense_ids = [chunk_id for chunk_id, _ in self.dense.search(query, principal_id, self.depth, eligible=eligible)]
        by_id = {c.chunk_id: c for c in self.lexical.chunks}
        ranks: dict[str, dict[str, int]] = defaultdict(dict)
        for position, chunk in enumerate(lexical, start=1):
            ranks[chunk.chunk_id]["bm25"] = position
        for position, chunk_id in enumerate(dense_ids, start=1):
            ranks[chunk_id]["dense"] = position
        order = reciprocal_rank_fusion([[c.chunk_id for c in lexical], dense_ids], self.rrf_k)
        exact = self.lexical.chunks_naming(identifiers(query), principal_id, eligible)
        return [(by_id[chunk_id], score) for chunk_id, score in order], dict(ranks), exact

    def retrieve(self, request: RetrievalRequest) -> list[EvidenceCandidate]:
        ranked, ranks, exact = self.fused(request.query, request.principal_id, self.eligible_for(request))
        exact_ids = {c.chunk_id for c in exact}
        candidates = [
            self.candidate(chunk, rank, score, ranks, exact_ids, "hybrid")
            for rank, (chunk, score) in enumerate(ranked[: request.limit], start=1)
        ]
        return self.finish(candidates, request, exact)

    def candidate(
        self, chunk: Chunk, rank: int, score: float, ranks: dict[str, dict[str, int]], exact_ids: set[str], channel: str
    ) -> EvidenceCandidate:
        base = candidate_from_chunk(chunk, self.view.document(chunk.doc_id).record, rank, score, channel)
        meta = {
            **base.additional_metadata,
            "channel_ranks": ranks.get(chunk.chunk_id, {}),
            "exact_key_match": chunk.chunk_id in exact_ids,
        }
        return EvidenceCandidate.from_dict({**base.to_dict(), "additional_metadata": meta})

    def finish(
        self, candidates: list[EvidenceCandidate], request: RetrievalRequest, exact: list[Chunk]
    ) -> list[EvidenceCandidate]:
        bundle = enforce_budget(candidates, request.max_evidence_tokens)
        self.last_notes = {
            "truncated": bundle.truncated,
            "dropped": bundle.dropped,
            "cut_words": bundle.cut_words,
            "words": bundle.words,
            "exact_key_chunks": [c.chunk_id for c in exact],
        }
        return list(bundle.kept)


class RerankedArm:
    """The R3 arm: the fused top candidates reordered by the pinned cross-encoder."""

    def __init__(self, hybrid: HybridArm, reranker: Reranker, *, depth: int = RERANK_DEPTH, arm_id: str = "R3") -> None:
        if not 1 <= depth <= MAX_RERANK_DEPTH:
            raise AdapterError(f"the rerank depth is between 1 and {MAX_RERANK_DEPTH}")
        self.hybrid, self.reranker, self.depth, self.arm_id = hybrid, reranker, depth, arm_id
        self.view = hybrid.view
        self.condition = hybrid.condition

    @property
    def last_notes(self) -> dict[str, Any]:
        """Truncation and exact-key notes of the latest call (the bundle is finished by the shared hybrid code)."""
        return self.hybrid.last_notes

    def call_flags(self) -> tuple[str, ...]:
        return flags_from_notes(self.last_notes)

    def build_index(self, source_manifest_uri: str, index_namespace: str) -> None:
        self.hybrid.build_index(source_manifest_uri, index_namespace)

    def index_stats(self) -> dict[str, Any]:
        return {**self.hybrid.index_stats(), "arm": self.arm_id, "reranker_fingerprint": self.reranker.fingerprint}

    def describe(self) -> dict[str, Any]:
        return {
            "arm": self.arm_id,
            "depth": self.depth,
            "reranker": RERANKER_NAME,
            "reranker_fingerprint": self.reranker.fingerprint,
            "reranker_language_note": RERANKER_LANGUAGE_NOTE,
            "condition": self.condition.value,
            "hybrid": self.hybrid.describe(),
        }

    def retrieve(self, request: RetrievalRequest) -> list[EvidenceCandidate]:
        fused, ranks, exact = self.hybrid.fused(request.query, request.principal_id, self.hybrid.eligible_for(request))
        pool = fused[: self.depth]
        if not pool:
            return self.hybrid.finish([], request, exact)
        scores = self.reranker.rerank(request.query, [chunk.text for chunk, _ in pool])
        order = sorted(range(len(pool)), key=lambda i: (-scores[i], i))
        exact_ids = {c.chunk_id for c in exact}
        candidates = [
            self.hybrid.candidate(pool[i][0], rank, scores[i], ranks, exact_ids, "rerank")
            for rank, i in enumerate(order[: request.limit], start=1)
        ]
        return self.hybrid.finish(candidates, request, exact)
