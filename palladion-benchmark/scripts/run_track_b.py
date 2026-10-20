"""Run Track B: retrievers composed with the shared generator, through the real Runner (B05-T05.01).

    uv run python scripts/run_track_b.py --root artifacts/fixtures/S --split smoke --out artifacts/runs/b-stub \\
        --run-id b-stub --arms R2,R3 --generator stub --start-qdrant

The default generator is the offline stand-in, which makes no provider call and says nothing about any model. A live
run needs ``--generator live --enable-live`` and an explicit ``--call-budget``; the benchmark-local ``.env`` is read
only then, and the owner's authorization for live use is a separate decision (BADR-0028). Questions the label audit
withdrew are not asked, and the locked test split is refused.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import palladion_runtime
import run_track_a

from benchmark.adapters.common import AdapterError, Condition, PublishedView
from benchmark.adapters.dense import DEFAULT_URL
from benchmark.config import load_benchmark_config
from benchmark.eval.normalize import PublishedCorpus
from benchmark.fixtures.manifest import Layout, Namespace
from benchmark.generator import GenerationError, GeneratorPool
from benchmark.run_manifest import tree_state
from benchmark.runner import RunnerError
from benchmark.track_a import (
    WITHDRAWN,
    DescribedArm,
    TrackAError,
    build_local_arms,
    load_pinned_models,
    read_annotations,
    read_withdrawn,
)
from benchmark.track_b import (
    TOKENS_PER_QUESTION,
    ExtractiveStubTransport,
    TrackBSpec,
    asked_records,
    eligible_records,
    execute_track_b,
    make_pool_paths,
    pick_subset,
    plan_assignment,
)

PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_COMPLETION_TOKENS = 700


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--split", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--index-dir", type=Path, default=None)
    parser.add_argument("--arms", default="R2,R3")
    parser.add_argument("--condition", choices=[c.value for c in Condition], default=Condition.C2.value)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--budget", type=int, default=4000, help="evidence budget in whitespace words")
    parser.add_argument("--generator", choices=["stub", "live"], default="stub")
    parser.add_argument(
        "--enable-live", action="store_true", help="allow provider calls (needs the owner's authorization)"
    )
    parser.add_argument("--env-file", type=Path, default=PROJECT / ".env")
    parser.add_argument("--call-budget", type=int, default=None, help="hard cap on provider calls for a live run")
    parser.add_argument("--max-completion-tokens", type=int, default=DEFAULT_COMPLETION_TOKENS)
    parser.add_argument("--tokens-per-question", type=int, default=TOKENS_PER_QUESTION)
    parser.add_argument("--withdrawn", type=Path, default=WITHDRAWN)
    parser.add_argument("--limit-questions", type=int, default=None, help="ask a seeded, stratum-balanced subset")
    parser.add_argument(
        "--allow-failover", action="store_true", help="on a rate limit move down the approved model list (recorded)"
    )
    parser.add_argument("--pace-seconds", type=float, default=0.0, help="minimum time between provider calls")
    parser.add_argument("--case-deadline-seconds", type=float, default=None, help="replaces the configured deadline")
    parser.add_argument("--qdrant-url", default=DEFAULT_URL)
    parser.add_argument("--start-qdrant", action="store_true")
    parser.add_argument("--palladion", action="store_true", help="add R7a over the isolated Palladion runtime")
    parser.add_argument("--palladion-mode", choices=["lexical", "dense", "hybrid", "reranked"], default="hybrid")
    parser.add_argument("--load-palladion", action="store_true")
    parser.add_argument("--models-dir", type=Path, default=PROJECT / "artifacts" / "models")
    options = parser.parse_args(argv)
    live = options.generator == "live"
    if live and (not options.enable_live or options.call_budget is None):
        print("refused: a live run needs --enable-live and an explicit --call-budget", file=sys.stderr)
        return 2
    if options.enable_live and not live:
        print("refused: --enable-live applies only with --generator live", file=sys.stderr)
        return 2
    condition = Condition(options.condition)
    arms = [a for a in options.arms.split(",") if a]
    index_dir = options.index_dir or options.out / "index"
    started = False
    runtime: palladion_runtime.PalladionRuntime | None = None
    try:
        view = PublishedView.load(Layout(options.root).path(Namespace.PUBLISHED))
        corpus = PublishedCorpus.load(view.root)
        encoder, reranker = (
            load_pinned_models(PROJECT / "configs", options.models_dir)
            if any(a in ("R1", "R2", "R3") for a in arms)
            else (None, None)
        )
        if options.start_qdrant and encoder is not None:
            if run_track_a.run_qdrant("start") != 0:
                print("refused: the benchmark's Qdrant could not be started", file=sys.stderr)
                return 2
            started = True
        local, builds = build_local_arms(
            view, arms, condition=condition, index_dir=index_dir, qdrant_url=options.qdrant_url,
            encoder=encoder, reranker=reranker, expected_qdrant=run_track_a.qdrant_pin(),
        )  # fmt: skip
        retrievers: dict[str, DescribedArm] = dict(local)
        trees = {}
        if options.palladion:
            runtime = palladion_runtime.PalladionRuntime(rerank=options.palladion_mode == "reranked")
            retrievers["R7a"] = run_track_a.palladion_arm(view, runtime, options, condition, index_dir, builds)
            trees["R7a"] = tree_state(palladion_runtime.application_dir(), label="palladion")
        benchmark_config = load_benchmark_config(PROJECT / "configs" / "benchmark.yaml")
        generator = replace(
            benchmark_config.generator,
            max_completion_tokens=options.max_completion_tokens,
            allow_automatic_failover=options.allow_failover or benchmark_config.generator.allow_automatic_failover,
        )
        withdrawn = read_withdrawn(options.withdrawn)
        records, _ = read_annotations(options.root, options.split)
        seed = benchmark_config.default_seed
        subset = (
            None
            if options.limit_questions is None
            else tuple(pick_subset(eligible_records(records, withdrawn), options.limit_questions, seed))
        )
        spec = TrackBSpec(
            options.run_id, options.split, options.k, options.budget, options.root, options.out,
            condition=condition.value, live=live, tokens_per_question=options.tokens_per_question, withdrawn=withdrawn,
            question_ids=subset, case_deadline_seconds=options.case_deadline_seconds, pace_seconds=options.pace_seconds,
        )  # fmt: skip
        plan = plan_assignment(asked_records(records, withdrawn, subset), generator, spec, seed)
        options.out.mkdir(parents=True, exist_ok=True)
        record_path, prompt_path = make_pool_paths(options.out)
        pool: GeneratorPool
        if live:
            pool = GeneratorPool.live(
                generator, options.env_file, enabled=True, assignment=dict(plan.assigned),
                call_budget=int(options.call_budget or 0), record_path=record_path, prompt_path=prompt_path,
                pace_seconds=options.pace_seconds,
            )  # fmt: skip
            label = "groq"
        else:
            pool = GeneratorPool(
                generator, ExtractiveStubTransport(), enabled=True, assignment=dict(plan.assigned),
                call_budget=10_000_000, record_path=record_path, prompt_path=prompt_path,
            )  # fmt: skip
            label = "offline-stub"
        outcome = execute_track_b(spec, retrievers, pool, plan, corpus, generator, pool_label=label, system_trees=trees)
        print(
            json.dumps(
                {
                    "run_dir": str(outcome.run_dir),
                    "questions": outcome.questions,
                    "arms": outcome.arms,
                    "unassigned": len(outcome.unassigned),
                    "generator": label,
                    "status_counts": dict(outcome.summary.status_counts),
                },
                indent=2,
            )
        )
        return 0
    except (AdapterError, TrackAError, GenerationError, RunnerError, palladion_runtime.PalladionRuntimeError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    finally:
        if runtime is not None:
            runtime.stop()
        if started:
            run_track_a.run_qdrant("stop")


if __name__ == "__main__":
    raise SystemExit(main())
