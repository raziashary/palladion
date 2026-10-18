"""Optional, bounded FastEmbed cross-encoder reranking."""

from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
from typing import Protocol, Sequence

from fastembed.rerank.cross_encoder import TextCrossEncoder
from huggingface_hub import snapshot_download

from evidence_agent.core.errors import DependencyUnavailable
from evidence_agent.core.retrieval import Chunk

RERANKER_NAME = "Xenova/ms-marco-MiniLM-L-6-v2"
RERANKER_REVISION = "a09144355adeed5f58c8ed011d209bf8ee5a1fec"
RERANKER_FILES = (
    "onnx/model.onnx",
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.txt",
)
CPU_THREADS = 2
MAX_RERANK_CANDIDATES = 30
_ort = importlib.import_module("onnxruntime.capi.onnxruntime_pybind11_state")
_BACKEND_ERRORS = (OSError, ValueError, RuntimeError, _ort.Fail, _ort.InvalidArgument,
                   _ort.InvalidProtobuf, _ort.NoSuchFile, _ort.RuntimeException)


class ChunkReranker(Protocol):
    def rank(self, query: str, chunks: Sequence[Chunk]) -> tuple[Chunk, ...]: ...


class FastEmbedReranker:
    """Use a pinned CPU cross-encoder when enabled; otherwise preserve input order."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        cache_dir: Path | None = None,
        max_candidates: int = MAX_RERANK_CANDIDATES,
    ) -> None:
        if not 1 <= max_candidates <= MAX_RERANK_CANDIDATES:
            raise ValueError(f"max_candidates must be between 1 and {MAX_RERANK_CANDIDATES}")
        self.enabled = enabled
        self.max_candidates = max_candidates
        self._cache_dir = cache_dir or Path(__file__).resolve().parents[3] / "runtime" / "model_cache"
        self._model: TextCrossEncoder | None = None
        self._fingerprint: str | None = None
        self._manifest: dict[str, object] | None = None

    @property
    def worker_configuration(self) -> dict[str, str | int | bool]:
        """Non-secret reconstruction settings for the owned runtime search process."""
        return {"enabled": self.enabled, "cache_dir": str(self._cache_dir),
                "max_candidates": self.max_candidates}

    @property
    def manifest(self) -> dict[str, object]:
        if not self.enabled:
            return {"enabled": False}
        self._load()
        assert self._manifest is not None
        return dict(self._manifest)

    @property
    def fingerprint(self) -> str:
        if not self.enabled:
            return "disabled"
        self._load()
        assert self._fingerprint is not None
        return self._fingerprint

    def _load(self) -> TextCrossEncoder:
        try:
            return self._load_model()
        except _BACKEND_ERRORS as exc:
            raise DependencyUnavailable("Reranker model unavailable") from exc

    def _load_model(self) -> TextCrossEncoder:
        if self._model is None:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            model_path = Path(
                snapshot_download(
                    repo_id=RERANKER_NAME,
                    revision=RERANKER_REVISION,
                    cache_dir=str(self._cache_dir / "huggingface"),
                    allow_patterns=list(RERANKER_FILES),
                    token=False,
                )
            )
            hashes: dict[str, str] = {}
            for name in RERANKER_FILES:
                digest = hashlib.sha256()
                with (model_path / name).open("rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(block)
                hashes[name] = digest.hexdigest()
            manifest = {
                "model": RERANKER_NAME,
                "revision": RERANKER_REVISION,
                "files": hashes,
                "threads": CPU_THREADS,
            }
            self._manifest = manifest
            self._fingerprint = hashlib.sha256(
                json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            self._model = TextCrossEncoder(
                model_name=RERANKER_NAME,
                cache_dir=str(self._cache_dir / "fastembed"),
                threads=CPU_THREADS,
                cuda=False,
                specific_model_path=str(model_path),
                local_files_only=True,
            )
        return self._model

    def rank(self, query: str, chunks: Sequence[Chunk]) -> tuple[Chunk, ...]:
        if not query.strip():
            raise ValueError("query must not be empty")
        if len(chunks) > self.max_candidates:
            raise ValueError(f"candidate count exceeds configured limit {self.max_candidates}")
        if not self.enabled or len(chunks) < 2:
            return tuple(chunks)

        try:
            scores = list(self._load().rerank(query, [chunk.text for chunk in chunks], batch_size=16))
        except _BACKEND_ERRORS as exc:
            raise DependencyUnavailable("Reranker inference unavailable") from exc
        if len(scores) != len(chunks):
            raise RuntimeError("cross-encoder returned a score count different from the input count")
        return tuple(
            chunk
            for _, chunk in sorted(
                enumerate(chunks), key=lambda item: (-float(scores[item[0]]), item[0])
            )
        )
