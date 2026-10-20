"""Score a Track A run directory into scorecards and a run-state table (B04-T04.02, BR20).

    uv run python scripts/score_track_a.py --run-dir artifacts/runs/pilot-c2 --root artifacts/fixtures/S --k 10

The scorer refuses a run whose ledger has a hole, whose manifests disagree with the gold, the corpus or K, or whose
published documents changed. Run states are listed beside accuracy, never inside it. Nothing here claims that one arm
is better than another: the scorecard reports counts, intervals and the intention-to-treat accounting only.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmark.analysis.tables import build_scorecard, render_markdown
from benchmark.config import load_evaluation_config
from benchmark.eval.retrieval import RETRIEVAL_METRICS
from benchmark.eval.score_run import ScoreRunError, score_run
from benchmark.fixtures.manifest import Layout, Namespace, read_identity
from benchmark.runner import RunnerError
from benchmark.track_a import RUNNABLE_SPLITS, WITHDRAWN, read_withdrawn

PROJECT = Path(__file__).resolve().parents[1]


def withdrawn_note(withdrawn: Mapping[str, str]) -> str:
    if not withdrawn:
        return ""
    lines = [f"Withdrawn before scoring ({len(withdrawn)}; BADR-0026): every denominator below excludes them.", ""]
    lines += [f"- {question}: {reason}" for question, reason in sorted(withdrawn.items())]
    return "\n".join(lines) + "\n\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--k", type=int, required=True)
    parser.add_argument("--reference", default=None, help="arm to compare the others against")
    parser.add_argument(
        "--withdrawn", type=Path, default=WITHDRAWN, help="questions left out of the scores, with reasons"
    )
    options = parser.parse_args(argv)
    try:
        config = json.loads((options.run_dir / "run_config.json").read_text(encoding="utf-8"))
        split = str(config["split"])
        if split not in RUNNABLE_SPLITS:
            raise ScoreRunError("the split is not runnable by Track A")
        evaluation = load_evaluation_config(PROJECT / "configs" / "evaluation.yaml")
        published = Layout(options.root).path(Namespace.PUBLISHED)
        identity = read_identity(published)
        score = score_run(
            ledger_path=options.run_dir / "ledger.jsonl",
            manifests={arm: options.run_dir / f"manifest-{arm}.json" for arm in config["arms"]},
            gold_path=Layout(options.root).path(Namespace.DEV_ANNOTATIONS) / f"questions_{split}.jsonl",
            published_dir=published,
            roles={p.principal_id: p.role_id for p in identity.principals},
            kinds=evaluation.slot_kinds,
            k=options.k,
            withdrawn=read_withdrawn(options.withdrawn),
        )
        card = build_scorecard(
            score, metrics=RETRIEVAL_METRICS, stats=evaluation.statistics, reference=options.reference
        )
        (options.run_dir / "scorecard.md").write_text(
            withdrawn_note(score.withdrawn) + render_markdown(card), encoding="utf-8"
        )
        (options.run_dir / "scores.json").write_text(
            json.dumps(
                {
                    "run_id": score.run_id,
                    "k": score.k,
                    "withdrawn": score.withdrawn,
                    "pairs": [asdict(p) for p in score.pairs],
                },
                default=str,
                indent=1,
            ),
            encoding="utf-8",
        )
        print(
            f"PASS: {len(score.pairs)} pairs scored for {len(score.arms)} arm(s); "
            f"scorecard in {options.run_dir / 'scorecard.md'}"
        )
        return 0
    except (ScoreRunError, RunnerError, OSError, KeyError, ValueError) as exc:
        print(f"refused: {str(exc)[:300]}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
