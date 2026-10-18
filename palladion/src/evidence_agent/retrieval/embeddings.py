"""Pinned local embedding models used by the P02 retrieval substrate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable, Protocol

from fastembed import TextEmbedding
from huggingface_hub import snapshot_download

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODEL_REPOSITORY = "Qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q"
MODEL_REVISION = "faf4aa4225822f3bc6376869cb1164e8e3feedd0"
MODEL_FILES = (
    "model_optimized.onnx",
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
)
EMBEDDING_DIMENSION = 384
CPU_THREADS = 2


class DenseEncoder(Protocol):
    """Minimal interface needed by the index and its isolated tests."""

    @property
    def fingerprint(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    def embed_documents(self, texts: Iterable[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class FastEmbedDenseEncoder:
    """FastEmbed encoder whose model snapshot is pinned and locally verified."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        self._cache_dir = cache_dir or Path(__file__).resolve().parents[3] / "runtime" / "model_cache"
        self._model: TextEmbedding | None = None
        self._model_path: Path | None = None
        self._file_hashes: dict[str, str] | None = None

    @property
    def dimension(self) -> int:
        return EMBEDDING_DIMENSION

    def _load(self) -> TextEmbedding:
        if self._model is None:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            model_path = Path(
                snapshot_download(
                    repo_id=MODEL_REPOSITORY,
                    revision=MODEL_REVISION,
                    cache_dir=str(self._cache_dir / "huggingface"),
                    allow_patterns=list(MODEL_FILES),
                    token=False,
                )
            )
            hashes = {name: _sha256(model_path / name) for name in MODEL_FILES}
            self._model_path = model_path
            self._file_hashes = hashes
            self._model = TextEmbedding(
                model_name=MODEL_NAME,
                cache_dir=str(self._cache_dir / "fastembed"),
                threads=CPU_THREADS,
                cuda=False,
                specific_model_path=str(model_path),
                local_files_only=True,
            )
        return self._model

    @property
    def file_hashes(self) -> dict[str, str]:
        self._load()
        assert self._file_hashes is not None
        return dict(self._file_hashes)

    @property
    def manifest(self) -> dict[str, object]:
        return {
            "model": MODEL_NAME,
            "repository": MODEL_REPOSITORY,
            "revision": MODEL_REVISION,
            "files": self.file_hashes,
            "dimension": EMBEDDING_DIMENSION,
            "threads": CPU_THREADS,
            "normalization": "FastEmbed model output",
        }

    @property
    def fingerprint(self) -> str:
        manifest = self.manifest
        encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    def embed_documents(self, texts: Iterable[str]) -> list[list[float]]:
        model = self._load()
        return [vector.tolist() for vector in model.embed(list(texts), batch_size=32, parallel=None)]

    def embed_query(self, text: str) -> list[float]:
        model = self._load()
        return next(vector.tolist() for vector in model.query_embed(text))


def fingerprint_manifest(encoder: DenseEncoder) -> str:
    """Expose the verified model fingerprint through the small encoder contract."""

    return encoder.fingerprint
