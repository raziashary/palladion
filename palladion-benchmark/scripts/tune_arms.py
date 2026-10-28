"""Tune the benchmark's own arms on the development worlds under one budget for every arm (B08-T02.01, BADR-0047).

    uv run python scripts/tune_arms.py trial --arm R0 --worlds D11,D12 --baseline --trial k1=1.5 --trial b=0.9
    uv run python scripts/tune_arms.py choose --arm R0 --min-gain 0.01 --out configs/tuned_arms.json

``trial`` runs the arm on each development world at C2 (K 10, 4,000 words), pools the worlds, and appends the pooled
intention-to-treat scores to ``artifacts/tuning/tuning_log.jsonl``: the baseline once (free), then one lever per trial,
at most six trials per arm in all. Only development worlds are accepted; a test world is refused by name. ``choose``
reads the log and writes the arm's chosen levers, which stay at the defaults unless a trial beat the baseline by the
margin. Nothing here reads a test world or a model: the arms are retrieval only.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmark.adapters.common import Condition, PublishedView
from benchmark.adapters.dense import DenseArm, Encoder
from benchmark.adapters.hybrid import Reranker
from benchmark.analysis.pooling import pool_runs
from benchmark.analysis.tables import ALL_STRATA, build_scorecard
from benchmark.config import load_all
from benchmark.eval.retrieval import RETRIEVAL_METRICS
from benchmark.eval.score_run import RunScore, score_run
from benchmark.fixtures.manifest import Layout, Namespace, read_identity
from benchmark.track_a import (
    DENSE_ARMS,
    LOCAL_ARMS,
    ArmSettings,
    RunSpec,
    TrackAError,
    build_local_arms,
    execute,
    load_pinned_models,
)
from benchmark.tuning import BASELINE, Trial, TuningError, TuningLog, choose, one_lever

PROJECT = Path(__file__).resolve().parents[1]
FIXTURES = PROJECT / "artifacts" / "fixtures"
LOG = PROJECT / "artifacts" / "tuning" / "tuning_log.jsonl"
INDEXES = PROJECT / "artifacts" / "tuning" / "index"  # embeddings are cached per world, so trials share them
K, BUDGET, SPLIT = 10, 4000, "smoke"
DEVELOPMENT = frozenset({"D11", "D12"})  # the worlds tuning may read; every other world is refused
Models = tuple[Encoder | None, Reranker | None]


def parse_trial(text: str) -> tuple[str, float | int]:
    lever, _, raw = text.partition("=")
    try:
        return lever, int(raw) if raw.lstrip("-").isdigit() else float(raw)
    except ValueError as error:
        raise TuningError(f"{text!r} is not lever=value") from error


def score_world(arm: str, levers: ArmSettings, root: Path, out: Path, models: Models) -> RunScore:
    """Run the arm on one world and return its scored run."""
    bundle = load_all(PROJECT / "configs")
    view = PublishedView.load(Layout(root).path(Namespace.PUBLISHED))
    arms, builds = build_local_arms(
        view, [arm], condition=Condition.C2, index_dir=INDEXES / root.name, encoder=models[0], reranker=models[1],
        settings={arm: levers},
    )  # fmt: skip
    try:
        execute(RunSpec(f"tune-{out.name}", SPLIT, Condition.C2, K, BUDGET, root, out), arms, builds=builds)
    finally:
        for built in arms.values():
            if isinstance(built, DenseArm):
                built.close()
    published = Layout(root).path(Namespace.PUBLISHED)
    return score_run(
        ledger_path=out / "ledger.jsonl",
        manifests={arm: out / f"manifest-{arm}.json"},
        gold_path=Layout(root).path(Namespace.DEV_ANNOTATIONS) / f"questions_{SPLIT}.jsonl",
        published_dir=published,
        roles={p.principal_id: p.role_id for p in read_identity(published).principals},
        kinds=bundle.evaluation.slot_kinds,
        k=K,
        withdrawn={},
    )


def run_trial(arm: str, name: str, levers: ArmSettings, worlds: tuple[str, ...], models: Models) -> Trial:
    """Run one setting on every development world, pool the worlds and return the trial's pooled scores."""
    scored: dict[str, RunScore] = {}
    for world in worlds:
        out = PROJECT / "artifacts" / "runs" / "tune" / f"{arm}-{name.replace('=', '-')}-{world}"
        scored[world] = score_world(arm, levers, FIXTURES / world, out, models)
    pooled = pool_runs(scored)
    card = build_scorecard(pooled, metrics=RETRIEVAL_METRICS, stats=load_all(PROJECT / "configs").evaluation.statistics)
    cells = ((m, card.cell(ALL_STRATA, arm, m).itt) for m in RETRIEVAL_METRICS)
    scores = {metric: itt.estimate for metric, itt in cells if itt is not None}
    return Trial(arm, name, levers.to_dict(), worlds, len(pooled.arm_pairs(arm)), scores)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    trial = sub.add_parser("trial")
    trial.add_argument("--arm", required=True, choices=LOCAL_ARMS)
    trial.add_argument("--worlds", default="D11,D12")
    trial.add_argument("--baseline", action="store_true", help="run the defaults once (not counted in the budget)")
    trial.add_argument("--trial", action="append", default=[], help="lever=value; each is one trial of the budget")
    trial.add_argument("--models-dir", type=Path, default=PROJECT / "artifacts" / "models")
    pick = sub.add_parser("choose")
    pick.add_argument("--arm", required=True, choices=LOCAL_ARMS)
    pick.add_argument("--min-gain", type=float, required=True)
    pick.add_argument("--out", type=Path, required=True)
    options = parser.parse_args(argv)
    log = TuningLog(LOG)
    try:
        if options.command == "choose":
            best = choose(log.read(), options.arm, min_gain=options.min_gain)
            held: dict[str, Mapping[str, float | int]] = (
                json.loads(options.out.read_text(encoding="utf-8")) if options.out.exists() else {}
            )
            defaults = ArmSettings().to_dict()
            held[options.arm] = {k: v for k, v in best.settings.items() if v != defaults[k]}
            options.out.write_text(json.dumps(held, indent=1, sort_keys=True), encoding="utf-8")
            print(json.dumps({"arm": options.arm, "chosen": best.name, "settings": held[options.arm]}))
            return 0
        worlds = tuple(w for w in options.worlds.split(",") if w)
        refused = sorted(set(worlds) - DEVELOPMENT)
        if refused:
            raise TuningError(f"tuning reads development worlds only; refused {', '.join(refused)}")
        models: Models = (
            load_pinned_models(PROJECT / "configs", options.models_dir) if options.arm in DENSE_ARMS else (None, None)
        )
        base = ArmSettings()
        plan = [(BASELINE, base)] if options.baseline else []
        for text in options.trial:
            lever, value = parse_trial(text)
            plan.append((text, ArmSettings.from_dict(one_lever(base.to_dict(), lever, value))))
        for name, levers in plan:
            if name != BASELINE and log.spent(options.arm) >= 6:
                raise TuningError(f"{options.arm} has used its 6 trials")
            result = run_trial(options.arm, name, levers, worlds, models)
            log.append(result)
            print(json.dumps(result.to_dict()))
        return 0
    except (TuningError, TrackAError) as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
