"""Run a checksum-pinned standalone Qdrant server without Docker or system installation."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import signal
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path

VERSION = "1.19.2"
ASSETS = {
    "Linux": ("qdrant-x86_64-unknown-linux-musl.tar.gz",
              "50b253243309ed0ae50a19f678f0d0adcc4f0b567b3bd2c5c0c7e02fa8404bb6"),
}


def install(root: Path) -> Path:
    """Download only an official pinned public release; never overwrite persistent data."""
    system = platform.system()
    if system not in ASSETS or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise ValueError("The server requires x86_64 Linux; Windows uses the WSL entry point")
    asset, checksum = ASSETS[system]
    root.mkdir(parents=True, exist_ok=True)
    archive = root / asset
    if not archive.exists():
        url = f"https://github.com/qdrant/qdrant/releases/download/v{VERSION}/{asset}"
        # Bounded download and exclusive final publication; interrupted files stay temporary.
        with tempfile.TemporaryDirectory(prefix="download-", dir=root) as temporary:
            target = Path(temporary) / asset
            with urllib.request.urlopen(url, timeout=120) as response, target.open("wb") as output:
                total = 0
                while block := response.read(1024 * 1024):
                    total += len(block)
                    if total > 128 * 1024 * 1024:
                        raise ValueError("Release archive exceeds download bound")
                    output.write(block)
            if hashlib.sha256(target.read_bytes()).hexdigest() != checksum:
                raise ValueError("Qdrant release checksum mismatch")
            os.replace(target, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != checksum:
        raise ValueError("Cached release checksum mismatch; inspect it before replacement")
    filename = "qdrant"
    binary = root / filename
    # Extract only the executable, never arbitrary archive paths or symlinks.
    with tarfile.open(archive) as tar:
        member_info = next(item for item in tar.getmembers()
                           if Path(item.name).name == filename and item.isfile())
        stream = tar.extractfile(member_info)
        if stream is None:
            raise ValueError("Missing executable")
        data = stream.read()
    if not binary.exists():
        with binary.open("xb") as output:
            output.write(data)
        binary.chmod(0o700)
    elif binary.read_bytes() != data:
        raise ValueError("Cached executable differs from verified release")
    return binary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--port", type=int, default=16333)
    parser.add_argument("--install-only", action="store_true")
    parser.add_argument("--stop", action="store_true", help="Stop only this launcher's recorded server")
    parser.add_argument("--wsl", action="store_true", help="Use Ubuntu's Linux filesystem on Windows")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65534:
        raise ValueError("Use a nonprivileged port with one adjacent gRPC port")
    if args.wsl or platform.system() == "Windows":
        if platform.system() != "Windows" or args.root is not None:
            raise ValueError("Windows runs through WSL using a Linux-owned persistent data directory")
        script = str(Path(__file__).resolve())
        converted = subprocess.run(["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", script],
                                   capture_output=True, text=True, check=True).stdout.strip()
        command = ["wsl", "-d", "Ubuntu", "--exec", "python3", converted, "--port", str(args.port)]
        if args.install_only:
            command.append("--install-only")
        if args.stop:
            command.append("--stop")
        raise SystemExit(subprocess.call(command))
    default_root = (Path.home() / ".local/share/palladion/qdrant" if platform.system() == "Linux"
                    else Path(__file__).resolve().parents[1] / "runtime/qdrant")
    root = (args.root or default_root).resolve()
    marker = root / "server.json"
    if args.stop:
        if not marker.exists():
            print("No recorded standalone server")
            return
        record = json.loads(marker.read_text(encoding="utf-8"))
        pid = int(record["pid"])
        process_executable = Path(f"/proc/{pid}/exe")
        if not process_executable.exists():
            print("Recorded server is already stopped")
            return
        if process_executable.resolve() != Path(record["executable"]).resolve():
            raise ValueError("Recorded PID belongs to a different executable; refusing to stop it")
        os.kill(pid, signal.SIGTERM)
        print(f"Termination requested for recorded Qdrant PID {pid}; storage preserved")
        return
    binary = install(root / f"bin-{VERSION}")
    if args.install_only:
        subprocess.run([str(binary), "--version"], check=True)
        return
    # JSON string quoting is valid YAML and handles Windows paths and spaces safely.
    config = root / "standalone.yaml"
    config.write_text(
        f"storage:\n  storage_path: {json.dumps(str(root / 'storage'))}\n"
        f"service:\n  host: 127.0.0.1\n  http_port: {args.port}\n  grpc_port: {args.port + 1}\n"
        "telemetry_disabled: true\n", encoding="utf-8")
    child = subprocess.Popen([str(binary), "--config-path", str(config)], cwd=root)
    marker.write_text(json.dumps({"pid": child.pid, "executable": str(binary)}), encoding="utf-8")
    print(f"Standalone Qdrant {VERSION}, PID {child.pid}, localhost:{args.port}", flush=True)
    try:
        raise SystemExit(child.wait())
    except KeyboardInterrupt:
        child.terminate()
        child.wait(timeout=20)


if __name__ == "__main__":
    main()
