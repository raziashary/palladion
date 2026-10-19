"""Explicit local cosine supplement; automatic deterministic promotion needs no CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evidence_agent.memory.promotion_worker import run_job


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enable-path-b", action="store_true", required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--principal", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--event", action="append", required=True)
    parser.add_argument("--timeout", type=float, default=30)
    arguments = parser.parse_args()
    report = run_job(
        arguments.root,
        arguments.principal,
        arguments.case,
        arguments.session,
        arguments.event,
        enabled=arguments.enable_path_b,
        timeout_seconds=arguments.timeout,
    )
    print(json.dumps(report, sort_keys=True))
    if report["status"] != "COMPLETED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
