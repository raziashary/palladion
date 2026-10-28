#!/usr/bin/env python
"""Where a Palladion search spends its time, stage by stage, on the smoke questions (P11-T05, Palladion ADR-0109).

Loads the published corpus into the isolated runtime (or keeps one already loaded), sends every smoke question as the
Track A runner does, and writes the wall time of each stage Palladion reports (``stage_ms``) with the total as the
client saw it. Retrieval only: no model, no quota. The numbers belong to the commit, the corpus and the machine
recorded beside them; they are not a latency claim for anything else.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import palladion_runtime

from benchmark.adapters.common import Condition, PublishedView
from benchmark.adapters.palladion import TABLE_FILE, PalladionArm
from benchmark.fixtures.manifest import Layout, Namespace
from benchmark.track_a import RUNNABLE_SPLITS, build_request, read_annotations


def percentile(values: list[float], share: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(share * len(ordered)))]


def summarise(samples: list[dict[str, float]]) -> dict[str, dict[str, float]]:
    names = sorted({name for sample in samples for name in sample})
    return {
        name: {
            "calls": len(values),
            "mean_ms": round(statistics.fmean(values), 1),
            "p50_ms": round(percentile(values, 0.5), 1),
            "p95_ms": round(percentile(values, 0.95), 1),
        }
        for name in names
        if (values := [sample[name] for sample in samples if name in sample])
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--split", default="smoke", choices=sorted(RUNNABLE_SPLITS))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--mode", default="reranked", choices=("lexical", "dense", "hybrid", "reranked"))
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--keep-loaded", action="store_true", help="use the runtime as it is; do not reset or load")
    options = parser.parse_args(argv)

    view = PublishedView.load(Layout(options.root).path(Namespace.PUBLISHED))
    records, _ = read_annotations(options.root, options.split)
    if not options.keep_loaded:
        palladion_runtime.prepare(reset=True)
    out: dict[str, object] = {"commit": palladion_runtime.PINNED_COMMIT, "mode": options.mode, "k": options.k}
    with palladion_runtime.PalladionRuntime() as server:
        arm = PalladionArm(
            view, server.base_url, palladion_runtime.load_tokens(), mode=options.mode, condition=Condition.C1
        )
        table = options.out.parent / TABLE_FILE
        table.parent.mkdir(parents=True, exist_ok=True)
        if options.keep_loaded:
            arm.read_table(table)
        else:
            began = time.perf_counter()
            arm.load_corpus(table)
            out["load_seconds"] = round(time.perf_counter() - began, 1)
        stages: list[dict[str, float]] = []
        totals: list[float] = []
        for record in records:
            request = build_request(record, view.identity, k=options.k, budget=4000, condition=Condition.C1)
            began = time.perf_counter()
            arm.retrieve(request)
            totals.append((time.perf_counter() - began) * 1000)
            stages.append(dict(arm.last_notes["palladion_stage_ms"]))
    out["questions"] = len(records)
    out["total_ms"] = summarise([{"total": ms} for ms in totals])["total"]
    out["stages"] = summarise(stages)
    options.out.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    print(f"PASS: {len(records)} searches timed at {palladion_runtime.PINNED_COMMIT[:7]}; written to {options.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
