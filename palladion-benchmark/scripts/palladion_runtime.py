"""Provision and run an isolated Palladion for the R7a arm (B04-T03.03, BADR-0016, BADR-0025).

Palladion is reached only over HTTP and never imported. To have something to call, this script builds a runtime the
benchmark owns: a detached git worktree of Palladion at a recorded commit, its own environment, its own data root, and
its own Qdrant collection on the benchmark's server (127.0.0.1:17333). Palladion's default root, port and collection
belong to its contributor and are never used; ``live_state`` is read before and after every session so a change would
show.

Palladion's own seed (``scripts/seed.py``) creates its demo principals, cases and four demo sources; the demo sources
are then revoked through its HTTP API so that only the benchmark corpus is retrievable. Tokens live in the runtime
root's ``demo_auth.json``; they are read inside this module and handed to the adapter, never printed or logged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from benchmark.adapters.models import spec_from_pin, verify
from benchmark.config import load_all

PINNED_COMMIT = "6444345209cabd9dc0b637c53ee063dd2fe87303"
BENCH = Path(__file__).resolve().parents[1]
PROJECT = BENCH
sys.path.insert(0, str(BENCH))
REPO = BENCH.parent
WORKTREE = BENCH / "artifacts" / f"palladion-{PINNED_COMMIT[:7]}"
RUNTIME_ROOT = BENCH / "artifacts" / "palladion-runtime"
QDRANT_URL = "http://127.0.0.1:17333"
COLLECTION = "bench_palladion"
PORT = 18081
PALLADION_DEFAULT_PORT = 18080
PALLADION_QDRANT = "http://127.0.0.1:16333"
PALLADION_COLLECTION = "knowledge_chunks_v1"
ADMIN = "admin-a"
HEALTH_TIMEOUT_SECONDS = 120.0
MODEL_CACHES = (BENCH / "artifacts" / "models" / "embeddings", BENCH / "artifacts" / "models" / "reranker")


class PalladionRuntimeError(RuntimeError):
    """The isolated runtime could not be provisioned safely. The message holds no tokens or secrets."""


def run(command: list[str], cwd: Path, *, timeout: float = 900) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False, timeout=timeout)


def application_dir(worktree: Path = WORKTREE) -> Path:
    return worktree / "palladion"


def ensure_worktree(worktree: Path = WORKTREE, commit: str = PINNED_COMMIT) -> Path:
    """A detached checkout of ``commit`` under the benchmark's artifacts; an existing one must be at that commit."""
    if worktree.exists():
        head = run(["git", "rev-parse", "HEAD"], worktree).stdout.strip()
        if head != commit:
            raise PalladionRuntimeError("the existing Palladion worktree is not at the pinned commit")
        return worktree
    result = run(["git", "worktree", "add", "--detach", str(worktree), commit], REPO)
    if result.returncode != 0:
        raise PalladionRuntimeError("git could not create the Palladion worktree")
    return worktree


def worktree_state(worktree: Path = WORKTREE) -> dict[str, Any]:
    """Commit, whether the checkout has uncommitted changes, and the digests of its settings and lock file."""
    app = application_dir(worktree)
    return {
        "commit": run(["git", "rev-parse", "HEAD"], worktree).stdout.strip(),
        "dirty": bool(run(["git", "status", "--porcelain", "--", "palladion"], worktree).stdout.strip()),
        "settings_sha256": hashlib.sha256((app / "config/settings.yaml").read_bytes()).hexdigest(),
        "lock_sha256": hashlib.sha256((app / "uv.lock").read_bytes()).hexdigest(),
    }


def pins_from_source(worktree: Path = WORKTREE) -> dict[str, str]:
    """The embedding and reranker pins as Palladion's own source states them."""
    app = application_dir(worktree) / "src/evidence_agent/retrieval"
    embeddings, rerank = (
        (app / "embeddings.py").read_text(encoding="utf-8"),
        (app / "rerank.py").read_text(encoding="utf-8"),
    )

    def constant(source: str, name: str) -> str:
        found = re.search(rf'^{name} = "([^"]+)"', source, re.MULTILINE)
        if found is None:
            raise PalladionRuntimeError(f"{name} was not found in Palladion's source")
        return found.group(1)

    return {
        "embedding_repository": constant(embeddings, "MODEL_REPOSITORY"),
        "embedding_revision": constant(embeddings, "MODEL_REVISION"),
        "reranker_repository": constant(rerank, "RERANKER_NAME"),
        "reranker_revision": constant(rerank, "RERANKER_REVISION"),
    }


def sync_environment(worktree: Path = WORKTREE) -> None:
    result = run(["uv", "sync", "--frozen"], application_dir(worktree), timeout=1800)
    if result.returncode != 0:
        raise PalladionRuntimeError("uv could not build Palladion's environment from its lock file")


def install_model_cache(worktree: Path = WORKTREE) -> None:
    """Give Palladion the benchmark's model files so it does not download them again, verified against the pins.

    Each snapshot is checked against its digests before it is copied and again where Palladion will read it.
    """
    shared = load_all(PROJECT / "configs").comparators.shared_models
    target = application_dir(worktree) / "runtime/model_cache/huggingface"
    target.mkdir(parents=True, exist_ok=True)
    for name, cache in (("embeddings", MODEL_CACHES[0]), ("reranker", MODEL_CACHES[1])):
        spec = spec_from_pin(shared[name])
        found = sorted(cache.glob(f"models--*/snapshots/{spec.revision}"))
        if not found:
            raise PalladionRuntimeError(f"the {name} model is not downloaded")
        verify(found[0], spec)
        folder = found[0].parents[1]
        if not (target / folder.name).exists():
            shutil.copytree(folder, target / folder.name)
        verify(target / folder.name / "snapshots" / spec.revision, spec)


def live_state() -> dict[str, Any]:
    """What Palladion's contributor-owned defaults look like now: the demo root listing and the 16333 collection."""
    default_root = REPO / "palladion" / "runtime" / "demo"
    listing = (
        sorted(
            (str(p.relative_to(default_root)), p.stat().st_size, p.stat().st_mtime_ns)
            for p in default_root.rglob("*")
            if p.is_file()
        )
        if default_root.exists()
        else []
    )
    points: int | None
    try:
        with urllib.request.urlopen(f"{PALLADION_QDRANT}/collections/{PALLADION_COLLECTION}", timeout=3) as response:
            points = json.loads(response.read())["result"]["points_count"]
    except (urllib.error.URLError, OSError, KeyError, ValueError):
        points = None
    return {"default_root": listing, "qdrant_16333_points": points}


def health(port: int = PORT) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as response:
            return bool(response.status == 200)
    except (urllib.error.URLError, OSError):
        return False


def qdrant_healthy(url: str = QDRANT_URL) -> bool:
    try:
        with urllib.request.urlopen(f"{url}/healthz", timeout=2) as response:
            return bool(response.status == 200)
    except (urllib.error.URLError, OSError):
        return False


def drop_collection(url: str = QDRANT_URL, name: str = COLLECTION) -> None:
    request = urllib.request.Request(f"{url}/collections/{name}", method="DELETE")
    try:
        urllib.request.urlopen(request, timeout=30).close()
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise


def seed(worktree: Path = WORKTREE, root: Path = RUNTIME_ROOT) -> dict[str, str]:
    """Palladion's own seed into a root and collection of the benchmark's. Returns its demo revision ids."""
    if root.resolve() == (REPO / "palladion" / "runtime" / "demo").resolve():
        raise PalladionRuntimeError("the benchmark never seeds Palladion's own demo root")
    result = run(
        [
            "uv",
            "run",
            "python",
            "scripts/seed.py",
            "--root",
            str(root),
            "--url",
            QDRANT_URL,
            "--collection",
            COLLECTION,
        ],
        application_dir(worktree),
        timeout=1800,
    )
    if result.returncode != 0:
        raise PalladionRuntimeError("Palladion's seed failed")
    revisions: dict[str, str] = json.loads(result.stdout)["revisions"]
    return revisions


def load_tokens(root: Path = RUNTIME_ROOT) -> dict[str, str]:
    """principal id -> bearer token, from the runtime's own file. The values are never printed."""
    mapping = json.loads((root / "demo_auth.json").read_text(encoding="utf-8"))
    return {principal: token for token, principal in mapping.items()}


@dataclass
class PalladionRuntime:
    """A running isolated Palladion. Use as a context manager so the server is always stopped."""

    worktree: Path = WORKTREE
    root: Path = RUNTIME_ROOT
    port: int = PORT
    rerank: bool = True
    process: subprocess.Popen[bytes] | None = None

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        if self.port == PALLADION_DEFAULT_PORT:
            raise PalladionRuntimeError("port 18080 is Palladion's own; the benchmark uses another")
        if health(self.port):
            raise PalladionRuntimeError("something already answers on the benchmark's Palladion port")
        log = (self.root.parent / "palladion-serve.log").open("wb")
        command = [
            "uv", "run", "python", "scripts/serve.py", "--root", str(self.root), "--url", QDRANT_URL,
            "--collection", COLLECTION, "--port", str(self.port),
        ]  # fmt: skip
        if self.rerank:
            command.append("--rerank")
        self.process = subprocess.Popen(
            command, cwd=application_dir(self.worktree), stdout=log, stderr=subprocess.STDOUT
        )
        deadline = time.monotonic() + HEALTH_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if health(self.port):
                return
            if self.process.poll() is not None:
                raise PalladionRuntimeError("Palladion's server exited before it became healthy")
            time.sleep(1)
        self.stop()
        raise PalladionRuntimeError("Palladion's server did not become healthy in time")

    def stop(self) -> None:
        """Stop only the process this object started, with its children (uv starts Python as a child)."""
        if self.process is None:
            return
        if self.process.poll() is None:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(self.process.pid)], capture_output=True, check=False)
            self.process.wait(timeout=30)
        self.process = None

    def __enter__(self) -> PalladionRuntime:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()


OUTAGE_WARNINGS = frozenset({"INDEX_UNAVAILABLE", "INDEX_MANIFEST_MISMATCH", "ACCEPTED_BUT_UNINDEXED"})
DEMO_PROBES = (
    "reversal review settlement",
    "exception delay approved appendix",
    "SOP 2025 dispute",
    "draft memo proposal",
)


def post(base_url: str, path: str, token: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        base_url + path,
        method="POST",
        data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, None


def revoke_demo_sources(base_url: str, revisions: dict[str, str], tokens: dict[str, str]) -> None:
    """Revoke Palladion's own demo documents through its HTTP API, then prove none of them can be retrieved.

    A source that is still a draft cannot be revoked (HTTP 409) and is not retrievable either; the check after the
    loop is what decides, not the status codes.
    """
    for revision in revisions.values():
        status, _ = post(base_url, f"/sources/{revision}/revoke", tokens[ADMIN])
        if status not in (200, 409):
            raise PalladionRuntimeError(f"revoking a demo source returned HTTP {status}")
    demo = set(revisions.values())
    for mode in ("lexical", "dense", "hybrid"):
        for query in DEMO_PROBES:
            status, body = post(
                base_url,
                "/search",
                tokens["reader-a"],
                {"case_id": "case-42", "query": query, "mode": mode, "limit": 12},
            )
            if status != 200 or body["status"] == "UNAVAILABLE" or set(body["warnings"]) & OUTAGE_WARNINGS:
                raise PalladionRuntimeError("Palladion could not answer the probe, so the revocation is unproven")
            if any(p["revision_id"] in demo for p in body["passages"]):
                raise PalladionRuntimeError("a Palladion demo document is still retrievable after revocation")


def prepare(*, reset: bool = False) -> dict[str, Any]:
    """Worktree, environment, model cache, a freshly seeded root and the revoked demo sources; returns the record."""
    if not qdrant_healthy():
        raise PalladionRuntimeError("start the benchmark's Qdrant first (scripts/qdrant_server.py start --detach)")
    before = live_state()
    ensure_worktree()
    sync_environment()
    install_model_cache()
    if RUNTIME_ROOT.exists():
        if not reset:
            raise PalladionRuntimeError("the runtime root exists; pass --reset to rebuild it")
        shutil.rmtree(RUNTIME_ROOT)
    drop_collection()
    revisions = seed()
    with PalladionRuntime() as runtime:
        revoke_demo_sources(runtime.base_url, revisions, load_tokens())
    after = live_state()
    return {"worktree": worktree_state(), "pins": pins_from_source(), "live_state_unchanged": before == after,
            "demo_revisions_revoked": len(revisions)}  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=("prepare", "serve", "state"))
    parser.add_argument("--reset", action="store_true", help="with prepare: rebuild the runtime root")
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            record = prepare(reset=args.reset)
            print(json.dumps(record, indent=2))
            if not record["live_state_unchanged"]:
                message = "FAIL: Palladion's own root or collection changed while preparing; inspect before trusting"
                print(message, file=sys.stderr)
                return 1
        elif args.command == "state":
            print(
                json.dumps({"worktree": worktree_state(), "pins": pins_from_source(), "live": live_state()}, indent=2)
            )
        else:
            with PalladionRuntime() as runtime:
                print(f"Palladion (isolated) at {runtime.base_url}; press Ctrl-C to stop", flush=True)
                while runtime.process is not None and runtime.process.poll() is None:
                    time.sleep(1)
    except PalladionRuntimeError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
