"""Trusted local synthetic operator control; requires filesystem access to the registry.

This CLI is not a multiuser authentication boundary and is never an LLM tool.
Runtime read tools cannot invoke it. Existing persisted owner/admin checks still apply.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from evidence_agent.memory.store import CaseStore, MemorySpec
from evidence_agent.storage.originals import OriginalStore
from evidence_agent.storage.registry import Registry
from evidence_agent.storage.sqlite import Database


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--principal", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("action", choices=("write", "correct", "revoke", "recall", "team-add", "team-revoke", "close"))
    parser.add_argument("--spec", type=Path, help="MemorySpec JSON; owner supplies validity explicitly")
    parser.add_argument("--id")
    parser.add_argument("--query")
    parser.add_argument("--team")
    parser.add_argument("--member")
    args = parser.parse_args()
    path = args.root / "registry.sqlite"
    if not path.is_file():
        parser.error("Existing explicitly selected synthetic registry required")
    with Database(path) as database:
        registry = Registry(database, OriginalStore(args.root / "originals"))
        store = CaseStore(registry, registry.access.authenticate(args.principal), args.case).memory()
        if args.action in {"write", "correct"}:
            if args.spec is None or args.spec.stat().st_size > 16384:
                parser.error("Bounded --spec JSON required")
            if args.action == "correct" and not args.id:
                parser.error("--id required")
            identifier = store.write(MemorySpec.model_validate_json(args.spec.read_text(encoding="utf-8")),
                supersedes_id=args.id if args.action == "correct" else None)
            print(json.dumps({"memory_id": identifier}))
        elif args.action == "revoke":
            if not args.id:
                parser.error("--id required")
            store.revoke(args.id)
        elif args.action in {"team-add", "team-revoke"}:
            if not args.team or not args.member:
                parser.error("--team and --member required")
            store.team_membership(args.team, args.member, revoke=args.action == "team-revoke")
        elif args.action == "close":
            store.close_case()
        else:
            print(json.dumps(store.recall(query=args.query, memory_id=args.id), indent=2))


if __name__ == "__main__":
    main()
