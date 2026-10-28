"""Create or verify the seal of the confirmatory Track A run (B08-T03.01, BADR-0047).

    uv run python scripts/seal_worlds.py create --out artifacts/comparison/seal-track-a.json
    uv run python scripts/seal_worlds.py verify --seal artifacts/comparison/seal-track-a.json

The seal hashes the six test worlds' files, the registration, the configuration, the tuned arm settings, the wording
variants, the benchmark's code and the pinned Palladion tree. It is stored outside the sealed code (under artifacts/) so
that writing it does not change what it seals; its own hash is recorded in the decision log. ``verify`` lists every
difference and exits 1 if there is one: a changed world means the run did not read what was sealed, anything else that
changed makes the result exploratory. No test file is opened, only hashed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import palladion_runtime

from benchmark import seal as sealing
from benchmark.paraphrase import OutcomeLog, collect
from benchmark.seal import Seal, SealError

PROJECT = Path(__file__).resolve().parents[1]
REGISTRATION = PROJECT / "configs" / "registration_track_a.json"
CODE_PATHS = ("benchmark", "scripts", "configs", "pyproject.toml", "uv.lock")
FILES = {
    "registration": REGISTRATION,
    "preregistration_text": PROJECT / "docs" / "development" / "PREREGISTRATION_TRACK_A.md",
    "comparators": PROJECT / "configs" / "comparators.yaml",
    "benchmark": PROJECT / "configs" / "benchmark.yaml",
    "evaluation": PROJECT / "configs" / "evaluation.yaml",
    "tuned_arms": PROJECT / "configs" / "tuned_arms.json",
}


def read_registration() -> dict[str, Any]:
    return dict(json.loads(REGISTRATION.read_text(encoding="utf-8")))


def world_roots(registration: dict[str, Any]) -> dict[str, Path]:
    return {name: PROJECT / "artifacts" / "fixtures" / name for name in registration["worlds"]}


def paraphrase_digests(registration: dict[str, Any]) -> dict[str, str]:
    """The digest of each world's accepted wording variants, for the worlds that have a log."""
    found: dict[str, str] = {}
    for name in registration["worlds"]:
        log = OutcomeLog(PROJECT / "artifacts" / "runs" / f"para-{name}" / "paraphrases.jsonl")
        if log.path.exists():
            found[name] = collect(log).digest
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--out", type=Path, required=True)
    check = sub.add_parser("verify")
    check.add_argument("--seal", type=Path, required=True)
    options = parser.parse_args(argv)
    registration = read_registration()
    try:
        common: dict[str, Any] = {
            "worlds": world_roots(registration),
            "files": FILES,
            "project": PROJECT,
            "code_paths": CODE_PATHS,
            "system": palladion_runtime.application_dir(),
        }
        if options.command == "create":
            settings = {key: registration[key] for key in ("arms", "k", "budget_words", "condition", "repeats")}
            sealed = sealing.create(
                purpose=registration["scope"], registration=registration, settings=settings,
                paraphrases=paraphrase_digests(registration), **common,
            )  # fmt: skip
            digest = sealed.write(options.out)
            print(json.dumps({"seal": str(options.out), "sha256": digest, "worlds": sorted(sealed.worlds)}))
            return 0
        problems = sealing.verify(
            Seal.load(options.seal), paraphrases=paraphrase_digests(registration), **common
        )  # fmt: skip
        for problem in problems:
            print(f"{problem.kind.value}: {problem.subject}", file=sys.stderr)
        print(json.dumps({"intact": not problems, "problems": len(problems)}))
        return 1 if problems else 0
    except (SealError, OSError, KeyError, ValueError) as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
