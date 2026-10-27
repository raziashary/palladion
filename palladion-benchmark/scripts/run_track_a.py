"""Run Track A arms on a split through the real Runner and write a run directory (B04-T04.02).

    uv run python scripts/run_track_a.py --root artifacts/fixtures/S --split smoke --out artifacts/runs/pilot-c2 \\
        --run-id pilot-c2 --k 10 --budget 4000 --condition C2 --start-qdrant

The questions come from the split's own annotation file and the locked test split is refused. Every arm runs every
question with intention-to-treat accounting; an arm that cannot run stays in the ledger as a run state with its reason.
``--palladion`` adds R7a, which needs the isolated runtime (``scripts/palladion_runtime.py prepare``) and a corpus
loaded into it; ``--load-palladion`` does that once, before the first run, and writes the revision table next
to the index.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import palladion_runtime

from benchmark import matched as matched_lists
from benchmark.adapters.common import AdapterError, Condition, PublishedView
from benchmark.adapters.dense import DEFAULT_URL
from benchmark.adapters.palladion import CASE, TABLE_FILE, PalladionArm, PrincipalMap
from benchmark.config import load_all
from benchmark.fixtures.manifest import Layout, Namespace
from benchmark.matched import MatchedListError
from benchmark.run_manifest import tree_state
from benchmark.track_a import (
    LOCAL_ARMS,
    DescribedArm,
    RunSpec,
    TrackAError,
    UnavailableArm,
    build_local_arms,
    execute,
    load_pinned_models,
    read_annotations,
)

PROJECT = Path(__file__).resolve().parents[1]


def qdrant_pin() -> str:
    return load_all(PROJECT / "configs").comparators.shared_models["qdrant_server"].value


def run_qdrant(command: str) -> int:
    script = str(PROJECT / "scripts" / "qdrant_server.py")
    args = [sys.executable, script, command] + (["--detach"] if command == "start" else [])
    return subprocess.run(args, check=False, capture_output=True, text=True, timeout=180).returncode


def palladion_arm(
    view: PublishedView,
    runtime: palladion_runtime.PalladionRuntime,
    options: argparse.Namespace,
    condition: Condition,
    index_dir: Path,
    builds: list[dict[str, Any]],
) -> DescribedArm:
    """R7a over the isolated runtime. A setup failure is recorded; R7a stays in the run as not run, with its reason."""
    try:
        principals = PrincipalMap()
        if condition is Condition.C2:  # a reader per benchmark principal; a server reads its tokens when it starts
            with palladion_runtime.PalladionRuntime(rerank=False) as provisioning:
                issued = palladion_runtime.provision_readers(
                    provisioning.base_url, [p.principal_id for p in view.identity.principals], case_id=CASE
                )
            principals = PrincipalMap(overrides={key: (reader, CASE) for key, (reader, _) in issued.items()})
        runtime.start()
        arm = PalladionArm(
            view, runtime.base_url, palladion_runtime.load_tokens(), mode=options.palladion_mode, condition=condition,
            principals=principals,
        )  # fmt: skip
        table = index_dir / TABLE_FILE
        index_dir.mkdir(parents=True, exist_ok=True)
        record: dict[str, Any] = {"arm": "R7a", "status": "BUILT"}
        if options.load_palladion:
            report = arm.load_corpus(table)
            record["load"] = {"uploaded": report.uploaded, "approved": report.approved, "revoked": report.revoked}
        arm.read_table(table)
        record["verify"] = arm.verify_load()
        record["acl"] = arm.verify_acl()
        arm.build_index(str(view.root), "track_a")
        builds.append(record)
        return arm
    except (AdapterError, palladion_runtime.PalladionRuntimeError, OSError, ValueError) as exc:
        reason = f"R7a setup failed: {type(exc).__name__}"
        builds.append({"arm": "R7a", "status": "FAILED", "error": type(exc).__name__, "reason": str(exc)[:200]})
        return UnavailableArm("R7a", reason)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--root", type=Path, required=True, help="snapshot root; only published/ and the split's file are read"
    )
    parser.add_argument("--split", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--index-dir", type=Path, default=None)
    parser.add_argument("--arms", default=",".join(LOCAL_ARMS))
    parser.add_argument("--condition", choices=[c.value for c in Condition], default=Condition.C2.value)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--budget", type=int, default=4000, help="evidence budget in whitespace words")
    parser.add_argument("--qdrant-url", default=DEFAULT_URL)
    parser.add_argument("--start-qdrant", action="store_true")
    parser.add_argument("--palladion", action="store_true", help="add R7a over the isolated Palladion runtime")
    parser.add_argument("--palladion-mode", choices=["lexical", "dense", "hybrid", "reranked"], default="hybrid")
    parser.add_argument("--load-palladion", action="store_true", help="load the corpus into Palladion first (once)")
    parser.add_argument("--models-dir", type=Path, default=PROJECT / "artifacts" / "models")
    parser.add_argument("--matched-list", type=Path, default=None, help="the frozen lists this run must match")
    options = parser.parse_args(argv)
    condition = Condition(options.condition)
    arms = [a for a in options.arms.split(",") if a]
    index_dir = options.index_dir or options.out / "index"
    started = False
    runtime: palladion_runtime.PalladionRuntime | None = None
    try:
        view = PublishedView.load(Layout(options.root).path(Namespace.PUBLISHED))
        needs_models = any(a in ("R1", "R2", "R3") for a in arms)
        encoder, reranker = (
            load_pinned_models(PROJECT / "configs", options.models_dir) if needs_models else (None, None)
        )
        if options.start_qdrant and needs_models:
            if run_qdrant("start") != 0:
                print("refused: the benchmark's Qdrant could not be started", file=sys.stderr)
                return 2
            started = True
        adapters: dict[str, DescribedArm] = {}
        local, builds = build_local_arms(
            view, arms, condition=condition, index_dir=index_dir, qdrant_url=options.qdrant_url,
            encoder=encoder, reranker=reranker, expected_qdrant=qdrant_pin(),
        )  # fmt: skip
        adapters.update(local)
        trees = {}
        if options.palladion:
            runtime = palladion_runtime.PalladionRuntime(rerank=options.palladion_mode == "reranked")
            adapters["R7a"] = palladion_arm(view, runtime, options, condition, index_dir, builds)
            trees["R7a"] = tree_state(palladion_runtime.application_dir(), label="palladion")
        matched = matched_lists.load(options.matched_list) if options.matched_list else None
        if matched is not None:
            asked = [r.question_id for r in read_annotations(options.root, options.split)[0]]
            matched.require("track_a", asked)
        spec = RunSpec(
            options.run_id, options.split, condition, options.k, options.budget, options.root, options.out,
            matched_list_sha256=matched.digest if matched else None,
        )  # fmt: skip
        outcome = execute(spec, adapters, builds=builds, system_trees=trees)
        print(json.dumps({"run_dir": str(outcome.run_dir), "questions": outcome.questions, "arms": outcome.arms,
                          "status_counts": dict(outcome.summary.status_counts)}, indent=2))  # fmt: skip
        return 0
    except (AdapterError, TrackAError, MatchedListError, palladion_runtime.PalladionRuntimeError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    finally:
        if runtime is not None:
            runtime.stop()
        if started:
            run_qdrant("stop")


if __name__ == "__main__":
    raise SystemExit(main())
