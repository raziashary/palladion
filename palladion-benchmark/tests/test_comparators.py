"""Comparator pins: only the approved artifact at the approved commit is accepted (B06-T00.03, OQ14)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import comparators
from benchmark.run_manifest import ComparatorPin
from comparators import (
    APPROVED,
    FRAMEWORKS,
    NOT_INSTALLED,
    Approved,
    ComparatorPinError,
    approved,
    build_framework_pin,
    build_pin,
    framework_pin,
    installed_packages,
    interpreter_version,
    lock_digest,
    verify_checkout,
)

REPO = "https://github.com/example/stub"


def git(path: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(path), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    return done.stdout.strip()


@pytest.fixture
def checkout(tmp_path: Path) -> tuple[Path, str]:
    path = tmp_path / "stub"
    path.mkdir()
    git(path, "init", "-q")
    (path / "a.txt").write_text("one", encoding="utf-8")
    git(path, "add", "a.txt")
    git(path, "commit", "-q", "-m", "first")
    git(path, "remote", "add", "origin", REPO + ".git")
    return path, git(path, "rev-parse", "HEAD")


def env_python(env: Path) -> Path:
    return env / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def make_env(path: Path) -> Path:
    subprocess.run(["uv", "venv", "-q", "--python", sys.executable, str(path)], check=True, capture_output=True)
    return path


# --------------------------------------------------------------------------- the checkout


def test_the_approved_repository_at_the_approved_commit_is_accepted(checkout: tuple[Path, str]) -> None:
    path, commit = checkout
    verify_checkout(path, REPO, commit)


def test_a_wrong_repository_a_wrong_commit_a_changed_file_and_no_checkout_are_each_refused(
    checkout: tuple[Path, str], tmp_path: Path
) -> None:
    path, commit = checkout
    with pytest.raises(ComparatorPinError, match="origin"):
        verify_checkout(path, "https://github.com/example/other", commit)
    with pytest.raises(ComparatorPinError, match="HEAD"):
        verify_checkout(path, REPO, "0" * 40)
    with pytest.raises(ComparatorPinError, match="not a git checkout"):
        verify_checkout(tmp_path, REPO, commit)
    (path / "a.txt").write_text("changed", encoding="utf-8")
    with pytest.raises(ComparatorPinError, match="differ"):
        verify_checkout(path, REPO, commit)


def test_a_later_commit_is_not_the_approved_one(checkout: tuple[Path, str]) -> None:
    path, commit = checkout
    (path / "b.txt").write_text("two", encoding="utf-8")
    git(path, "add", "b.txt")
    git(path, "commit", "-q", "-m", "second")
    with pytest.raises(ComparatorPinError, match="HEAD"):
        verify_checkout(path, REPO, commit)


# --------------------------------------------------------------------------- the environment


def test_the_interpreter_and_the_lock_digest_describe_the_environment(tmp_path: Path) -> None:
    env = make_env(tmp_path / "env")
    assert interpreter_version(env).startswith(f"{sys.version_info.major}.{sys.version_info.minor}")
    digest = lock_digest(env)
    assert len(digest) == 64 and digest == lock_digest(env), "the same environment gives the same digest"


def test_installing_a_package_changes_the_digest(tmp_path: Path) -> None:
    env = make_env(tmp_path / "env")
    before = lock_digest(env)
    site = (
        next(env.glob("Lib/site-packages")) if sys.platform == "win32" else next(env.glob("lib/python*/site-packages"))
    )
    info = site / "pinprobe-1.0.dist-info"  # what an installer leaves behind, written by hand so no network is needed
    info.mkdir()
    (info / "METADATA").write_text("Metadata-Version: 2.1\nName: pinprobe\nVersion: 1.0\n", encoding="utf-8")
    (info / "RECORD").write_text("", encoding="utf-8")
    after = lock_digest(env)
    assert after != before
    upgraded = info.rename(info.with_name("pinprobe-1.1.dist-info"))  # the installer names the directory by version
    (upgraded / "METADATA").write_text("Metadata-Version: 2.1\nName: pinprobe\nVersion: 1.1\n", encoding="utf-8")
    assert lock_digest(env) not in {before, after}, "a version change is a different environment"


def test_an_environment_with_no_interpreter_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ComparatorPinError, match="no interpreter"):
        interpreter_version(tmp_path / "nowhere")


# --------------------------------------------------------------------------- the pin


def test_the_pin_carries_the_commit_the_digest_and_the_interpreter(
    checkout: tuple[Path, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, commit = checkout
    root = tmp_path / "root"
    root.mkdir()
    path.rename(root / "stub")
    make_env(root / "env-stub")
    monkeypatch.setitem(
        APPROVED, "R4", Approved("R4", "Stub", REPO, commit, "stub", ".", "env-stub", "a test artifact")
    )
    pin = build_pin("R4", root=root, native_config={"mode": "local"}, deviations=["a deviation"])
    assert isinstance(pin, ComparatorPin) and pin.commit == commit and pin.repository == REPO
    assert pin.native_config == {"mode": "local"} and pin.deviations == ("a deviation",)
    assert ComparatorPin.from_dict(pin.to_dict()) == pin


def test_a_pin_is_refused_when_the_checkout_is_not_the_approved_commit(
    checkout: tuple[Path, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path, _ = checkout
    root = tmp_path / "root"
    root.mkdir()
    path.rename(root / "stub")
    make_env(root / "env-stub")
    monkeypatch.setitem(APPROVED, "R4", Approved("R4", "Stub", REPO, "f" * 40, "stub", ".", "env-stub", "a test"))
    with pytest.raises(ComparatorPinError, match="HEAD"):
        build_pin("R4", root=root, native_config={}, deviations=[])


def test_only_the_three_approved_comparators_are_known() -> None:
    assert sorted(comparators.APPROVED) == ["R4", "R5", "R6"]
    for arm in ("R0", "R7a", "R7b", "E3", "R9", ""):
        with pytest.raises(ComparatorPinError, match="not an approved comparator"):
            approved(arm)


def test_every_approved_commit_is_a_full_id_and_every_repository_is_https() -> None:
    for artifact in comparators.APPROVED.values():
        assert len(artifact.commit) == 40 and set(artifact.commit) <= set("0123456789abcdef")
        assert artifact.repository.startswith("https://github.com/")


def test_the_command_line_refuses_a_missing_checkout(tmp_path: Path) -> None:
    done = subprocess.run(
        [sys.executable, str(Path(comparators.__file__)), "verify", "--root", str(tmp_path)],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert done.returncode == 2 and done.stderr.startswith("refused:")


REAL = Path(comparators.COMPARATORS_DIR)


@pytest.mark.skipif(not (REAL / "LightRAG" / ".git").exists(), reason="the comparators are not downloaded here")
def test_the_downloaded_checkouts_are_the_approved_commits() -> None:
    done = subprocess.run(
        [sys.executable, str(Path(comparators.__file__)), "verify"], capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.count("the checkout is the approved commit") == 3
    assert json.dumps(sorted(comparators.APPROVED))


# --------------------------------------------------------------------------- the end-to-end frameworks (BADR-0040)


def site_packages(env: Path) -> Path:
    return (
        next(env.glob("Lib/site-packages")) if sys.platform == "win32" else next(env.glob("lib/python*/site-packages"))
    )


def install_by_hand(env: Path, name: str, version: str) -> None:
    """What an installer leaves behind, written by hand so no network is needed."""
    info = site_packages(env) / f"{name.replace('-', '_')}-{version}.dist-info"
    info.mkdir()
    lines = ["Metadata-Version: 2.1", f"Name: {name}", f"Version: {version}", ""]
    (info / "METADATA").write_text(chr(10).join(lines), encoding="utf-8")
    (info / "RECORD").write_text("", encoding="utf-8")


def framework_root(tmp_path: Path, versions: dict[str, str]) -> Path:
    make_env(tmp_path / FRAMEWORKS["E1"].environment)
    for name, version in versions.items():
        install_by_hand(tmp_path / FRAMEWORKS["E1"].environment, name, version)
    return tmp_path


def test_the_framework_environment_must_hold_exactly_the_approved_versions(tmp_path: Path) -> None:
    root = framework_root(tmp_path, dict(FRAMEWORKS["E1"].packages))
    pin = framework_pin("E1", root=root)
    assert pin["packages"] == dict(FRAMEWORKS["E1"].packages) and len(pin["lock_sha256"]) == 64
    assert pin["interpreter"].startswith(f"{sys.version_info.major}.{sys.version_info.minor}")
    assert framework_pin("E0", root=root)["environment"] == pin["environment"], "E0 and E1 share one environment"


def test_a_missing_or_different_version_is_refused_by_name(tmp_path: Path) -> None:
    approved_packages = dict(FRAMEWORKS["E1"].packages)
    wrong = {**approved_packages, "langgraph": "0.0.1"}
    with pytest.raises(ComparatorPinError, match="langgraph"):
        framework_pin("E1", root=framework_root(tmp_path / "a", wrong))
    missing = {name: version for name, version in approved_packages.items() if name != "openai"}
    with pytest.raises(ComparatorPinError, match="openai"):
        framework_pin("E1", root=framework_root(tmp_path / "b", missing))


def test_google_adk_is_recorded_not_installed_and_an_unknown_arm_is_refused(tmp_path: Path) -> None:
    assert set(NOT_INSTALLED) == {"E2"}
    with pytest.raises(ComparatorPinError, match="recorded only"):
        framework_pin("E2", root=tmp_path)
    with pytest.raises(ComparatorPinError, match="not an approved framework"):
        framework_pin("E9", root=tmp_path)


def test_installed_packages_lists_what_is_there_with_normalised_names(tmp_path: Path) -> None:
    env = make_env(tmp_path / "env")
    install_by_hand(env, "Some_Package", "2.3")
    assert installed_packages(env)["some-package"] == "2.3"


@pytest.mark.skipif(
    not (REAL / FRAMEWORKS["E0"].environment).exists(), reason="the framework environment is not installed"
)
def test_the_installed_framework_environment_is_the_approved_one() -> None:
    assert framework_pin("E0")["packages"] == dict(FRAMEWORKS["E0"].packages)


def test_the_framework_pin_carries_exact_versions_and_no_commit(tmp_path: Path) -> None:
    root = framework_root(tmp_path, dict(FRAMEWORKS["E1"].packages))
    pin = build_framework_pin("E1", root=root, native_config={"k": 4}, deviations=["a"])
    assert isinstance(pin, ComparatorPin) and pin.commit == "" and dict(pin.packages) == dict(FRAMEWORKS["E1"].packages)
    assert ComparatorPin.from_dict(pin.to_dict()) == pin
    with pytest.raises(ComparatorPinError, match="langgraph"):
        build_framework_pin(
            "E1",
            root=framework_root(tmp_path / "x", {**FRAMEWORKS["E1"].packages, "langgraph": "0.1"}),
            native_config={},
            deviations=[],
        )
