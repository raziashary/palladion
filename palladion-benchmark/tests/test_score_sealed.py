"""The sealed scorer through its entry point: it verifies the seal and prints aggregates only (BADR-0047)."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from benchmark import seal as sealing
from benchmark.adapters.common import Condition, PublishedView
from benchmark.analysis.pooling import Claim, Registered, Registration
from benchmark.analysis.tables import Effect
from benchmark.eval.statistics import Interval
from benchmark.track_a import ArmSettings, RunSpec, build_local_arms, execute

ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str) -> ModuleType:
    sys.path.insert(0, str(ROOT / "scripts"))  # the scripts import their siblings by name, as they do when run
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


seal_worlds = load_script("seal_worlds")
score_sealed = load_script("score_sealed")

REGISTRATION: dict[str, Any] = {
    "scope": "test",
    "endpoint": "complete_set_at_k",
    "k": 10,
    "budget_words": 4000,
    "condition": "C2",
    "repeats": 1,
    "primary": {"arm": "R0x", "reference": "R0"},
    "secondary_references": [],
    "minimum_effect": 0.05,
    "arms": ["R0", "R0x"],
    "worlds": ["W1"],
}


def git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false", *args],
        cwd=repo, check=True, capture_output=True,
    )  # fmt: skip


@pytest.fixture
def sealed_setup(s_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """A tiny project, the S fixture as world W1, a real two-arm run of it, and a seal over all three."""
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
    (world / "generator" / "report.json").write_text("{}", encoding="utf-8")  # the fixture has no generator report
    runs = tmp_path / "runs"
    view = PublishedView.load(world / "published")
    arms, builds = build_local_arms(view, ["R0", "R0x"], condition=Condition.C2, index_dir=tmp_path / "index")
    defaults = ArmSettings().to_dict()
    execute(
        RunSpec(
            "sealed-W1-c2-r1", "smoke", Condition.C2, 10, 4000, s_root, runs / "t-W1-c2-r1",
            arm_settings={"R0": defaults, "R0x": defaults},
        ),
        arms,
        builds=builds,
    )  # fmt: skip
    monkeypatch.setattr(seal_worlds, "REGISTRATION", project / "registration.json")
    monkeypatch.setattr(
        seal_worlds, "FILES", {"registration": project / "registration.json", "tuned_arms": project / "tuned_arms.json"}
    )
    monkeypatch.setattr(seal_worlds, "CODE_PATHS", ("code.py",))
    monkeypatch.setattr(seal_worlds, "PROJECT", project)
    monkeypatch.setattr(seal_worlds, "world_roots", lambda registration: {"W1": world})
    monkeypatch.setattr(seal_worlds, "paraphrase_digests", lambda registration: {})
    monkeypatch.setattr(score_sealed.palladion_runtime, "application_dir", lambda: project)
    monkeypatch.setattr(seal_worlds.palladion_runtime, "application_dir", lambda: project)
    monkeypatch.setattr(score_sealed, "RUNS", runs)
    seal = sealing.create(
        purpose="test", worlds={"W1": world}, files={"registration": project / "registration.json"}, project=project,
        code_paths=("code.py",), system=project, registration=REGISTRATION, settings={}, paraphrases={},
    )  # fmt: skip
    seal.write(tmp_path / "seal.json")
    return {"project": project, "seal": tmp_path / "seal.json", "out": tmp_path / "out" / "card.md", "world": world}


def run_scorer(setup: dict[str, Path]) -> int:
    return int(score_sealed.main(["--seal", str(setup["seal"]), "--tag", "t", "--out", str(setup["out"])]))


def test_an_intact_seal_gives_a_pooled_card_with_the_registered_pairing_and_no_per_question_output(
    sealed_setup: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_scorer(sealed_setup) == 0
    card = sealed_setup["out"].read_text(encoding="utf-8")
    assert "Seal intact." in card and "EXPLORATORY" not in card
    assert "Registered comparisons" in card and "R0x - R0 (primary)" in card and "Claim on the primary pairing" in card
    questions = (sealed_setup["world"] / "annotations_dev" / "questions_smoke.jsonl").read_text(encoding="utf-8")
    ids = [json.loads(line)["question_id"] for line in questions.splitlines()]
    printed = capsys.readouterr()
    assert not any(i in card or i in printed.out or i in printed.err for i in ids), "no question id leaves the scorer"
    assert sorted(p.name for p in sealed_setup["out"].parent.iterdir()) == ["card.md"], "nothing but the aggregate card"


def test_a_change_to_the_sealed_code_marks_every_table_exploratory_but_still_scores(
    sealed_setup: dict[str, Path],
) -> None:
    (sealed_setup["project"] / "code.py").write_text("x = 2" + chr(10), encoding="utf-8")
    assert run_scorer(sealed_setup) == 0
    assert "EXPLORATORY: CODE_CHANGED benchmark tree" in sealed_setup["out"].read_text(encoding="utf-8")


def test_a_changed_world_file_refuses_the_scoring_and_writes_nothing(sealed_setup: dict[str, Path]) -> None:
    # The generator report plays no part in scoring, so only the seal can notice that it changed.
    changed = sealed_setup["world"] / "generator" / "report.json"
    changed.write_text('{"edited": true}', encoding="utf-8")
    assert run_scorer(sealed_setup) == 2
    assert not sealed_setup["out"].exists()


def test_a_missing_run_directory_is_refused_not_scored_as_zero(sealed_setup: dict[str, Path]) -> None:
    for entry in (score_sealed.RUNS / "t-W1-c2-r1").iterdir():
        if entry.is_file():
            entry.unlink()
    assert run_scorer(sealed_setup) == 2 and not sealed_setup["out"].exists()


def test_the_registered_block_names_the_claim_and_every_pairing() -> None:
    interval = Interval(0.2, 0.1, 0.3, 40, 20, False)
    effect = Effect("ALL", "R7a", "R3", "complete_set_at_k", 40, interval, 12, 2, 0.01, None, True)
    other = Effect("ALL", "R7a", "R0", "complete_set_at_k", 40, interval, 9, 3, 0.07, 0.14)
    result = Registered(
        Registration("R7a", "R3", ("R0",), "complete_set_at_k", 0.05), effect, Claim.CONFIRMED, (other,)
    )
    block = score_sealed.render_registered(result)
    assert "R7a - R3 (primary)" in block and "R7a - R0 |" in block and "+0.200 [+0.100, +0.300]" in block
    assert "12 against 2" in block and "Claim on the primary pairing: CONFIRMED." in block


def edit_run_config(setup: dict[str, Path], **changes: object) -> None:
    path = score_sealed.RUNS / "t-W1-c2-r1" / "run_config.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    config.update(changes)
    path.write_text(json.dumps(config), encoding="utf-8")


def test_a_run_made_with_other_wording_variants_than_the_seal_holds_is_refused(sealed_setup: dict[str, Path]) -> None:
    edit_run_config(sealed_setup, paraphrase_sha256="f" * 64)
    assert run_scorer(sealed_setup) == 2 and not sealed_setup["out"].exists()


def test_a_run_made_with_other_arm_settings_than_the_tuned_ones_is_refused(sealed_setup: dict[str, Path]) -> None:
    assert run_scorer(sealed_setup) == 0, "positive control: the defaults are what the empty tuned file means"
    sealed_setup["out"].unlink()
    (sealed_setup["project"] / "tuned_arms.json").write_text('{"R0": {"k1": 1.5}}', encoding="utf-8")
    assert run_scorer(sealed_setup) == 2 and not sealed_setup["out"].exists()


def test_fewer_repeats_than_registered_are_refused_not_scored_as_one(
    sealed_setup: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(seal_worlds, "read_registration", lambda: {**REGISTRATION, "repeats": 2})
    assert run_scorer(sealed_setup) == 2 and not sealed_setup["out"].exists()
