"""The seal of a confirmatory run: an edit after it is detected (B08-T03.01, BADR-0047)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from benchmark import seal as sealing
from benchmark.seal import WORLD_FILES, Kind, Seal, SealError

REGISTRATION = {"primary": "R7a", "reference": "R3", "metric": "complete_set_at_k", "minimum_effect": 0.05}
CODE = ("code.py",)  # what is sealed as code; prereg.md and notes.md are outside it
SETTINGS = {"arms": ["R0", "R3", "R7a"], "k": 10, "budget": 4000, "conditions": ["C2", "C1"], "repeats": 3}


def git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false", *args],
        cwd=repo, check=True, capture_output=True,
    )  # fmt: skip


@pytest.fixture
def project(tmp_path: Path) -> Path:
    repo = tmp_path / "project"
    repo.mkdir()
    git(repo, "init", "-q")
    (repo / "code.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "prereg.md").write_text("primary: R7a against R3\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def make_world(root: Path, tag: str) -> Path:
    for name, relative in WORLD_FILES.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{tag} {name}\n", encoding="utf-8")
    return root


@pytest.fixture
def worlds(tmp_path: Path) -> dict[str, Path]:
    return {name: make_world(tmp_path / name, name) for name in ("T101", "T102")}


def made(project: Path, worlds: dict[str, Path], paraphrases: dict[str, str] | None = None) -> Seal:
    variants = paraphrases if paraphrases is not None else {"T101": "a" * 64}
    return sealing.create(
        purpose="test", worlds=worlds, files={"prereg": project / "prereg.md"}, project=project,
        code_paths=CODE, system=None, registration=REGISTRATION, settings=SETTINGS, paraphrases=variants,
    )  # fmt: skip


def check(seal: Seal, project: Path, worlds: dict[str, Path], paraphrases: dict[str, str] | None = None):  # type: ignore[no-untyped-def]
    return sealing.verify(
        seal, worlds=worlds, files={"prereg": project / "prereg.md"}, project=project, code_paths=CODE, system=None,
        paraphrases=paraphrases if paraphrases is not None else {"T101": "a" * 64},
    )  # fmt: skip


def test_a_seal_round_trips_with_its_own_hash_and_is_intact_when_nothing_changed(
    project: Path, worlds: dict[str, Path], tmp_path: Path
) -> None:
    seal = made(project, worlds)
    digest = seal.write(tmp_path / "seal.json")
    loaded = Seal.load(tmp_path / "seal.json")
    assert loaded == seal and loaded.digest == digest and check(loaded, project, worlds) == []
    assert set(seal.worlds["T101"]) == set(WORLD_FILES) and seal.trees["benchmark"]["tree_sha256"]


def test_a_seal_is_never_rewritten(project: Path, worlds: dict[str, Path], tmp_path: Path) -> None:
    seal = made(project, worlds)
    seal.write(tmp_path / "seal.json")
    with pytest.raises(SealError, match="never rewritten"):
        seal.write(tmp_path / "seal.json")


def test_a_seal_edited_after_it_was_written_is_refused_when_read(
    project: Path, worlds: dict[str, Path], tmp_path: Path
) -> None:
    path = tmp_path / "seal.json"
    made(project, worlds).write(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["seal"]["registration"]["minimum_effect"] = 0.0
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(SealError, match="edited"):
        Seal.load(path)
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(SealError, match="not a seal"):
        Seal.load(path)


@pytest.mark.parametrize("label", sorted(WORLD_FILES))
def test_a_changed_world_file_is_found_by_name(project: Path, worlds: dict[str, Path], label: str) -> None:
    seal = made(project, worlds)
    (worlds["T102"] / WORLD_FILES[label]).write_text("changed\n", encoding="utf-8")
    problems = check(seal, project, worlds)
    assert [(p.kind, p.subject) for p in problems] == [(Kind.WORLD_CHANGED, f"T102:{label}")]


def test_a_missing_world_and_a_missing_world_file_are_changes_not_errors(
    project: Path, worlds: dict[str, Path]
) -> None:
    seal = made(project, worlds)
    (worlds["T101"] / WORLD_FILES["questions"]).unlink()
    assert {p.subject for p in check(seal, project, worlds) if p.kind is Kind.WORLD_CHANGED} == {
        f"T101:{n}" for n in WORLD_FILES
    }
    only = {"T101": worlds["T101"]}
    assert {p.subject.split(":")[0] for p in check(seal, project, only)} >= {"T102"}


def test_a_changed_registration_file_makes_the_result_exploratory_but_a_changed_document_does_not(
    project: Path, worlds: dict[str, Path]
) -> None:
    seal = made(project, worlds)
    (project / "notes.md").write_text("evidence written after the run" + chr(10), encoding="utf-8")
    git(project, "add", "notes.md")
    git(project, "commit", "-q", "-m", "write the evidence")
    assert check(seal, project, worlds) == [], "a document outside the sealed code does not break the seal"
    (project / "prereg.md").write_text("primary: something else" + chr(10), encoding="utf-8")
    assert [(p.kind, p.subject) for p in check(seal, project, worlds)] == [(Kind.CODE_CHANGED, "prereg")]


def test_a_committed_change_to_the_code_is_found_whatever_the_commit(project: Path, worlds: dict[str, Path]) -> None:
    seal = made(project, worlds)
    (project / "code.py").write_text("x = 2" + chr(10), encoding="utf-8")
    git(project, "commit", "-q", "-am", "change the code after the seal")
    assert [(p.kind, p.subject) for p in check(seal, project, worlds)] == [(Kind.CODE_CHANGED, "benchmark tree")]


def test_uncommitted_code_after_the_seal_is_found_through_the_tree_digest(
    project: Path, worlds: dict[str, Path]
) -> None:
    seal = made(project, worlds)
    (project / "code.py").write_text("x = 2\n", encoding="utf-8")
    assert [(p.kind, p.subject) for p in check(seal, project, worlds)] == [(Kind.CODE_CHANGED, "benchmark tree")]


def test_changed_wording_variants_are_found(project: Path, worlds: dict[str, Path]) -> None:
    seal = made(project, worlds)
    assert [p.kind for p in check(seal, project, worlds, {"T101": "b" * 64})] == [Kind.PARAPHRASES_CHANGED]
    assert [p.kind for p in check(seal, project, worlds, {})] == [Kind.PARAPHRASES_CHANGED]


def test_code_with_uncommitted_or_new_changes_cannot_be_sealed(project: Path, worlds: dict[str, Path]) -> None:
    (project / "code.py").write_text("x = 3" + chr(10), encoding="utf-8")
    with pytest.raises(SealError, match="uncommitted"):
        made(project, worlds)
    git(project, "checkout", "--", "code.py")
    (project / "other.py").write_text("y = 1" + chr(10), encoding="utf-8")
    assert made(project, worlds).trees["benchmark"], "a file outside the sealed paths is not code"


def test_a_world_without_a_sealed_file_and_variants_for_an_unknown_world_are_refused(
    project: Path, worlds: dict[str, Path]
) -> None:
    (worlds["T101"] / WORLD_FILES["answers"]).unlink()
    with pytest.raises(SealError, match="lacks"):
        made(project, worlds)
    with pytest.raises(SealError, match="not in the seal"):
        made(project, {"T102": worlds["T102"]}, {"T999": "a" * 64})


def test_a_key_added_to_the_stored_seal_is_refused_as_an_edit(
    project: Path, worlds: dict[str, Path], tmp_path: Path
) -> None:
    path = tmp_path / "seal.json"
    made(project, worlds).write(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["seal"]["approved_by"] = "someone"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(SealError, match="edited"):
        Seal.load(path)
