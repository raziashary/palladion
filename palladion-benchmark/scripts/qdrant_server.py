"""Run the benchmark's own checksum-pinned standalone Qdrant under WSL, without Docker (B04-T01.05, BADR-0017).

The server listens on 127.0.0.1:17333 (gRPC 17334) with a data directory of its own. Palladion's server (16333, 16334)
and its store are never touched: those ports are refused outright and a busy port is refused rather than shared.

Commands: ``install`` (download and verify the pinned release), ``start`` (add ``--detach`` to return once healthy),
``status``, ``stop``. On Windows every command is forwarded into the Ubuntu distribution; the script itself uses only
the standard library and runs on the Python 3.10 that Ubuntu ships.

This script downloads only from the official Qdrant release URL, only the pinned version, and refuses an archive whose
SHA-256 differs from the pin. The pin below is checked against ``configs/comparators.yaml`` by the launcher's tests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import signal
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

VERSION = "1.19.2"
ASSET = "qdrant-x86_64-unknown-linux-musl.tar.gz"
SHA256 = "50b253243309ed0ae50a19f678f0d0adcc4f0b567b3bd2c5c0c7e02fa8404bb6"
URL = f"https://github.com/qdrant/qdrant/releases/download/v{VERSION}/{ASSET}"
DEFAULT_PORT = 17333
PALLADION_PORTS = frozenset({16333, 16334})
MAX_DOWNLOAD_BYTES = 128 * 1024 * 1024
HEALTH_TIMEOUT_SECONDS = 60.0
DISTRIBUTION = "Ubuntu"
DEFAULT_ROOT = Path.home() / ".local/share/palladion-benchmark/qdrant"
PALLADION_ROOT_FRAGMENT = "share/palladion/qdrant"


class LauncherError(ValueError):
    """The launcher refused to do something unsafe or unverifiable. The message holds no secrets."""


def ensure_allowed_port(port: int) -> int:
    """A non-privileged port that is not Palladion's, with the adjacent gRPC port also allowed."""
    if not 1024 <= port <= 65534:
        raise LauncherError("use a non-privileged port with one adjacent gRPC port")
    if port in PALLADION_PORTS or port + 1 in PALLADION_PORTS:
        raise LauncherError("that port belongs to Palladion's server; the benchmark never uses it")
    return port


def ensure_allowed_root(root: Path) -> Path:
    resolved = root.resolve()
    if PALLADION_ROOT_FRAGMENT in resolved.as_posix() and "palladion-benchmark" not in resolved.as_posix():
        raise LauncherError("that data directory belongs to Palladion; the benchmark keeps its own")
    return resolved


def port_is_free(port: int) -> bool:
    """True when nothing accepts connections on 127.0.0.1:port, for the port and its gRPC neighbour."""
    for candidate in (port, port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.5)
            if probe.connect_ex(("127.0.0.1", candidate)) == 0:
                return False
    return True


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_archive(path: Path, expected: str = SHA256) -> None:
    if sha256_of(path) != expected:
        raise LauncherError("the Qdrant archive does not match its pinned SHA-256")


def download(root: Path, url: str = URL, expected: str = SHA256) -> Path:
    """Fetch the pinned archive into ``root`` (bounded size, exclusive publication) and verify it."""
    root.mkdir(parents=True, exist_ok=True)
    archive = root / ASSET
    if archive.exists():
        verify_archive(archive, expected)
        return archive
    with tempfile.TemporaryDirectory(prefix="download-", dir=root) as temporary:
        target = Path(temporary) / ASSET
        total = 0
        with urllib.request.urlopen(url, timeout=120) as response, target.open("wb") as output:
            while block := response.read(1024 * 1024):
                total += len(block)
                if total > MAX_DOWNLOAD_BYTES:
                    raise LauncherError("the release archive exceeds the download bound")
                output.write(block)
        verify_archive(target, expected)
        os.replace(target, archive)
    return archive


def extract_binary(archive: Path, root: Path) -> Path:
    """Extract only the ``qdrant`` executable; never other archive paths or links."""
    root.mkdir(parents=True, exist_ok=True)
    binary = root / "qdrant"
    with tarfile.open(archive) as tar:
        member = next((m for m in tar.getmembers() if Path(m.name).name == "qdrant" and m.isfile()), None)
        if member is None:
            raise LauncherError("the archive holds no qdrant executable")
        stream = tar.extractfile(member)
        if stream is None:
            raise LauncherError("the archive's executable could not be read")
        data = stream.read()
    if binary.exists():
        if binary.read_bytes() != data:
            raise LauncherError("the cached executable differs from the verified release")
        return binary
    with binary.open("xb") as output:
        output.write(data)
    binary.chmod(0o700)
    return binary


def install(root: Path) -> Path:
    return extract_binary(download(root), root)


def write_config(root: Path, port: int) -> Path:
    config = root / "standalone.yaml"
    config.write_text(
        f"storage:\n  storage_path: {json.dumps(str(root / 'storage'))}\n"
        f"service:\n  host: 127.0.0.1\n  http_port: {port}\n  grpc_port: {port + 1}\n"
        "telemetry_disabled: true\n",
        encoding="utf-8",
    )
    return config


def healthy(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=2) as response:
            return bool(response.status == 200)
    except (urllib.error.URLError, OSError):
        return False


def start(root: Path, port: int, *, detach: bool) -> int:
    ensure_allowed_port(port)
    root = ensure_allowed_root(root)
    marker = root / "server.json"
    if marker.exists() and recorded_process_alive(root):
        raise LauncherError("a server recorded by this launcher is already running")
    if not port_is_free(port):
        raise LauncherError("the port is busy; the launcher never shares or takes over a port")
    binary = install(root)
    config = write_config(root, port)
    child = subprocess.Popen([str(binary), "--config-path", str(config)], cwd=root, start_new_session=detach)
    marker.write_text(json.dumps({"pid": child.pid, "executable": str(binary), "port": port}), encoding="utf-8")
    print(f"Standalone Qdrant {VERSION}, PID {child.pid}, 127.0.0.1:{port}", flush=True)
    if detach:
        deadline = time.monotonic() + HEALTH_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if healthy(port):
                return 0
            if child.poll() is not None:
                raise LauncherError("the server exited before it became healthy")
            time.sleep(0.5)
        raise LauncherError("the server did not become healthy in time")
    try:
        return child.wait()
    except KeyboardInterrupt:
        child.terminate()
        child.wait(timeout=20)
        return 0


def recorded_process_alive(root: Path, proc_root: Path = Path("/proc")) -> bool:
    marker = root / "server.json"
    if not marker.exists():
        return False
    record = json.loads(marker.read_text(encoding="utf-8"))
    executable = proc_root / str(int(record["pid"])) / "exe"
    return executable.exists() and executable.resolve() == Path(record["executable"]).resolve()


def stop(root: Path, proc_root: Path = Path("/proc")) -> str:
    """Stop only the server this launcher recorded, and only if that PID still runs the recorded executable."""
    marker = root / "server.json"
    if not marker.exists():
        return "no recorded server"
    record = json.loads(marker.read_text(encoding="utf-8"))
    pid = int(record["pid"])
    executable = proc_root / str(pid) / "exe"
    if not executable.exists():
        return "the recorded server is already stopped"
    if executable.resolve() != Path(record["executable"]).resolve():
        raise LauncherError("the recorded PID belongs to a different executable; refusing to stop it")
    os.kill(pid, signal.SIGTERM)
    return f"termination requested for recorded PID {pid}; storage preserved"


def forward_to_wsl(argv: list[str]) -> int:
    script = str(Path(__file__).resolve())
    converted = subprocess.run(
        ["wsl", "-d", DISTRIBUTION, "--exec", "wslpath", "-a", script], capture_output=True, text=True, check=True
    ).stdout.strip()
    return subprocess.call(["wsl", "-d", DISTRIBUTION, "--exec", "python3", converted, *argv])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=("install", "start", "status", "stop"))
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--root", type=Path, default=None, help="Linux only; Windows always uses the WSL default")
    parser.add_argument("--detach", action="store_true", help="with start: return once the server answers /healthz")
    args = parser.parse_args(argv)
    if platform.system() == "Windows":
        if args.root is not None:
            print("refused: on Windows the data directory is the WSL default", file=sys.stderr)
            return 2
        forwarded = [args.command, "--port", str(args.port)] + (["--detach"] if args.detach else [])
        return forward_to_wsl(forwarded)
    try:
        port = ensure_allowed_port(args.port)
        root = ensure_allowed_root(args.root or DEFAULT_ROOT)
        if args.command == "install":
            binary = install(root)
            subprocess.run([str(binary), "--version"], check=True)
            return 0
        if args.command == "start":
            return start(root, port, detach=args.detach)
        if args.command == "status":
            print(f"port {port}: {'healthy' if healthy(port) else 'not answering'}")
            return 0 if healthy(port) else 1
        print(stop(root))
        return 0
    except LauncherError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
