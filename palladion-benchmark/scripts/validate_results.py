"""Validate a Track A run directory: schema, budgets, leakage, secrets and hashes (B04-T04.03).

    uv run python scripts/validate_results.py --run-dir artifacts/runs/pilot-c2 --root artifacts/fixtures/S \\
        --env-file .env --tokens-file artifacts/palladion-runtime/demo_auth.json

Exit status: 0 the directory is clean, 1 it has findings (each names a rule and a file, never matched text), 2 a usage
error. ``--env-file`` and ``--tokens-file`` supply values that must appear nowhere in the artifacts; they are read in
memory and never printed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmark.results_check import validate_run
from benchmark.secret_scan import load_env_values


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument("--tokens-file", type=Path, default=None)
    options = parser.parse_args(argv)
    values: list[str] = []
    try:
        if options.env_file is not None:
            values += load_env_values(options.env_file)
        if options.tokens_file is not None:
            mapping = json.loads(options.tokens_file.read_text(encoding="utf-8"))
            values += [str(token) for token in mapping]
    except (OSError, ValueError) as exc:
        print(f"refused: a secrets file could not be read ({type(exc).__name__})", file=sys.stderr)
        return 2
    findings = validate_run(options.run_dir, root=options.root, secret_values=values)
    if findings:
        for finding in findings:
            print(f"FINDING {finding.render()}")
        print(f"FAIL: {len(findings)} finding(s) in {options.run_dir}")
        return 1
    print(f"PASS: {options.run_dir} is complete, consistent and clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
