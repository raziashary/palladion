"""Immutable run manifest (protocol section 7.2) and read-only tree-state capture.

A manifest is written once, before the first arm runs, with an exclusive create. Its digest is
embedded in the file and must also be recorded outside it (every ledger record), because a file
that carries its own digest cannot prove it was not rewritten with a recomputed one. The
evaluator-only gold digest never appears in the view handed to arms.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

from benchmark.contracts import (
    CacheCondition,
    ContractError,
    Track,
    enum_member,
    freeze,
    normalise_timestamp,
    require_bool,
    require_ident,
    require_int,
    require_text,
    thaw,
)

_HEX64 = re.compile(r"[0-9a-f]{64}")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_FLOATING = frozenset({"latest", "main", "master", "head", "stable", "nightly", "unpinned"})
MAX_HASHED_FILE_BYTES = 64 * 1024 * 1024
# Arms whose behavior depends on the Palladion tree: a confirmatory run must pin and record it.
SYSTEM_UNDER_TEST_ARMS = frozenset({"R7", "R7a", "R7b", "E3", "E4"})
# Arms that use no model at all; every other arm must name the models it uses.
MODELLESS_ARMS = frozenset({"R0"})


class ManifestError(ContractError):
    """A manifest is invalid, was altered, or cannot be written without overwriting."""


# --------------------------------------------------------------------------- read-only git capture


def _git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "--no-optional-locks", "-C", str(repo), *args], check=False, capture_output=True)
    if result.returncode != 0:
        raise ManifestError(f"git {args[0]} failed in {repo.name} (exit {result.returncode})")
    return result.stdout


@dataclass(frozen=True)
class TreeState:
    """State of one working tree: commit, content digest of its files, and every dirty path."""

    label: str
    commit: str | None
    tree_sha256: str | None
    dirty_files: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "label", require_ident("TreeState.label", self.label))
        if self.commit is not None and not _COMMIT.fullmatch(self.commit):
            raise ManifestError("TreeState.commit must be a 40-character lowercase hex id")
        if self.tree_sha256 is not None and not _HEX64.fullmatch(self.tree_sha256):
            raise ManifestError("TreeState.tree_sha256 must be a 64-character lowercase hex digest")
        object.__setattr__(self, "dirty_files", tuple(sorted(self.dirty_files)))

    @property
    def is_clean(self) -> bool:
        return not self.dirty_files

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "commit": self.commit,
            "tree_sha256": self.tree_sha256,
            "dirty_files": list(self.dirty_files),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TreeState:
        _only(cls.__name__, data, ("label", "commit", "tree_sha256", "dirty_files"))
        return cls(data["label"], data["commit"], data["tree_sha256"], tuple(data["dirty_files"]))


@dataclass(frozen=True)
class ComparatorPin:
    """What identifies a third-party comparator's build: where its code came from and how it was installed.

    ``deviations`` lists every way the run differs from the upstream's own defaults, so a reader can see how official
    the run is. A floating reference is refused: the commit is a full lower-case id.
    """

    repository: str
    commit: str
    lock_sha256: str
    interpreter: str
    native_config: Mapping[str, Any]
    deviations: tuple[str, ...]

    def __post_init__(self) -> None:
        o = "ComparatorPin"
        object.__setattr__(self, "repository", require_text(f"{o}.repository", self.repository, max_len=300))
        if not self.repository.startswith("https://"):
            raise ManifestError(f"{o}.repository must be an https URL")
        if not _COMMIT.fullmatch(self.commit):
            raise ManifestError(f"{o}.commit must be a 40-character lowercase hex id, not a branch or tag")
        if not _HEX64.fullmatch(self.lock_sha256):
            raise ManifestError(f"{o}.lock_sha256 must be a 64-character lowercase hex digest")
        object.__setattr__(self, "interpreter", require_text(f"{o}.interpreter", self.interpreter, max_len=40))
        object.__setattr__(self, "native_config", freeze(f"{o}.native_config", self.native_config))
        deviations = tuple(require_text(f"{o}.deviations", d, max_len=300) for d in self.deviations)
        object.__setattr__(self, "deviations", deviations)

    def to_dict(self) -> dict[str, Any]:
        return {
            "repository": self.repository,
            "commit": self.commit,
            "lock_sha256": self.lock_sha256,
            "interpreter": self.interpreter,
            "native_config": thaw(self.native_config),
            "deviations": list(self.deviations),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ComparatorPin:
        _only(cls.__name__, data, ("repository", "commit", "lock_sha256", "interpreter", "native_config", "deviations"))
        return cls(
            data["repository"], data["commit"], data["lock_sha256"], data["interpreter"],
            data["native_config"], tuple(data["deviations"]),
        )  # fmt: skip


def _only(owner: str, data: Mapping[str, Any], allowed: tuple[str, ...]) -> None:
    unknown = sorted(set(data) - set(allowed))
    missing = sorted(set(allowed) - set(data))
    if unknown or missing:
        raise ManifestError(f"{owner} fields differ (unknown {unknown}, missing {missing})")


def tree_state(path: Path, *, label: str) -> TreeState:
    """Capture commit, content digest and dirty paths of the subtree at ``path`` using read-only git calls."""
    if not path.is_dir():
        raise ManifestError(f"{label}: directory does not exist")
    commit_text = _git(path, "rev-parse", "HEAD").decode("ascii").strip()
    listing = _git(path, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    digest = hashlib.sha256()
    for relative in sorted({item for item in listing.decode("utf-8").split("\0") if item}):
        candidate = path / relative
        if not candidate.is_file():
            continue  # tracked but deleted: shows up in the dirty list instead
        if candidate.stat().st_size > MAX_HASHED_FILE_BYTES:
            raise ManifestError(f"{label}: {relative} is too large to hash")
        digest.update(relative.encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(candidate.read_bytes()).digest())
    status = _git(path, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--", ".").decode("utf-8")
    dirty: list[str] = []
    entries = iter(status.split("\0"))
    for entry in entries:
        if not entry:
            continue
        dirty.append(entry[3:])
        if entry[0] in "RC":  # renames and copies carry the old path as a separate entry
            next(entries, None)
    return TreeState(label, commit_text, digest.hexdigest(), tuple(dirty))


def collect_hardware() -> dict[str, Any]:
    """Coarse host description for the manifest. No hostname, user name or network identity."""
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "python": sys.version.split()[0],
        "gpu": None,
    }


# --------------------------------------------------------------------------- manifest

# Fields that may be null; each null must carry a reason in ``null_reasons``.
_NULLABLE = (
    "source_manifest_sha256",
    "question_manifest_sha256",
    "gold_manifest_sha256",
    "system_under_test",
    "container_image_digest",
    "method_version",
    "prompt_digest",
    "pricing_snapshot",
    "generator_assignment_sha256",
)


def _digest_or_none(name: str, value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _HEX64.fullmatch(value):
        raise ManifestError(f"{name} must be a 64-character lowercase hex digest or null")
    return value


@dataclass(frozen=True)
class RunManifest:
    run_id: str
    track: Track
    arm: str
    split: str
    source_manifest_sha256: str | None
    question_manifest_sha256: str | None
    gold_manifest_sha256: str | None  # evaluator-only; never in the arm-visible view
    benchmark: TreeState
    system_under_test: TreeState | None
    container_image_digest: str | None
    method_version: str | None
    model_versions: Mapping[str, str | None]
    retrieval_config: Mapping[str, Any]
    prompt_digest: str | None
    hardware: Mapping[str, Any]
    pricing_snapshot: str | None
    seed: int
    order_seed: int
    cache_condition: CacheCondition
    started_at_utc: str
    retry_policy: Mapping[str, Any]
    generator_assignment_sha256: str | None
    confirmatory: bool
    null_reasons: Mapping[str, str]

    def __post_init__(self) -> None:
        set_ = object.__setattr__
        set_(self, "run_id", require_ident("RunManifest.run_id", self.run_id))
        set_(self, "track", enum_member(Track, "RunManifest.track", self.track))
        set_(self, "arm", require_ident("RunManifest.arm", self.arm))
        if self.split not in ("smoke", "dev", "test", "pilot", "none"):
            raise ManifestError("RunManifest.split is not recognised")
        for name in (
            "source_manifest_sha256",
            "question_manifest_sha256",
            "gold_manifest_sha256",
            "container_image_digest",
            "prompt_digest",
            "generator_assignment_sha256",
        ):
            set_(self, name, _digest_or_none(f"RunManifest.{name}", getattr(self, name)))
        if self.method_version is not None:
            set_(self, "method_version", require_text("RunManifest.method_version", self.method_version, max_len=120))
        if self.pricing_snapshot is not None:
            set_(
                self,
                "pricing_snapshot",
                require_text("RunManifest.pricing_snapshot", self.pricing_snapshot, max_len=200),
            )
        if not isinstance(self.benchmark, TreeState):
            raise ManifestError("RunManifest.benchmark must be a TreeState")
        if self.system_under_test is not None and not isinstance(self.system_under_test, TreeState):
            raise ManifestError("RunManifest.system_under_test must be a TreeState or null")
        models = freeze("RunManifest.model_versions", self.model_versions)
        if not all(v is None or isinstance(v, str) for v in models.values()):
            raise ManifestError("RunManifest.model_versions must map names to strings or null")
        set_(self, "model_versions", models)
        set_(self, "retrieval_config", freeze("RunManifest.retrieval_config", self.retrieval_config))
        set_(self, "hardware", freeze("RunManifest.hardware", self.hardware))
        set_(self, "retry_policy", freeze("RunManifest.retry_policy", self.retry_policy))
        set_(self, "seed", require_int("RunManifest.seed", self.seed))
        set_(self, "order_seed", require_int("RunManifest.order_seed", self.order_seed))
        set_(self, "cache_condition", enum_member(CacheCondition, "RunManifest.cache_condition", self.cache_condition))
        set_(self, "started_at_utc", normalise_timestamp("RunManifest.started_at_utc", self.started_at_utc))
        set_(self, "confirmatory", require_bool("RunManifest.confirmatory", self.confirmatory))
        reasons = freeze("RunManifest.null_reasons", self.null_reasons)
        if not all(isinstance(v, str) and v.strip() for v in reasons.values()):
            raise ManifestError("RunManifest.null_reasons must hold non-empty strings")
        set_(self, "null_reasons", reasons)
        unknown = sorted(set(reasons) - set(_NULLABLE))
        if unknown:
            raise ManifestError(f"null_reasons names fields that cannot be null: {', '.join(unknown)}")
        for name in _NULLABLE:
            if getattr(self, name) is None and name not in reasons:
                raise ManifestError(f"{name} is null and needs a reason in null_reasons")
        if self.confirmatory:
            self.require_confirmatory()

    # -- confirmatory rules -------------------------------------------------

    def require_confirmatory(self) -> None:
        """Refuse a confirmatory run whose code, models or trees are not exactly identified."""
        problems: list[str] = []
        for state in (self.benchmark, self.system_under_test):
            if state is None:
                continue
            if state.commit is None or state.tree_sha256 is None:
                problems.append(f"{state.label} has no commit or tree digest")
            if not state.is_clean:
                problems.append(f"{state.label} working tree is dirty ({len(state.dirty_files)} path(s))")
        if self.arm in SYSTEM_UNDER_TEST_ARMS and self.system_under_test is None:
            problems.append(f"arm {self.arm} needs the system under test pinned and recorded")
        if not self.model_versions and self.arm not in MODELLESS_ARMS:
            problems.append("model_versions must name every model the run uses")
        for name, version in self.model_versions.items():
            if version is None or version.lower() in _FLOATING:
                problems.append(f"model {name} is not pinned")
        if self.source_manifest_sha256 is None or self.question_manifest_sha256 is None:
            problems.append("source and question manifest digests are required")
        if problems:
            raise ManifestError("confirmatory run refused: " + "; ".join(problems))

    # -- serialisation ------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for f in fields(self):
            value = getattr(self, f.name)
            if isinstance(value, TreeState):
                result[f.name] = value.to_dict()
            elif hasattr(value, "value"):
                result[f.name] = value.value
            else:
                result[f.name] = thaw(value)
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RunManifest:
        names = [f.name for f in fields(cls)]
        _only(cls.__name__, data, tuple(names))
        values = dict(data)
        values["benchmark"] = TreeState.from_dict(values["benchmark"])
        if values["system_under_test"] is not None:
            values["system_under_test"] = TreeState.from_dict(values["system_under_test"])
        return cls(**values)

    def arm_visible_view(self) -> dict[str, Any]:
        """What an arm may be shown about its own run: no gold digest, no null-reason commentary."""
        view = self.to_dict()
        for name in ("gold_manifest_sha256", "null_reasons"):
            view.pop(name, None)
        return view

    def digest(self) -> str:
        return sha256_of(self.to_dict())

    def write(self, path: Path) -> str:
        """Create the manifest file exclusively and return its digest (record it outside the file)."""
        digest = self.digest()
        document = {"manifest": self.to_dict(), "manifest_sha256": digest}
        try:
            with path.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(document, sort_keys=True, indent=2) + "\n")
        except FileExistsError:
            raise ManifestError(f"{path.name} already exists; a manifest is never overwritten") from None
        return digest


def sha256_of(value: Any) -> str:
    """Digest of the canonical JSON form (sorted keys, fixed separators)."""
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def read_verified(path: Path, *, expected_digest: str | None = None) -> RunManifest:
    """Load a manifest, recompute its digest and compare with the embedded and the external digest.

    The embedded digest catches accidental damage. Only ``expected_digest``, recorded outside the
    file (for example in every ledger record), catches a rewrite that recomputed the embedded one.
    """
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ManifestError(f"{path.name} cannot be read as a manifest") from exc
    if not isinstance(document, dict) or set(document) != {"manifest", "manifest_sha256"}:
        raise ManifestError(f"{path.name} does not have the manifest layout")
    manifest = RunManifest.from_dict(document["manifest"])
    actual = manifest.digest()
    if actual != document["manifest_sha256"]:
        raise ManifestError(f"{path.name} does not match its embedded digest")
    if expected_digest is not None and actual != expected_digest:
        raise ManifestError(f"{path.name} does not match the externally recorded digest")
    return manifest
