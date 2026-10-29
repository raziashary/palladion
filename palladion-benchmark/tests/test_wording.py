"""Wording sensitivity: the paired comparison, and the scorer through its entry point, aggregates only (BADR-0047)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from test_score_sealed import REGISTRATION, git, load_script, score_sealed, seal_worlds

from benchmark import seal as sealing
from benchmark.adapters.common import Condition, PublishedView
from benchmark.analysis.wording import WordingError, change_share, compare
from benchmark.config import StatisticsSettings
from benchmark.contracts import RunStatus
from benchmark.eval.score_run import PairScore, RunScore
from benchmark.paraphrase import Outcome, OutcomeLog, Verdict, collect
from benchmark.track_a import ArmSettings, RunSpec, build_local_arms, execute

score_wording = load_script("score_wording")
METRIC = "complete_set_at_k"
STATS = StatisticsSettings(
    bootstrap_resamples=500, confidence=0.95, multiplicity="holm", cluster_by="family",
    zero_failure_bound_numerator=3, bootstrap_seed=7, min_clusters=3,
)  # fmt: skip


def pair(arm: str, i: int, value: float) -> PairScore:
    return PairScore(
        arm,
        f"q-{i:016d}",
        "Q1",
        f"F-{i}",
        RunStatus.OK,
        None,
        {METRIC: value},
        frozenset({METRIC}),
        {},
        0,
        0,
        0,
        10,
        1.0,
    )


def run(values: dict[str, list[float]]) -> RunScore:
    pairs = tuple(pair(arm, i, v) for arm, vs in values.items() for i, v in enumerate(vs))
    return RunScore("r", 10, "g", pairs, (), {})


# -- the comparison and the change share ------------------------------------------------------------------------------


def test_the_paired_difference_is_variant_minus_original_with_hand_computed_counts() -> None:
    original = run({"R7a": [1, 1, 1, 0, 0, 0, 0, 0], "R0": [1, 0, 0, 0, 0, 0, 0, 0]})
    variant = run({"R7a": [1, 1, 0, 0, 0, 0, 0, 1], "R0": [1, 0, 0, 0, 0, 0, 0, 0]})
    by_arm = {row.arm: row for row in compare(original, variant, ["R7a", "R0"], METRIC, STATS)}
    moved, same = by_arm["R7a"], by_arm["R0"]
    assert (moved.questions, moved.original, moved.variant) == (8, 3 / 8, 3 / 8)
    assert (moved.effect.only_arm, moved.effect.only_reference) == (1, 1) and moved.effect.difference.estimate == 0.0
    assert same.effect.difference.estimate == 0.0 and (same.effect.only_arm, same.effect.only_reference) == (0, 0)


def test_a_drop_in_the_other_wording_is_a_negative_difference() -> None:
    original = run({"R7a": [1.0] * 8})
    variant = run({"R7a": [1.0] * 4 + [0.0] * 4})
    row = compare(original, variant, ["R7a"], METRIC, STATS)[0]
    assert row.effect.difference.estimate == -0.5 and (row.effect.only_arm, row.effect.only_reference) == (0, 4)


def test_only_the_questions_both_runs_scored_are_compared_and_none_in_common_is_refused() -> None:
    original = run({"R7a": [1, 1, 1, 1]})
    variant = RunScore("v", 10, "g", tuple(pair("R7a", i, 0.0) for i in (2, 3, 4, 5)), (), {})
    row = compare(original, variant, ["R7a"], METRIC, STATS)[0]
    assert row.questions == 2 and (row.original, row.variant) == (1.0, 0.0)
    nothing = RunScore("v", 10, "g", tuple(pair("R7a", i, 0.0) for i in (10, 11)), (), {})
    with pytest.raises(WordingError, match="no question scored in both"):
        compare(original, nothing, ["R7a"], METRIC, STATS)


def test_the_change_share_is_the_share_of_words_only_one_text_has() -> None:
    assert change_share("What is the limit?", "what is the LIMIT") == 0.0
    assert change_share("a b c d", "a b x y") == pytest.approx(1 - 2 / 6)
    assert change_share("a b", "c d") == 1.0 and change_share("", "") == 0.0


# -- the entry point ---------------------------------------------------------------------------------------------------


@pytest.fixture
def setup(s_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    project = tmp_path / "project"
    project.mkdir()
    git(project, "init", "-q")
    (project / "code.py").write_text("x = 1" + chr(10), encoding="utf-8")
    (project / "registration.json").write_text(json.dumps(REGISTRATION), encoding="utf-8")
    (project / "tuned_arms.json").write_text("{}", encoding="utf-8")
    git(project, "add", ".")
    git(project, "commit", "-q", "-m", "init")
    world = tmp_path / "W1"
    shutil.copytree(s_root, world)
    (world / "generator").mkdir(exist_ok=True)
    (world / "generator" / "report.json").write_text("{}", encoding="utf-8")
    runs = tmp_path / "runs"
    records = [
        json.loads(line)
        for line in (world / "annotations_dev" / "questions_smoke.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    chosen = [r["question_id"] for r in records[:6]]
    log = OutcomeLog(runs / "para-W1" / "paraphrases.jsonl")
    originals = {r["question_id"]: r["query"] for r in records}
    for q in chosen:
        log.append(Outcome(q, originals[q], "reworded " + originals[q], Verdict.ACCEPTED, (), "openai/gpt-oss-20b"))
    variants = collect(log)
    view = PublishedView.load(world / "published")
    defaults = ArmSettings().to_dict()
    for name, texts, digest in (
        ("t-W1-c2-r1", None, None),
        ("t-W1-c2-r2", None, None),
        ("v-W1-c2-r1", variants.queries, variants.digest),
    ):
        arms, builds = build_local_arms(view, ["R0", "R0x"], condition=Condition.C2, index_dir=tmp_path / "index")
        spec = RunSpec(
            name, "smoke", Condition.C2, 10, 4000, s_root, runs / name,
            arm_settings={"R0": defaults, "R0x": defaults}, paraphrases=texts, paraphrase_sha256=digest,
        )  # fmt: skip
        execute(spec, arms, builds=builds)
    for module in (score_sealed, score_wording):
        monkeypatch.setattr(module, "RUNS", runs)
    monkeypatch.setattr(seal_worlds, "REGISTRATION", project / "registration.json")
    monkeypatch.setattr(
        seal_worlds, "FILES", {"registration": project / "registration.json", "tuned_arms": project / "tuned_arms.json"}
    )
    monkeypatch.setattr(seal_worlds, "CODE_PATHS", ("code.py",))
    monkeypatch.setattr(seal_worlds, "PROJECT", project)
    monkeypatch.setattr(seal_worlds, "world_roots", lambda registration: {"W1": world})
    monkeypatch.setattr(seal_worlds, "paraphrase_digests", lambda registration: {"W1": variants.digest})
    monkeypatch.setattr(score_sealed.palladion_runtime, "application_dir", lambda: project)
    seal = sealing.create(
        purpose="test", worlds={"W1": world}, files={"registration": project / "registration.json"}, project=project,
        code_paths=("code.py",), system=project, registration=REGISTRATION, settings={},
        paraphrases={"W1": variants.digest},
    )  # fmt: skip
    seal.write(tmp_path / "seal.json")
    return {"seal": tmp_path / "seal.json", "out": tmp_path / "out" / "card.md", "records": records, "world": world}


def run_scorer(setup: dict[str, Path]) -> int:
    return int(
        score_wording.main(
            ["--seal", str(setup["seal"]), "--original-tag", "t", "--variant-tag", "v", "--out", str(setup["out"])]
        )
    )


def test_the_scorer_writes_two_tables_of_totals_and_no_question_or_rewrite(
    setup: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_scorer(setup) == 0
    card = setup["out"].read_text(encoding="utf-8")
    assert "Seal intact." in card and "6 accepted rewrites" in card and "No claim" in card
    assert (
        "Same questions, rewritten (variant minus original)" in card
        and "Control: the original questions run again" in card
    )
    assert "| R0 | 6 | " in card and "| R0x | 6 | " in card, "only the six rewritten questions are compared"
    printed = capsys.readouterr()
    leaked = [r["question_id"] for r in setup["records"]] + [r["query"] for r in setup["records"]] + ["reworded "]
    assert not any(text in card or text in printed.out or text in printed.err for text in leaked)
    assert sorted(p.name for p in setup["out"].parent.iterdir()) == ["card.md"]


def test_a_variant_run_made_with_other_variants_than_the_seal_holds_is_refused(
    setup: dict[str, Any], tmp_path: Path
) -> None:
    path = tmp_path / "runs" / "v-W1-c2-r1" / "run_config.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    config["paraphrase_sha256"] = "f" * 64
    path.write_text(json.dumps(config), encoding="utf-8")
    assert run_scorer(setup) == 2 and not setup["out"].exists()


def test_a_missing_control_run_is_refused_not_skipped(setup: dict[str, Any], tmp_path: Path) -> None:
    for entry in (tmp_path / "runs" / "t-W1-c2-r2").iterdir():
        if entry.is_file():
            entry.unlink()
    assert run_scorer(setup) == 2 and not setup["out"].exists()
