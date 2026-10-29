"""Score wording sensitivity of the sealed worlds: aggregates only (BADR-0047).

    uv run python scripts/score_wording.py --seal artifacts/comparison/seal-track-a-variants.json

For each registered world the script scores three runs of the same questions: the original wording (repeat 1 of the
sealed run), the same questions in the accepted rewrites (``variants-<world>-c2-r1``) and, as a control for what running
the original questions again does, repeat 2 of the sealed run. All three are restricted to the questions that have an
accepted rewrite. It pools the worlds and prints, per system, the share of questions where the complete set was found in
each wording and the paired difference with a family-clustered interval, then the same for the control. No question, no
per-question value and no rewrite is printed or written. It claims nothing: a rewrite can change meaning in ways the
equivalence check does not read.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import palladion_runtime
import score_sealed
import seal_worlds

from benchmark import seal as sealing
from benchmark.analysis.pooling import pool_runs
from benchmark.analysis.wording import Sensitivity, change_share, compare
from benchmark.config import load_evaluation_config
from benchmark.eval.score_run import RunScore, ScoreRunError
from benchmark.eval.statistics import StatisticsError
from benchmark.paraphrase import OutcomeLog, collect
from benchmark.runner import RunnerError
from benchmark.seal import Kind, Seal, SealError
from benchmark.track_a import TrackAError, read_annotations, read_settings

PROJECT = Path(__file__).resolve().parents[1]
RUNS = PROJECT / "artifacts" / "runs"
METRIC = "complete_set_at_k"


def render(title: str, rows: Sequence[Sensitivity], first: str, second: str) -> str:
    lines = [
        f"## {title}",
        "",
        f"| system | questions | {first} | {second} | difference [95% interval] | only {second} / only {first} |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        interval = row.effect.difference
        low = "n/a" if interval.low is None else f"{interval.low:+.3f}"
        high = "n/a" if interval.high is None else f"{interval.high:+.3f}"
        lines.append(
            f"| {row.arm} | {row.questions} | {row.original:.3f} | {row.variant:.3f} | "
            f"{interval.estimate:+.3f} [{low}, {high}] | {row.effect.only_arm} / {row.effect.only_reference} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--seal", type=Path, required=True)
    parser.add_argument("--original-tag", default="sealed")
    parser.add_argument("--variant-tag", default="variants")
    parser.add_argument("--out", type=Path, default=None)
    options = parser.parse_args(argv)
    try:
        registration = seal_worlds.read_registration()
        sealed = Seal.load(options.seal)
        problems = sealing.verify(
            sealed, worlds=seal_worlds.world_roots(registration), files=seal_worlds.FILES, project=seal_worlds.PROJECT,
            code_paths=seal_worlds.CODE_PATHS, system=palladion_runtime.application_dir(),
            paraphrases=seal_worlds.paraphrase_digests(registration),
        )  # fmt: skip
        if any(p.kind is Kind.WORLD_CHANGED for p in problems):
            raise SealError("a sealed world changed: nothing is scored")
        arms, k = list(registration["arms"]), int(registration["k"])
        roots, tuned = seal_worlds.world_roots(registration), read_settings(seal_worlds.FILES["tuned_arms"])
        originals: dict[str, RunScore] = {}
        variants: dict[str, RunScore] = {}
        controls: dict[str, RunScore] = {}
        rewrites = 0
        shares: list[float] = []
        for world, root in roots.items():
            made = collect(OutcomeLog(RUNS / f"para-{world}" / "paraphrases.jsonl"))
            records, _ = read_annotations(root, "smoke")
            left_out = {r.question_id: "no accepted rewrite" for r in records if r.question_id not in made.queries}
            first = RUNS / f"{options.original_tag}-{world}-c2-r1"
            other = RUNS / f"{options.variant_tag}-{world}-c2-r1"
            repeat = RUNS / f"{options.original_tag}-{world}-c2-r2"
            for directory in (first, repeat):
                score_sealed.check_binding(directory, world, _unvariant(sealed), tuned, arms)
            score_sealed.check_binding(other, world, sealed, tuned, arms)
            originals[world] = score_sealed.score_world(root, first, arms, k, left_out)
            variants[world] = score_sealed.score_world(root, other, arms, k, left_out)
            controls[world] = score_sealed.score_world(root, repeat, arms, k, left_out)
            by_id = {r.question_id: r.query for r in records}
            rewrites += len(made.queries)
            shares += [change_share(by_id[q], text) for q, text in made.queries.items()]
        stats = load_evaluation_config(PROJECT / "configs" / "evaluation.yaml").statistics
        pooled = {name: pool_runs(runs) for name, runs in (("o", originals), ("v", variants), ("c", controls))}
        body = [
            "# Wording sensitivity, aggregates only",
            "",
            "EXPLORATORY: " + "; ".join(f"{p.kind.value} {p.subject}" for p in problems)
            if problems
            else "Seal intact.",
            "",
            f"Seal {sealed.digest}; {len(roots)} worlds; condition C2; {rewrites} accepted rewrites; on average "
            f"{100 * sum(shares) / max(len(shares), 1):.0f}% of the words of a question differ from its rewrite "
            "(Jaccard distance over words). No claim: a rewrite can change meaning in ways the check does not read.",
            "",
            render(
                "Same questions, rewritten (variant minus original)",
                compare(pooled["o"], pooled["v"], arms, METRIC, stats),
                "original",
                "variant",
            ),
            render(
                "Control: the original questions run again (repeat 2 minus repeat 1)",
                compare(pooled["o"], pooled["c"], arms, METRIC, stats),
                "repeat 1",
                "repeat 2",
            ),
        ]
        out = options.out or PROJECT / "artifacts" / "comparison" / "wording-sensitivity.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(body), encoding="utf-8")
        print(json.dumps({"card": str(out), "exploratory": bool(problems), "rewrites": rewrites}))
        return 0
    except (
        SealError,
        ScoreRunError,
        RunnerError,
        StatisticsError,
        TrackAError,
        OSError,
        KeyError,
        ValueError,
    ) as error:
        print(f"refused: {str(error)[:300]}", file=sys.stderr)
        return 2


def _unvariant(sealed: Seal) -> Seal:
    """The sealed record as it stood for the original runs, which used no wording variants."""
    return Seal(
        sealed.purpose, sealed.created_at_utc, sealed.worlds, sealed.files, sealed.trees, sealed.registration,
        sealed.settings, {},
    )  # fmt: skip


if __name__ == "__main__":
    raise SystemExit(main())
