"""Score a Track B run directory into a scorecard and a pair table (B05-T08.01).

    uv run python scripts/score_track_b.py --run-dir artifacts/runs/b-stub --root artifacts/fixtures/S

The scorer refuses a run whose ledger has a hole, whose manifests disagree with the gold, the answer-gold or the corpus,
or whose withdrawn questions differ from the list given. It never trusts an answer's own status or citations: both are
recomputed from what the generator was shown. Pairs that did not complete are listed as run states, never as zeros.
Nothing here ranks one arm above another; the scorecard reports counts, denominators and both accountings.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmark.analysis.tables import answer_effects, render_answer_scorecard
from benchmark.config import load_evaluation_config
from benchmark.contracts import ContractError
from benchmark.eval.score_answers import score_answer_run, summarize_arm, sweep_for
from benchmark.eval.score_run import ScoreRunError
from benchmark.eval.statistics import StatisticsError
from benchmark.runner import RunnerError
from benchmark.track_a import WITHDRAWN, TrackAError, read_withdrawn

PROJECT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--withdrawn", type=Path, default=WITHDRAWN)
    parser.add_argument("--reference", default=None, help="arm to pair the others with on both co-primary endpoints")
    parser.add_argument("--primary", default=None, help="the arm whose pairing with the reference was fixed in advance")
    options = parser.parse_args(argv)
    try:
        evaluation = load_evaluation_config(PROJECT / "configs" / "evaluation.yaml")
        score = score_answer_run(
            run_dir=options.run_dir, root=options.root, withdrawn=read_withdrawn(options.withdrawn)
        )
        confidence = evaluation.statistics.confidence
        summaries = [summarize_arm(score, arm, evaluation.loss_matrix, confidence) for arm in score.arms]
        sweep = sweep_for(score, evaluation.loss_matrix, evaluation.loss_sweep_scales)
        effects = (
            answer_effects(score, reference=options.reference, primary=options.primary, stats=evaluation.statistics)
            if options.reference
            else []
        )
        (options.run_dir / "scorecard.md").write_text(
            render_answer_scorecard(score, summaries, sweep, effects), encoding="utf-8"
        )
        table = [
            {
                "arm": p.arm,
                "question_id": p.question_id,
                "stratum": p.stratum,
                "status": p.status.value,
                "code": p.code,
                "correct": None if p.claims is None else p.claims.correct_answer,
                "events": [] if p.abstention is None else [e.value for e in p.abstention.events],
                "flags": list(p.flags),
                "mixed_model": p.mixed_model,
            }
            for p in score.pairs
        ]
        (options.run_dir / "scores.json").write_text(
            json.dumps(
                {
                    "run_id": score.run_id,
                    "k": score.k,
                    "withdrawn": score.withdrawn,
                    "summaries": [asdict(s) for s in summaries],
                    "sweep_conditional": sweep.conditional,
                    "pairs": table,
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
    except (
        ScoreRunError,
        RunnerError,
        TrackAError,
        ContractError,
        StatisticsError,
        OSError,
        KeyError,
        ValueError,
    ) as exc:
        print(f"refused: {str(exc)[:300]}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
