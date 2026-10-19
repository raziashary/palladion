"""The Docker-free Qdrant launcher: pins, refusals with negative controls, and a real start under WSL (B04-T01.05)."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import shutil
import socket
import subprocess
import tarfile
import urllib.error
import urllib.request
from pathlib import Path
from types import ModuleType

import pytest

from benchmark.config import load_comparators_config

ROOT = Path(__file__).resolve().parents[1]


def load_launcher() -> ModuleType:
    spec = importlib.util.spec_from_file_location("qdrant_server", ROOT / "scripts" / "qdrant_server.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


launcher = load_launcher()


def make_archive(path: Path, payload: bytes, member: str = "qdrant") -> str:
    with tarfile.open(path, "w:gz") as tar:
        info = tarfile.TarInfo(member)
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- the pin


def test_the_launcher_pin_equals_the_pin_in_comparators_yaml() -> None:
    pin = load_comparators_config(ROOT / "configs" / "comparators.yaml").shared_models["qdrant_server"]
    assert pin.value == launcher.VERSION
    assert pin.digests == {launcher.ASSET: launcher.SHA256}
    assert f"https://github.com/qdrant/qdrant/releases/download/v{launcher.VERSION}/{launcher.ASSET}" == launcher.URL


# --------------------------------------------------------------------------- refusals


@pytest.mark.parametrize("port", [16333, 16334, 16332, 18080, 18079])
def test_palladions_ports_and_their_neighbours_are_refused(port: int) -> None:
    with pytest.raises(launcher.LauncherError, match="Palladion"):
        launcher.ensure_allowed_port(port)


@pytest.mark.parametrize("port", [80, 1023, 65535, 70000])
def test_privileged_and_out_of_range_ports_are_refused(port: int) -> None:
    with pytest.raises(launcher.LauncherError, match="non-privileged"):
        launcher.ensure_allowed_port(port)


def test_the_default_port_is_allowed() -> None:
    assert launcher.ensure_allowed_port(launcher.DEFAULT_PORT) == 17333


def test_palladions_data_directory_is_refused(tmp_path: Path) -> None:
    with pytest.raises(launcher.LauncherError, match="Palladion"):
        launcher.ensure_allowed_root(tmp_path / "share/palladion/qdrant")
    assert launcher.ensure_allowed_root(tmp_path / "share/palladion-benchmark/qdrant")


def test_a_busy_port_is_detected_on_the_port_or_its_grpc_neighbour() -> None:
    with socket.socket() as first, socket.socket() as second:
        first.bind(("127.0.0.1", 0))
        first.listen()
        busy = first.getsockname()[1]
        assert not launcher.port_is_free(busy)
        second.bind(("127.0.0.1", 0))
        second.listen()
        neighbour = second.getsockname()[1]
        assert not launcher.port_is_free(neighbour - 1)
    quiet = socket.socket()
    quiet.bind(("127.0.0.1", 0))
    free = quiet.getsockname()[1]
    quiet.close()
    assert launcher.port_is_free(free)


def test_start_refuses_a_busy_port_before_touching_anything(tmp_path: Path) -> None:
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        port = occupied.getsockname()[1]
        with pytest.raises(launcher.LauncherError, match="busy"):
            launcher.start(tmp_path / "share/palladion-benchmark/qdrant", port, detach=True)
    assert not (tmp_path / "share/palladion-benchmark/qdrant/qdrant").exists()


# --------------------------------------------------------------------------- checksum


def test_a_wrong_checksum_is_refused_and_nothing_is_published(tmp_path: Path) -> None:
    source = tmp_path / "source.tar.gz"
    make_archive(source, b"binary")
    with pytest.raises(launcher.LauncherError, match="pinned SHA-256"):
        launcher.download(tmp_path / "root", source.as_uri(), "0" * 64)
    assert not (tmp_path / "root" / launcher.ASSET).exists()
    assert [p.name for p in (tmp_path / "root").iterdir()] == [], "the partial download is removed"


def test_the_right_checksum_is_published_and_reused(tmp_path: Path) -> None:
    source = tmp_path / "source.tar.gz"
    digest = make_archive(source, b"binary")
    archive = launcher.download(tmp_path / "root", source.as_uri(), digest)
    assert archive.name == launcher.ASSET and launcher.sha256_of(archive) == digest
    source.unlink()
    assert launcher.download(tmp_path / "root", source.as_uri(), digest) == archive, (
        "a cached archive is verified, not refetched"
    )


def test_a_cached_archive_that_no_longer_matches_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / launcher.ASSET).write_bytes(b"corrupted")
    with pytest.raises(launcher.LauncherError, match="pinned SHA-256"):
        launcher.download(root, "file:///does-not-matter", "1" * 64)


def test_an_oversized_download_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source.tar.gz"
    digest = make_archive(source, b"x" * 5000)
    monkeypatch.setattr(launcher, "MAX_DOWNLOAD_BYTES", 100)
    with pytest.raises(launcher.LauncherError, match="bound"):
        launcher.download(tmp_path / "root", source.as_uri(), digest)


# --------------------------------------------------------------------------- extraction


def test_only_the_executable_is_extracted_and_a_changed_cache_is_refused(tmp_path: Path) -> None:
    archive = tmp_path / "a.tar.gz"
    make_archive(archive, b"real binary", member="release/qdrant")
    binary = launcher.extract_binary(archive, tmp_path / "bin")
    assert binary.read_bytes() == b"real binary" and [p.name for p in (tmp_path / "bin").iterdir()] == ["qdrant"]
    assert launcher.extract_binary(archive, tmp_path / "bin") == binary
    binary.write_bytes(b"swapped")
    with pytest.raises(launcher.LauncherError, match="differs"):
        launcher.extract_binary(archive, tmp_path / "bin")


def test_an_archive_without_the_executable_is_refused(tmp_path: Path) -> None:
    archive = tmp_path / "a.tar.gz"
    make_archive(archive, b"data", member="README")
    (tmp_path / "bin").mkdir()
    with pytest.raises(launcher.LauncherError, match="no qdrant executable"):
        launcher.extract_binary(archive, tmp_path / "bin")


# --------------------------------------------------------------------------- stopping


def write_marker(root: Path, pid: int, executable: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "server.json").write_text(
        f'{{"pid": {pid}, "executable": "{executable.as_posix()}", "port": 17333}}', encoding="utf-8"
    )


def test_stop_does_nothing_without_a_record_or_for_a_dead_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    killed: list[int] = []
    monkeypatch.setattr(launcher.os, "kill", lambda pid, sig: killed.append(pid))
    assert launcher.stop(tmp_path) == "no recorded server"
    write_marker(tmp_path, 4242, tmp_path / "qdrant")
    assert "already stopped" in launcher.stop(tmp_path, proc_root=tmp_path / "proc")
    assert killed == []


def test_stop_refuses_a_pid_that_runs_a_different_executable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    killed: list[int] = []
    monkeypatch.setattr(launcher.os, "kill", lambda pid, sig: killed.append(pid))
    proc = tmp_path / "proc" / "4242"
    proc.mkdir(parents=True)
    (proc / "exe").write_bytes(b"someone else's program")
    write_marker(tmp_path, 4242, tmp_path / "qdrant")
    with pytest.raises(launcher.LauncherError, match="different executable"):
        launcher.stop(tmp_path, proc_root=tmp_path / "proc")
    assert killed == []


def test_stop_signals_only_the_recorded_matching_process(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    killed: list[int] = []
    monkeypatch.setattr(launcher.os, "kill", lambda pid, sig: killed.append(pid))
    binary = tmp_path / "qdrant"
    binary.write_bytes(b"x")
    proc = tmp_path / "proc" / "4242"
    proc.mkdir(parents=True)
    (proc / "exe").write_bytes(b"x")
    write_marker(tmp_path, 4242, proc / "exe")
    assert "termination requested" in launcher.stop(tmp_path, proc_root=tmp_path / "proc")
    assert killed == [4242]
    assert launcher.recorded_process_alive(tmp_path, tmp_path / "proc")


# --------------------------------------------------------------------------- the real server under WSL


def wsl_ubuntu_available() -> bool:
    if shutil.which("wsl") is None:
        return False
    result = subprocess.run(["wsl", "-l", "-q"], capture_output=True, text=True, check=False)
    return "Ubuntu" in result.stdout.replace("\x00", "")


def health(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=3) as response:
            return bool(response.status == 200)
    except (urllib.error.URLError, OSError):
        return False


@pytest.mark.skipif(not wsl_ubuntu_available(), reason="WSL Ubuntu is not available")
def test_the_server_starts_answers_stops_and_leaves_palladions_port_alone() -> None:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams

    script = str(ROOT / "scripts" / "qdrant_server.py")

    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["python", script, *args], capture_output=True, text=True, check=False, timeout=180)

    palladion_before = health(16333)
    assert run("stop").returncode == 0  # a leftover record from an interrupted run is cleared first
    assert not health(launcher.DEFAULT_PORT)
    started = run("start", "--detach")
    try:
        assert started.returncode == 0, started.stderr
        assert health(launcher.DEFAULT_PORT)
        busy = run("start", "--detach")
        assert busy.returncode == 2 and "already running" in busy.stderr
        client = QdrantClient(url=f"http://127.0.0.1:{launcher.DEFAULT_PORT}")
        client.create_collection("launcher_smoke", vectors_config=VectorParams(size=4, distance=Distance.COSINE))
        assert client.collection_exists("launcher_smoke")
        client.delete_collection("launcher_smoke")
        client.close()
    finally:
        stopped = run("stop")
    assert stopped.returncode == 0, stopped.stderr
    deadline = 20
    while health(launcher.DEFAULT_PORT) and deadline:
        subprocess.run(["python", "-c", "import time; time.sleep(0.5)"], check=True)
        deadline -= 1
    assert not health(launcher.DEFAULT_PORT)
    assert health(16333) == palladion_before, "Palladion's server must be exactly as it was"
    refused = run("start", "--port", "16333")
    assert refused.returncode == 2
