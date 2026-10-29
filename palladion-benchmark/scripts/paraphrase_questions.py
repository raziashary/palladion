"""Write wording variants of a world's questions with a model of another family (B08-T01.02, BADR-0047).

    uv run python scripts/paraphrase_questions.py --root artifacts/fixtures/D11 \
        --generator live --enable-live --call-budget 150 --daily-token-cap 190000

The model sees each question's words and language only: never the gold, the corpus or a system's output. Each rewrite is
judged by ``benchmark.paraphrase`` and the outcomes are appended to ``<out>/paraphrases.jsonl``, so a run a model's
daily limit stopped resumes where it stopped. The key is read from the benchmark-local ``.env`` only for an enabled live
run. Both gpt-oss models are used, one per question by position; qwen, the model Palladion's generator uses, is not.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmark.config import GeneratorSettings, load_benchmark_config
from benchmark.generator import GenerationError, GeneratorPool
from benchmark.paraphrase import MAX_COMPLETION_TOKENS, OutcomeLog, ParaphraseError, Paraphraser, QuestionText, collect
from benchmark.quota import QuotaError, remaining_today
from benchmark.track_a import TrackAError, read_annotations
from benchmark.track_b import make_pool_paths

PROJECT = Path(__file__).resolve().parents[1]
MODELS = ("openai/gpt-oss-120b", "openai/gpt-oss-20b")
ESTIMATED_TOKENS_PER_QUESTION = 450  # the prompt, the reasoning at low effort and the rewrite, from the first dev run


def generator_settings() -> GeneratorSettings:
    """The benchmark's generator settings for this job: the two gpt-oss models, no failover, and a completion cap that
    holds the rewrite (the pool refuses a call above the configured cap)."""
    return replace(
        load_benchmark_config(PROJECT / "configs" / "benchmark.yaml").generator,
        models=MODELS,
        allow_automatic_failover=False,
        max_completion_tokens=MAX_COMPLETION_TOKENS,
    )


def questions_of(root: Path, split: str) -> list[QuestionText]:
    """The words and language of each question, in id order. Everything else of the gold is dropped here."""
    records, _ = read_annotations(root, split)
    return [QuestionText(r.question_id, r.query, r.language) for r in sorted(records, key=lambda r: r.question_id)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, required=True, help="a world's root; only its question file is read")
    parser.add_argument("--split", default="smoke")
    parser.add_argument(
        "--out", type=Path, default=None,
        help="a run directory (its books count against the cap); default artifacts/runs/para-<world>",
    )  # fmt: skip
    parser.add_argument("--generator", choices=["plan", "live"], default="plan", help="plan only counts and estimates")
    parser.add_argument("--enable-live", action="store_true")
    parser.add_argument("--call-budget", type=int, default=None)
    parser.add_argument("--pace-seconds", type=float, default=2.0)
    parser.add_argument("--daily-token-cap", type=int, default=None)
    parser.add_argument("--ledger-root", type=Path, default=PROJECT / "artifacts" / "runs")
    parser.add_argument("--env-file", type=Path, default=PROJECT / ".env")
    options = parser.parse_args(argv)
    options.out = options.out or PROJECT / "artifacts" / "runs" / f"para-{options.root.name}"
    try:
        questions = questions_of(options.root, options.split)
        log = OutcomeLog(options.out / "paraphrases.jsonl")
        todo = [q for q in questions if q.question_id not in log.read()]
        estimate = len(todo) * ESTIMATED_TOKENS_PER_QUESTION
        if options.generator == "plan":
            print(json.dumps({"questions": len(questions), "to_do": len(todo), "estimated_tokens": estimate}, indent=2))
            return 0
        if not options.enable_live or options.call_budget is None or options.daily_token_cap is None:
            print("refused: a live run needs --enable-live, --call-budget and --daily-token-cap", file=sys.stderr)
            return 2
        generator = generator_settings()
        models = {q.question_id: MODELS[i % len(MODELS)] for i, q in enumerate(questions)}
        options.out.mkdir(parents=True, exist_ok=True)
        record_path, prompt_path = make_pool_paths(options.out)
        caps = remaining_today(options.ledger_root, [options.out], MODELS, options.daily_token_cap)
        pool = GeneratorPool.live(
            generator, options.env_file, enabled=True, assignment=models, call_budget=options.call_budget,
            record_path=record_path, prompt_path=prompt_path, pace_seconds=options.pace_seconds, token_caps=caps,
        )  # fmt: skip
        made = Paraphraser(pool, models).run(questions, log)
        result = collect(log)
        print(
            json.dumps(
                {
                    "asked_now": len(made),
                    "counts": dict(result.counts),
                    "accepted": len(result.queries),
                    "digest": result.digest,
                    "quota_blocked": sorted(pool.quota_blocked_models),
                    "tokens_left_before": caps,
                },
                indent=2,
            )
        )
        return 0
    except (ParaphraseError, TrackAError, GenerationError, QuotaError, OSError, ValueError) as exc:
        print(f"refused: {str(exc)[:300]}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
