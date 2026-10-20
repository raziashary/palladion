"""Track B scoring and validation: a clean run passes and is scored, each planted defect is rejected for its reason."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from support import citation_text, perfect_response
from test_track_b import GoldRetriever, make_pool

from benchmark.analysis.tables import render_answer_scorecard
from benchmark.config import load_evaluation_config
from benchmark.contracts import RunStatus
from benchmark.eval.normalize import PublishedCorpus
from benchmark.eval.score_answers import (
    INVALID_ANSWER,
    delivered_from_ids,
    score_answer_run,
    summarize_arm,
    sweep_for,
)
from benchmark.eval.score_run import ScoreRunError
from benchmark.fixtures.answer_gold import AnswerGold
from benchmark.fixtures.questions import GoldRecord
from benchmark.generator import TransportResponse
from benchmark.results_check import Finding, validate_run
from benchmark.runner import RunnerError
from benchmark.track_b import ExtractiveStubTransport, TrackBSpec, eligible_records, execute_track_b, plan_assignment

ROOT = Path(__file__).resolve().parents[1]
GENERATOR_MODEL = "offline-stub"


class PerfectTransport:
    """A test-only generator that returns each question's gold answer, citing only what the prompt delivered."""

    def __init__(self, records: tuple[GoldRecord, ...], golds: tuple[AnswerGold, ...]) -> None:
        self.by_query = {r.query: (r, g) for r, g in zip(records, golds, strict=True)}

    def post(self, payload: Any) -> TransportResponse:
        user = str(payload["messages"][-1]["content"])
        query = user.split("Question: ", 1)[1].split("\nEvaluation time:", 1)[0]
        record, gold = self.by_query[query]
        full = perfect_response(record, gold)
        shown = [c for c in record.citation_gold_spans if citation_text(c) in user]
        cites = [citation_text(c) for c in shown]
        data = full.to_dict()
        answer = {
            "evidence_status": data["evidence_status"], "abstention_reason": data["abstention_reason"],
            "action": data["action"], "policy_outcome": data["policy_outcome"], "version_ids": data["version_ids"],
            "answer_text": "see claims",
            "claims": [{"kind": c["kind"], "params": c["params"], "text": c["text"], "citations": cites}
                       for c in data["claims"]],
        }  # fmt: skip
        body = {"model": GENERATOR_MODEL, "choices": [{"message": {"content": json.dumps(answer)}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}}  # fmt: skip
        return TransportResponse(200, {}, json.dumps(body).encode())


def make_run(
    s_root: Path,
    tmp: Path,
    corpus: PublishedCorpus,
    records: tuple[GoldRecord, ...],
    golds: tuple[AnswerGold, ...],
    *,
    transport: Any = None,
    run_id: str = "run-b-1000",
    withdrawn: dict[str, str] | None = None,
) -> Path:
    arms = {
        "R2": GoldRetriever("R2", corpus, records),
        "R3": GoldRetriever("R3", corpus, records, empty=True),
    }
    out = tmp / run_id
    spec = TrackBSpec(run_id, "smoke", 10, 4000, s_root, out, withdrawn=withdrawn)
    from benchmark.config import load_benchmark_config

    generator = load_benchmark_config(ROOT / "configs" / "benchmark.yaml").generator
    plan = plan_assignment(eligible_records(records, withdrawn), generator, spec, 7)
    pool = make_pool(out, dict(plan.assigned), transport or ExtractiveStubTransport(), generator)
    execute_track_b(spec, arms, pool, plan, corpus, generator, pool_label="offline-stub")
    return out


@pytest.fixture(scope="module")
def perfect_run(
    s_root: Path,
    s_published_corpus: PublishedCorpus,
    s_questions: tuple[GoldRecord, ...],
    s_golds: tuple[AnswerGold, ...],
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    return make_run(
        s_root, tmp_path_factory.mktemp("answers"), s_published_corpus, s_questions, s_golds,
        transport=PerfectTransport(s_questions, s_golds),
    )  # fmt: skip


@pytest.fixture(scope="module")
def stub_run(
    s_root: Path,
    s_published_corpus: PublishedCorpus,
    s_questions: tuple[GoldRecord, ...],
    s_golds: tuple[AnswerGold, ...],
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    return make_run(s_root, tmp_path_factory.mktemp("stub"), s_published_corpus, s_questions, s_golds)


def copy(run: Path, tmp: Path) -> Path:
    target = tmp / "copy"
    shutil.copytree(run, target)
    return target


def edit_lines(path: Path, change: Callable[[list[dict[str, Any]]], list[dict[str, Any]]]) -> None:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in change(rows)), encoding="utf-8")


def rules(findings: list[Finding]) -> str:
    return " | ".join(f.render() for f in findings)


# --------------------------------------------------------------------------- scoring


def test_a_run_whose_generator_returns_the_gold_answer_scores_as_perfect_for_the_arm_that_delivered_the_evidence(
    perfect_run: Path, s_root: Path
) -> None:
    score = score_answer_run(run_dir=perfect_run, root=s_root)
    weights = load_evaluation_config(ROOT / "configs" / "evaluation.yaml").loss_matrix
    good, empty = (summarize_arm(score, arm, weights) for arm in ("R2", "R3"))
    assert good.states == {"OK": good.pairs} and good.endpoints.not_completed == 0
    assert good.citations.fabricated == 0 and good.citations.outside_bundle == 0 and good.citations.inaccessible == 0
    assert good.endpoints.unsupported_directives == 0 and good.endpoints.forbidden_hits == 0
    assert good.endpoints.coverage_itt is not None and good.endpoints.coverage_itt > 0.7
    assert empty.endpoints.coverage_itt is not None and empty.endpoints.coverage_itt < good.endpoints.coverage_itt
    assert empty.loss_per_100 is not None and good.loss_per_100 is not None and empty.loss_per_100 > good.loss_per_100


def test_the_scorecard_states_the_generator_the_denominators_and_both_accountings(
    perfect_run: Path, s_root: Path
) -> None:
    evaluation = load_evaluation_config(ROOT / "configs" / "evaluation.yaml")
    score = score_answer_run(run_dir=perfect_run, root=s_root)
    summaries = [summarize_arm(score, arm, evaluation.loss_matrix) for arm in score.arms]
    text = render_answer_scorecard(
        score, summaries, sweep_for(score, evaluation.loss_matrix, evaluation.loss_sweep_scales)
    )
    for needle in ("OFFLINE STAND-IN", "no ranking claim", "intention to treat", "conditional", "worst case",
                   "Loss weight sweep", "| R2 |", "| R3 |"):  # fmt: skip
        assert needle in text, needle


def test_delivered_ids_are_read_back_into_units() -> None:
    assert delivered_from_ids(["POL-1@v1#4.1", "ART-9"]) == frozenset(
        {("POL-1@v1", "doc"), ("POL-1@v1", "4.1"), ("ART-9", "doc")}
    )


def test_a_payload_that_is_not_a_valid_answer_is_kept_as_a_run_state_not_scored(
    perfect_run: Path, s_root: Path, tmp_path: Path
) -> None:
    copied = copy(perfect_run, tmp_path)

    def damage(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for row in rows:
            if row["is_final"] and row["status"] == "OK":
                row["payload"] = {"junk": 1}
                break
        return rows

    edit_lines(copied / "ledger.jsonl", damage)
    score = score_answer_run(run_dir=copied, root=s_root)
    bad = [p for p in score.pairs if p.code == INVALID_ANSWER]
    assert len(bad) == 1 and bad[0].status is RunStatus.INVALID_RUN and not bad[0].scored


def test_a_pair_whose_arms_used_different_models_is_flagged_not_dropped(
    perfect_run: Path, s_root: Path, tmp_path: Path
) -> None:
    copied = copy(perfect_run, tmp_path)
    seen: dict[str, str] = {}

    def swap(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for row in rows:
            if row["arm_id"] == "R3" and not seen:
                seen[row["question_id"]] = row["served_model"]
                row["served_model"] = "other-model"
        return rows

    edit_lines(copied / "generation_records.jsonl", swap)
    score = score_answer_run(run_dir=copied, root=s_root)
    flagged = {p.question_id for p in score.pairs if p.mixed_model}
    assert flagged == set(seen) and len(score.mixed_model_questions) == 1
    assert {p.arm for p in score.pairs if p.question_id in flagged} == {"R2", "R3"}


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("ledger_hole", "ledger is not complete"),
        ("gold_edit", "different question"),
        ("other_withdrawn", "withdrawn"),
        ("no_answer_gold", "answer-gold"),
        ("other_k", "records K="),
        ("published_edit", "published corpus"),
    ],
)
def test_inconsistent_inputs_stop_the_scorer(
    change: str, message: str, perfect_run: Path, s_root: Path, tmp_path: Path, s_questions: tuple[GoldRecord, ...]
) -> None:
    run_dir = copy(perfect_run, tmp_path)
    root = tmp_path / "root"
    shutil.copytree(s_root, root)
    withdrawn: dict[str, str] | None = None
    if change == "ledger_hole":
        lines = (run_dir / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
        (run_dir / "ledger.jsonl").write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    elif change == "gold_edit":
        path = root / "annotations_dev" / "questions_smoke.jsonl"
        first, *rest = path.read_text(encoding="utf-8").splitlines()
        record = json.loads(first)
        record["query"] += " (edited)"
        path.write_text("\n".join([json.dumps(record, sort_keys=True), *rest]) + "\n", encoding="utf-8")
    elif change == "other_withdrawn":
        withdrawn = {s_questions[0].question_id: "x"}
    elif change == "no_answer_gold":
        (root / "annotations_dev" / "answers_smoke.jsonl").unlink()
    elif change == "other_k":
        config = json.loads((run_dir / "run_config.json").read_text(encoding="utf-8"))
        config["k"] = 5
        (run_dir / "run_config.json").write_text(json.dumps(config), encoding="utf-8")
    else:
        victim = next((root / "published" / "docs").iterdir())
        victim.write_text(victim.read_text(encoding="utf-8") + "x", encoding="utf-8")
    with pytest.raises(RunnerError, match=message):
        score_answer_run(run_dir=run_dir, root=root, withdrawn=withdrawn)


def test_a_track_a_run_directory_is_not_scored_as_track_b(s_root: Path, tmp_path: Path) -> None:
    run_dir = tmp_path / "a"
    run_dir.mkdir()
    (run_dir / "run_config.json").write_text(json.dumps({"split": "smoke"}), encoding="utf-8")
    with pytest.raises(ScoreRunError, match="not a Track B run"):
        score_answer_run(run_dir=run_dir, root=s_root)


# --------------------------------------------------------------------------- the validator


def test_a_clean_stand_in_run_passes_the_validator(stub_run: Path, perfect_run: Path, s_root: Path) -> None:
    assert validate_run(stub_run, root=s_root) == []
    assert validate_run(perfect_run, root=s_root) == []


def test_an_answer_may_say_what_the_gold_says_without_being_leakage(
    perfect_run: Path, s_root: Path, tmp_path: Path, s_questions: tuple[GoldRecord, ...]
) -> None:
    copied = copy(perfect_run, tmp_path)
    claim = next(c for q in s_questions for c in q.required_claims)

    def say(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for row in rows:
            if row["is_final"] and row["status"] == "OK":
                row["payload"]["answer_text"] = claim
                break
        return rows

    edit_lines(copied / "ledger.jsonl", say)
    assert validate_run(copied, root=s_root) == []


def plant_in_prompts(change: Callable[[dict[str, Any]], None]) -> Callable[[Path], None]:
    def apply(run: Path) -> None:
        def edit(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            change(rows[0])
            return rows

        edit_lines(run / "prompts.jsonl", edit)

    return apply


def planted_defects(s_questions: tuple[GoldRecord, ...]) -> dict[str, tuple[Callable[[Path], None], str]]:
    claim = s_questions[0].required_claims[0]

    def user(entry: dict[str, Any]) -> dict[str, Any]:
        return next(m for m in entry["messages"] if m["role"] == "user")

    def drop_generation(run: Path) -> None:
        edit_lines(run / "generation_records.jsonl", lambda rows: rows[1:])

    def unknown_model(run: Path) -> None:
        def change(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            rows[0]["requested_model"] = "not/in-the-pool"
            return rows

        edit_lines(run / "generation_records.jsonl", change)

    def junk_payload(run: Path) -> None:
        def change(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            for row in rows:
                if row["is_final"] and row["status"] == "OK":
                    row["payload"] = {"junk": 1}
                    break
            return rows

        edit_lines(run / "ledger.jsonl", change)

    def drop_pair(run: Path) -> None:
        lines = (run / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
        (run / "ledger.jsonl").write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")

    return {
        "gold text in a prompt": (
            plant_in_prompts(lambda e: user(e).update({"content": user(e)["content"] + " " + claim})),
            "gold text appears in an artifact",
        ),
        "a gold marker in a prompt": (
            plant_in_prompts(lambda e: user(e).update({"content": user(e)["content"] + " the expected answer is"})),
            "a prompt carries a gold marker",
        ),
        "evidence over the budget": (
            plant_in_prompts(
                lambda e: user(e).update(
                    {"content": user(e)["content"] + '\n<<passage ids="X#1.1">>\n' + "word " * 5000 + "\n<<end>>"}
                )
            ),
            "exceeds the evidence budget",
        ),
        "a missing generation record": (drop_generation, "no successful generation record"),
        "a model outside the pool": (unknown_model, "outside the pool"),
        "an invalid answer": (junk_payload, "not a valid answer"),
        "a dropped pair": (drop_pair, "not a complete record"),
        "missing prompts": (lambda run: (run / "prompts.jsonl").unlink(), "generation records or prompts are missing"),
    }


@pytest.mark.parametrize(
    "name",
    [
        "gold text in a prompt", "a gold marker in a prompt", "evidence over the budget", "a missing generation record",
        "a model outside the pool", "an invalid answer", "a dropped pair", "missing prompts",
    ],
)  # fmt: skip
def test_each_planted_defect_is_rejected_for_its_own_reason(
    name: str, stub_run: Path, s_root: Path, tmp_path: Path, s_questions: tuple[GoldRecord, ...]
) -> None:
    copied = copy(stub_run, tmp_path)
    plant, expected = planted_defects(s_questions)[name]
    plant(copied)
    assert expected in rules(validate_run(copied, root=s_root)), name


def test_a_changed_manifest_a_secret_and_the_test_split_are_each_rejected(
    stub_run: Path, s_root: Path, tmp_path: Path
) -> None:
    copied = copy(stub_run, tmp_path)
    manifest = copied / "manifest-R2.json"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace('"k": 10', '"k": 99'), encoding="utf-8")
    assert "manifest is missing or does not verify" in rules(validate_run(copied, root=s_root))
    secret = tmp_path / "second"
    secret.mkdir()
    again = copy(stub_run, secret)
    with (again / "summary.json").open("a", encoding="utf-8") as stream:
        stream.write("\ngsk_" + "a" * 30 + "\n")
    assert "groq-key" in rules(validate_run(again, root=s_root))
    third = tmp_path / "third"
    third.mkdir()
    test_split = copy(stub_run, third)
    config = json.loads((test_split / "run_config.json").read_text(encoding="utf-8"))
    config["split"] = "test"
    (test_split / "run_config.json").write_text(json.dumps(config), encoding="utf-8")
    assert "not runnable" in rules(validate_run(test_split, root=s_root))


# --------------------------------------------------------------------------- the command line


def script(name: str, *args: str) -> Any:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / name), *args], capture_output=True, text=True, check=False, timeout=900
    )


def test_the_commands_score_and_validate_a_run(stub_run: Path, s_root: Path, tmp_path: Path) -> None:
    copied = copy(stub_run, tmp_path)
    none = tmp_path / "none.json"
    none.write_text(json.dumps({"questions": {}}), encoding="utf-8")
    scored = script("score_track_b.py", "--run-dir", str(copied), "--root", str(s_root), "--withdrawn", str(none))
    assert scored.returncode == 0 and scored.stdout.startswith("PASS"), scored.stderr
    assert (copied / "scorecard.md").is_file() and (copied / "scores.json").is_file()
    checked = script("validate_results.py", "--run-dir", str(copied), "--root", str(s_root))
    assert checked.returncode == 0 and checked.stdout.startswith("PASS"), checked.stdout
    other = tmp_path / "other.json"
    other.write_text(json.dumps({"questions": {"q-0000000000000000": "x"}}), encoding="utf-8")
    refused = script("score_track_b.py", "--run-dir", str(copied), "--root", str(s_root), "--withdrawn", str(other))
    assert refused.returncode == 2 and "refused" in refused.stderr


# --------------------------------------------------------------------------- audit fixes (aud-7, 8, 16, 17, 19)


def test_what_was_delivered_is_read_from_the_kept_prompt_not_from_the_answer(
    perfect_run: Path, s_root: Path, tmp_path: Path
) -> None:
    copied = copy(perfect_run, tmp_path)

    def widen(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for row in rows:
            if row["is_final"] and row["status"] == "OK":
                row["payload"]["used_evidence_ids"] = [*row["payload"]["used_evidence_ids"], "POL-001@v1#4.1"]
                break
        return rows

    edit_lines(copied / "ledger.jsonl", widen)
    score = score_answer_run(run_dir=copied, root=s_root)
    bad = [p for p in score.pairs if p.code == "DELIVERED_MISMATCH"]
    assert len(bad) == 1 and bad[0].status is RunStatus.INVALID_RUN and not bad[0].scored
    assert "delivered ids differ" in rules(validate_run(copied, root=s_root))


def test_an_answer_gold_file_that_changed_since_the_run_stops_the_scorer(
    perfect_run: Path, s_root: Path, tmp_path: Path
) -> None:
    root = tmp_path / "root"
    shutil.copytree(s_root, root)
    path = root / "annotations_dev" / "answers_smoke.jsonl"
    path.write_bytes(path.read_bytes().replace(b"ANSWER", b"ANSWEX", 1))
    with pytest.raises(ScoreRunError, match="answer-gold"):
        score_answer_run(run_dir=perfect_run, root=root)


def test_the_scorecard_names_the_single_model_and_prints_no_invented_numerators(
    perfect_run: Path, s_root: Path
) -> None:
    evaluation = load_evaluation_config(ROOT / "configs" / "evaluation.yaml")
    score = score_answer_run(run_dir=perfect_run, root=s_root)
    summaries = [summarize_arm(score, arm, evaluation.loss_matrix) for arm in score.arms]
    text = render_answer_scorecard(
        score, summaries, sweep_for(score, evaluation.loss_matrix, evaluation.loss_sweep_scales)
    )
    assert "Every question ran on one generator model" in text
    policy = text.split("## Policy and time")[1].split("## Abstention")[0]
    assert "(0/" not in policy and "(of " in policy, "accuracies print the items they are over, not a made-up numerator"


def test_a_planted_copy_of_the_answer_gold_in_a_run_directory_is_rejected(
    perfect_run: Path, s_root: Path, tmp_path: Path
) -> None:
    copied = copy(perfect_run, tmp_path)
    shutil.copy(s_root / "annotations_dev" / "answers_smoke.jsonl", copied / "notes.jsonl")
    assert "a JSON key names gold" in rules(validate_run(copied, root=s_root))


def test_an_answer_gold_file_in_the_published_tree_is_found_by_the_readback(s_root: Path, tmp_path: Path) -> None:
    from benchmark.fixtures.manifest import verify_published

    published = tmp_path / "published"
    shutil.copytree(s_root / "published", published)
    assert verify_published(published) == []
    shutil.copy(s_root / "annotations_dev" / "answers_smoke.jsonl", published / "docs" / "answers_smoke.jsonl")
    assert verify_published(published) != []
