"""The alias setup step for the isolated Palladion: pure rules, guards and the record it leaves (BADR-0027)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from test_palladion_adapter import arm

from benchmark.adapters.palladion import ALIASES_FILE, IDENTIFIER_SHAPE, TABLE_FILE

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load_script(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def driver() -> ModuleType:
    sys.path.insert(0, str(SCRIPTS))
    return load_script("palladion_aliases")


@pytest.fixture(scope="module")
def job() -> ModuleType:
    return load_script("palladion_alias_job")


def test_the_job_reads_identifiers_the_way_the_adapter_and_palladion_do(job: ModuleType) -> None:
    assert job.IDENTIFIER.pattern == IDENTIFIER_SHAPE.pattern


def test_aliases_are_the_family_and_each_identifier_once_in_order(job: ModuleType) -> None:
    text = "Error MS-1954 returns 503. See POL-001 and MS-1954 again; transaction TXN-KES-00042 is open."
    assert job.aliases_for("POL-001@v2", text) == ["POL-001", "MS-1954", "TXN-KES-00042"]
    assert job.aliases_for("SOP-9@v1", "no codes here") == ["SOP-9"]
    assert job.family_of("EXC-007@v4") == "EXC-007" and job.family_of("ART-57aae8fd5f") == "ART-57aae8fd5f"


def test_a_word_without_a_dash_or_dot_is_not_an_alias(job: ModuleType) -> None:
    assert job.aliases_for("A-1@v1", "refunds within seventy-two hours, at Q3 or q1-x") == ["A-1"]


def table(tmp_path: Path) -> Path:
    path = tmp_path / TABLE_FILE
    path.write_text(json.dumps({"revisions": {"D1": "rev_1"}, "states": {"D1": "APPROVED"}}), encoding="utf-8")
    return path


def test_the_step_refuses_without_a_table_with_a_server_running_and_a_second_time(
    tmp_path: Path, driver: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(driver.AliasError, match="does not exist"):
        driver.register(tmp_path / TABLE_FILE)
    path = table(tmp_path)
    monkeypatch.setattr(driver, "server_is_up", lambda port=0: True)
    with pytest.raises(driver.AliasError, match="is running"):
        driver.register(path)
    monkeypatch.setattr(driver, "server_is_up", lambda port=0: False)
    (tmp_path / ALIASES_FILE).write_text("{}", encoding="utf-8")
    with pytest.raises(driver.AliasError, match="already registered"):
        driver.register(path)


def test_a_successful_job_leaves_a_marker_and_a_failed_one_leaves_none(
    tmp_path: Path, driver: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = table(tmp_path)
    monkeypatch.setattr(driver, "server_is_up", lambda port=0: False)
    stats = {"revisions": 1, "chunks": 2, "aliases_attempted": 5, "distinct_aliases": 4}

    def failing(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 1, stdout="", stderr="boom\nValidationFailure")

    monkeypatch.setattr(subprocess, "run", failing)
    with pytest.raises(driver.AliasError, match="ValidationFailure"):
        driver.register(path)
    assert not (tmp_path / ALIASES_FILE).exists()

    def working(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert Path(command[-3]).is_absolute() and Path(command[-2]).is_absolute(), "the job runs elsewhere"
        return subprocess.CompletedProcess([], 0, stdout="noise\n" + json.dumps(stats) + "\n", stderr="")

    monkeypatch.setattr(subprocess, "run", working)
    monkeypatch.chdir(tmp_path)
    assert driver.register(Path(TABLE_FILE)) == stats
    marker = json.loads((tmp_path / ALIASES_FILE).read_text(encoding="utf-8"))
    assert marker["aliases_attempted"] == 5 and len(marker["job_sha256"]) == 64


def test_the_arm_states_in_its_description_whether_aliases_were_registered(tmp_path: Path) -> None:
    from test_palladion_adapter import Palladion

    path = table(tmp_path)
    plain = arm(Palladion(), tmp_path)
    plain.read_table(path)
    assert str(plain.describe()["aliases"]).startswith("registered by Palladion's own approval"), "no setup step ran"
    (tmp_path / ALIASES_FILE).write_text(json.dumps({"chunks": 2, "job_sha256": "a" * 64}), encoding="utf-8")
    aliased = arm(Palladion(), tmp_path)
    aliased.read_table(path)
    assert aliased.describe()["aliases"] == {"chunks": 2, "job_sha256": "a" * 64}
