"""The index build entry point: corpus facts, deterministic rebuilds, refusals, recorded failures (B04-T04.01)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from benchmark.adapters.common import PublishedView, build_chunks

ROOT = Path(__file__).resolve().parents[1]
UNREACHABLE = "http://127.0.0.1:17999"  # nothing listens here, and it is neither Palladion's port nor the benchmark's


def build(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_indices.py"), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=900,
    )


def arm_stats(data: dict[str, Any]) -> dict[str, Any]:
    stats: dict[str, Any] = data["arms"][0]["stats"]
    return stats


def report(index_dir: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((index_dir / "index_report.json").read_text(encoding="utf-8"))
    return data


def test_the_build_records_what_the_corpus_holds_and_what_each_arm_cost(s_published: Path, tmp_path: Path) -> None:
    result = build("--published", str(s_published), "--index-dir", str(tmp_path), "--arms", "R0")
    assert result.returncode == 0, result.stderr
    data = report(tmp_path)
    corpus = data["corpus"]
    view = PublishedView.load(s_published)
    chunks = build_chunks(view)
    assert corpus["documents"] == 1200 and corpus["chunks"] == len(chunks)
    assert corpus["words"] == sum(c.words for c in chunks) and corpus["characters"] == sum(c.characters for c in chunks)
    assert corpus["extraction_failures"] == [] and corpus["tables_lost"] == 0
    stats = arm_stats(data)
    assert len(data["arms"]) == 1 and stats["arm"] == "R0"
    assert stats["chunks"] == len(chunks) and stats["build_ms"] > 0


def test_rebuilding_from_the_same_manifest_gives_matching_counts(s_published: Path, tmp_path: Path) -> None:
    for name in ("a", "b"):
        assert (
            build("--published", str(s_published), "--index-dir", str(tmp_path / name), "--arms", "R0").returncode == 0
        )
    first, second = report(tmp_path / "a"), report(tmp_path / "b")
    assert first["corpus"] == second["corpus"]
    first_stats, second_stats = arm_stats(first), arm_stats(second)
    keep = ("documents", "chunks", "words", "characters", "terms")
    assert [first_stats[k] for k in keep] == [second_stats[k] for k in keep]


def test_the_snapshot_root_is_refused_as_the_corpus(s_root: Path, tmp_path: Path) -> None:
    result = build("--published", str(s_root), "--index-dir", str(tmp_path), "--arms", "R0")
    assert result.returncode == 2 and "refused" in result.stderr
    assert not (tmp_path / "index_report.json").exists()


def test_a_directory_with_annotation_material_is_refused(s_published: Path, s_root: Path, tmp_path: Path) -> None:
    mixed = tmp_path / "mixed"
    mixed.mkdir()
    (mixed / "corpus_manifest.jsonl").write_bytes((s_published / "corpus_manifest.jsonl").read_bytes())
    (mixed / "annotations_dev").mkdir()
    result = build("--published", str(mixed), "--index-dir", str(tmp_path / "index"), "--arms", "R0")
    assert result.returncode == 2 and "annotation or generator" in result.stderr


def test_an_unknown_arm_is_refused(s_published: Path, tmp_path: Path) -> None:
    result = build("--published", str(s_published), "--index-dir", str(tmp_path), "--arms", "R9")
    assert result.returncode == 2 and "not a local arm" in result.stderr


def test_a_failed_build_is_recorded_not_skipped_and_fails_the_command(s_published: Path, tmp_path: Path) -> None:
    cache = (
        ROOT / "artifacts" / "index" / "R1-test"
    )  # embeddings cached by the dense tests, so only the server is missing
    result = build(
        "--published", str(s_published), "--index-dir", str(cache), "--arms", "R0,R1", "--qdrant-url", UNREACHABLE
    )
    assert result.returncode == 1 and "FAIL" in result.stderr, result.stderr
    arms = {a["arm"]: a for a in report(cache)["arms"]}
    assert arms["R0"]["status"] == "BUILT"
    assert arms["R1"]["status"] == "FAILED" and arms["R1"]["error"]


def test_palladions_qdrant_port_is_refused_by_the_dense_arm(s_published: Path, tmp_path: Path) -> None:
    result = build(
        "--published", str(s_published), "--index-dir", str(ROOT / "artifacts" / "index" / "R1-test"),
        "--arms", "R1", "--qdrant-url", "http://127.0.0.1:16333",
    )  # fmt: skip
    assert result.returncode == 1
    record = report(ROOT / "artifacts" / "index" / "R1-test")["arms"][0]
    assert record["status"] == "FAILED" and record["error"] == "AdapterError"
