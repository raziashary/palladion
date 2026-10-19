"""R1: dense retrieval over the shared chunks with Palladion's pinned embedding model (B04-T01.02, OQ04).

Chunks are embedded with the pinned multilingual MiniLM model (revision and file digests verified on every load) and
stored in a Qdrant HNSW collection on the benchmark's own server (127.0.0.1:17333, never Palladion's). Access control is
applied inside the search as a payload filter, so the neutral filter acts before ranking as it does for every arm.
Approximate search is checked against Qdrant's exact search on the same collection: ``ann_recall`` reports the
measured overlap instead of assuming the index is lossless.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    HnswConfigDiff,
    MatchAny,
    PointStruct,
    SearchParams,
    VectorParams,
)

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
from benchmark.adapters.models import ModelSpec, verify
from benchmark.contracts import EvidenceCandidate, RetrievalRequest

CHANNEL = "dense"
DEFAULT_URL = "http://127.0.0.1:17333"
PALLADION_PORTS = frozenset({16333, 16334})
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DIMENSION = 384
THREADS = 2
HNSW_M = 16
HNSW_EF_CONSTRUCT = 100
HNSW_EF_SEARCH = 64
UPSERT_BATCH = 256
EMBED_BATCH = 32
ANN_SAMPLE = 25  # queries for the approximate-versus-exact check at build time
ANN_QUERY_CHARACTERS = 200
TIE_MARGIN = 10  # extra hits requested so that equal scores at the cut are ordered by chunk id, not by the graph
SCORE_DIGITS = 6


class Encoder(Protocol):
    """What the arm needs from an embedding model: document and query vectors and a fingerprint of the model."""

    @property
    def fingerprint(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class FastEmbedEncoder:
    """The pinned model through fastembed, loaded from a local snapshot whose files match their digests."""

    def __init__(self, snapshot: Path, spec: ModelSpec) -> None:
        from fastembed import TextEmbedding

        verify(snapshot, spec)
        self._spec = spec
        self._model = TextEmbedding(
            model_name=MODEL_NAME,
            specific_model_path=str(snapshot),
            local_files_only=True,
            cuda=False,
            threads=THREADS,
        )
        manifest = {
            "model": MODEL_NAME,
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

    @property
    def dimension(self) -> int:
        return DIMENSION

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._model.embed(list(texts), batch_size=EMBED_BATCH, parallel=None)]

    def embed_query(self, text: str) -> list[float]:
        return next(vector.tolist() for vector in self._model.query_embed(text))


def ensure_benchmark_qdrant(url: str) -> str:
    """The benchmark's server only: Palladion's ports are refused outright."""
    port = urlparse(url).port
    if port is None or port in PALLADION_PORTS:
        raise AdapterError("the dense arm uses the benchmark's own Qdrant, never Palladion's")
    if urlparse(url).hostname not in ("127.0.0.1", "localhost"):
        raise AdapterError("the dense arm talks to a local Qdrant only")
    return url


def chunk_digest(chunks: Iterable[Chunk]) -> str:
    sha = hashlib.sha256()
    for chunk in chunks:
        sha.update(chunk.chunk_id.encode())
        sha.update(hashlib.sha256(chunk.text.encode()).digest())
    return sha.hexdigest()


class DenseArm:
    """The R1 arm. Vectors are cached in ``index_dir`` keyed by model fingerprint and chunk digest."""

    arm_id = "R1"

    def __init__(
        self,
        view: PublishedView,
        encoder: Encoder,
        index_dir: Path,
        *,
        qdrant_url: str = DEFAULT_URL,
        condition: Condition = Condition.C2,
        chunk_words: int = DEFAULT_CHUNK_WORDS,
        collection: str | None = None,
    ) -> None:
        self.view = view
        self.encoder = encoder
        self.index_dir = index_dir
        self.qdrant_url = ensure_benchmark_qdrant(qdrant_url)
        self.condition = condition
        self.chunk_words = chunk_words
        self.access = AccessFilter(view, condition)
        self._collection_name = collection
        self.collection = collection or f"bench_r1_{encoder.fingerprint[:8]}_{condition.value}"
        self._client = QdrantClient(url=self.qdrant_url, timeout=60)
        self._chunks: list[Chunk] = []
        self._by_id: dict[str, Chunk] = {}
        self._vectors: np.ndarray | None = None
        self._stats: dict[str, Any] = {}
        self.last_notes: dict[str, Any] = {}

    # -- the adapter surface ---------------------------------------------------------------------

    def build_index(self, source_manifest_uri: str, index_namespace: str) -> None:
        if Path(source_manifest_uri).resolve() != self.view.root.resolve():
            raise AdapterError("the index is built from the published directory this arm was created with")
        started = time.perf_counter()
        self._chunks = build_chunks(self.view, self.chunk_words)
        self._by_id = {c.chunk_id: c for c in self._chunks}
        digest = chunk_digest(self._chunks)
        if self._collection_name is None:  # a collection belongs to one model, condition and set of chunks
            self.collection = f"bench_r1_{self.encoder.fingerprint[:8]}_{self.condition.value}_{digest[:8]}"
        vectors, cached = self._vectors_for(digest)
        self._vectors = vectors
        embedded = time.perf_counter()
        self._load_collection(vectors)
        self._stats = {
            "arm": self.arm_id,
            "namespace": index_namespace,
            "documents": len(self.view.records),
            "chunks": len(self._chunks),
            "words": sum(chunk.words for chunk in self._chunks),
            "characters": sum(chunk.characters for chunk in self._chunks),
            "dimension": self.encoder.dimension,
            "model_fingerprint": self.encoder.fingerprint,
            "chunk_digest": digest,
            "collection": self.collection,
            "hnsw": {"m": HNSW_M, "ef_construct": HNSW_EF_CONSTRUCT, "ef_search": HNSW_EF_SEARCH},
            "embeddings_from_cache": cached,
            "qdrant_server_version": self.server_version(),
            "ann_recall": self.measure_ann_recall(),
            "condition": self.condition.value,
            "embed_ms": (embedded - started) * 1000,
            "build_ms": (time.perf_counter() - started) * 1000,
        }

    def index_stats(self) -> dict[str, Any]:
        return dict(self._stats)

    def describe(self) -> dict[str, Any]:
        """Settings that define this arm's behaviour, for the run manifest."""
        return {
            "arm": self.arm_id,
            "model_fingerprint": self.encoder.fingerprint,
            "chunk_words": self.chunk_words,
            "hnsw": {"m": HNSW_M, "ef_construct": HNSW_EF_CONSTRUCT, "ef_search": HNSW_EF_SEARCH},
            "condition": self.condition.value,
        }

    def retrieve(self, request: RetrievalRequest) -> list[EvidenceCandidate]:
        hits = self.search(request.query, request.principal_id, request.limit)
        candidates = [
            candidate_from_chunk(
                self._by_id[chunk_id], self.view.document(self._by_id[chunk_id].doc_id).record, rank, score, CHANNEL
            )
            for rank, (chunk_id, score) in enumerate(hits, start=1)
        ]
        bundle = enforce_budget(candidates, request.max_evidence_tokens)
        self.last_notes = {
            "truncated": bundle.truncated,
            "dropped": bundle.dropped,
            "cut_words": bundle.cut_words,
            "words": bundle.words,
        }
        return list(bundle.kept)

    def call_flags(self) -> tuple[str, ...]:
        return flags_from_notes(self.last_notes)

    def close(self) -> None:
        self._client.close()

    # -- search ----------------------------------------------------------------------------------

    def _filter(self, principal_id: str) -> Filter | None:
        if self.condition is Condition.C1:
            return None
        visible = sorted(self.access.visible_documents(principal_id))
        return Filter(must=[FieldCondition(key="doc_id", match=MatchAny(any=visible))])

    def search(self, query: str, principal_id: str, limit: int, *, exact: bool = False) -> list[tuple[str, float]]:
        """(chunk id, cosine score) best first; ``exact=True`` asks Qdrant for brute-force search instead of HNSW."""
        if not self._chunks:
            raise AdapterError("build_index must run before retrieve")
        response = self._client.query_points(
            collection_name=self.collection,
            query=self.encoder.embed_query(query),
            query_filter=self._filter(principal_id),
            limit=limit + TIE_MARGIN,
            search_params=SearchParams(hnsw_ef=HNSW_EF_SEARCH, exact=exact),
            with_payload=True,
        )
        scored = [
            (str(p.payload["chunk_id"]), round(float(p.score), SCORE_DIGITS)) for p in response.points if p.payload
        ]
        scored.sort(key=lambda item: (-item[1], item[0]))  # equal scores order by chunk id, not by graph position
        return scored[:limit]

    def server_version(self) -> str:
        """The version the Qdrant server reports, recorded with the index so a result is tied to the binary."""
        with urllib.request.urlopen(self.qdrant_url + "/", timeout=10) as response:
            return str(json.loads(response.read())["version"])

    def measure_ann_recall(self, sample: int = ANN_SAMPLE, k: int = 10) -> dict[str, Any]:
        """Approximate-versus-exact recall on queries taken evenly from the corpus, recorded in the index stats."""
        step = max(1, len(self._chunks) // sample)
        principals = [p.principal_id for p in self.view.identity.principals] or ["-"]
        queries = [
            (chunk.text[:ANN_QUERY_CHARACTERS], principals[i % len(principals)])
            for i, chunk in enumerate(self._chunks[::step][:sample])
        ]
        return self.ann_recall(queries, k)

    def ann_recall(self, queries: Sequence[tuple[str, str]], k: int) -> dict[str, Any]:
        """Mean overlap of approximate and exact top-k over (query, principal) pairs; 1.0 means HNSW lost nothing."""
        if not queries:
            raise AdapterError("an approximate-versus-exact check needs queries")
        overlaps: list[float] = []
        for query, principal_id in queries:
            approximate = {c for c, _ in self.search(query, principal_id, k)}
            exact = {c for c, _ in self.search(query, principal_id, k, exact=True)}
            overlaps.append(len(approximate & exact) / len(exact) if exact else 1.0)
        return {
            "k": k,
            "queries": len(queries),
            "mean_recall": sum(overlaps) / len(overlaps),
            "min_recall": min(overlaps),
        }

    def exact_scores(self, query: str, chunk_ids: Sequence[str]) -> list[float]:
        """Cosine scores computed locally from the cached vectors, to check what the server reports."""
        if self._vectors is None:
            raise AdapterError("build_index must run first")
        position = {c.chunk_id: i for i, c in enumerate(self._chunks)}
        q = np.asarray(self.encoder.embed_query(query), dtype=np.float32)
        q /= np.linalg.norm(q)
        rows = self._vectors[[position[c] for c in chunk_ids]]
        rows = rows / np.linalg.norm(rows, axis=1, keepdims=True)
        return [float(x) for x in rows @ q]

    # -- index construction ----------------------------------------------------------------------

    def _vectors_for(self, digest: str) -> tuple[np.ndarray, bool]:
        self.index_dir.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256(f"{self.encoder.fingerprint}:{digest}".encode()).hexdigest()[:16]
        path, seal = self.index_dir / f"vectors-{key}.npy", self.index_dir / f"vectors-{key}.sha256"
        if (
            path.exists()
            and seal.exists()
            and hashlib.sha256(path.read_bytes()).hexdigest() == seal.read_text().strip()
        ):
            cached = np.load(path)
            if cached.shape == (len(self._chunks), self.encoder.dimension):
                return cached, True
        vectors = np.asarray(self.encoder.embed_documents([c.text for c in self._chunks]), dtype=np.float32)
        if vectors.shape != (len(self._chunks), self.encoder.dimension):
            raise AdapterError("the encoder returned vectors of an unexpected shape")
        np.save(path, vectors)
        seal.write_text(hashlib.sha256(path.read_bytes()).hexdigest(), encoding="utf-8")
        return vectors, False

    def _load_collection(self, vectors: np.ndarray) -> None:
        if self._client.collection_exists(self.collection):
            self._client.delete_collection(self.collection)
        self._client.create_collection(
            self.collection,
            vectors_config=VectorParams(size=self.encoder.dimension, distance=Distance.COSINE),
            hnsw_config=HnswConfigDiff(m=HNSW_M, ef_construct=HNSW_EF_CONSTRUCT),
        )
        for start in range(0, len(self._chunks), UPSERT_BATCH):
            batch = self._chunks[start : start + UPSERT_BATCH]
            self._client.upsert(
                self.collection,
                points=[
                    PointStruct(
                        id=start + offset,
                        vector=vectors[start + offset].tolist(),
                        payload={"chunk_id": chunk.chunk_id, "doc_id": chunk.doc_id},
                    )
                    for offset, chunk in enumerate(batch)
                ],
                wait=True,
            )
        count = self._client.count(self.collection, exact=True).count
        if count != len(self._chunks):
            raise AdapterError(f"the collection holds {count} points for {len(self._chunks)} chunks")
