"""Qdrant discovery index; canonical source and ACL checks remain external."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import re
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Callable, Literal, TypeVar
from urllib.parse import urlsplit

from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse
from qdrant_client.http.models import PointStruct

from evidence_agent.core.errors import DependencyUnavailable
from evidence_agent.core.models import Principal
from evidence_agent.core.retrieval import TEXT_REPRESENTATION, Candidate, Chunk, index_text
from evidence_agent.retrieval.embeddings import DenseEncoder, FastEmbedDenseEncoder

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_DENSE_VECTOR = "dense"
_SPARSE_VECTOR = "bm25"
_COLLECTION = "knowledge_chunks_v1"
_MAX_QUERY_LIMIT = 100
_MAX_FACET_GENERATIONS = 20000  # twice the 10,000-source bound: current generations plus leftovers of earlier ones
_T = TypeVar("_T")


class IndexConsistencyError(RuntimeError):
    """Raised when a Qdrant point cannot be reconciled with its source manifest."""


def _point_id(chunk: Chunk) -> str:
    identity = f"{chunk.tenant_id}\0{chunk.revision_id}\0{chunk.chunk_id}"
    return str(uuid.uuid5(uuid.NAMESPACE_OID, identity))


def _hash_json(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _bm25_config(profile: Literal["english", "no_stemming"]) -> models.Bm25Config:
    if profile == "english":
        return models.Bm25Config(language="english", lowercase=True)
    if profile != "no_stemming":
        raise ValueError("bm25_profile must be 'english' or 'no_stemming'")
    return models.Bm25Config(
        lowercase=True,
        stemmer=models.DisabledStemmerParams(type=models.NoStemmer.NONE),
        stopwords=models.StopwordsSet(languages=[]),
    )


class QdrantIndex:
    """Named dense/BM25 vectors in one UUID point with scoped discovery filters.

    The optional ``active_generation`` should come from the canonical publication
    catalog. Without it, this low-level adapter searches all indexed generations;
    callers must still resolve every result against that catalog before exposure.
    """

    def __init__(
        self,
        url: str = "http://127.0.0.1:16333",
        collection_name: str = _COLLECTION,
        model_cache_dir: str | None = None,
        bm25_profile: Literal["english", "no_stemming"] = "english",
        active_generation: str | None = None,
        *,
        client: QdrantClient | None = None,
        encoder: DenseEncoder | None = None,
    ) -> None:
        if not collection_name:
            raise ValueError("collection_name must not be empty")
        self.collection_name = collection_name
        self.model_cache_dir = None if model_cache_dir is None else Path(model_cache_dir)
        # Non-secret reconstruction parameters for the approved runtime search worker.
        self.worker_configuration = None if client is not None or encoder is not None else {
            "url": url, "collection_name": collection_name,
            "model_cache_dir": None if model_cache_dir is None else str(model_cache_dir),
            "bm25_profile": bm25_profile, "active_generation": active_generation}
        self.bm25_profile = bm25_profile
        self.active_generation = active_generation
        self._client = client or QdrantClient(url=url, timeout=10)
        self._encoder = encoder or FastEmbedDenseEncoder(
            None if model_cache_dir is None else Path(model_cache_dir)
        )
        self._bm25 = _bm25_config(bm25_profile)
        self._server_version: str | None = None

    def _get_server_version(self) -> str:
        if self._server_version is None:
            info = self._call_qdrant(self._client.info)
            self._server_version = str(info.version)
        return self._server_version

    @staticmethod
    def _call_qdrant(operation: Callable[..., _T], **kwargs: Any) -> _T:
        try:
            return operation(**kwargs)
        except ResponseHandlingException as error:
            raise DependencyUnavailable() from error
        except UnexpectedResponse as error:
            if error.status_code is not None and (error.status_code in {408,429} or error.status_code >= 500):
                raise DependencyUnavailable() from error
            raise

    @property
    def audit_cache_identity(self) -> str | None:
        """Identify a validated remote SDK endpoint without credentials or reprs.

        Custom clients and local/in-memory backends cannot share physical-audit rows.
        A supplied encoder remains bound through the exact representation fingerprint.
        """
        if type(self._client) is not QdrantClient:
            return None
        options = self._client.init_options
        url = options.get("url")
        if not isinstance(url, str):
            return None
        parsed = urlsplit(url)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            return None
        return _hash_json({"endpoint": [parsed.scheme, parsed.hostname, parsed.port,
            parsed.path, options.get("port"), options.get("grpc_port"), options.get("prefix")],
            "collection": self.collection_name, "representation": self.fingerprint})

    @property
    def fingerprint(self) -> str:
        return _hash_json(self.representation_manifest)

    @property
    def representation_manifest(self) -> dict[str, Any]:
        dense_manifest = getattr(self._encoder, "manifest", None)
        if dense_manifest is None:
            dense_manifest = {
                "fingerprint": self._encoder.fingerprint,
                "dimension": self._encoder.dimension,
            }
        return {
            "dense": dense_manifest,
            "dense_vector": _DENSE_VECTOR,
            "sparse_vector": _SPARSE_VECTOR,
            "bm25_model": "Qdrant/bm25",
            "bm25_profile": self.bm25_profile,
            "bm25_options": self._bm25.model_dump(mode="json", exclude_none=True),
            "text_representation": TEXT_REPRESENTATION,
            "qdrant_client_version": importlib.metadata.version("qdrant-client"),
            "qdrant_server_version": self._get_server_version(),
            "rrf_k": 60,
        }

    def ensure_collection(self) -> None:
        if not self._call_qdrant(
            self._client.collection_exists, collection_name=self.collection_name
        ):
            try:
                self._call_qdrant(
                    self._client.create_collection,
                    collection_name=self.collection_name,
                    vectors_config={
                        _DENSE_VECTOR: models.VectorParams(
                            size=self._encoder.dimension, distance=models.Distance.COSINE
                        )
                    },
                    sparse_vectors_config={
                        _SPARSE_VECTOR: models.SparseVectorParams(modifier=models.Modifier.IDF)
                    },
                    replication_factor=1,
                )
            except UnexpectedResponse as error:
                # Another caller created it first; the schema validation below judges what it created.
                if error.status_code != 409 or not self._call_qdrant(
                    self._client.collection_exists, collection_name=self.collection_name
                ):
                    raise

        info = self._call_qdrant(
            self._client.get_collection, collection_name=self.collection_name
        )
        self._validate_collection_config(info)

        expected_indexes = {
            "tenant_id": models.PayloadSchemaType.KEYWORD,
            "case_id": models.PayloadSchemaType.KEYWORD,
            "revision_id": models.PayloadSchemaType.KEYWORD,
            "index_generation": models.PayloadSchemaType.KEYWORD,
            "case_members": models.PayloadSchemaType.BOOL,
            "allowed_principal_ids": models.PayloadSchemaType.KEYWORD,
        }
        payload_schema = info.payload_schema or {}
        for field_name, expected_type in expected_indexes.items():
            existing = payload_schema.get(field_name)
            if existing is not None:
                if existing.data_type != expected_type:
                    raise IndexConsistencyError(
                        f"payload index {field_name!r} has type {existing.data_type!r}; "
                        f"expected {expected_type!r}"
                    )
                continue
            self._call_qdrant(
                self._client.create_payload_index,
                collection_name=self.collection_name,
                field_name=field_name,
                field_schema=expected_type,
                wait=True,
            )

    def _validate_collection_config(self, info: Any) -> None:
        params = info.config.params
        vectors = params.vectors
        dense = vectors.get(_DENSE_VECTOR) if isinstance(vectors, dict) else None
        if (
            dense is None
            or dense.size != self._encoder.dimension
            or dense.distance != models.Distance.COSINE
        ):
            raise IndexConsistencyError(
                "collection dense vector must be named 'dense' with the configured "
                "dimension and cosine distance"
            )
        sparse_vectors = params.sparse_vectors or {}
        sparse = sparse_vectors.get(_SPARSE_VECTOR)
        if sparse is None or sparse.modifier != models.Modifier.IDF:
            raise IndexConsistencyError("collection BM25 vector must use IDF modifier")

    def upsert(
        self,
        chunks: Sequence[Chunk],
        generation: str,
        allowed_principal_ids: tuple[str, ...],
    ) -> None:
        if not generation:
            raise ValueError("generation must not be empty")
        if len(allowed_principal_ids) != len(set(allowed_principal_ids)):
            raise ValueError("allowed_principal_ids must not contain duplicates")
        if any(not principal_id for principal_id in allowed_principal_ids):
            raise ValueError("allowed_principal_ids cannot contain empty IDs")
        if not chunks:
            return
        identities = [_point_id(chunk) for chunk in chunks]
        if len(identities) != len(set(identities)):
            raise ValueError("upsert batch contains duplicate chunk identities")
        self.ensure_collection()
        dense_vectors = self._encoder.embed_documents(index_text(chunk) for chunk in chunks)
        if dense_vectors is None or len(dense_vectors) != len(chunks):
            raise IndexConsistencyError("dense encoder returned a vector count different from input")
        fingerprint = self.fingerprint
        points: list[PointStruct] = []
        for chunk, dense in zip(chunks, dense_vectors, strict=True):
            if len(dense) != self._encoder.dimension:
                raise IndexConsistencyError("dense vector dimension differs from collection schema")
            calculated_content_hash = hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()
            if calculated_content_hash != chunk.content_sha256:
                raise IndexConsistencyError("chunk text does not match its declared content hash")
            if not _HASH_RE.fullmatch(chunk.content_sha256) or not _HASH_RE.fullmatch(
                chunk.source_sha256
            ):
                raise ValueError("chunk content/source hashes must be lowercase SHA-256 values")
            points.append(
                models.PointStruct(
                    id=_point_id(chunk),
                    vector={
                        _DENSE_VECTOR: dense,
                        _SPARSE_VECTOR: models.Document(
                            text=index_text(chunk),
                            model="Qdrant/bm25",
                            options=self._bm25,
                        ),
                    },
                    payload={
                        "tenant_id": chunk.tenant_id,
                        "case_id": chunk.case_id,
                        "revision_id": chunk.revision_id,
                        "section_id": chunk.section_id,
                        "chunk_id": chunk.chunk_id,
                        "content_sha256": chunk.content_sha256,
                        "source_sha256": chunk.source_sha256,
                        "index_generation": generation,
                        "case_members": not allowed_principal_ids,
                        "allowed_principal_ids": list(allowed_principal_ids),
                        "representation_fingerprint": fingerprint,
                    },
                )
            )
        self._call_qdrant(
            self._client.upsert,
            collection_name=self.collection_name,
            points=points,
            wait=True,
        )

    def generation_counts(self, tenant_id: str, case_id: str, generations: Sequence[str]) -> dict[str, int]:
        """Exact point count of the given index generations, from one facet call on the payload index.

        The facet counts every generation of the case and the answer is cut to the ones asked about: filtering the
        facet to those generations instead made the call 35 times slower at 1,167 generations (888 ms against 25 ms).
        A case holding more generations than one call reports could hide an asked-about one, which is an error.
        """
        if not generations:
            return {}
        response = self._call_qdrant(
            self._client.facet,
            collection_name=self.collection_name,
            key="index_generation",
            facet_filter=models.Filter(must=[
                models.FieldCondition(key="tenant_id", match=models.MatchValue(value=tenant_id)),
                models.FieldCondition(key="case_id", match=models.MatchValue(value=case_id)),
            ]),
            limit=_MAX_FACET_GENERATIONS,
            exact=True,
        )
        if len(response.hits) >= _MAX_FACET_GENERATIONS:
            raise IndexConsistencyError("the case holds more index generations than one facet call reports")
        wanted = set(generations)
        return {str(hit.value): int(hit.count) for hit in response.hits if str(hit.value) in wanted}

    def readback(self, tenant_id: str, revision_id: str, generation: str) -> dict[str, str]:
        if not tenant_id or not revision_id or not generation:
            raise ValueError("tenant_id, revision_id and generation are required")
        groups = self.readback_many(tenant_id, {revision_id: generation})
        return groups.get((revision_id, generation), {})

    def readback_many(self, tenant_id: str, revisions: dict[str, str]) -> dict[tuple[str, str], dict[str, str]]:
        """Read up to64 requested generations in one bounded physical scroll.

        Validates the same vectors/fingerprints/hashes as single-generation readback.
        Caller owns batching; no cache hides physical drift after publication.
        """
        if not tenant_id or not revisions or len(revisions) > 64 or any(
                not revision or not generation for revision, generation in revisions.items()):
            raise ValueError("Physical readback batch bounds exceeded")
        query_filter = models.Filter(must=[
            models.FieldCondition(key="tenant_id", match=models.MatchValue(value=tenant_id)),
            models.Filter(should=[models.Filter(must=[
                models.FieldCondition(key="revision_id", match=models.MatchValue(value=revision)),
                models.FieldCondition(key="index_generation", match=models.MatchValue(value=generation)),
            ]) for revision, generation in revisions.items()]),
        ])
        expected_fingerprint = self.fingerprint
        result: dict[tuple[str, str], dict[str, str]] = {}
        offset: Any = None
        seen_offsets: set[str] = set()
        scanned = 0
        while True:
            records, offset = self._call_qdrant(
                self._client.scroll,
                collection_name=self.collection_name,
                scroll_filter=query_filter,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=True,
            )
            for point in records:
                payload = point.payload or {}
                scanned += 1
                if scanned > 100000:
                    raise IndexConsistencyError("physical readback point bound exceeded")
                revision_id = payload.get("revision_id")
                generation = payload.get("index_generation")
                if (payload.get("tenant_id") != tenant_id or not isinstance(revision_id, str)
                        or revisions.get(revision_id) != generation):
                    raise IndexConsistencyError("readback returned a point outside its requested scope")
                vectors = point.vector
                if not isinstance(vectors, dict) or not all(
                    name in vectors and vectors[name] is not None
                    for name in (_DENSE_VECTOR, _SPARSE_VECTOR)
                ):
                    raise IndexConsistencyError("indexed point is missing a dense or BM25 vector")
                sparse = vectors[_SPARSE_VECTOR]
                if not getattr(sparse, "indices", None) or not getattr(sparse, "values", None):
                    raise IndexConsistencyError("indexed point has an empty or invalid BM25 vector")
                dense = vectors[_DENSE_VECTOR]
                if not isinstance(dense, list) or len(dense) != self._encoder.dimension:
                    raise IndexConsistencyError("indexed point has an invalid dense vector dimension")
                chunk_id = payload.get("chunk_id")
                content_hash = payload.get("content_sha256")
                source_hash = payload.get("source_sha256")
                if not isinstance(chunk_id, str) or not chunk_id:
                    raise IndexConsistencyError("indexed point has no canonical chunk ID")
                if not isinstance(content_hash, str) or not _HASH_RE.fullmatch(content_hash):
                    raise IndexConsistencyError("indexed point has an invalid content hash")
                if not isinstance(source_hash, str) or not _HASH_RE.fullmatch(source_hash):
                    raise IndexConsistencyError("indexed point has an invalid source hash")
                if payload.get("representation_fingerprint") != expected_fingerprint:
                    raise IndexConsistencyError("indexed point uses a different representation")
                group = result.setdefault((revision_id, str(generation)), {})
                if chunk_id in group:
                    raise IndexConsistencyError("duplicate chunk ID in tenant/revision/generation")
                group[chunk_id] = content_hash
            if offset is None:
                break
            key = str(offset)
            if key in seen_offsets:
                raise IndexConsistencyError("physical readback repeated page offset")
            seen_offsets.add(key)
        return result

    def query(
        self,
        query: str,
        principal: Principal,
        case_id: str,
        mode: Literal["lexical", "dense", "hybrid"] = "hybrid",
        limit: int = 20,
        exact: bool = False,
        generations: Sequence[str] | None = None,
    ) -> tuple[Candidate, ...]:
        """Ranked candidates of the caller's scope; `generations` restricts them to those index generations (None: no restriction; empty: no hits)."""
        if not query.strip():
            raise ValueError("query must not be empty")
        if not 1 <= limit <= _MAX_QUERY_LIMIT:
            raise ValueError(f"limit must be between 1 and {_MAX_QUERY_LIMIT}")
        if mode not in ("lexical", "dense", "hybrid"):
            raise ValueError("mode must be 'lexical', 'dense' or 'hybrid'")
        if case_id not in principal.allowed_case_ids:
            raise PermissionError("principal is not authorized for the requested case")
        if not principal.tenant_id or not principal.principal_id:
            raise PermissionError("principal has no valid tenant identity")
        if generations is not None and not generations:
            return ()
        query_filter = self._scope_filter(principal, case_id, generations)
        response = self._query_points(query, query_filter, mode, limit, exact)
        candidates: list[Candidate] = []
        for point in response.points:
            payload = point.payload or {}
            chunk_id = payload.get("chunk_id")
            generation = payload.get("index_generation")
            content_hash = payload.get("content_sha256")
            source_hash = payload.get("source_sha256")
            if not isinstance(chunk_id, str) or not chunk_id:
                raise IndexConsistencyError("search hit has no canonical chunk ID")
            if not isinstance(generation, str) or not generation:
                raise IndexConsistencyError("search hit has no index generation")
            if not isinstance(content_hash, str) or not _HASH_RE.fullmatch(content_hash):
                raise IndexConsistencyError("search hit has an invalid content hash")
            if not isinstance(source_hash, str) or not _HASH_RE.fullmatch(source_hash):
                raise IndexConsistencyError("search hit has an invalid source hash")
            if (
                payload.get("tenant_id") != principal.tenant_id
                or payload.get("case_id") != case_id
                or not (
                    payload.get("case_members") is True
                    or principal.principal_id in payload.get("allowed_principal_ids", [])
                )
            ):
                raise IndexConsistencyError("search returned a point outside its requested ACL scope")
            if self.active_generation is not None and generation != self.active_generation:
                raise IndexConsistencyError("search returned a point outside the active generation")
            candidates.append(
                Candidate(
                    chunk_id=chunk_id,
                    generation=generation,
                    score=float(point.score),
                    channel=mode,
                )
            )
        return tuple(candidates)

    def _scope_filter(
        self, principal: Principal, case_id: str, generations: Sequence[str] | None = None
    ) -> models.Filter:
        must: list[models.Condition] = [
            models.FieldCondition(
                key="tenant_id", match=models.MatchValue(value=principal.tenant_id)
            ),
            models.FieldCondition(key="case_id", match=models.MatchValue(value=case_id)),
        ]
        if generations is not None:
            must.append(
                models.FieldCondition(
                    key="index_generation", match=models.MatchAny(any=list(generations))
                )
            )
        if self.active_generation is not None:
            must.append(
                models.FieldCondition(
                    key="index_generation",
                    match=models.MatchValue(value=self.active_generation),
                )
            )
        return models.Filter(
            must=must,
            min_should=models.MinShould(
                conditions=[
                    models.FieldCondition(
                        key="case_members", match=models.MatchValue(value=True)
                    ),
                    models.FieldCondition(
                        key="allowed_principal_ids",
                        match=models.MatchValue(value=principal.principal_id),
                    ),
                ],
                min_count=1,
            ),
        )

    def _query_points(
        self,
        query: str,
        query_filter: models.Filter,
        mode: Literal["lexical", "dense", "hybrid"],
        limit: int,
        exact: bool,
    ) -> Any:
        if mode == "lexical":
            return self._call_qdrant(
                self._client.query_points,
                collection_name=self.collection_name,
                query=self._bm25_document(query),
                using=_SPARSE_VECTOR,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
        dense_query = self._encoder.embed_query(query)
        if mode == "dense":
            return self._call_qdrant(
                self._client.query_points,
                collection_name=self.collection_name,
                query=dense_query,
                using=_DENSE_VECTOR,
                query_filter=query_filter,
                search_params=models.SearchParams(exact=exact),
                limit=limit,
                with_payload=True,
            )
        return self._call_qdrant(
            self._client.query_points,
            collection_name=self.collection_name,
            prefetch=[
                models.Prefetch(
                    query=dense_query,
                    using=_DENSE_VECTOR,
                    filter=query_filter,
                    limit=max(limit, 40),
                    params=models.SearchParams(exact=exact),
                ),
                models.Prefetch(
                    query=self._bm25_document(query),
                    using=_SPARSE_VECTOR,
                    filter=query_filter,
                    limit=max(limit, 40),
                ),
            ],
            query=models.RrfQuery(rrf=models.Rrf(k=60)),
            limit=limit,
            with_payload=True,
        )

    def _bm25_document(self, text: str) -> models.Document:
        return models.Document(text=text, model="Qdrant/bm25", options=self._bm25)

    def health(self) -> dict[str, Any]:
        if not self._call_qdrant(
            self._client.collection_exists, collection_name=self.collection_name
        ):
            return {
                "status": "missing",
                "collection": self.collection_name,
                "points_count": 0,
                "indexed_vectors_count": 0,
                "dense_vector": _DENSE_VECTOR,
                "sparse_vector": _SPARSE_VECTOR,
                "expected_named_vectors_per_point": 2,
                "server_version": self._get_server_version(),
                "fingerprint": self.fingerprint,
                "representation": self.representation_manifest,
            }
        info = self._call_qdrant(
            self._client.get_collection, collection_name=self.collection_name
        )
        points_count = int(info.points_count or 0)
        return {
            "status": str(info.status),
            "collection": self.collection_name,
            "points_count": points_count,
            "indexed_vectors_count": int(info.indexed_vectors_count or 0),
            "expected_named_vectors_per_point": 2,
            "server_version": self._get_server_version(),
            "dense_vector": _DENSE_VECTOR,
            "sparse_vector": _SPARSE_VECTOR,
            "fingerprint": self.fingerprint,
            "representation": self.representation_manifest,
        }

    def close(self) -> None:
        self._client.close()
