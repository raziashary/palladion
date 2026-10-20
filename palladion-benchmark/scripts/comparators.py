"""Pin the third-party comparators: verify the checkout, record the lock digest and the interpreter (B06-T00.03).

Only artifacts the owner approved are accepted (OQ14, BADR-0031): HippoRAG 2, GraphRAG and LightRAG, each from its
upstream repository at one commit, installed into its own uv environment. Nothing is downloaded by this module; it
checks what is on disk against the approval and describes it as a ``ComparatorPin`` for the run manifest.

    python scripts/comparators.py verify            check every checkout against its approved commit
    python scripts/comparators.py pin R6            print the pin of one comparator as JSON
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from benchmark.run_manifest import ComparatorPin, ManifestError  # noqa: E402

COMPARATORS_DIR = PROJECT / "artifacts" / "comparators"


class ComparatorPinError(ValueError):
    """A comparator is not what the owner approved. The message holds no secret."""


@dataclass(frozen=True)
class Approved:
    """One approved artifact: the repository, the commit, where in it the package installs from, and its environment."""

    arm_id: str
    name: str
    repository: str
    commit: str
    checkout: str  # directory under artifacts/comparators
    install_subdir: str  # the package directory inside the checkout
    environment: str
    note: str


APPROVED: Mapping[str, Approved] = {
    "R4": Approved(
        arm_id="R4",
        name="HippoRAG 2",
        repository="https://github.com/OSU-NLP-Group/HippoRAG",
        commit="d5c8329422e0a0b834a15874545cb6a74b4f9b26",
        checkout="HippoRAG",
        install_subdir=".",
        environment="env-HippoRAG",
        note="no HippoRAG 2 release tag exists; the default branch at this commit (2.0.0a5) is pinned, one step "
        "ahead of the PyPI 2.0.0a4",
    ),
    "R5": Approved(
        arm_id="R5",
        name="GraphRAG",
        repository="https://github.com/microsoft/graphrag",
        commit="5faaaf4f5685fa2056fa8c3bf9342cb089f2942f",
        checkout="graphrag",
        install_subdir="packages/graphrag",
        environment="env-graphrag",
        note="release tag v3.3.0; the package needs Python 3.11 to 3.13",
    ),
    "R6": Approved(
        arm_id="R6",
        name="LightRAG",
        repository="https://github.com/HKUDS/LightRAG",
        commit="28ff1b05f2ac3f3e6fa14dd2cd33656579bd0c9c",
        checkout="LightRAG",
        install_subdir=".",
        environment="env-LightRAG",
        note="release tag v1.5.7",
    ),
}


def approved(arm_id: str) -> Approved:
    try:
        return APPROVED[arm_id]
    except KeyError:
        raise ComparatorPinError(f"{arm_id} is not an approved comparator (approved: {', '.join(APPROVED)})") from None


def _git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(path), *args], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise ComparatorPinError(f"git {args[0]} failed in {path.name}")
    return result.stdout.strip()


def verify_checkout(path: Path, repository: str, commit: str) -> None:
    """The checkout is the approved repository at the approved commit, with no change on top of it."""
    if not (path / ".git").exists():
        raise ComparatorPinError(f"{path.name} is not a git checkout")
    if _git(path, "remote", "get-url", "origin").removesuffix(".git") != repository:
        raise ComparatorPinError(f"{path.name}: the origin is not the approved repository")
    if _git(path, "rev-parse", "HEAD") != commit:
        raise ComparatorPinError(f"{path.name}: HEAD is not the approved commit")
    if _git(path, "status", "--porcelain", "--untracked-files=no"):
        raise ComparatorPinError(f"{path.name}: tracked files differ from the commit")


def _env_python(environment: Path) -> Path:
    return environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def interpreter_version(environment: Path) -> str:
    python = _env_python(environment)
    if not python.is_file():
        raise ComparatorPinError(f"{environment.name} has no interpreter")
    result = subprocess.run(
        [str(python), "-c", "import platform; print(platform.python_version())"],
        capture_output=True, text=True, check=False, timeout=60,
    )  # fmt: skip
    if result.returncode != 0 or not result.stdout.strip():
        raise ComparatorPinError(f"{environment.name}: the interpreter did not report a version")
    return result.stdout.strip()


def lock_digest(environment: Path) -> str:
    """SHA-256 of the sorted list of installed distributions with their versions (``uv pip freeze``)."""
    result = subprocess.run(
        ["uv", "pip", "freeze", "--python", str(_env_python(environment))],
        capture_output=True, text=True, check=False, timeout=120,
    )  # fmt: skip
    if result.returncode != 0:
        raise ComparatorPinError(f"{environment.name}: the installed packages could not be listed")
    lines = sorted(line.strip() for line in result.stdout.splitlines() if line.strip())
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def build_pin(
    arm_id: str,
    *,
    root: Path = COMPARATORS_DIR,
    native_config: Mapping[str, Any],
    deviations: Sequence[str],
) -> ComparatorPin:
    """Verify the approved checkout and describe the installed comparator as a manifest pin."""
    artifact = approved(arm_id)
    verify_checkout(root / artifact.checkout, artifact.repository, artifact.commit)
    environment = root / artifact.environment
    try:
        return ComparatorPin(
            repository=artifact.repository,
            commit=artifact.commit,
            lock_sha256=lock_digest(environment),
            interpreter=interpreter_version(environment),
            native_config=dict(native_config),
            deviations=tuple(deviations),
        )
    except ManifestError as exc:
        raise ComparatorPinError(str(exc)) from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--root", type=Path, default=COMPARATORS_DIR)
    one = sub.add_parser("pin")
    one.add_argument("arm", choices=sorted(APPROVED))
    one.add_argument("--root", type=Path, default=COMPARATORS_DIR)
    options = parser.parse_args(argv)
    try:
        if options.command == "verify":
            for arm_id, artifact in APPROVED.items():
                verify_checkout(options.root / artifact.checkout, artifact.repository, artifact.commit)
                print(f"{arm_id} {artifact.name}: the checkout is the approved commit")
            return 0
        print(
            json.dumps(build_pin(options.arm, root=options.root, native_config={}, deviations=[]).to_dict(), indent=2)
        )
        return 0
    except ComparatorPinError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
