"""The Track A runner and scoring entry point through the real Runner (B04-T04.02)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from support import HashingEncoder
from test_hybrid import OverlapReranker

from benchmark.adapters.common import Condition, PublishedView
from benchmark.adapters.dense import DenseArm
from benchmark.contracts import RunStatus
from benchmark.fixtures.questions import GoldRecord
from benchmark.results_check import validate_run
from benchmark.runner import RunLedger
from benchmark.track_a import (
    DescribedArm,
    RunSpec,
    TrackAError,
    build_local_arms,
    build_request,
    execute,
    read_annotations,
)

ROOT = Path(__file__).resolve().parents[1]
K, BUDGET = 10, 4000


@pytest.fixture(scope="module")
def n(s_questions: tuple[GoldRecord, ...]) -> int:
    """How many questions the smoke file holds."""
    return len(s_questions)


def spec(root: Path, out: Path, run_id: str = "run-a-0001", split: str = "smoke") -> RunSpec:
    return RunSpec(run_id, split, Condition.C2, K, BUDGET, root, out)


def r0_only(root: Path, index_dir: Path) -> tuple[dict[str, DescribedArm], list[dict[str, Any]]]:
    view = PublishedView.load(root / "published")
    return build_local_arms(view, ["R0"], condition=Condition.C2, index_dir=index_dir)


@pytest.fixture(scope="module")
def r0_run(s_root: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("run") / "r0"
    arms, builds = r0_only(s_root, out / "index")
    execute(spec(s_root, out), arms, builds=builds)
    return out


# --------------------------------------------------------------------------- the split rules


def test_the_locked_test_split_is_refused(s_root: Path) -> None:
    with pytest.raises(TrackAError, match="locked test split"):
        read_annotations(s_root, "test")
    with pytest.raises(TrackAError, match="locked test split"):
        read_annotations(s_root, "pilot")


def test_reading_a_split_logs_exactly_the_files_it_read(s_root: Path, n: int) -> None:
    records, log = read_annotations(s_root, "smoke")
    assert len(records) == n and all(r.split.value == "smoke" for r in records)
    assert (log.annotation_namespace, log.annotation_file, log.test_namespace_read) == (
        "annotations_dev",
        "questions_smoke.jsonl",
        False,
    )
    with pytest.raises(TrackAError, match="does not exist"):
        read_annotations(s_root, "dev")


def test_a_request_shows_the_question_and_the_principal_and_nothing_of_the_gold(
    s_root: Path, s_questions: tuple[GoldRecord, ...]
) -> None:
    from benchmark.fixtures.manifest import read_identity

    identity = read_identity(s_root / "published")
    request = build_request(s_questions[0], identity, k=K, budget=BUDGET, condition=Condition.C2)
    assert request.limit == K and request.max_evidence_tokens == BUDGET
    assert set(request.filters) == {"tenant_id", "role", "metadata_condition"}
    flat = json.dumps(request.to_dict())
    for gold in (*s_questions[0].required_claims, *s_questions[0].forbidden_claims):
        assert gold not in flat
    with pytest.raises(TrackAError, match="not in the identity manifest"):
        build_request(
            GoldRecord.from_dict({**s_questions[0].to_dict(), "principal_id": "ghost"}),
            identity, k=K, budget=BUDGET, condition=Condition.C2,
        )  # fmt: skip


# --------------------------------------------------------------------------- a real run


def test_every_pair_has_one_final_record_and_the_run_directory_is_complete(r0_run: Path, n: int) -> None:
    for name in ("ledger.jsonl", "run_config.json", "read_log.json", "summary.json", "manifest-R0.json"):
        assert (r0_run / name).is_file(), name
    finals = [r for r in RunLedger(r0_run / "ledger.jsonl").records if r.is_final]
    assert len(finals) == n and {r.arm for r in finals} == {"R0"} and all(r.status is RunStatus.OK for r in finals)
    config = json.loads((r0_run / "run_config.json").read_text(encoding="utf-8"))
    assert (config["k"], config["budget_words"], config["metadata_condition"], config["questions"]) == (
        K,
        BUDGET,
        "C2",
        n,
    )
    assert config["builds"][0]["status"] == "BUILT"


def test_the_manifest_records_k_budget_condition_and_the_arms_settings(r0_run: Path) -> None:
    from benchmark.run_manifest import read_verified

    manifest = read_verified(r0_run / "manifest-R0.json")
    recorded = manifest.retrieval_config
    assert (recorded["k"], recorded["budget_words"], recorded["metadata_condition"]) == (K, BUDGET, "C2")
    assert recorded["k1"] == 1.2 and recorded["arm"] == "R0"
    assert manifest.method_version == "1.1.0" and manifest.split == "smoke" and manifest.confirmatory is False


def test_the_artifacts_contain_no_gold(r0_run: Path, s_questions: tuple[GoldRecord, ...]) -> None:
    blob = "\n".join(
        p.read_text(encoding="utf-8") for p in r0_run.rglob("*") if p.is_file() and p.suffix in (".json", ".jsonl")
    )
    for record in s_questions:
        for text in (*record.required_claims, *record.forbidden_claims):
            assert text not in blob
    assert '"answerability"' not in blob and '"minimal_sets"' not in blob and '"citation_gold_spans"' not in blob


def test_the_validator_accepts_the_clean_run(r0_run: Path, s_root: Path) -> None:
    assert validate_run(r0_run, root=s_root) == []


def test_an_arm_that_could_not_be_built_stays_in_the_run_as_not_run_with_its_reason(
    s_root: Path, tmp_path: Path, n: int
) -> None:
    view = PublishedView.load(s_root / "published")
    arms, builds = build_local_arms(view, ["R0", "R1"], condition=Condition.C2, index_dir=tmp_path / "index")
    assert [b["status"] for b in builds] == ["BUILT", "FAILED"]
    execute(spec(s_root, tmp_path / "run"), arms, builds=builds)
    finals = [r for r in RunLedger(tmp_path / "run" / "ledger.jsonl").records if r.is_final]
    r1 = [r for r in finals if r.arm == "R1"]
    assert len(r1) == n and {(r.status, r.code) for r in r1} == {(RunStatus.NOT_RUN, "ARM_UNAVAILABLE")}
    assert all(r.status is RunStatus.OK for r in finals if r.arm == "R0")
    assert (
        json.loads((tmp_path / "run" / "run_config.json").read_text(encoding="utf-8"))["builds"][1]["status"]
        == "FAILED"
    )


def test_all_four_local_arms_run_the_split_through_the_real_runner(
    qdrant_server: str, s_root: Path, tmp_path: Path, n: int
) -> None:
    view = PublishedView.load(s_root / "published")
    arms, builds = build_local_arms(
        view, ["R0", "R1", "R2", "R3"], condition=Condition.C2, index_dir=tmp_path / "index",
        qdrant_url=qdrant_server, encoder=HashingEncoder(), reranker=OverlapReranker(),
    )  # fmt: skip
    try:
        assert [b["status"] for b in builds] == ["BUILT"] * 4
        outcome = execute(spec(s_root, tmp_path / "run", "run-a-0002"), arms, builds=builds)
        assert outcome.summary.planned_pairs == 4 * n and outcome.summary.status_counts == {"OK": 4 * n}
        assert validate_run(tmp_path / "run", root=s_root) == []
    finally:
        dense = arms["R1"]
        assert isinstance(dense, DenseArm)
        dense.close()


# --------------------------------------------------------------------------- the entry points


def run_script(name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / name), *args], capture_output=True, text=True, check=False, timeout=900
    )


def none_withdrawn(tmp_path: Path) -> Path:
    path = tmp_path / "none.json"
    path.write_text(json.dumps({"questions": {}}), encoding="utf-8")
    return path


def test_the_shipped_withdrawal_list_names_three_questions_with_reasons() -> None:
    data = json.loads((ROOT / "configs" / "withdrawn_questions.json").read_text(encoding="utf-8"))
    assert data["decision"] == "BADR-0026" and len(data["questions"]) == 3
    assert all(q.startswith("q-") and len(q) == 18 and reason for q, reason in data["questions"].items())


def test_the_command_line_runs_scores_and_validates_a_run(
    s_root: Path, tmp_path: Path, n: int, s_questions: tuple[GoldRecord, ...]
) -> None:
    out = tmp_path / "cli-run"
    ran = run_script("run_track_a.py", "--root", str(s_root), "--split", "smoke", "--out", str(out),
                     "--run-id", "run-a-0003", "--arms", "R0", "--k", "10", "--budget", "4000")  # fmt: skip
    assert ran.returncode == 0, ran.stderr
    summary = json.loads(ran.stdout)
    assert summary["questions"] == n and summary["arms"] == ["R0"] and summary["status_counts"] == {"OK": n}
    scored = run_script("score_track_a.py", "--run-dir", str(out), "--root", str(s_root), "--k", "10",
                        "--withdrawn", str(none_withdrawn(tmp_path)))  # fmt: skip
    assert scored.returncode == 0, scored.stderr
    card = (out / "scorecard.md").read_text(encoding="utf-8")
    assert "Run states and severe failures" in card and "R0" in card and "NOT_RUN" not in card
    assert not card.startswith("Withdrawn")
    assert len(json.loads((out / "scores.json").read_text(encoding="utf-8"))["pairs"]) == n
    first = s_questions[0].question_id
    listed = tmp_path / "listed.json"
    listed.write_text(json.dumps({"questions": {first: "a gold defect"}}), encoding="utf-8")
    again = run_script("score_track_a.py", "--run-dir", str(out), "--root", str(s_root), "--k", "10",
                       "--withdrawn", str(listed))  # fmt: skip
    assert again.returncode == 0, again.stderr
    assert (out / "scorecard.md").read_text(encoding="utf-8").startswith("Withdrawn before scoring (1; BADR-0026)")
    pairs = json.loads((out / "scores.json").read_text(encoding="utf-8"))["pairs"]
    assert len(pairs) == n - 1 and first not in {p["question_id"] for p in pairs}
    checked = run_script("validate_results.py", "--run-dir", str(out), "--root", str(s_root))
    assert checked.returncode == 0 and checked.stdout.startswith("PASS"), checked.stdout


def test_the_command_line_refuses_the_test_split_and_a_different_k(s_root: Path, tmp_path: Path) -> None:
    refused = run_script("run_track_a.py", "--root", str(s_root), "--split", "test", "--out", str(tmp_path / "x"),
                         "--run-id", "run-a-0004", "--arms", "R0")  # fmt: skip
    assert refused.returncode == 2 and "locked test split" in refused.stderr
    ran = run_script("run_track_a.py", "--root", str(s_root), "--split", "smoke", "--out", str(tmp_path / "y"),
                     "--run-id", "run-a-0005", "--arms", "R0", "--k", "10")  # fmt: skip
    assert ran.returncode == 0, ran.stderr
    wrong = run_script("score_track_a.py", "--run-dir", str(tmp_path / "y"), "--root", str(s_root), "--k", "5",
                       "--withdrawn", str(none_withdrawn(tmp_path)))  # fmt: skip
    assert wrong.returncode == 2 and "K=10" in wrong.stderr


def test_a_second_run_in_the_same_directory_cannot_repeat_the_plan(s_root: Path, tmp_path: Path, n: int) -> None:
    arms, builds = r0_only(s_root, tmp_path / "index")
    execute(spec(s_root, tmp_path / "run", "run-a-0006"), arms, builds=builds)
    assert sum(1 for r in RunLedger(tmp_path / "run" / "ledger.jsonl").records if r.is_final) == n
    again = spec(s_root, tmp_path / "run", "run-a-0006")
    execute(again, arms, builds=builds)
    assert sum(1 for r in RunLedger(tmp_path / "run" / "ledger.jsonl").records if r.is_final) == n, (
        "no pair is run twice"
    )


def test_truncation_notes_reach_the_ledger_as_flags(s_root: Path, tmp_path: Path) -> None:
    view = PublishedView.load(s_root / "published")
    arms, builds = build_local_arms(view, ["R0"], condition=Condition.C2, index_dir=tmp_path / "index")
    tight = RunSpec("run-a-0007", "smoke", Condition.C2, K, 30, s_root, tmp_path / "run")
    outcome = execute(tight, arms, builds=builds)
    flagged = [r for r in RunLedger(tmp_path / "run" / "ledger.jsonl").records if r.is_final and r.flags]
    assert flagged and all("BUDGET_TRUNCATED" in r.flags for r in flagged)
    assert outcome.summary.flag_counts["BUDGET_TRUNCATED"] == len(flagged)
    assert validate_run(tmp_path / "run", root=s_root) == []


def test_a_manifest_written_under_another_k_is_not_reused(s_root: Path, tmp_path: Path) -> None:
    arms, builds = r0_only(s_root, tmp_path / "index")
    execute(spec(s_root, tmp_path / "run", "run-a-0008"), arms, builds=builds)
    different = RunSpec("run-a-0008", "smoke", Condition.C2, 5, BUDGET, s_root, tmp_path / "run")
    with pytest.raises(TrackAError, match="different K, budget or condition"):
        execute(different, arms, builds=builds)


def test_a_qdrant_server_that_is_not_the_pinned_version_fails_the_dense_arms_build(
    qdrant_server: str, s_root: Path, tmp_path: Path
) -> None:
    view = PublishedView.load(s_root / "published")
    _, builds = build_local_arms(
        view, ["R1"], condition=Condition.C2, index_dir=tmp_path, qdrant_url=qdrant_server,
        encoder=HashingEncoder(), expected_qdrant="9.9.9",
    )  # fmt: skip
    assert builds[0]["status"] == "FAILED" and builds[0]["error"] == "AdapterError"
    assert "9.9.9" in builds[0]["reason"]
