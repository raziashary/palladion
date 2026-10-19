"""Pins for models and binaries: schema, loading, verification and refusal (B04-T01.04)."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from functools import partial
from pathlib import Path

import pytest

from benchmark.adapters.models import (
    ModelIntegrityError,
    ModelSpec,
    digest_files,
    spec_from_pin,
    verify,
)
from benchmark.config import ConfigError, Pin, load_comparators_config

CONFIGS = Path(__file__).resolve().parents[1] / "configs"
REVISION = "a" * 40
DIGEST = "b" * 64


def test_pin_schema_accepts_revision_and_digests_and_refuses_malformed_ones() -> None:
    pin = Pin("model", "org/name", REVISION, {"f.onnx": DIGEST})
    assert pin.is_verifiable and pin.revision == REVISION
    malformed: list[Callable[[], Pin]] = [
        partial(Pin, "model", "org/name", "main", {}),
        partial(Pin, "model", "org/name", REVISION[:-1], {}),
        partial(Pin, "model", "org/name", REVISION, {"f": "xyz"}),
        partial(Pin, "model", "org/name", REVISION, {"f": DIGEST.upper()}),
        partial(Pin, "unpinned", "UNPINNED", REVISION),
        partial(Pin, "unpinned", "UNPINNED", None, {"f": DIGEST}),
    ]
    for build in malformed:
        with pytest.raises(ConfigError):
            build()


def test_a_model_pin_without_revision_or_digests_is_not_verifiable() -> None:
    assert not Pin("model", "org/name").is_verifiable
    assert not Pin("model", "org/name", REVISION).is_verifiable
    assert not Pin("unpinned", "UNPINNED").is_verifiable
    assert Pin("version", "1.19.2").is_verifiable


def test_the_shipped_comparators_pin_the_models_and_the_qdrant_binary() -> None:
    config = load_comparators_config(CONFIGS / "comparators.yaml")
    for name in ("embeddings", "reranker", "qdrant_server"):
        assert config.shared_models[name].is_verifiable, name
    assert config.shared_models["embeddings"].revision == "faf4aa4225822f3bc6376869cb1164e8e3feedd0"
    assert len(config.shared_models["qdrant_server"].digests) == 1


def test_confirmatory_mode_refuses_an_unverifiable_model_even_when_every_arm_is_pinned(tmp_path: Path) -> None:
    text = (CONFIGS / "comparators.yaml").read_text(encoding="utf-8")
    pinned = text.replace('pin: {kind: unpinned, value: "UNPINNED"}', 'pin: {kind: version, value: "1.0.0"}')
    pinned = pinned.replace(
        'system_under_test: {kind: unpinned, value: "UNPINNED"}', 'system_under_test: {kind: version, value: "1.0.0"}'
    )
    assert "kind: unpinned" not in pinned
    path = tmp_path / "comparators.yaml"
    path.write_text(pinned, encoding="utf-8")
    assert load_comparators_config(path, confirmatory=True).shared_models["reranker"].is_verifiable
    stripped = pinned.replace('    revision: "a09144355adeed5f58c8ed011d209bf8ee5a1fec"\n', "")
    other = tmp_path / "other.yaml"
    other.write_text(stripped, encoding="utf-8")
    with pytest.raises(ConfigError, match=r"revision and file digests for: reranker"):
        load_comparators_config(other, confirmatory=True)


def make_snapshot(tmp_path: Path) -> tuple[Path, ModelSpec]:
    folder = tmp_path / "snapshot"
    (folder / "onnx").mkdir(parents=True)
    (folder / "onnx" / "model.onnx").write_bytes(b"weights")
    (folder / "config.json").write_text("{}", encoding="utf-8")
    files = ("onnx/model.onnx", "config.json")
    return folder, ModelSpec("org/name", REVISION, files, digest_files(folder, files))


def test_verify_accepts_the_pinned_files(tmp_path: Path) -> None:
    folder, spec = make_snapshot(tmp_path)
    verify(folder, spec)


def test_verify_refuses_a_tampered_missing_or_unpinned_snapshot(tmp_path: Path) -> None:
    folder, spec = make_snapshot(tmp_path)
    (folder / "config.json").write_text('{"x": 1}', encoding="utf-8")
    with pytest.raises(ModelIntegrityError, match=r"differ from the pin: config.json"):
        verify(folder, spec)
    (folder / "config.json").unlink()
    with pytest.raises(ModelIntegrityError, match="missing model file"):
        verify(folder, spec)
    with pytest.raises(ModelIntegrityError, match="no recorded digests"):
        verify(folder, ModelSpec("org/name", REVISION, spec.files, {}))


def test_spec_validation() -> None:
    with pytest.raises(ModelIntegrityError):
        ModelSpec("org/name", "main", ("f",), {})
    with pytest.raises(ModelIntegrityError):
        ModelSpec("org/name", REVISION, ("f", "f"), {})
    with pytest.raises(ModelIntegrityError):
        ModelSpec("org/name", REVISION, ("f",), {"other": DIGEST})


def test_the_comparators_pin_converts_to_a_spec_and_rejects_non_models() -> None:
    config = load_comparators_config(CONFIGS / "comparators.yaml")
    spec = spec_from_pin(config.shared_models["embeddings"])
    assert spec.repository.startswith("Qdrant/") and spec.is_pinned and "model_optimized.onnx" in spec.files
    with pytest.raises(ModelIntegrityError):
        spec_from_pin(config.shared_models["qdrant_server"])
    with pytest.raises(ModelIntegrityError):
        spec_from_pin(Pin("model", "org/name"))


def test_the_downloaded_snapshots_match_the_pins_when_present() -> None:
    cache = Path(__file__).resolve().parents[1] / "artifacts" / "models"
    config = load_comparators_config(CONFIGS / "comparators.yaml")
    found = 0
    for name in ("embeddings", "reranker"):
        spec = spec_from_pin(config.shared_models[name])
        for snapshot in cache.glob(f"{name}/models--*/snapshots/{spec.revision}"):
            verify(snapshot, spec)
            found += 1
    if not cache.exists():
        pytest.skip("models are not downloaded on this machine")
    assert found == 2


class FakeFile:
    def __init__(self, name: str, size: int) -> None:
        self.rfilename, self.size = name, size


def fake_hub(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, sizes: dict[str, int], content: dict[str, bytes]
) -> list[str]:
    """Stand in for the Hub: file sizes from model_info, and a download that writes ``content`` into a folder."""
    import huggingface_hub

    calls: list[str] = []

    def model_info(self: object, repo: str, revision: str, files_metadata: bool) -> object:
        calls.append("info")
        return type("Info", (), {"siblings": [FakeFile(n, s) for n, s in sizes.items()]})()

    def snapshot_download(**kwargs: object) -> str:
        calls.append("download")
        folder = tmp_path / "downloaded"
        for name, data in content.items():
            (folder / name).parent.mkdir(parents=True, exist_ok=True)
            (folder / name).write_bytes(data)
        return str(folder)

    monkeypatch.setattr(huggingface_hub.HfApi, "model_info", model_info)
    monkeypatch.setattr(huggingface_hub, "snapshot_download", snapshot_download)
    return calls


def test_fetch_checks_the_size_first_then_downloads_and_verifies(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from benchmark.adapters.models import fetch

    good = {"a.bin": b"weights", "b.json": b"{}"}
    spec = ModelSpec("org/name", REVISION, tuple(good), {n: hashlib.sha256(d).hexdigest() for n, d in good.items()})
    calls = fake_hub(monkeypatch, tmp_path, {"a.bin": 7, "b.json": 2, "other": 10**9}, good)
    folder = fetch(spec, tmp_path / "cache")
    assert calls == ["info", "download"] and (folder / "a.bin").read_bytes() == b"weights"


def test_fetch_refuses_an_oversized_download_before_downloading(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from benchmark.adapters.models import fetch

    spec = ModelSpec("org/name", REVISION, ("a.bin",), {})
    calls = fake_hub(monkeypatch, tmp_path, {"a.bin": 5_000}, {"a.bin": b"x"})
    with pytest.raises(ModelIntegrityError, match="above the bound"):
        fetch(spec, tmp_path / "cache", max_bytes=1_000)
    assert calls == ["info"], "nothing is downloaded when the bound is exceeded"


def test_fetch_refuses_a_file_the_repository_does_not_have(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from benchmark.adapters.models import fetch

    fake_hub(monkeypatch, tmp_path, {"a.bin": 1}, {"a.bin": b"x"})
    with pytest.raises(ModelIntegrityError, match="no file"):
        fetch(ModelSpec("org/name", REVISION, ("a.bin", "missing.bin"), {}), tmp_path / "cache")


def test_fetch_refuses_a_download_that_differs_from_the_pin(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from benchmark.adapters.models import fetch

    spec = ModelSpec("org/name", REVISION, ("a.bin",), {"a.bin": "0" * 64})
    fake_hub(monkeypatch, tmp_path, {"a.bin": 7}, {"a.bin": b"weights"})
    with pytest.raises(ModelIntegrityError, match="differ from the pin"):
        fetch(spec, tmp_path / "cache")
