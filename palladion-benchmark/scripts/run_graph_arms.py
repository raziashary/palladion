"""Run one graph comparator (R4 HippoRAG 2, R5 GraphRAG Local, R6 LightRAG) on a snapshot, from cold (B06-T06.01).

    python scripts/run_graph_arms.py --root artifacts/fixtures/Ssub60 --arm R6 --out artifacts/runs/g-r6 \
        --run-id g-r6 --enable-live --call-cap 300 --token-cap 900000 --pace-seconds 20

The comparator runs in its own process behind the counting proxy (``benchmark/llm_proxy.py``). A live run needs the
explicit ``--enable-live`` flag and the owner's limits (BADR-0032); the key is read from the benchmark-local ``.env``
only then and is held by the proxy, never by the comparator. Nothing here prints a key. The run directory holds the
usual Track A files plus ``proxy.jsonl`` (one row per model call: numbers and codes only) and ``spend.json``.
"""

from __future__ import annotations

import argparse
import json
import secrets
import shutil
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "scripts"))

import comparators  # noqa: E402
from benchmark.adapters.common import AdapterError, Condition, PublishedView  # noqa: E402
from benchmark.adapters.dense import Encoder  # noqa: E402
from benchmark.adapters.graphrag import build_graphrag_arm  # noqa: E402
from benchmark.adapters.hipporag2 import build_hipporag2_arm  # noqa: E402
from benchmark.adapters.lightrag import build_lightrag_arm  # noqa: E402
from benchmark.adapters.worker import WorkerArm  # noqa: E402
from benchmark.contracts import ArmUnavailable, ContractError  # noqa: E402
from benchmark.fixtures.manifest import Layout, Namespace  # noqa: E402
from benchmark.generator import HttpxTransport, Transport, read_api_key  # noqa: E402
from benchmark.llm_proxy import CountingProxy, ProxyLimits, ProxyServer  # noqa: E402
from benchmark.run_manifest import ComparatorPin  # noqa: E402
from benchmark.track_a import (  # noqa: E402
    COMPARATOR_ARMS,
    DescribedArm,
    RunSpec,
    TrackAError,
    UnavailableArm,
    execute,
    load_pinned_models,
)

Factory = Callable[..., WorkerArm]
FACTORIES: Mapping[str, Factory] = {
    "R4": build_hipporag2_arm,
    "R5": build_graphrag_arm,
    "R6": build_lightrag_arm,
}
PRIMARY_MODEL = "qwen/qwen3.8-27b"
ENV_FILE = PROJECT / ".env"


class UnbuiltComparator(UnavailableArm):
    """A comparator whose index did not build: every pair is a run state with the reason, and its manifest still names
    the pinned comparator and the models it was to use, so a failed build is on record as exactly what failed."""

    def __init__(self, arm_id: str, reason: str, described: Mapping[str, Any]) -> None:
        super().__init__(arm_id, reason)
        self._described = dict(described)

    def describe(self) -> dict[str, Any]:
        return {**self._described, "reason": self.reason}


def write_spend(
    out: Path,
    arm_id: str,
    run_id: str,
    limits: ProxyLimits,
    usage: Mapping[str, Any],
    build: Mapping[str, Any] | None,
    resume_from: Path | None,
    status_counts: Mapping[str, Any] | None,
    *,
    status: str = "COMPLETED",
    reconstructed: bool = False,
) -> dict[str, Any]:
    """Write ``spend.json``: what the run spent against what it was allowed, and how it ended."""
    spend = {
        "arm": arm_id,
        "run_id": run_id,
        "status": status,
        "reconstructed_from_book": reconstructed,
        "model": limits.models[0],
        "limits": {"calls": limits.max_calls, "tokens": limits.max_tokens, "pace_seconds": limits.pace_seconds},
        "usage": dict(usage),
        "status_counts": dict(status_counts) if status_counts is not None else None,
        "build": dict(build) if build is not None else None,
        "resumed_from": str(resume_from) if resume_from else None,
    }
    (out / "spend.json").write_text(json.dumps(spend, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return spend


def usage_from_book(book: Path) -> dict[str, int]:
    """The provider spend of a run, recounted from its ``proxy.jsonl`` (numbers and codes only)."""
    totals = dict.fromkeys(
        ("calls", "rate_limited", "errors", "refused", "prompt_tokens", "completion_tokens", "estimated_tokens",
         "embedding_requests", "embedding_inputs"), 0
    )  # fmt: skip
    for line in book.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        outcome = row["outcome"]
        if outcome == "EMBEDDING":
            totals["embedding_requests"] += 1
            totals["embedding_inputs"] += int(row.get("inputs") or 0)
        elif outcome == "REFUSED":
            totals["refused"] += 1
        else:
            totals["calls"] += 1
            totals["rate_limited"] += outcome == "RATE_LIMITED"
            totals["errors"] += outcome == "ERROR"
            totals["prompt_tokens"] += int(row.get("prompt_tokens") or 0)
            totals["completion_tokens"] += int(row.get("completion_tokens") or 0)
    return totals


def reconstruct_spend(
    run_dir: Path, arm_id: str, model: str, limits: ProxyLimits, resume_from: Path | None
) -> dict[str, Any]:
    """Give a run stopped from outside (it had no chance to write its record) a ``spend.json`` rebuilt from its book.

    The result says it was reconstructed and carries no build or status counts: only the book is evidence."""
    return write_spend(
        run_dir, arm_id, run_dir.name, limits, usage_from_book(run_dir / "proxy.jsonl"), None, resume_from, None,
        status="STOPPED_BY_OPERATOR", reconstructed=True,
    )  # fmt: skip


def interpreter_of(arm_id: str, root: Path = comparators.COMPARATORS_DIR) -> Path:
    environment = root / comparators.approved(arm_id).environment
    return environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def run_arm(
    arm_id: str,
    *,
    root: Path,
    out: Path,
    run_id: str,
    transport: Transport,
    encoder: Encoder,
    limits: ProxyLimits,
    embedding_model: str,
    token: str,
    factory: Factory | None = None,
    interpreter: Path | None = None,
    pin: ComparatorPin | None = None,
    k: int = 10,
    budget: int = 4000,
    condition: Condition = Condition.C2,
    build_timeout: float = 3 * 3600.0,
    resume_from: Path | None = None,
) -> dict[str, Any]:
    """Index and answer every question of the snapshot's smoke split; return what the run spent.

    Cold unless ``resume_from`` names an earlier run directory whose comparator state is copied in (the earlier run is
    left as it was): the comparator then finishes the work it had not, and the run records that it did so."""
    if arm_id not in COMPARATOR_ARMS:
        raise TrackAError(f"{arm_id} is not a graph comparator")
    view = PublishedView.load(Layout(root).path(Namespace.PUBLISHED))
    out.mkdir(parents=True, exist_ok=False)
    if resume_from is not None:
        shutil.copytree(resume_from / "work" / "native", out / "work" / "native")
    proxy = CountingProxy(
        transport,
        limits,
        record_path=out / "proxy.jsonl",
        embedder=encoder.embed_documents,
        embedding_model=embedding_model,
    )
    server = ProxyServer(proxy, token=token)
    started = factory or FACTORIES[arm_id]
    builds: list[dict[str, Any]] = []
    adapters: dict[str, DescribedArm] = {}
    server.start()
    arm: WorkerArm | None = None
    try:
        the_pin = pin or comparators.build_pin(arm_id, native_config={}, deviations=[])
        arm = started(
            interpreter=interpreter or interpreter_of(arm_id), server=server, pin=the_pin, view=view,
            work_dir=out / "work", llm_model=limits.models[0], embedding_model=embedding_model,
            condition=condition, build_timeout=build_timeout,
        )  # fmt: skip
        try:
            arm.build_index(str(view.root), "track_a")
            builds.append({"arm": arm_id, "status": "BUILT", "stats": arm.index_stats()})
            adapters[arm_id] = arm
        except (ArmUnavailable, AdapterError, ContractError) as exc:
            builds.append(
                {"arm": arm_id, "status": "FAILED", "error": type(exc).__name__, "reason": str(exc)[:200],
                 "spend_before_failure": proxy.usage()}
            )  # fmt: skip
            adapters[arm_id] = UnbuiltComparator(arm_id, f"index build failed: {type(exc).__name__}", arm.describe())
        spec = RunSpec(run_id, "smoke", condition, k, budget, root, out)
        outcome = execute(spec, adapters, builds=builds)  # comparators are not the system under test
        return write_spend(out, arm_id, run_id, limits, proxy.usage(), builds[0], resume_from,
                           dict(outcome.summary.status_counts))  # fmt: skip
    except BaseException:
        # An interrupted run is a result too: what it spent is written before the error leaves.
        write_spend(out, arm_id, run_id, limits, proxy.usage(), builds[0] if builds else None, resume_from, None,
                    status="INTERRUPTED")  # fmt: skip
        raise
    finally:
        if arm is not None:
            arm.close()
        server.stop()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, required=True, help="the snapshot (a matched subset)")
    parser.add_argument("--arm", choices=sorted(COMPARATOR_ARMS), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--enable-live", action="store_true", help="allow provider calls (the owner's limits apply)")
    parser.add_argument("--call-cap", type=int, required=True)
    parser.add_argument("--token-cap", type=int, required=True)
    parser.add_argument("--pace-seconds", type=float, required=True)
    parser.add_argument("--max-completion-tokens", type=int, default=700)
    parser.add_argument("--model", default=PRIMARY_MODEL)
    parser.add_argument("--env-file", type=Path, default=ENV_FILE)
    parser.add_argument("--models-dir", type=Path, default=PROJECT / "artifacts" / "models")
    parser.add_argument("--resume-from", type=Path, default=None, help="an earlier run directory to finish")
    parser.add_argument("--reconstruct", action="store_true", help="write spend.json for a run stopped from outside")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--budget", type=int, default=4000)
    options = parser.parse_args(argv)
    if options.reconstruct:  # reads a book already on disk; no provider is called and no key is read
        limits = ProxyLimits(
            max_calls=options.call_cap, max_tokens=options.token_cap,
            max_completion_tokens=options.max_completion_tokens, pace_seconds=options.pace_seconds,
            models=(options.model,),
        )  # fmt: skip
        spend = reconstruct_spend(options.out, options.arm, options.model, limits, options.resume_from)
        print(json.dumps(spend, indent=2, sort_keys=True))
        return 0
    if not options.enable_live:
        print("refused: a graph comparator's extraction is a live provider call; pass --enable-live", file=sys.stderr)
        return 2
    try:
        key = read_api_key(options.env_file, enabled=True)
        encoder, _ = load_pinned_models(PROJECT / "configs", options.models_dir)
        shared = comparators_config_embedding()
        limits = ProxyLimits(
            max_calls=options.call_cap, max_tokens=options.token_cap,
            max_completion_tokens=options.max_completion_tokens, pace_seconds=options.pace_seconds,
            models=(options.model,),
        )  # fmt: skip
        spend = run_arm(
            options.arm, root=options.root, out=options.out, run_id=options.run_id,
            transport=HttpxTransport(key, timeout_seconds=120.0), encoder=encoder, limits=limits,
            embedding_model=shared, token=secrets.token_hex(16), k=options.k, budget=options.budget,
            resume_from=options.resume_from,
        )  # fmt: skip
    except (comparators.ComparatorPinError, TrackAError, AdapterError, ContractError, OSError) as exc:
        print(f"refused: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # a generation fault must reach the user by name only; the key is never in a message
        print(f"failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(json.dumps(spend, indent=2, sort_keys=True, default=str))
    return 0


def comparators_config_embedding() -> str:
    """The pinned embedding model's name, as the benchmark's own dense arms record it."""
    from benchmark.config import load_comparators_config

    shared = load_comparators_config(PROJECT / "configs" / "comparators.yaml").shared_models["embeddings"]
    return f"{shared.value}@{shared.revision}"


if __name__ == "__main__":
    raise SystemExit(main())
