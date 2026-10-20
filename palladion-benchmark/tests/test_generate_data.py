"""The S-tier generation entry point (B02-T07.01): reproducible digests, validation gate, readback and the card."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from benchmark.fixtures.entities import WorldError
from benchmark.fixtures.manifest import Namespace, read_records, scan_published, verify_published
from benchmark.fixtures.validation import Finding, ValidationReport

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_data.py"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_data_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script() -> ModuleType:
    return load_script()


@pytest.fixture(scope="module")
def generated(script: ModuleType, tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, object]]:
    out = tmp_path_factory.mktemp("s_tier") / "S"
    return out, script.generate("S", None, out)


def run_cli(out: Path, *, hash_seed: str, tz: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONHASHSEED": hash_seed, "TZ": tz, "LANG": "C"}
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--tier", "S", "--out", str(out)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


# --------------------------------------------------------------------------- reproducibility


def test_two_subprocess_runs_under_different_environments_give_identical_digests(tmp_path: Path) -> None:
    first = run_cli(tmp_path / "a", hash_seed="0", tz="UTC", cwd=ROOT)
    second = run_cli(tmp_path / "b", hash_seed="4242", tz="Asia/Jakarta", cwd=tmp_path)
    assert first.returncode == 0 and second.returncode == 0, first.stderr + second.stderr
    assert first.stdout == second.stdout
    digests = json.loads(first.stdout)
    assert digests["documents"] == 1200 and digests["questions"] == 100
    manifest = "published/corpus_manifest.jsonl"
    assert (tmp_path / "a" / manifest).read_bytes() == (tmp_path / "b" / manifest).read_bytes()


def test_a_different_base_seed_gives_a_different_fixture(script: ModuleType, tmp_path: Path) -> None:
    one = script.generate("S", 7, tmp_path / "a")["digests"]
    two = script.generate("S", 9, tmp_path / "b")["digests"]
    assert one["corpus_manifest_sha256"] != two["corpus_manifest_sha256"] and one["world_digest"] != two["world_digest"]


# --------------------------------------------------------------------------- the written tree, read back


def test_the_written_tree_reads_back_with_the_configured_sizes(generated: tuple[Path, dict[str, object]]) -> None:
    out, summary = generated
    published = out / Namespace.PUBLISHED.value
    assert verify_published(published) == [] and len(read_records(published)) == summary["documents"] == 1200
    assert summary["validation_findings"] == 0


def test_the_pilot_annotations_are_smoke_only_and_kept_out_of_the_published_tree(
    generated: tuple[Path, dict[str, object]],
) -> None:
    out, _ = generated
    lines = (out / "annotations_dev" / "questions_smoke.jsonl").read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines]
    assert len(records) == 100 and {r["split"] for r in records} == {"smoke"}
    assert not list((out / "annotations_test").iterdir())
    assert scan_published(out / "published", forbidden=[r["question_id"] for r in records]) == []


def test_the_answer_gold_is_written_beside_the_questions_and_matches_them(
    generated: tuple[Path, dict[str, object]],
) -> None:
    from benchmark.fixtures.answer_gold import answer_gold_path, check_matches_questions, read_answer_gold
    from benchmark.fixtures.manifest import Split
    from benchmark.fixtures.questions import read_gold

    out, summary = generated
    questions = read_gold(out / "annotations_dev" / "questions_smoke.jsonl")
    golds = read_answer_gold(answer_gold_path(out, Split.SMOKE))
    check_matches_questions(golds, questions)
    assert len(golds) == 100 and summary["digests"]["questions_sha256"]  # type: ignore[index]
    assert not list((out / "published").rglob("answers_*")), "the answer-gold never enters the published tree"


def test_the_report_carries_the_figures_the_card_needs(generated: tuple[Path, dict[str, object]]) -> None:
    out, summary = generated
    report = json.loads((out / "generator" / "report.json").read_text(encoding="utf-8"))
    assert report["digests"] == summary["digests"]
    for key in (
        "tokens_total",
        "tokens_mean",
        "language_measured",
        "revisions",
        "near_duplicate_share",
        "graph_degree",
    ):
        assert key in report["corpus"]
    assert sum(report["questions_by_stratum"].values()) == 100 and set(report["realism"]) >= {"lexical_solvability"}


# --------------------------------------------------------------------------- gates


def test_a_failing_validation_stops_the_run_before_anything_is_written(
    script: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broken = ValidationReport((Finding("leakage", "doc", "planted"),))
    monkeypatch.setattr(script, "validate_fixture", lambda *_: broken)
    out = tmp_path / "S"
    with pytest.raises(script.GenerationError, match="validation failed"):
        script.generate("S", None, out)
    assert not out.exists()


def test_a_tier_that_is_not_built_yet_is_refused(script: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(script.GenerationError, match="later phase"):
        script.generate("M", None, tmp_path / "M")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--tier", "M", "--out", str(tmp_path / "M")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1 and "later phase" in result.stderr


def test_an_existing_output_directory_is_not_overwritten_without_the_flag(script: ModuleType, tmp_path: Path) -> None:
    out = tmp_path / "S"
    script.generate("S", None, out)
    with pytest.raises(WorldError, match="not empty"):
        script.generate("S", None, out)
    script.generate("S", None, out, overwrite=True)


# --------------------------------------------------------------------------- the dataset card


def test_the_dataset_card_matches_what_the_script_produces(
    script: ModuleType, generated: tuple[Path, dict[str, object]]
) -> None:
    _, summary = generated
    card = (ROOT / "docs" / "dataset_card.md").read_text(encoding="utf-8")
    begin, end = card.index(script.CARD_BEGIN), card.index(script.CARD_END)
    assert card[begin + len(script.CARD_BEGIN) : end].strip() == script.render_card_block(summary).strip()


def test_the_card_says_the_fixtures_are_fictional_and_names_its_limits() -> None:
    card = (ROOT / "docs" / "dataset_card.md").read_text(encoding="utf-8")
    for phrase in (
        "Everything here is fictional",
        "an actual operating procedure",
        "Template-first text",
        "Few scenario families",
    ):
        assert phrase in card


def test_write_card_replaces_only_the_generated_block(
    script: ModuleType, generated: tuple[Path, dict[str, object]], tmp_path: Path
) -> None:
    _, summary = generated
    card = tmp_path / "card.md"
    card.write_text(f"intro\n{script.CARD_BEGIN}\nold\n{script.CARD_END}\noutro\n", encoding="utf-8")
    script.write_card(summary, card)
    text = card.read_text(encoding="utf-8")
    assert text.startswith("intro\n") and text.endswith("outro\n") and "old" not in text and "| Documents |" in text
    card.write_text("no markers here\n", encoding="utf-8")
    with pytest.raises(script.GenerationError, match="no generated block"):
        script.write_card(summary, card)


def test_a_failed_readback_of_the_written_tree_stops_the_run(
    script: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(script, "verify_published", lambda _: ["hash mismatch for X"])
    with pytest.raises(script.GenerationError, match="failed its readback"):
        script.generate("S", None, tmp_path / "S")
