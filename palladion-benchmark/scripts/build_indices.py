"""Build the Track A indexes from the published namespace and record what the build cost (B04-T04.01).

    uv run python scripts/build_indices.py --published artifacts/fixtures/S/published --index-dir artifacts/index/S

The corpus argument is the published directory itself, never the snapshot root: a directory that holds annotation or
generator material is refused. Each arm's build is recorded (time, sizes, tokens, extraction failures); a build that
fails is recorded as FAILED and makes the exit status 1 after the report is written. Only common-chunk mode exists;
native ingestion of the other arms is deferred (BADR-0025). The dense arms need the Qdrant server of
``scripts/qdrant_server.py`` (``--start-qdrant`` starts and stops it) and the pinned models already downloaded.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmark.adapters.common import AdapterError, Condition, PublishedView, build_chunks
from benchmark.adapters.dense import DEFAULT_URL
from benchmark.config import load_all
from benchmark.track_a import LOCAL_ARMS, TrackAError, build_local_arms, load_pinned_models

PROJECT = Path(__file__).resolve().parents[1]
REPORT = "index_report.json"


def corpus_facts(view: PublishedView) -> dict[str, Any]:
    """What the published namespace holds, so a build can be compared with it: documents, chunks, words, failures."""
    chunks = build_chunks(view)
    unreadable = [d.record.doc_id for d in view.documents() if not d.text.strip()]
    return {
        "documents": len(view.records),
        "chunks": len(chunks),
        "words": sum(c.words for c in chunks),
        "characters": sum(c.characters for c in chunks),
        "extraction_failures": unreadable,
        "tables_lost": 0,
        "tables_lost_basis": "no table parser exists: pipe tables stay as text, so none can be lost by parsing",
        "note": "documents are Markdown text with pipe tables kept as text; nothing is parsed away",
    }


def run_qdrant(command: str) -> int:
    script = str(PROJECT / "scripts" / "qdrant_server.py")
    args = [sys.executable, script, command] + (["--detach"] if command == "start" else [])
    return subprocess.run(args, check=False, capture_output=True, text=True, timeout=180).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--published", type=Path, required=True)
    parser.add_argument("--index-dir", type=Path, required=True)
    parser.add_argument("--arms", default=",".join(LOCAL_ARMS))
    parser.add_argument("--condition", choices=[c.value for c in Condition], default=Condition.C2.value)
    parser.add_argument("--qdrant-url", default=DEFAULT_URL)
    parser.add_argument(
        "--start-qdrant", action="store_true", help="start the benchmark's Qdrant and stop it afterwards"
    )
    parser.add_argument("--models-dir", type=Path, default=PROJECT / "artifacts" / "models")
    options = parser.parse_args(argv)
    arms = [a for a in options.arms.split(",") if a]
    started = False
    try:
        view = PublishedView.load(options.published)
        needs_models = any(a in ("R1", "R2", "R3") for a in arms)
        encoder, reranker = (
            load_pinned_models(PROJECT / "configs", options.models_dir) if needs_models else (None, None)
        )
        if options.start_qdrant and needs_models:
            if run_qdrant("start") != 0:
                print("refused: the benchmark's Qdrant could not be started", file=sys.stderr)
                return 2
            started = True
        built, records = build_local_arms(
            view, arms, condition=Condition(options.condition), index_dir=options.index_dir,
            qdrant_url=options.qdrant_url, encoder=encoder, reranker=reranker,
            expected_qdrant=load_all(PROJECT / "configs").comparators.shared_models["qdrant_server"].value,
        )  # fmt: skip
        report = {"corpus": corpus_facts(view), "condition": options.condition, "arms": records}
        options.index_dir.mkdir(parents=True, exist_ok=True)
        (options.index_dir / REPORT).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        failed = [r["arm"] for r in records if r["status"] != "BUILT"]
        for record in records:
            print(f"{record['arm']}: {record['status']}")
        for arm in built.values():
            close = getattr(arm, "close", None)
            if callable(close):
                close()
        if failed:
            print(f"FAIL: {', '.join(failed)} could not be built; see {REPORT}", file=sys.stderr)
            return 1
        print(f"PASS: {len(records)} arm(s) built; report in {options.index_dir / REPORT}")
        return 0
    except (AdapterError, TrackAError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    finally:
        if started:
            run_qdrant("stop")


if __name__ == "__main__":
    raise SystemExit(main())
