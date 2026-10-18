"""Run manifest: tamper evidence, exclusive creation, evaluator-only gold, read-only tree capture."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from benchmark.contracts import CacheCondition, ContractError, Track
from benchmark.run_manifest import (
    ManifestError,
    RunManifest,
    TreeState,
    collect_hardware,
    read_verified,
    sha256_of,
    tree_state,
)

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
H1, H2, H3 = "a" * 64, "b" * 64, "c" * 64
COMMIT = "1" * 40


def clean_tree(label: str = "benchmark") -> TreeState:
    return TreeState(label, COMMIT, H1, ())


def make_manifest(**overrides: Any) -> RunManifest:
    values: dict[str, Any] = {
        "run_id": "palladion_bench_dev_r3_seed_004",
        "track": Track.RETRIEVAL_ONLY,
        "arm": "R3",
        "split": "dev",
        "source_manifest_sha256": H1,
        "question_manifest_sha256": H2,
        "gold_manifest_sha256": H3,
        "benchmark": clean_tree(),
        "system_under_test": None,
        "container_image_digest": None,
        "method_version": None,
        "model_versions": {"embeddings": "model-a@rev1", "reranker": None, "generator": None},
        "retrieval_config": {"dense_top_k": 40, "fusion": "rrf", "output_k": 10, "evidence_token_budget": 4000},
        "prompt_digest": None,
        "hardware": {"platform": "test", "cpu_count": 4},
        "pricing_snapshot": None,
        "seed": 4,
        "order_seed": 99,
        "cache_condition": CacheCondition.COLD,
        "started_at_utc": "2026-10-18T03:00:00Z",
        "retry_policy": {"max_attempts": 2},
        "generator_assignment_sha256": None,
        "confirmatory": False,
        "null_reasons": {
            "system_under_test": "retrieval-only arm of the benchmark",
            "container_image_digest": "no container runtime installed",
            "method_version": "implemented in the benchmark itself",
            "prompt_digest": "no prompts in a retrieval-only run",
            "pricing_snapshot": "free tier",
            "generator_assignment_sha256": "no generator in a retrieval-only run",
        },
    }
    values.update(overrides)
    return RunManifest(**values)


# ----------------------------------------------------------------------------- digest and files


def test_digest_is_stable_and_changes_with_one_changed_byte() -> None:
    assert make_manifest().digest() == make_manifest().digest()
    assert make_manifest(seed=5).digest() != make_manifest().digest()
    assert make_manifest(source_manifest_sha256="a" * 63 + "b").digest() != make_manifest().digest()


def test_digest_does_not_depend_on_key_order() -> None:
    assert sha256_of({"a": 1, "b": 2}) == sha256_of({"b": 2, "a": 1})


def test_write_then_read_round_trips_and_verifies(tmp_path: Path) -> None:
    manifest = make_manifest()
    digest = manifest.write(tmp_path / "manifest.json")
    loaded = read_verified(tmp_path / "manifest.json", expected_digest=digest)
    assert loaded == manifest and loaded.digest() == digest


def test_a_second_write_to_the_same_path_is_refused_and_leaves_the_file_intact(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    first = make_manifest().write(path)
    before = path.read_bytes()
    with pytest.raises(ManifestError, match="never overwritten"):
        make_manifest(seed=5).write(path)
    assert path.read_bytes() == before
    assert read_verified(path, expected_digest=first)


def test_editing_a_field_without_touching_the_digest_is_detected(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    make_manifest().write(path)
    document = json.loads(path.read_text(encoding="utf-8"))
    document["manifest"]["seed"] = 5
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ManifestError, match="embedded digest"):
        read_verified(path)


def test_a_rewrite_with_a_recomputed_digest_passes_alone_but_not_against_the_external_digest(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    external = make_manifest().write(path)
    document = json.loads(path.read_text(encoding="utf-8"))
    document["manifest"]["seed"] = 5
    document["manifest_sha256"] = sha256_of(document["manifest"])
    path.write_text(json.dumps(document), encoding="utf-8")
    assert read_verified(path).seed == 5  # the in-file digest alone cannot detect this
    with pytest.raises(ManifestError, match="externally recorded"):
        read_verified(path, expected_digest=external)


def test_wrong_layout_and_unknown_fields_are_refused(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"hello": 1}), encoding="utf-8")
    with pytest.raises(ManifestError, match="layout"):
        read_verified(path)
    make_manifest().write(tmp_path / "ok.json")
    document = json.loads((tmp_path / "ok.json").read_text(encoding="utf-8"))
    document["manifest"]["surprise"] = 1
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ManifestError, match="unknown"):
        read_verified(path)
    with pytest.raises(ManifestError, match="cannot be read"):
        read_verified(tmp_path / "missing.json")


# ----------------------------------------------------------------------------- evaluator-only gold


def test_gold_digest_never_appears_in_the_arm_visible_view() -> None:
    manifest = make_manifest()
    view = manifest.arm_visible_view()
    assert "gold_manifest_sha256" not in view and "null_reasons" not in view
    assert H3 not in json.dumps(view)
    assert H3 in json.dumps(manifest.to_dict())  # present in the evaluator's own file


# ----------------------------------------------------------------------------- validation


@pytest.mark.parametrize("field", ["source_manifest_sha256", "gold_manifest_sha256", "prompt_digest"])
@pytest.mark.parametrize("bad", ["A" * 64, "a" * 63, "xyz", 5])
def test_digest_fields_must_be_lowercase_sha256_hex(field: str, bad: object) -> None:
    with pytest.raises(ManifestError):
        make_manifest(**{field: bad})


def test_a_null_needs_a_reason_and_a_reason_needs_a_nullable_field() -> None:
    reasons = dict(make_manifest().null_reasons)
    del reasons["pricing_snapshot"]
    with pytest.raises(ManifestError, match="pricing_snapshot is null"):
        make_manifest(null_reasons=reasons)
    with pytest.raises(ManifestError, match="cannot be null"):
        make_manifest(null_reasons={**make_manifest().null_reasons, "seed": "why"})
    with pytest.raises(ManifestError):
        make_manifest(null_reasons={**make_manifest().null_reasons, "pricing_snapshot": " "})


@pytest.mark.parametrize("field", ["seed", "order_seed"])
@pytest.mark.parametrize("bad", [True, 1.5, -1, "4"])
def test_seeds_must_be_non_negative_integers(field: str, bad: object) -> None:
    with pytest.raises(ContractError):
        make_manifest(**{field: bad})


def test_naive_start_time_and_unknown_split_are_refused() -> None:
    with pytest.raises(ContractError):
        make_manifest(started_at_utc="2026-10-18T03:00:00")
    with pytest.raises(ManifestError, match="split"):
        make_manifest(split="holdout")


def test_commit_and_tree_digest_forms_are_checked() -> None:
    with pytest.raises(ManifestError):
        TreeState("benchmark", "abc", H1, ())
    with pytest.raises(ManifestError):
        TreeState("benchmark", COMMIT, "short", ())


# ----------------------------------------------------------------------------- confirmatory mode


def confirmatory(**overrides: Any) -> RunManifest:
    base: dict[str, Any] = {
        "confirmatory": True,
        "model_versions": {"embeddings": "model-a@rev1", "generator": "qwen/qwen3.8-27b"},
    }
    base.update(overrides)
    return make_manifest(**base)


def test_clean_pinned_confirmatory_run_is_accepted() -> None:
    assert confirmatory().confirmatory is True


def test_dirty_benchmark_tree_is_refused() -> None:
    with pytest.raises(ManifestError, match="benchmark working tree is dirty"):
        confirmatory(benchmark=TreeState("benchmark", COMMIT, H1, ("benchmark/x.py",)))


def test_dirty_system_under_test_is_refused_independently_of_a_clean_benchmark() -> None:
    sut = TreeState("palladion", COMMIT, H2, ("src/a.py", "src/b.py"))
    with pytest.raises(ManifestError, match=r"palladion working tree is dirty \(2 path"):
        confirmatory(
            system_under_test=sut,
            null_reasons={k: v for k, v in make_manifest().null_reasons.items() if k != "system_under_test"},
        )


def test_missing_commit_floating_model_and_missing_manifests_are_refused() -> None:
    with pytest.raises(ManifestError, match="no commit"):
        confirmatory(benchmark=TreeState("benchmark", None, None, ()))
    with pytest.raises(ManifestError, match="not pinned"):
        confirmatory(model_versions={"generator": "latest"})
    with pytest.raises(ManifestError, match="not pinned"):
        confirmatory(model_versions={"generator": None})
    reasons = {**make_manifest().null_reasons, "source_manifest_sha256": "not built yet"}
    with pytest.raises(ManifestError, match="manifest digests are required"):
        confirmatory(source_manifest_sha256=None, null_reasons=reasons)


def test_exploratory_runs_may_have_dirty_trees() -> None:
    manifest = make_manifest(benchmark=TreeState("benchmark", COMMIT, H1, ("a.py",)))
    assert not manifest.benchmark.is_clean and manifest.confirmatory is False


# ----------------------------------------------------------------------------- tree capture


def run_git(repo: Path, *args: str) -> None:
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "-C",
            str(repo),
            *args,
        ],
        check=True,
        capture_output=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "sut"
    root.mkdir()
    run_git(root, "init", "-q")
    (root / "a.txt").write_text("alpha\n", encoding="utf-8")
    (root / "sub").mkdir()
    (root / "sub" / "b.txt").write_text("beta\n", encoding="utf-8")
    run_git(root, "add", "-A")
    run_git(root, "commit", "-q", "-m", "init")
    return root


@needs_git
def test_clean_tree_state_has_a_commit_a_digest_and_no_dirty_paths(repo: Path) -> None:
    state = tree_state(repo, label="sut")
    assert state.is_clean and state.commit is not None and state.tree_sha256 is not None
    assert tree_state(repo, label="sut") == state  # deterministic


@needs_git
def test_modified_and_untracked_files_make_the_tree_dirty_and_change_the_digest(repo: Path) -> None:
    clean = tree_state(repo, label="sut")
    (repo / "a.txt").write_text("changed\n", encoding="utf-8")
    (repo / "new.txt").write_text("fresh\n", encoding="utf-8")
    dirty = tree_state(repo, label="sut")
    assert dirty.dirty_files == ("a.txt", "new.txt")
    assert dirty.tree_sha256 != clean.tree_sha256 and dirty.commit == clean.commit


@needs_git
def test_deleted_tracked_file_is_dirty_and_ignored_files_are_not(repo: Path) -> None:
    (repo / ".gitignore").write_text("ignored.log\n", encoding="utf-8")
    run_git(repo, "add", ".gitignore")
    run_git(repo, "commit", "-q", "-m", "ignore")
    (repo / "ignored.log").write_text("noise\n", encoding="utf-8")
    assert tree_state(repo, label="sut").is_clean
    (repo / "a.txt").unlink()
    assert tree_state(repo, label="sut").dirty_files == ("a.txt",)


@needs_git
def test_a_subtree_reports_only_its_own_dirty_paths(repo: Path) -> None:
    (repo / "a.txt").write_text("changed\n", encoding="utf-8")
    assert tree_state(repo / "sub", label="sub").is_clean
    (repo / "sub" / "b.txt").write_text("changed\n", encoding="utf-8")
    assert tree_state(repo / "sub", label="sub").dirty_files == ("sub/b.txt",)


@needs_git
def test_a_rename_is_reported_once_under_its_new_path(repo: Path) -> None:
    run_git(repo, "mv", "a.txt", "renamed.txt")
    assert tree_state(repo, label="sut").dirty_files == ("renamed.txt",)


@needs_git
def test_tree_state_does_not_modify_the_repository_index(repo: Path) -> None:
    before = (repo / ".git" / "index").read_bytes()
    tree_state(repo, label="sut")
    assert (repo / ".git" / "index").read_bytes() == before


def test_missing_directory_and_non_repository_are_refused(tmp_path: Path) -> None:
    with pytest.raises(ManifestError, match="does not exist"):
        tree_state(tmp_path / "nope", label="sut")
    if shutil.which("git"):
        plain = tmp_path / "plain"
        plain.mkdir()
        with pytest.raises(ManifestError, match="git rev-parse failed"):
            tree_state(plain, label="sut")


def test_hardware_description_has_no_host_or_user_identity() -> None:
    text = json.dumps(collect_hardware()).lower()
    import socket

    assert set(collect_hardware()) == {"platform", "machine", "cpu_count", "python", "gpu"}  # no user or host field
    assert socket.gethostname().lower() not in text or len(socket.gethostname()) < 4


@needs_git
def test_an_untracked_file_alone_changes_the_content_digest(repo: Path) -> None:
    clean = tree_state(repo, label="sut")
    (repo / "extra.txt").write_text("only untracked\n", encoding="utf-8")
    assert tree_state(repo, label="sut").tree_sha256 != clean.tree_sha256


def test_a_palladion_arm_needs_its_system_under_test_pinned_in_a_confirmatory_run() -> None:
    reasons = {k: v for k, v in make_manifest().null_reasons.items() if k != "system_under_test"}
    with pytest.raises(ManifestError, match="needs the system under test pinned"):
        confirmatory(arm="R7a", null_reasons={**reasons, "system_under_test": "forgot"})
    sut = TreeState("palladion", COMMIT, H2, ())
    assert confirmatory(arm="R7a", system_under_test=sut, null_reasons=reasons).arm == "R7a"


def test_a_confirmatory_run_must_name_the_models_it_uses() -> None:
    with pytest.raises(ManifestError, match="must name every model"):
        confirmatory(model_versions={})


def test_the_lexical_arm_needs_no_model_but_a_dense_arm_does() -> None:
    assert confirmatory(arm="R0", model_versions={}).arm == "R0"
    with pytest.raises(ManifestError, match="must name every model"):
        confirmatory(arm="R1", model_versions={})
