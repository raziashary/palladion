"""Write a matched subset of the S tier for the graph comparators' cold-state pilot (B06-T06.01).

    python scripts/build_subset.py --root artifacts/fixtures/S --out artifacts/fixtures/Ssub -q 16 -d 100

(arguments: the parent snapshot, the new root, the number of questions and the document total; --seed defaults to 7)

The subset has the same layout as the parent snapshot, so every runner, scorer and validator takes it as ``--root``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from benchmark.subset import SubsetError, build_subset  # noqa: E402
from benchmark.track_a import WITHDRAWN, read_withdrawn  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--questions", "-q", type=int, required=True)
    parser.add_argument("--documents", "-d", type=int, required=True)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--withdrawn", type=Path, default=WITHDRAWN)
    options = parser.parse_args(argv)
    try:
        provenance = build_subset(
            options.root, options.out, question_count=options.questions, document_total=options.documents,
            seed=options.seed, withdrawn=read_withdrawn(options.withdrawn),
        )  # fmt: skip
    except SubsetError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(provenance, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
