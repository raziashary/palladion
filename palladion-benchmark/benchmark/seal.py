"""The seal of a confirmatory run: hashes that make an edit after it detectable (B08-T03.01, BADR-0047).

Before the sealed run the test worlds' files, the pre-registration, the configuration and the code of the benchmark and
of each system are hashed into one record whose own hash is stored with it. After the run the same hashes are computed
again. A world's file that changed means the run did not read what was sealed; code, configuration or registration that
changed means the result is exploratory, whatever it shows. The seal proves that nothing changed after it was made; it
cannot prove that nobody read a test file before it, which is why the sealed run's scorer prints aggregates only.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from benchmark.contracts import ContractError
from benchmark.run_manifest import TreeState, tree_state

SCHEMA = 1
# What of a world is sealed: the documents' manifest (which holds every document's hash), who may read what, the
# questions and their gold, and the generator's own report. Hashed as bytes; nothing is parsed or printed.
WORLD_FILES = {
    "corpus_manifest": "published/corpus_manifest.jsonl",
    "identity_manifest": "published/identity_manifest.json",
    "snapshot": "published/snapshot.json",
    "questions": "annotations_dev/questions_smoke.jsonl",
    "answers": "annotations_dev/answers_smoke.jsonl",
    "generator_report": "generator/report.json",
}


class SealError(ContractError):
    """A seal cannot be made, read or trusted."""


class Kind(StrEnum):
    WORLD_CHANGED = "WORLD_CHANGED"  # the run did not read what was sealed: nothing about it is confirmatory
    CODE_CHANGED = "CODE_CHANGED"  # code, configuration or registration moved: the result is exploratory
    PARAPHRASES_CHANGED = "PARAPHRASES_CHANGED"


@dataclass(frozen=True)
class Problem:
    kind: Kind
    subject: str
    sealed: str | None
    now: str | None


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, capture_output=True, check=False, timeout=60)
    if done.returncode != 0:
        raise SealError(f"git {args[0]} failed in {repo.name}")
    return done.stdout.decode("utf-8")


def code_state(project: Path, paths: Sequence[str]) -> tuple[str, tuple[str, ...]]:
    """The digest of the files under ``paths`` (tracked and untracked, ignored files left out) and those not committed.

    Only the code and configuration that decide a result are sealed. Documents and tests change after a run (the
    evidence is written, a test is added) without changing what ran, so they are outside the digest.
    """
    listing = _git(project, "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", *paths)
    digest = hashlib.sha256()
    for relative in sorted({item for item in listing.split("\0") if item}):
        if (project / relative).is_file():
            digest.update(relative.encode("utf-8") + b"\0" + hashlib.sha256((project / relative).read_bytes()).digest())
    status = _git(project, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--", *paths)
    dirty = tuple(entry[3:] for entry in status.split("\0") if entry)
    return digest.hexdigest(), dirty


def _tree(state: TreeState) -> dict[str, Any]:
    return {"commit": state.commit, "tree_sha256": state.tree_sha256}


def world_digests(root: Path) -> dict[str, str]:
    missing = [name for name, relative in WORLD_FILES.items() if not (root / relative).is_file()]
    if missing:
        raise SealError(f"{root.name} lacks the sealed file(s) {', '.join(sorted(missing))}")
    return {name: file_sha256(root / relative) for name, relative in WORLD_FILES.items()}


@dataclass(frozen=True)
class Seal:
    purpose: str
    created_at_utc: str
    worlds: Mapping[str, Mapping[str, str]]  # world name -> file label -> sha256
    files: Mapping[str, str]  # project-relative path -> sha256 (pre-registration, configuration)
    trees: Mapping[str, Mapping[str, str]]  # "benchmark" (code digest) and "palladion" (commit and tree digest)
    registration: Mapping[str, Any]
    settings: Mapping[str, Any]  # arms, K, budget, conditions, repeats
    paraphrases: Mapping[str, str]  # world name -> the digest of its accepted wording variants

    def body(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "purpose": self.purpose,
            "created_at_utc": self.created_at_utc,
            "worlds": {w: dict(sorted(f.items())) for w, f in sorted(self.worlds.items())},
            "files": dict(sorted(self.files.items())),
            "trees": {label: dict(t) for label, t in sorted(self.trees.items())},
            "registration": dict(self.registration),
            "settings": dict(self.settings),
            "paraphrases": dict(sorted(self.paraphrases.items())),
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.body(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def write(self, path: Path) -> str:
        """Write the seal beside its own hash. An existing seal is never replaced."""
        if path.exists():
            raise SealError(f"{path.name} already exists; a seal is never rewritten")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"seal": self.body(), "sha256": self.digest}, indent=2, sort_keys=True), encoding="utf-8"
        )
        return self.digest

    @classmethod
    def load(cls, path: Path) -> Seal:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            body, recorded = data["seal"], data["sha256"]
            seal = cls(
                body["purpose"], body["created_at_utc"], body["worlds"], body["files"], body["trees"],
                body["registration"], body["settings"], body["paraphrases"],
            )  # fmt: skip
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise SealError(f"{path.name} is not a seal") from error
        if body.get("schema") != SCHEMA or set(body) != set(seal.body()) or seal.digest != recorded:
            raise SealError(f"{path.name} does not match its own hash: it was edited after it was written")
        return seal


def create(
    *,
    purpose: str,
    worlds: Mapping[str, Path],
    files: Mapping[str, Path],
    project: Path,
    code_paths: Sequence[str],
    system: Path | None,
    registration: Mapping[str, Any],
    settings: Mapping[str, Any],
    paraphrases: Mapping[str, str],
) -> Seal:
    """Hash the worlds, the files and the code; code with uncommitted changes is refused (not reproducible)."""
    code, dirty = code_state(project, code_paths)
    trees: dict[str, dict[str, str]] = {"benchmark": {"tree_sha256": code}}
    if system is not None:
        state = tree_state(system, label="palladion")
        dirty += state.dirty_files
        trees["palladion"] = _tree(state)
    if dirty:
        raise SealError(f"uncommitted changes in the sealed code ({', '.join(dirty[:3])}...)")
    if set(paraphrases) - set(worlds):
        raise SealError("wording variants are sealed for worlds that are not in the seal")
    return Seal(
        purpose,
        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        {name: world_digests(root) for name, root in worlds.items()},
        {name: file_sha256(path) for name, path in files.items()},
        trees,
        registration,
        settings,
        paraphrases,
    )


def verify(
    seal: Seal,
    *,
    worlds: Mapping[str, Path],
    files: Mapping[str, Path],
    project: Path,
    code_paths: Sequence[str],
    system: Path | None,
    paraphrases: Mapping[str, str],
) -> list[Problem]:
    """Every difference between what was sealed and what is on disk now; empty when the seal is intact."""
    found: list[Problem] = []
    for name, sealed in seal.worlds.items():
        root = worlds.get(name)
        try:
            now = world_digests(root) if root is not None else {}
        except SealError:
            now = {}
        found += [
            Problem(Kind.WORLD_CHANGED, f"{name}:{label}", digest, now.get(label))
            for label, digest in sealed.items()
            if now.get(label) != digest
        ]
    found += [
        Problem(
            Kind.CODE_CHANGED,
            name,
            digest,
            file_sha256(files[name]) if name in files and files[name].is_file() else None,
        )
        for name, digest in seal.files.items()
        if name not in files or not files[name].is_file() or file_sha256(files[name]) != digest
    ]
    current: dict[str, dict[str, str]] = {"benchmark": {"tree_sha256": code_state(project, code_paths)[0]}}
    if system is not None:
        current["palladion"] = _tree(tree_state(system, label="palladion"))
    for label, sealed in seal.trees.items():
        if current.get(label) != dict(sealed):
            found.append(
                Problem(
                    Kind.CODE_CHANGED, f"{label} tree", sealed["tree_sha256"], current.get(label, {}).get("tree_sha256")
                )
            )
    found += [
        Problem(Kind.PARAPHRASES_CHANGED, name, digest, paraphrases.get(name))
        for name, digest in seal.paraphrases.items()
        if paraphrases.get(name) != digest
    ]
    return found
