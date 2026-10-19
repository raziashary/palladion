"""Pinned model snapshots for the dense and reranker arms (B04-T01.04, OQ04, OQ05, BADR-0025).

A model is pinned by repository, a 40-character revision and the SHA-256 of every file the arm loads. Nothing here
runs unless a command calls ``fetch`` on purpose: downloading is explicit and goes into a benchmark-owned cache, never
Palladion's. ``verify`` is called on every load, so a replaced or corrupted file is refused instead of used.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from benchmark.config import Pin

REVISION = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")


class ModelIntegrityError(ValueError):
    """A model file is missing or differs from its pinned digest. The message names the file, never its content."""


@dataclass(frozen=True)
class ModelSpec:
    """The exact files of one model snapshot. ``digests`` is empty only while the pin is being created."""

    repository: str
    revision: str
    files: tuple[str, ...]
    digests: Mapping[str, str]

    def __post_init__(self) -> None:
        if not REVISION.fullmatch(self.revision):
            raise ModelIntegrityError("a model revision is a 40-character commit, not a branch or tag")
        if not self.files or len(set(self.files)) != len(self.files):
            raise ModelIntegrityError("a model lists each of its files once")
        if self.digests and (
            set(self.digests) != set(self.files) or not all(SHA256.fullmatch(d) for d in self.digests.values())
        ):
            raise ModelIntegrityError("a model pin carries one SHA-256 for each of its files")

    @property
    def is_pinned(self) -> bool:
        return bool(self.digests)


def digest_file(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def digest_files(directory: Path, files: tuple[str, ...]) -> dict[str, str]:
    missing = [f for f in files if not (directory / f).is_file()]
    if missing:
        raise ModelIntegrityError(f"missing model file(s): {', '.join(missing)}")
    return {f: digest_file(directory / f) for f in files}


def verify(directory: Path, spec: ModelSpec) -> None:
    """Refuse a snapshot whose files do not match the pin. An unpinned spec is refused: nothing is unchecked."""
    if not spec.is_pinned:
        raise ModelIntegrityError("the model has no recorded digests; pin it before using it")
    actual = digest_files(directory, spec.files)
    wrong = sorted(f for f in spec.files if actual[f] != spec.digests[f])
    if wrong:
        raise ModelIntegrityError(f"model file(s) differ from the pin: {', '.join(wrong)}")


def fetch(spec: ModelSpec, cache_dir: Path) -> Path:
    """Download exactly the listed files at the pinned revision into ``cache_dir`` and return the snapshot folder.

    This is the only place a model is downloaded. Call it from an explicit command, never at import or on first use.
    """
    from huggingface_hub import snapshot_download

    cache_dir.mkdir(parents=True, exist_ok=True)
    return Path(
        snapshot_download(
            repo_id=spec.repository,
            revision=spec.revision,
            cache_dir=str(cache_dir),
            allow_patterns=list(spec.files),
            token=False,
        )
    )


def spec_from_pin(pin: Pin) -> ModelSpec:
    """The model spec a comparators.yaml pin describes; refused unless the pin names a revision and file digests."""
    if pin.kind != "model" or pin.revision is None or not pin.digests:
        raise ModelIntegrityError("a model pin needs kind model, a revision and file digests")
    return ModelSpec(pin.value, pin.revision, tuple(pin.digests), dict(pin.digests))
