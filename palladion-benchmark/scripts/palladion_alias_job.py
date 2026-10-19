"""Register exact aliases in the benchmark's isolated Palladion runtime (BADR-0027, PALLADION_FIXES A1).

This file runs inside Palladion's own environment (``uv run`` in the isolated worktree), never inside the
benchmark's. It calls Palladion's own ``Catalog.add_alias`` once per chunk and identifier, the way Palladion's seed
does for the sources it loads itself. It reads the revision table the HTTP loader wrote and the chunks Palladion
stored; it never reads gold. Nothing under ``palladion/`` is edited: the only writes go to the runtime root it is given.

    python palladion_alias_job.py RUNTIME_ROOT REVISION_TABLE ADMIN_PRINCIPAL

It prints one JSON line with the counts. The Palladion server must be stopped.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# What Palladion reads as an identifier in a query (storage/exact.py), copied so this file can be tested without it.
IDENTIFIER = re.compile(r"(?<![A-Za-z0-9])(?:[A-Z][A-Z0-9_.]*[-.][A-Z0-9_.-]+)(?![A-Za-z0-9])")


def family_of(doc_id: str) -> str:
    """``POL-001@v2`` belongs to the family ``POL-001``; a document id without a version is its own family."""
    return doc_id.split("@", 1)[0]


def aliases_for(doc_id: str, chunk_text: str) -> list[str]:
    """The family id and every identifier-shaped token in the chunk, once each, in order of appearance."""
    return list(dict.fromkeys([family_of(doc_id), *IDENTIFIER.findall(chunk_text)]))


def main(argv: list[str]) -> int:
    root, table_path, admin_id = Path(argv[1]), Path(argv[2]), argv[3]
    from evidence_agent.storage.catalog import Catalog
    from evidence_agent.storage.originals import OriginalStore
    from evidence_agent.storage.registry import Registry
    from evidence_agent.storage.sqlite import Database

    table = json.loads(table_path.read_text(encoding="utf-8"))
    revisions: dict[str, str] = table["revisions"]
    states: dict[str, str] = table["states"]
    revisions_done = chunks = attempted = 0
    distinct: set[str] = set()
    with Database(root / "registry.sqlite") as database:
        registry = Registry(database, OriginalStore(root / "originals"))
        catalog = Catalog(registry)
        admin = registry.access.authenticate(admin_id)
        for doc_id, revision in sorted(revisions.items()):
            if states.get(doc_id) != "APPROVED":
                continue
            revisions_done += 1
            for chunk in catalog.chunks_for_revision(admin, revision):
                chunks += 1
                for alias in aliases_for(doc_id, chunk.text):
                    catalog.add_alias(admin, alias, revision, chunk.chunk_id)
                    attempted += 1
                    distinct.add(alias)
    print(json.dumps({"revisions": revisions_done, "chunks": chunks, "aliases_attempted": attempted,
                      "distinct_aliases": len(distinct)}))  # fmt: skip
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
