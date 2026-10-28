"""Command line: real entry point, exit codes, and output that never hides a missing capability."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from benchmark import __version__
from benchmark.cli import main

ROOT = Path(__file__).resolve().parents[1]


def run_module(*args: str) -> subprocess.CompletedProcess[str]:
    """The actual entry point, in a fresh interpreter from the project root."""
    return subprocess.run(
        [sys.executable, "-m", "benchmark.cli", *args], cwd=ROOT, capture_output=True, text=True, check=False
    )


def test_capability_matrix_exits_zero_and_lists_all_seventeen_arms_via_the_real_entry_point() -> None:
    result = run_module("capability-matrix")
    assert result.returncode == 0, result.stderr
    rows = [line for line in result.stdout.splitlines() if line.startswith("| ")]
    assert len(rows) == 18  # header plus seventeen arms
    for arm in ("R0", "R7a", "R7b", "E0", "E2", "E3", "E4"):
        assert any(row.startswith(f"| {arm} |") for row in rows), arm
    assert "unsupported" in result.stdout and "UNVERIFIED" in result.stdout


def test_unknown_arm_exits_nonzero_and_names_the_arm_on_stderr() -> None:
    result = run_module("capability-matrix", "--arm", "R99")
    assert result.returncode == 2 and "R99" in result.stderr and result.stdout == ""


def test_known_and_unknown_arms_together_still_fail() -> None:
    assert main(["capability-matrix", "--arm", "R0", "--arm", "R99"]) == 2


def test_arm_filter_limits_the_rows(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["capability-matrix", "--arm", "R0", "--arm", "E3"]) == 0
    rows = [line for line in capsys.readouterr().out.splitlines() if line.startswith("| ")]
    assert [row.split("|")[1].strip() for row in rows] == ["arm", "R0", "E3"]


def test_list_arms_prints_ids_and_names(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["list-arms"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "R0\tBM25 lexical" and len(lines) == 17


def test_version_matches_the_package(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["version"]) == 0
    assert capsys.readouterr().out.strip() == __version__


def test_validate_config_passes_in_exploratory_mode_and_fails_in_confirmatory_mode(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["validate-config"]) == 0
    assert "PASS: configuration valid (exploratory); 17 arms" in capsys.readouterr().out
    assert main(["validate-config", "--confirmatory"]) == 1
    assert "confirmatory mode refuses unpinned" in capsys.readouterr().err


def test_a_broken_config_directory_fails_with_exit_one(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    broken = tmp_path / "configs"
    shutil.copytree(ROOT / "configs", broken)
    text = (broken / "benchmark.yaml").read_text(encoding="utf-8")
    (broken / "benchmark.yaml").write_text(text + "\nsurprise: 1\n", encoding="utf-8")
    assert main(["validate-config", "--config-dir", str(broken)]) == 1
    assert "unknown key" in capsys.readouterr().err
    assert main(["capability-matrix", "--config-dir", str(tmp_path / "missing")]) == 1


def test_registry_and_config_drift_fails_the_listing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    drifted = tmp_path / "configs"
    shutil.copytree(ROOT / "configs", drifted)
    text = (drifted / "comparators.yaml").read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if not line.startswith("  - {id: R6,")]
    (drifted / "comparators.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert main(["list-arms", "--config-dir", str(drifted)]) == 1
    assert "differ" in capsys.readouterr().err


def test_missing_subcommand_is_a_usage_error() -> None:
    with pytest.raises(SystemExit) as caught:
        main([])
    assert caught.value.code == 2
