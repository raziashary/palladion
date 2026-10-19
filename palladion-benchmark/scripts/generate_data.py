"""Generate the S-tier synthetic fixture: corpus, manifests, pilot questions and a statistics report (B02-T07.01).

Usage (from ``palladion-benchmark/``)::

    uv run python scripts/generate_data.py --tier S --out artifacts/fixtures/S

Everything is fictional and deterministic: the same base seed and tier give the same manifest digest in any process,
time zone or working directory. The fixture is validated before anything is written; a failing check stops the run.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmark.config import FixturesConfig, load_all
from benchmark.fixtures import FICTIONAL_NOTICE, canonical_json, digest_of, to_plain
from benchmark.fixtures.artifacts import build_corpus, plan_from_config
from benchmark.fixtures.audit import build_packet, write_packet
from benchmark.fixtures.documents import measure_corpus
from benchmark.fixtures.knowledge import DocumentState
from benchmark.fixtures.manifest import (
    Namespace,
    Split,
    build_records,
    scan_published,
    snapshot_id,
    verify_published,
    write_annotations,
    write_namespaces,
)
from benchmark.fixtures.question_gen import build_questions
from benchmark.fixtures.validation import validate_fixture
from benchmark.fixtures.world import S_SCALE, build_world, tier_seed

CONFIGS = Path(__file__).resolve().parents[1] / "configs"
CARD = Path(__file__).resolve().parents[1] / "docs" / "dataset_card.md"
CARD_BEGIN, CARD_END = "<!-- BEGIN GENERATED -->", "<!-- END GENERATED -->"
TIER_DIVISOR = {"S": 10}


class GenerationError(RuntimeError):
    """The fixture failed validation or the request cannot be met. The message names the failing check."""


def generate(
    tier: str,
    base_seed: int | None,
    out: Path,
    *,
    overwrite: bool = False,
    audit_packet: bool = False,
    id_secret: str = "",
) -> dict[str, Any]:
    """Build, validate and write one tier. Returns the summary printed by the command line."""
    if tier not in TIER_DIVISOR:
        raise GenerationError(f"tier {tier} is generated in a later phase; only S exists now")
    bundle = load_all(CONFIGS)
    fixtures: FixturesConfig = bundle.fixtures
    seed = bundle.benchmark.default_seed if base_seed is None else base_seed
    world_seed = tier_seed(seed, tier)
    world = build_world(world_seed, S_SCALE)
    drafts = sum(v.state is DocumentState.DRAFT for v in world.knowledge.versions)
    plan = plan_from_config(fixtures, TIER_DIVISOR[tier], authoritative_drafts=drafts)
    tier_config = bundle.benchmark.tiers[tier]
    if plan.total != tier_config.documents:
        raise GenerationError(
            f"plan has {plan.total} documents but the {tier} tier is configured for {tier_config.documents}"
        )
    corpus = build_corpus(world, plan)
    records = build_records(world, corpus, world_seed)
    snapshot = snapshot_id(records)
    targets = {Split.SMOKE: bundle.benchmark.splits.smoke}
    questions = build_questions(world, corpus, snapshot, world_seed, tier, targets, id_secret)
    if len(questions) != tier_config.single_turn_questions:
        raise GenerationError(f"{len(questions)} questions generated, {tier_config.single_turn_questions} configured")
    validation = validate_fixture(world, corpus, questions)
    if not validation.ok:
        detail = "; ".join(f"{f.check}: {f.subject}: {f.detail}" for f in validation.findings[:5])
        raise GenerationError(f"fixture validation failed ({len(validation.findings)} findings): {detail}")
    digests = write_namespaces(out, world, corpus, world_seed, overwrite=overwrite)
    write_annotations(out, Split.SMOKE, [q.to_dict() | {"split": Split.SMOKE.value} for q in questions])
    published = out / Namespace.PUBLISHED.value
    written_problems = verify_published(published) + scan_published(
        published, forbidden=[q.question_id for q in questions]
    )
    if written_problems:
        raise GenerationError(
            f"the written tree failed its readback ({len(written_problems)} problems): {written_problems[0]}"
        )
    if audit_packet:
        write_packet(out, build_packet(questions, corpus, world, world_seed), questions)
    report = measure_corpus(world, corpus)
    summary: dict[str, Any] = {
        "tier": tier,
        "base_seed": seed,
        "world_seed": world_seed,
        "notice": FICTIONAL_NOTICE,
        "documents": report.documents,
        "questions": len(questions),
        "digests": {**digests, "questions_sha256": digest_of([q.to_dict() for q in questions])},
        "corpus": to_plain(report),
        "questions_by_stratum": dict(sorted(Counter(q.stratum.value for q in questions).items())),
        "questions_by_answerability": dict(sorted(Counter(q.answerability.value for q in questions).items())),
        "questions_by_language": dict(sorted(Counter(q.language for q in questions).items())),
        "realism": dict(validation.metrics),
        "validation_findings": len(validation.findings),
        "readback_problems": len(written_problems),
    }
    (out / "generator" / "report.json").write_text(canonical_json(summary) + "\n", encoding="utf-8")
    return summary


def _shares(shares: dict[str, float]) -> str:
    return " / ".join(f"{shares[key]:.1%}" for key in ("en", "id", "mixed"))


def _counted(share: float, count: int) -> str:
    return f"{share:.1%} ({count} documents)"


def render_card_block(summary: dict[str, Any]) -> str:
    """The numeric part of the dataset card, so the card cannot drift from what the script produces."""
    corpus, digests, realism = summary["corpus"], summary["digests"], summary["realism"]
    counts, degree = corpus["counts"], corpus["graph_degree"]
    tokens = f"{corpus['tokens_total']:,} / {corpus['tokens_mean']} / {corpus['tokens_median']}"
    rows = [
        ("Documents", f"{summary['documents']:,}"),
        ("Pilot questions", f"{summary['questions']} (all smoke; none test)"),
        ("Words (whitespace-separated), total / mean / median", tokens),
        ("Language share, tagged (en / id / mixed)", _shares(corpus["language_tagged"])),
        ("Language share, measured from text", _shares(corpus["language_measured"])),
        ("Tagged and measured language agree", f"{corpus['language_agreement']:.1%}"),
        ("Document families / revisions", f"{corpus['families']} / {corpus['revisions']}"),
        ("Near-duplicates, measured", _counted(corpus["near_duplicate_share"], counts["near_duplicate"])),
        ("Stale text, measured", _counted(corpus["stale_share"], counts["stale"])),
        (
            "Unapproved (draft or proposal), from registry state",
            _counted(corpus["unapproved_share"], counts["unapproved"]),
        ),
        ("Injection documents, measured", _counted(corpus["injection_share"], counts["injection"])),
        (
            "Graph degree mean / median / p95 / max",
            " / ".join(str(degree[k]) for k in ("mean", "median", "p95", "max")),
        ),
        ("Identifier-free lexical solvability (ceiling 0.60)", f"{realism['lexical_solvability']:.2f}"),
        ("Sentence-length variation (floor 0.25)", f"{realism['sentence_length_cv']:.2f}"),
        ("Skeleton diversity (floor 0.10)", f"{realism['skeleton_diversity']:.2f}"),
        ("Newest-version rule right on version questions (ceiling 0.30)", f"{realism['naive_newest_correct']:.2f}"),
        ("Oldest-version rule right on version questions (ceiling 0.60)", f"{realism['naive_oldest_correct']:.2f}"),
        ("Corpus manifest SHA-256", digests["corpus_manifest_sha256"]),
        ("Questions SHA-256", digests["questions_sha256"]),
        ("Snapshot id", digests["snapshot_id"]),
    ]
    lines = ["| Measure | Value |", "|---|---|", *(f"| {name} | {value} |" for name, value in rows)]
    strata = ", ".join(f"{k} {v}" for k, v in summary["questions_by_stratum"].items())
    answer = ", ".join(f"{k} {v}" for k, v in summary["questions_by_answerability"].items())
    return "\n".join([*lines, "", f"Questions by stratum: {strata}.", f"Questions by answerability: {answer}."])


def write_card(summary: dict[str, Any], card: Path = CARD) -> None:
    """Replace the generated block of the dataset card, leaving the hand-written text untouched."""
    text = card.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(CARD_BEGIN) + r".*?" + re.escape(CARD_END), re.DOTALL)
    if not pattern.search(text):
        raise GenerationError("the dataset card has no generated block")
    block = f"{CARD_BEGIN}\n{render_card_block(summary)}\n{CARD_END}"
    card.write_text(pattern.sub(lambda _: block, text), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--tier", default="S")
    parser.add_argument("--seed", type=int, default=None, help="base seed; defaults to configs/benchmark.yaml")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--id-secret", default="", help="keys the question ids; use a private value for a locked split")
    parser.add_argument("--audit-packet", action="store_true", help="also write the blinded label-audit packet")
    parser.add_argument("--write-card", action="store_true", help="refresh the generated block of docs/dataset_card.md")
    args = parser.parse_args(argv)
    try:
        summary = generate(
            args.tier,
            args.seed,
            args.out,
            overwrite=args.overwrite,
            audit_packet=args.audit_packet,
            id_secret=args.id_secret,
        )
        if args.write_card:
            write_card(summary)
    except GenerationError as exc:
        print(f"generate_data: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            summary["digests"] | {"documents": summary["documents"], "questions": summary["questions"]}, indent=2
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
