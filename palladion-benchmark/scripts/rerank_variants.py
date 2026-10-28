#!/usr/bin/env python
"""Experiment: R3 with other rerank depths and a multilingual cross-encoder (Palladion ADR-0109, E-P11-003).

Builds the shared hybrid arm once, then runs the smoke split through RerankedArm variants and writes one Track A run per
variant under artifacts/runs/rr-<name>, so the benchmark's own scorer reads them. Retrieval only: no model, no quota.
"""

from __future__ import annotations

import hashlib
import sys
import time
from collections.abc import Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from run_track_a import PROJECT, qdrant_pin

from benchmark import matched as matched_lists
from benchmark.adapters.common import AdapterError, Condition, PublishedView
from benchmark.adapters.hybrid import RERANK_BATCH, RERANKER_THREADS, HybridArm, RerankedArm
from benchmark.fixtures.manifest import Layout, Namespace
from benchmark.track_a import RunSpec, build_local_arms, execute, load_pinned_models

ROOT = Path("artifacts/fixtures/S")
BGE = Path(
    "artifacts/models/reranker-candidates/models--onnx-community--bge-reranker-v2-m3-ONNX/snapshots/"
    "6f5ff65298512715a1e669753bc754d2bc8f367b"
)


class Cross:
    """A cross-encoder through fastembed from a local snapshot, with the benchmark's reranker interface."""

    def __init__(self, name: str, snapshot: Path) -> None:
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        self._model = TextCrossEncoder(
            model_name=name,
            specific_model_path=str(snapshot),
            local_files_only=True,
            cuda=False,
            threads=RERANKER_THREADS,
        )
        self.fingerprint = hashlib.sha256(name.encode()).hexdigest()

    def rerank(self, query: str, texts: Sequence[str]) -> list[float]:
        scores = [float(s) for s in self._model.rerank(query, list(texts), batch_size=RERANK_BATCH)]
        if len(scores) != len(texts):
            raise AdapterError("score count differs")
        return scores


def main() -> int:
    wanted = sys.argv[1].split(",")
    view = PublishedView.load(Layout(ROOT).path(Namespace.PUBLISHED))
    encoder, minilm = load_pinned_models(PROJECT / "configs", PROJECT / "artifacts" / "models")
    index_dir = Path("artifacts/runs/rr-index")
    arms, builds = build_local_arms(
        view, ["R2"], condition=Condition.C2, index_dir=index_dir, encoder=encoder, expected_qdrant=qdrant_pin()
    )
    hybrid = arms["R2"]
    if not isinstance(hybrid, HybridArm):
        raise AdapterError("the shared hybrid arm did not build")
    bge = Cross("BAAI/bge-reranker-v2-m3-int8", BGE) if any(w.startswith("bge") for w in wanted) else None
    variants = {
        "minilm30": (minilm, 30),
        "minilm20": (minilm, 20),
        "minilm15": (minilm, 15),
        "minilm10": (minilm, 10),
        "bge30": (bge, 30),
        "bge15": (bge, 15),
        "bge10": (bge, 10),
    }
    matched = matched_lists.load(Path("artifacts/comparison/matched.json"))
    for name in wanted:
        reranker, depth = variants[name]
        if reranker is None:
            raise AdapterError(f"{name} needs a reranker that was not loaded")
        arm = RerankedArm(hybrid, reranker, depth=depth)
        spec = RunSpec(
            f"rr-{name}",
            "smoke",
            Condition.C2,
            10,
            4000,
            ROOT,
            Path(f"artifacts/runs/rr-{name}"),
            matched_list_sha256=matched.digest,
        )
        began = time.perf_counter()
        outcome = execute(spec, {"R3": arm}, builds=builds, system_trees={})
        print(name, "done", round(time.perf_counter() - began), "s", dict(outcome.summary.status_counts), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
