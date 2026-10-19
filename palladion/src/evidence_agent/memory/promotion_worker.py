"""Explicit bounded local Path B job; independent of answer/provider call budgets."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from evidence_agent.memory.classification import SimilaritySupplement
from evidence_agent.memory.promotion import PromotionEngine
from evidence_agent.memory.sessions import Sessions
from evidence_agent.memory.store import CaseStore
from evidence_agent.retrieval.embeddings import FastEmbedDenseEncoder
from evidence_agent.storage.originals import OriginalStore
from evidence_agent.storage.registry import Registry
from evidence_agent.storage.sqlite import Database

_ENVIRONMENT = {
    "SYSTEMROOT",
    "WINDIR",
    "TEMP",
    "TMP",
    "PATH",
    "PATHEXT",
    "USERPROFILE",
    "LOCALAPPDATA",
    "APPDATA",
    "HOMEDRIVE",
    "HOMEPATH",
    "PROCESSOR_ARCHITECTURE",
    "NUMBER_OF_PROCESSORS",
}


def run_job(
    root: Path,
    principal_id: str,
    case_id: str,
    session_id: str,
    event_ids: list[str],
    *,
    enabled: bool = False,
    timeout_seconds: float = 30,
    cache_dir: Path | None = None,
) -> dict[str, Any]:
    if not enabled:
        raise ValueError("Path B requires explicit enablement")
    if (
        not 0 < timeout_seconds <= 30
        or not 1 <= len(event_ids) <= 8
        or len(set(event_ids)) != len(event_ids)
    ):
        raise ValueError("Path B job bounds")
    payload = json.dumps(
        {
            "root": str(root.resolve()),
            "principal_id": principal_id,
            "case_id": case_id,
            "session_id": session_id,
            "event_ids": event_ids,
            "cache_dir": str((cache_dir or Path.cwd() / "runtime" / "model_cache").resolve()),
        }
    ).encode()
    if len(payload) > 4096:
        raise ValueError("Path B IPC bound")
    environment = {k: v for k, v in os.environ.items() if k.upper() in _ENVIRONMENT}
    environment.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", PYTHONUTF8="1")
    started = time.monotonic()
    try:
        # subprocess.run kills and joins its owned child on timeout, including pipe cleanup.
        result = subprocess.run(
            (sys.executable, "-X", "utf8", "-m", "evidence_agent.memory.promotion_worker"),
            input=payload,
            capture_output=True,
            timeout=timeout_seconds,
            env=environment,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "TIMEOUT",
            "elapsed_seconds": time.monotonic() - started,
            "committed_state": "RECHECK_IDEMPOTENT_LEDGER",
            "provider_calls": 0,
        }
    if result.returncode or len(result.stdout) > 65536:
        return {
            "status": "FAILED",
            "elapsed_seconds": time.monotonic() - started,
            "committed_state": "RECHECK_IDEMPOTENT_LEDGER",
            "provider_calls": 0,
        }
    report: dict[str, Any] = json.loads(result.stdout)
    report["elapsed_seconds"] = time.monotonic() - started
    return report


def main() -> None:
    raw = sys.stdin.buffer.read(4097)
    if len(raw) > 4096:
        raise ValueError("Path B IPC bound")
    payload = json.loads(raw)
    root = Path(payload["root"])
    events = payload["event_ids"]
    if not isinstance(events, list) or not 1 <= len(events) <= 8:
        raise ValueError("Path B event bound")
    with Database(root / "registry.sqlite") as database:
        registry = Registry(database, OriginalStore(root / "originals"))
        principal = registry.access.authenticate(payload["principal_id"])
        session = Sessions(registry, principal, payload["case_id"]).resolve(payload["session_id"])
        store = CaseStore(registry, principal, payload["case_id"], session)
        supplement = SimilaritySupplement(FastEmbedDenseEncoder(Path(payload["cache_dir"])))
        counts = {"processed": 0, "promoted": 0, "omitted_bytes": 0}
        for event_id in events:
            result = PromotionEngine(store, supplement).process(event_id)
            for key in counts:
                counts[key] += result[key]
        report = {
            "status": "COMPLETED",
            "provider_calls": 0,
            "event_count": len(events),
            "max_chunks": 64,
            "max_embedding_calls": 64,
            "embedding_calls": supplement.embedding_calls,
            "embedding_texts": supplement.embedding_texts,
            "profile": supplement.profile if supplement.embedding_calls else None,
            **counts,
        }
        sys.stdout.write(json.dumps(report))


if __name__ == "__main__":
    main()
