"""Explicit Docker-free synthetic Neo4j launcher; preserves project-owned storage."""

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

VERSION = "2026.09.0"
ARCHIVES = (
    (
        "neo4j",
        f"https://dist.neo4j.org/neo4j-community-{VERSION}-unix.tar.gz",
        "cdaa0905d9a533bbbc474d239c268f69978982eb5ca3177666c04c9792d1c399",
    ),
    (
        "java",
        "https://github.com/adoptium/temurin21-binaries/releases/download/"
        "jdk-21.0.12.1%2B1/OpenJDK21U-jre_x64_linux_hotspot_21.0.12.1_1.tar.gz",
        "2413149700df0f7d440500a84a8f764c535f21e5a5e87d38328b64eec2c5b500",
    ),
)


def install(root: Path) -> None:
    for name, url, checksum in ARCHIVES:
        archive = root / (name + ".tar.gz")
        if not archive.exists():
            temporary = root / (name + ".download")
            # Interrupted downloads are overwritten only in the named scratch file.
            with urllib.request.urlopen(url, timeout=60) as response, temporary.open("wb") as out:
                size = 0
                while block := response.read(1024 * 1024):
                    size += len(block)
                    if size > 512 * 1024 * 1024:
                        raise ValueError("Archive exceeds download bound")
                    out.write(block)
            if hashlib.sha256(temporary.read_bytes()).hexdigest() != checksum:
                raise ValueError("Official archive checksum mismatch")
            temporary.rename(archive)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != checksum:
            raise ValueError("Cached archive checksum mismatch")
        target = root / name
        if not target.exists():
            temporary_root = Path(tempfile.mkdtemp(prefix=name + "-extract-", dir=root))
            with tarfile.open(archive) as bundle:
                # Materialize archive-contained link bytes rather than filesystem links.
                # This preserves the JRE's shared license files without permitting escape.
                for member in bundle.getmembers():
                    destination = (temporary_root / member.name).resolve()
                    if not destination.is_relative_to(temporary_root) or member.name.startswith(
                        "/"
                    ):
                        raise ValueError("Archive path escapes extraction root")
                    if member.isdir():
                        destination.mkdir(parents=True, exist_ok=True)
                    elif member.isfile() or member.issym() or member.islnk():
                        stream = bundle.extractfile(member)
                        if stream is None or member.size > 256 * 1024 * 1024:
                            raise ValueError("Archive member exceeds bound")
                        data = stream.read(256 * 1024 * 1024 + 1)
                        if len(data) > 256 * 1024 * 1024:
                            raise ValueError("Archive member exceeds bound")
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        with destination.open("xb") as output:
                            output.write(data)
                        destination.chmod(member.mode & 0o777)
                    else:
                        raise ValueError("Archive device/unsupported member")
            children = list(temporary_root.iterdir())
            if len(children) != 1 or not children[0].is_dir():
                raise ValueError("Unexpected archive layout")
            children[0].rename(target)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wsl", action="store_true")
    parser.add_argument("--install-only", action="store_true")
    parser.add_argument("--stop", action="store_true")
    args = parser.parse_args()
    if platform.system() == "Windows":
        converted = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--exec", "wslpath", "-a", str(Path(__file__).resolve())],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        command = ["wsl", "-d", "Ubuntu", "--exec", "python3", converted]
        command += ["--install-only"] if args.install_only else ["--stop"] if args.stop else []
        raise SystemExit(subprocess.call(command))
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise ValueError("Synthetic launcher requires Linux x86_64 / Windows WSL")
    root = Path.home() / ".local/share/palladion/neo4j-p07"
    root.mkdir(parents=True, exist_ok=True)
    marker = root / "server.json"
    if args.stop:
        if not marker.exists():
            print("No recorded Neo4j server")
            return
        record = json.loads(marker.read_text())
        pid = record["pid"]
        command_line = Path(f"/proc/{pid}/cmdline")
        if not command_line.exists():
            print("Recorded Neo4j already stopped")
            return
        if str(root / "neo4j") not in command_line.read_bytes().decode().replace("\x00", " "):
            raise ValueError("Recorded PID belongs to another process")
        children_path = Path(f"/proc/{pid}/task/{pid}/children")
        children = children_path.read_text().split() if children_path.exists() else []
        for child_pid in children:
            child_command = Path(f"/proc/{child_pid}/cmdline")
            if (
                child_command.exists()
                and str(root / "neo4j") in child_command.read_bytes().decode()
            ):
                os.kill(int(child_pid), signal.SIGTERM)
        os.kill(pid, signal.SIGTERM)
        print("Recorded Neo4j terminated; storage preserved")
        return
    install(root)
    environment = dict(os.environ, JAVA_HOME=str(root / "java"))
    if args.install_only:
        subprocess.run([str(root / "java/bin/java"), "-version"], check=True, env=environment)
        return
    configuration = root / "neo4j/conf/neo4j.conf"
    configuration.write_text(
        "\n".join(
            (
                "server.default_listen_address=127.0.0.1",
                "server.bolt.enabled=true",
                "server.bolt.listen_address=127.0.0.1:17687",
                "server.fleet_discovery.enabled=false",
                "dbms.fleet_manager.enabled=false",
                "dbms.usage_report.enabled=false",
                "server.jvm.additional=-Djava.net.preferIPv4Stack=true",
                "server.bolt.advertised_address=127.0.0.1:17687",
                "server.http.enabled=false",
                "server.https.enabled=false",
                "dbms.security.auth_enabled=false",
                "server.memory.heap.initial_size=256m",
                "server.memory.heap.max_size=512m",
                "server.memory.pagecache.size=256m",
                "db.tx_log.rotation.retention_policy=256M size",
            )
        )
        + "\n"
    )
    # The official script execs Java; preserve its actual PID for scoped shutdown.
    child = subprocess.Popen(
        [str(root / "neo4j/bin/neo4j"), "console"], env=environment, cwd=root / "neo4j"
    )
    marker.write_text(json.dumps({"pid": child.pid, "root": str(root)}))
    try:
        raise SystemExit(child.wait())
    except KeyboardInterrupt:
        child.terminate()
        child.wait(timeout=30)


if __name__ == "__main__":
    main()
