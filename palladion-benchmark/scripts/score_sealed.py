"""Score the confirmatory Track A run: aggregates only (B08-T04.01, BADR-0047).

    uv run python scripts/score_sealed.py --seal artifacts/comparison/seal-track-a.json --tag sealed --condition C2

For each registered world the script reads the run directory ``artifacts/runs/<tag>-<world>-<condition>-r<n>`` of
every repeat, scores it against the world's gold, pools the worlds of the first repeat and writes the pooled table, the
table by stratum and the registered pairings. It writes no per-question file and prints no per-question line: the
coordinator who tuned the systems must not learn from the sealed questions which ones failed. The seal is verified
first; a changed world refuses the scoring, any other change prints EXPLORATORY above every table.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import palladion_runtime
import seal_worlds

from benchmark import seal as sealing
from benchmark.analysis.pooling import Registered, Registration, pool_runs, registered_comparisons, repeat_agreement
from benchmark.analysis.tables import Effect, build_scorecard, render_markdown
from benchmark.config import load_evaluation_config
from benchmark.eval.retrieval import RETRIEVAL_METRICS
from benchmark.eval.score_run import RunScore, ScoreRunError, score_run
from benchmark.eval.statistics import StatisticsError
from benchmark.fixtures.manifest import Layout, Namespace, read_identity
from benchmark.runner import RunnerError
from benchmark.seal import Kind, Seal, SealError
from benchmark.track_a import LOCAL_ARMS, ArmSettings, read_settings

PROJECT = Path(__file__).resolve().parents[1]
RUNS = PROJECT / "artifacts" / "runs"


def score_world(root: Path, run_dir: Path, arms: list[str], k: int) -> RunScore:
    evaluation = load_evaluation_config(PROJECT / "configs" / "evaluation.yaml")
    published = Layout(root).path(Namespace.PUBLISHED)
    return score_run(
        ledger_path=run_dir / "ledger.jsonl",
        manifests={arm: run_dir / f"manifest-{arm}.json" for arm in arms},
        gold_path=Layout(root).path(Namespace.DEV_ANNOTATIONS) / "questions_smoke.jsonl",
        published_dir=published,
        roles={p.principal_id: p.role_id for p in read_identity(published).principals},
        kinds=evaluation.slot_kinds,
        k=k,
        withdrawn={},
    )


def check_binding(run_dir: Path, world: str, sealed: Seal, tuned: dict[str, ArmSettings], arms: list[str]) -> None:
    """Refuse a run that was not made under what the seal fixed: the wording variants and the arm levers."""
    config = json.loads((run_dir / "run_config.json").read_text(encoding="utf-8"))
    if config.get("paraphrase_sha256") != sealed.paraphrases.get(world):
        raise SealError(f"{run_dir.name} used other wording variants than the seal holds for {world}")
    expected = {arm: tuned.get(arm, ArmSettings()).to_dict() for arm in arms if arm in LOCAL_ARMS}
    if config.get("arm_settings") != expected:
        raise SealError(f"{run_dir.name} ran the arms with other settings than the sealed ones")


def render_registered(result: Registered) -> str:
    lines = ["## Registered comparisons (BADR-0047)", ""]
    registration = result.registration
    lines.append(
        f"Primary: {registration.primary_arm} against {registration.reference_arm} on {registration.metric}; the "
        f"claim needs a lower bound above {registration.minimum_effect}."
    )

    def row(label: str, effect: Effect) -> str:
        interval = effect.difference
        low = "n/a" if interval.low is None else f"{interval.low:+.3f}"
        high = "n/a" if interval.high is None else f"{interval.high:+.3f}"
        counts = f"{effect.only_arm} against {effect.only_reference}"
        return (
            f"| {label} | {effect.pairs} | {interval.estimate:+.3f} [{low}, {high}] | {counts} | "
            f"{effect.p_value} | {effect.adjusted_p} |"
        )

    head = f"{registration.primary_arm} - {registration.reference_arm} (primary)"
    lines += [
        "",
        "| pairing | pairs | difference [95% interval] | only the first / only the other | exact p | Holm p |",
        "|---|---|---|---|---|---|",
        row(head, result.primary),
    ]
    lines += [row(f"{registration.primary_arm} - {e.reference}", e) for e in result.secondaries]
    lines += ["", f"**Claim on the primary pairing: {result.claim.value}.**", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--seal", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--condition", choices=["C1", "C2"], default="C2")
    parser.add_argument("--repeats", type=int, default=None, help="default: the registered number for C2, one for C1")
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
            raise SealError("a sealed world changed: the run did not read what was sealed; nothing is scored")
        arms, k = list(registration["arms"]), int(registration["k"])
        roots = seal_worlds.world_roots(registration)
        name = options.condition.lower()
        count = options.repeats or (int(registration["repeats"]) if options.condition == "C2" else 1)
        tuned = read_settings(seal_worlds.FILES["tuned_arms"])
        repeats: list[dict[str, RunScore]] = []
        for n in range(1, count + 1):
            directories = {w: RUNS / f"{options.tag}-{w}-{name}-r{n}" for w in roots}
            for world, directory in directories.items():
                check_binding(directory, world, sealed, tuned, arms)
            repeats.append({w: score_world(roots[w], directories[w], arms, k) for w in roots})
        pooled = [pool_runs(r) for r in repeats]
        stats = load_evaluation_config(PROJECT / "configs" / "evaluation.yaml").statistics
        primary = registration["primary"]
        card = build_scorecard(
            pooled[0], metrics=RETRIEVAL_METRICS, stats=stats, reference=primary["reference"], primary=primary["arm"]
        )
        body = [
            f"# Sealed Track A, {options.condition}, aggregates only",
            "",
            "EXPLORATORY: " + "; ".join(f"{p.kind.value} {p.subject}" for p in problems)
            if problems
            else "Seal intact.",
            "",
            f"Seal {sealed.digest}; worlds {', '.join(roots)}; {len(repeats)} repeat(s); "
            "labels delegated and unaudited by a human.",
            "",
            render_markdown(card),
        ]
        if options.condition == "C2":
            reg = Registration(
                primary["arm"], primary["reference"], tuple(registration["secondary_references"]),
                registration["endpoint"], float(registration["minimum_effect"]),
            )  # fmt: skip
            body.append(render_registered(registered_comparisons(pooled[0], reg, stats)))
        if len(repeats) > 1:
            body += [
                "## Repeats",
                "",
                "| repeat | same documents in the same order as repeat 1, by arm (questions) |",
                "|---|---|",
            ]
            for n, run in enumerate(pooled[1:], start=2):
                same = repeat_agreement(pooled[0], run)
                body.append(f"| {n} | " + ", ".join(f"{arm} {a} of {b}" for arm, (a, b) in same.items()) + " |")
        out = options.out or PROJECT / "artifacts" / "comparison" / f"sealed-track-a-{name}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(body), encoding="utf-8")
        print(json.dumps({"scorecard": str(out), "exploratory": bool(problems), "worlds": len(roots)}))
        return 0
    except (SealError, ScoreRunError, RunnerError, StatisticsError, OSError, KeyError, ValueError) as error:
        print(f"refused: {str(error)[:300]}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
