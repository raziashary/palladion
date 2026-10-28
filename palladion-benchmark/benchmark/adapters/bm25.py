"""R0: lexical Okapi BM25 over the shared chunks (B04-T01.01).

A standard-library implementation, so the scores can be checked by hand. Identifiers such as ``MS-4021`` or
``POL-020@v2`` are kept as whole tokens beside their parts, so an exact error-code query matches the clause that
names it. The index is built over every chunk of the published namespace; the neutral access filter and the evidence
budget come from the shared harness and are applied identically for every arm.
"""

from __future__ import annotations

import math
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from benchmark.adapters.common import (
    DEFAULT_CHUNK_WORDS,
    AccessFilter,
    AdapterError,
    Chunk,
    Condition,
    PublishedView,
    build_chunks,
    candidate_from_chunk,
    enforce_budget,
    flags_from_notes,
)
from benchmark.contracts import EvidenceCandidate, RetrievalRequest

K1 = 1.2
B = 0.75
CHANNEL = "bm25"
_WORD = re.compile(r"[^\W_]+")
IDENTIFIER = re.compile(r"[A-Za-z]{2,}(?:-[A-Za-z0-9]+)+(?:@v\d+)?")


def _identifier_matches(text: str) -> list[str]:
    """Hyphenated codes and versioned ids that hold a digit (``MS-4021``, ``POL-020@v2``); plain compounds do not."""
    return [m for m in IDENTIFIER.findall(text) if any(ch.isdigit() for ch in m)]


def tokenize(text: str) -> list[str]:
    """Case-folded words plus whole identifiers (a hyphenated code with digits or a versioned id)."""
    return [w.casefold() for w in _WORD.findall(text)] + [m.casefold() for m in _identifier_matches(text)]


def identifiers(text: str) -> list[str]:
    """The whole identifiers in a text, case-folded, in order of appearance without repeats."""
    seen: dict[str, None] = {}
    for match in _identifier_matches(text):
        seen.setdefault(match.casefold(), None)
    return list(seen)


@dataclass(frozen=True)
class Scored:
    chunk: Chunk
    score: float


class Bm25Arm:
    """The R0 arm. ``view`` is the published namespace; ``condition`` is C2 (filter on) or C1 (filter off)."""

    arm_id = "R0"

    def __init__(
        self,
        view: PublishedView,
        condition: Condition = Condition.C2,
        chunk_words: int = DEFAULT_CHUNK_WORDS,
        k1: float = K1,
        b: float = B,
    ) -> None:
        if k1 <= 0 or not 0 <= b <= 1:
            raise AdapterError("BM25 needs k1 > 0 and 0 <= b <= 1")
        self.view = view
        self.condition = condition
        self.chunk_words = chunk_words
        self.k1, self.b = k1, b
        self.access = AccessFilter(view, condition)
        self._chunks: list[Chunk] = []
        self._postings: dict[str, dict[int, int]] = {}
        self._lengths: list[int] = []
        self._average = 0.0
        self._stats: dict[str, Any] = {}
        self.last_notes: dict[str, Any] = {}

    # -- the adapter surface ---------------------------------------------------------------------

    def build_index(self, source_manifest_uri: str, index_namespace: str) -> None:
        if Path(source_manifest_uri).resolve() != self.view.root.resolve():
            raise AdapterError("the index is built from the published directory this arm was created with")
        started = time.perf_counter()
        self._chunks = build_chunks(self.view, self.chunk_words)
        postings: dict[str, dict[int, int]] = defaultdict(dict)
        self._lengths = []
        for index, chunk in enumerate(self._chunks):
            tokens = tokenize(chunk.text)
            self._lengths.append(len(tokens))
            for term, count in Counter(tokens).items():
                postings[term][index] = count
        self._postings = dict(postings)
        self._average = sum(self._lengths) / len(self._lengths) if self._lengths else 0.0
        self._stats = {
            "arm": self.arm_id,
            "namespace": index_namespace,
            "documents": len(self.view.records),
            "chunks": len(self._chunks),
            "words": sum(chunk.words for chunk in self._chunks),
            "characters": sum(chunk.characters for chunk in self._chunks),
            "terms": len(self._postings),
            "chunk_words": self.chunk_words,
            "k1": self.k1,
            "b": self.b,
            "condition": self.condition.value,
            "build_ms": (time.perf_counter() - started) * 1000,
        }

    def index_stats(self) -> dict[str, Any]:
        return dict(self._stats)

    def describe(self) -> dict[str, Any]:
        """Settings that define this arm's behaviour, for the run manifest."""
        return {
            "arm": self.arm_id,
            "k1": self.k1,
            "b": self.b,
            "chunk_words": self.chunk_words,
            "condition": self.condition.value,
        }

    def retrieve(self, request: RetrievalRequest) -> list[EvidenceCandidate]:
        ranked = self.rank(request.query, request.principal_id)[: request.limit]
        candidates = [
            candidate_from_chunk(s.chunk, self.view.document(s.chunk.doc_id).record, rank, s.score, CHANNEL)
            for rank, s in enumerate(ranked, start=1)
        ]
        bundle = enforce_budget(candidates, request.max_evidence_tokens)
        self.last_notes = {
            "truncated": bundle.truncated,
            "dropped": bundle.dropped,
            "cut_words": bundle.cut_words,
            "words": bundle.words,
        }
        return list(bundle.kept)

    @property
    def chunks(self) -> list[Chunk]:
        return list(self._chunks)

    def call_flags(self) -> tuple[str, ...]:
        return flags_from_notes(self.last_notes)

    # -- ranking ---------------------------------------------------------------------------------

    def idf(self, term: str) -> float:
        n = len(self._postings.get(term, ()))
        return math.log(1 + (len(self._chunks) - n + 0.5) / (n + 0.5))

    def score(self, index: int, query_terms: Counter[str]) -> float:
        length = self._lengths[index]
        norm = self.k1 * (1 - self.b + self.b * length / self._average) if self._average else self.k1
        total = 0.0
        for term, weight in query_terms.items():
            frequency = self._postings.get(term, {}).get(index, 0)
            if frequency:
                total += weight * self.idf(term) * frequency * (self.k1 + 1) / (frequency + norm)
        return total

    def rank(self, query: str, principal_id: str, eligible: frozenset[str] | None = None) -> list[Scored]:
        """Every chunk with a positive score for a document the principal may see (and, when the arm applies an
        eligibility rule, that the rule admits), best first; ties by chunk id."""
        if not self._chunks:
            raise AdapterError("build_index must run before retrieve")
        query_terms = Counter(tokenize(query))
        candidates: set[int] = set()
        for term in query_terms:
            candidates.update(self._postings.get(term, ()))
        scored = [
            Scored(self._chunks[i], self.score(i, query_terms))
            for i in candidates
            if self.access.allows(principal_id, self._chunks[i].doc_id)
            and (eligible is None or self._chunks[i].doc_id in eligible)
        ]
        scored.sort(key=lambda s: (-s.score, s.chunk.chunk_id))
        return [s for s in scored if s.score > 0]

    def chunks_naming(
        self, identifier_tokens: list[str], principal_id: str, eligible: frozenset[str] | None = None
    ) -> list[Chunk]:
        """Chunks that contain any of the whole identifiers, in index order, for documents the principal may see."""
        found: dict[int, None] = {}
        for token in identifier_tokens:
            for index in self._postings.get(token, ()):
                if self.access.allows(principal_id, self._chunks[index].doc_id) and (
                    eligible is None or self._chunks[index].doc_id in eligible
                ):
                    found.setdefault(index, None)
        return [self._chunks[i] for i in sorted(found)]
