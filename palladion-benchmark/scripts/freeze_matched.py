"""Choose and freeze the matched lists of the comparison before anything is spent (BADR-0044, B08-T08.09).

    python scripts/freeze_matched.py --root artifacts/fixtures/S --graph-root artifacts/fixtures/Ssub60 \\
        --out artifacts/comparison/matched.json

Track A asks every question of the split; Track B asks a seeded, stratum-balanced subset of the eligible ones, each
assigned the one model every arm will use for it; Track C asks the first episodes outside the locked test split and a
few mutation cases; the graph arms ask the questions of their 60-document subset. The file is written once. It holds
ids and models, never gold.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run_track_c

from benchmark.config import load_all
from benchmark.contracts import ContractError
from benchmark.fixtures.episodes import Episode
from benchmark.matched import MatchedListError, MatchedLists, freeze
from benchmark.track_a import WITHDRAWN, TrackAError, read_annotations, read_withdrawn
from benchmark.track_b import (
    TrackBSpec,
    asked_records,
    eligible_records,
    pick_subset,
    plan_assignment,
)

PROJECT = Path(__file__).resolve().parents[1]
# Five arms at about 2,700 tokens a call (E-B05-005): the share of a model's budget one question uses (BADR-0044).
TOKENS_PER_QUESTION = 14000


def build_lists(options: argparse.Namespace) -> MatchedLists:
    bundle = load_all(PROJECT / "configs")
    seed = bundle.benchmark.default_seed
    withdrawn = read_withdrawn(options.withdrawn)
    records, _ = read_annotations(options.root, options.split)
    track_b = tuple(pick_subset(eligible_records(records, withdrawn), options.track_b_count, seed))
    spec = TrackBSpec(
        "matched", options.split, 10, 4000, options.root, options.out, tokens_per_question=options.tokens_per_question
    )
    generator = replace(
        bundle.benchmark.generator,
        max_completion_tokens=options.max_completion_tokens,
        token_budgets=dict(options.model_budget),
    )
    plan = plan_assignment(asked_records(records, withdrawn, track_b), generator, spec, seed)
    if plan.unassigned:
        raise MatchedListError(f"the model budgets cover {len(plan.assigned)} of {len(track_b)} questions")
    mutations = [m for m in options.mutations.split(",") if m]
    episodes: tuple[Episode, ...] = ()
    if options.episodes or mutations:
        fixture = run_track_c.rebuild_fixture(options.root, bundle)
        episodes = run_track_c.pick_episodes(fixture, options.episodes) if options.episodes else ()
        run_track_c.pick_cases(fixture, mutations)  # refuses a case based on a locked test question
    graph_records, _ = read_annotations(options.graph_root, options.split)
    return MatchedLists(
        seed,
        {
            "track_a": tuple(sorted(r.question_id for r in records)),
            "track_b": track_b,
            "track_c_episodes": tuple(sorted(e.episode_id for e in episodes)),
            "track_c_cases": tuple(sorted(mutations)),
            "graph": tuple(sorted(r.question_id for r in graph_records)),
        },
        dict(plan.assigned),
    )


def _model_budget(text: str) -> tuple[str, int]:
    model, _, tokens = text.rpartition("=")
    if not model or not tokens.isdigit() or int(tokens) < 1:
        raise argparse.ArgumentTypeError("a budget reads MODEL=TOKENS with a positive number")
    return model, int(tokens)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--graph-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--split", default="smoke")
    parser.add_argument("--withdrawn", type=Path, default=WITHDRAWN)
    parser.add_argument("--track-b-count", type=int, default=40)
    parser.add_argument("--tokens-per-question", type=int, default=TOKENS_PER_QUESTION)
    parser.add_argument("--max-completion-tokens", type=int, default=2000)
    parser.add_argument(
        "--model-budget", type=_model_budget, action="append", required=True, metavar="MODEL=TOKENS",
        help="a model's whole-comparison share of Track B tokens; repeat for each approved model",
    )  # fmt: skip
    parser.add_argument("--episodes", type=int, default=2)
    parser.add_argument("--mutations", default="M01,M13,M14")
    options = parser.parse_args(argv)
    try:
        lists = build_lists(options)
        options.out.parent.mkdir(parents=True, exist_ok=True)
        digest = freeze(options.out, lists)
    except (ContractError, TrackAError, run_track_c.TrackCRunError, OSError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    sizes = {name: len(ids) for name, ids in lists.lists.items()}
    models = sorted(set(lists.assignment.values()))
    print(json.dumps({"matched": str(options.out), "sha256": digest, "sizes": sizes, "models": models}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
