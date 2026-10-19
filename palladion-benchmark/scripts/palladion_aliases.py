"""Register exact aliases for the corpus loaded into the isolated Palladion (BADR-0027, PALLADION_FIXES A1).

    uv run python scripts/palladion_aliases.py --table artifacts/runs/pilot-c2/index/palladion_revisions.json

Palladion registers aliases only for the sources its own seed loads, so a query naming a code returns nothing for
documents loaded over HTTP (BR24). This step runs ``palladion_alias_job.py`` inside the isolated worktree's
environment, which calls Palladion's own ``Catalog.add_alias``. It edits nothing under ``palladion/`` and writes only
to the runtime root the benchmark owns. The server must be stopped first; a marker file next to the revision table
records what was done so a later run can state, in its manifest, that it ran with aliases.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import palladion_runtime

from benchmark.adapters.palladion import ALIASES_FILE

JOB = Path(__file__).resolve().with_name("palladion_alias_job.py")


class AliasError(RuntimeError):
    """The aliases could not be registered; the message holds no tokens."""


def server_is_up(port: int = palladion_runtime.PORT) -> bool:
    with socket.socket() as probe:
        probe.settimeout(1.0)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def register(table: Path, root: Path = palladion_runtime.RUNTIME_ROOT) -> dict[str, int]:
    if not table.exists():
        raise AliasError("the revision table does not exist; load the corpus first")
    table, root = table.resolve(), root.resolve()  # the job runs in another directory, so paths must be absolute
    if (table.parent / ALIASES_FILE).exists():
        raise AliasError("aliases are already registered for this table")
    if server_is_up():
        raise AliasError("the isolated Palladion is running; stop it before registering aliases")
    app = palladion_runtime.application_dir()
    result = subprocess.run(
        ["uv", "run", "--frozen", "python", str(JOB), str(root), str(table), palladion_runtime.ADMIN],
        cwd=app,
        capture_output=True,
        text=True,
        check=False,
        timeout=1800,
    )
    if result.returncode != 0:
        raise AliasError(f"the alias job failed: {result.stderr.strip().splitlines()[-1:]}")
    stats: dict[str, int] = json.loads(result.stdout.strip().splitlines()[-1])
    marker = {"job_sha256": hashlib.sha256(JOB.read_bytes()).hexdigest(), **stats}
    (table.parent / ALIASES_FILE).write_text(json.dumps(marker, sort_keys=True), encoding="utf-8")
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--table", type=Path, required=True)
    options = parser.parse_args(argv)
    try:
        print(json.dumps(register(options.table), sort_keys=True))
        return 0
    except (AliasError, OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
