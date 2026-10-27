"""Matched lists frozen before the first spend (B08-T08.09)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from benchmark.contracts import ContractError
from benchmark.fixtures.documents import Document
from benchmark.fixtures.questions import GoldRecord
from benchmark.fixtures.world import World
from benchmark.matched import MatchedListError, MatchedLists, freeze, load
from benchmark.run_manifest import read_verified

Q1, Q2, Q3 = "q-0000000000000001", "q-0000000000000002", "q-0000000000000003"
MODEL = "qwen/qwen3.8-27b"
ROOT = Path(__file__).resolve().parents[1]


def lists() -> MatchedLists:
    return MatchedLists(
        7, {"track_a": (Q1, Q2, Q3), "track_b": (Q1, Q3), "track_c_cases": ("M01", "M13")}, {Q1: MODEL, Q3: MODEL}
    )


def test_frozen_lists_read_back_with_the_digest_they_were_written_with(tmp_path: Path) -> None:
    path = tmp_path / "matched.json"
    digest = freeze(path, lists())
    back = load(path)
    assert back == lists() and back.digest == digest == lists().digest


def test_frozen_lists_are_never_rewritten(tmp_path: Path) -> None:
    path = tmp_path / "matched.json"
    freeze(path, lists())
    with pytest.raises(MatchedListError, match="never rewritten"):
        freeze(path, lists())  # not even the same lists


def test_an_edit_after_freezing_is_detected(tmp_path: Path) -> None:
    path = tmp_path / "matched.json"
    freeze(path, lists())
    document = json.loads(path.read_text(encoding="utf-8"))
    document["matched"]["lists"]["track_b"] = [Q1]
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(MatchedListError, match="changed after it was frozen"):
        load(path)


def test_a_file_that_is_not_a_frozen_list_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "matched.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(MatchedListError, match="not a readable frozen list"):
        load(path)
    with pytest.raises(MatchedListError, match="not a readable frozen list"):
        load(tmp_path / "missing.json")


@pytest.mark.parametrize("ids", [(Q2, Q1), (Q1, Q1)])
def test_a_list_must_hold_sorted_distinct_ids(ids: tuple[str, ...]) -> None:
    with pytest.raises(MatchedListError, match="sorted, distinct"):
        MatchedLists(7, {"track_a": ids}, {})


def test_an_assignment_must_name_real_questions_and_models() -> None:
    with pytest.raises(ContractError):
        MatchedLists(7, {"track_a": (Q1,)}, {"not-a-question": MODEL})
    with pytest.raises(MatchedListError, match="names a model"):
        MatchedLists(7, {"track_a": (Q1,)}, {Q1: ""})


def test_a_run_must_ask_exactly_the_frozen_questions() -> None:
    frozen = lists()
    frozen.require("track_b", [Q3, Q1])  # order does not matter
    with pytest.raises(MatchedListError, match="1 missing, 0 not on the list"):
        frozen.require("track_b", [Q1])
    with pytest.raises(MatchedListError, match="0 missing, 1 not on the list"):
        frozen.require("track_b", [Q1, Q2, Q3])
    with pytest.raises(MatchedListError, match="no list 'track_z'"):
        frozen.require("track_z", [Q1])


# ----------------------------------------------------------------------- the entry points that choose and use lists


def script(name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / name), *args], capture_output=True, text=True, check=False, timeout=900
    )


def freeze_args(s_root: Path, out: Path, *budgets: str, count: str = "6") -> list[str]:
    models = [("qwen/qwen3.8-27b", "21000"), ("openai/gpt-oss-120b", "14000"), ("openai/gpt-oss-20b", "7000")]
    shares = budgets or tuple(f"{m}={t}" for m, t in models)
    flags = [x for share in shares for x in ("--model-budget", share)]
    return ["--root", str(s_root), "--graph-root", str(s_root), "--out", str(out), "--track-b-count", count,
            "--tokens-per-question", "7000", "--episodes", "0", "--mutations", "", *flags]  # fmt: skip


def test_the_freeze_command_writes_once_and_spreads_questions_over_the_budgets(s_root: Path, tmp_path: Path) -> None:
    out = tmp_path / "matched.json"
    done = script("freeze_matched.py", *freeze_args(s_root, out))
    assert done.returncode == 0, done.stderr
    report = json.loads(done.stdout)
    assert (
        report["sizes"]["track_a"] == 100 and report["sizes"]["track_b"] == 6 and report["sizes"]["track_c_cases"] == 0
    )
    frozen = load(out)
    assert report["sha256"] == frozen.digest and set(frozen.assignment) == set(frozen.lists["track_b"])
    assert sorted(set(frozen.assignment.values())) == sorted(report["models"])
    assert len(report["models"]) == 3, "6 questions at 7,000 tokens fill 3 + 2 + 1 places across the three budgets"
    again = script("freeze_matched.py", *freeze_args(s_root, out))
    assert again.returncode == 2 and "never rewritten" in again.stderr


def test_the_freeze_command_refuses_budgets_that_do_not_cover_the_list(s_root: Path, tmp_path: Path) -> None:
    out = tmp_path / "short.json"
    done = script("freeze_matched.py", *freeze_args(s_root, out, "qwen/qwen3.8-27b=14000"))
    assert done.returncode == 2 and "cover" in done.stderr and not out.exists()


def test_track_b_asks_the_frozen_questions_with_the_frozen_models_and_records_the_list(
    s_root: Path, tmp_path: Path
) -> None:
    lists_file = tmp_path / "matched.json"
    assert script("freeze_matched.py", *freeze_args(s_root, lists_file)).returncode == 0
    frozen = load(lists_file)
    out = tmp_path / "b"
    done = script(
        "run_track_b.py", "--root", str(s_root), "--split", "smoke", "--out", str(out),
        "--run-id", "run-b-0100", "--arms", "R0", "--matched-list", str(lists_file),
    )  # fmt: skip
    assert done.returncode == 0, done.stderr
    config = json.loads((out / "run_config.json").read_text(encoding="utf-8"))
    assert config["asked"] == list(frozen.lists["track_b"]) and config["matched_list_sha256"] == frozen.digest
    used = {}
    for line in (out / "generation_records.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        used[row["question_id"]] = row["requested_model"]
    assert used == dict(frozen.assignment), "every question ran on the model the frozen list gave it"
    assert read_verified(out / "manifest-R0.json").comparability()["matched_list"] == frozen.digest
    both = script(
        "run_track_b.py", "--root", str(s_root), "--split", "smoke", "--out", str(tmp_path / "c"),
        "--run-id", "run-b-0101", "--arms", "R0", "--matched-list", str(lists_file), "--limit-questions", "3",
    )  # fmt: skip
    assert both.returncode == 2 and "both choose the questions" in both.stderr


def test_track_a_checks_its_questions_against_the_frozen_list(s_root: Path, tmp_path: Path) -> None:
    lists_file = tmp_path / "matched.json"
    assert script("freeze_matched.py", *freeze_args(s_root, lists_file)).returncode == 0
    out = tmp_path / "a"
    done = script(
        "run_track_a.py", "--root", str(s_root), "--split", "smoke", "--out", str(out),
        "--run-id", "run-a-0100", "--arms", "R0", "--matched-list", str(lists_file),
    )  # fmt: skip
    assert done.returncode == 0, done.stderr
    frozen = load(lists_file)
    assert json.loads((out / "run_config.json").read_text(encoding="utf-8"))["matched_list_sha256"] == frozen.digest
    drifted = MatchedLists(frozen.seed, {**frozen.lists, "track_a": frozen.lists["track_a"][:-1]}, frozen.assignment)
    other = tmp_path / "drifted.json"
    freeze(other, drifted)
    refused = script(
        "run_track_a.py", "--root", str(s_root), "--split", "smoke", "--out", str(tmp_path / "a2"),
        "--run-id", "run-a-0101", "--arms", "R0", "--matched-list", str(other),
    )  # fmt: skip
    assert (
        refused.returncode == 2
        and "not the frozen one" in refused.stderr
        and not (tmp_path / "a2" / "ledger.jsonl").exists()
    )


def load_freeze_script() -> ModuleType:
    sys.path.insert(0, str(ROOT / "scripts"))  # the script imports its sibling run_track_c
    spec = importlib.util.spec_from_file_location("freeze_matched", ROOT / "scripts" / "freeze_matched.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_track_c_episodes_and_cases_are_chosen_outside_the_locked_test_split(
    s_root: Path,
    s_world: World,
    s_corpus: tuple[Document, ...],
    s_questions: tuple[GoldRecord, ...],
    s_snapshot: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    freezer = load_freeze_script()
    fixture = freezer.run_track_c.Fixture(s_world, s_corpus, s_questions, s_snapshot, 7)
    monkeypatch.setattr(freezer.run_track_c, "rebuild_fixture", lambda root, bundle: fixture)
    args = freezer.argparse.Namespace(
        root=s_root, graph_root=s_root, out=tmp_path / "m.json", split="smoke", withdrawn=freezer.WITHDRAWN,
        track_b_count=4, tokens_per_question=7000, max_completion_tokens=2000, episodes=3, mutations="M13,M01",
        model_budget=[("qwen/qwen3.8-27b", 28000)],
    )  # fmt: skip
    chosen = freezer.build_lists(args)
    expected = freezer.run_track_c.pick_episodes(fixture, 3)
    assert chosen.lists["track_c_episodes"] == tuple(sorted(e.episode_id for e in expected))
    assert all(e.split.value != "test" for e in expected)
    assert chosen.lists["track_c_cases"] == ("M01", "M13"), "sorted, whatever order they were named in"
    assert set(chosen.assignment) == set(chosen.lists["track_b"]) and len(chosen.lists["track_b"]) == 4
