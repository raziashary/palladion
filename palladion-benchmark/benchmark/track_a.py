"""Build the local arms and run Track A through the real Runner (B04-T04.01, B04-T04.02, BADR-0025).

The scripts are thin; the rules live here so tests can exercise them:

* An arm is given the published namespace and an index directory, never the snapshot root.
* A split's questions come from that split's annotation file only, and the locked test split is refused until the
  B08 seal exists. Which annotation file was read is written to ``read_log.json`` so the validator can check it.
* Every pair is run through ``Runner`` with intention-to-treat accounting. An arm whose index could not be built
  stays in the run as an arm that is not run, with its reason, never silently dropped.
* The manifests record K, the evidence budget, the metadata condition and each arm's settings, so a scorer can refuse a
  run scored under different ones.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

from benchmark.adapters.bm25 import Bm25Arm
from benchmark.adapters.common import DEFAULT_CHUNK_WORDS, AdapterError, Condition, PublishedView
from benchmark.adapters.dense import DEFAULT_URL, DenseArm, Encoder, FastEmbedEncoder
from benchmark.adapters.hybrid import FastEmbedReranker, HybridArm, RerankedArm, Reranker
from benchmark.adapters.models import ModelSpec, spec_from_pin
from benchmark.config import ConfigBundle, load_all
from benchmark.contracts import (
    ArmUnavailable,
    CacheCondition,
    ContractError,
    EvidenceCandidate,
    RetrievalRequest,
    Track,
)
from benchmark.fixtures import sha256_hex
from benchmark.fixtures.manifest import (
    IdentityManifest,
    Layout,
    Namespace,
    Split,
    manifest_digest,
    read_identity,
)
from benchmark.fixtures.questions import GoldRecord, read_gold
from benchmark.registry import default_registry
from benchmark.run_manifest import (
    ComparatorPin,
    RunManifest,
    TreeState,
    collect_hardware,
    read_verified,
    sha256_of,
    tree_state,
)
from benchmark.runner import (
    ArmBinding,
    PlanRegistry,
    RunLedger,
    Runner,
    RunnerCase,
    RunnerSettings,
    RunSummary,
)


class DescribedArm(Protocol):
    """A retriever that also says which settings define it, for the run manifest."""

    def build_index(self, source_manifest_uri: str, index_namespace: str) -> None: ...

    def retrieve(self, request: RetrievalRequest) -> list[EvidenceCandidate]: ...

    def index_stats(self) -> dict[str, Any]: ...

    def describe(self) -> dict[str, Any]: ...


LOCAL_ARMS = ("R0", "R1", "R2", "R3")
# Third-party graph comparators: built and run in their own environment, identified by a ComparatorPin (BADR-0031).
COMPARATOR_ARMS = ("R4", "R5", "R6")
COST_KEYS = (
    "build_ms",
    "extraction_calls",
    "extraction_prompt_tokens",
    "extraction_completion_tokens",
    "storage_bytes",
)
RUNNABLE_SPLITS = ("smoke", "dev")
METHOD_VERSION = "1.0.0"
FICTION = "The corpus, questions and identities are fictional (Meridian Switchworks)."
GOLD_KEYS = (
    "answerability",
    "slots",
    "minimal_sets",
    "citation_gold_spans",
    "gold_applicable_version_ids",
    "required_claims",
    "forbidden_claims",
    "inaccessible_sources",
    "abstention_note",
    "policy_outcome",
)


WITHDRAWN = Path(__file__).resolve().parents[1] / "configs" / "withdrawn_questions.json"


def read_withdrawn(path: Path) -> dict[str, str]:
    """Question ids the label audit found defective, with the reason (BADR-0026); empty when the file is absent."""
    if not path.exists():
        return {}
    questions = json.loads(path.read_text(encoding="utf-8"))["questions"]
    return {str(q): str(reason) for q, reason in questions.items()}


class TrackAError(ValueError):
    """A Track A run was set up in a way the benchmark refuses. The message holds no secrets."""


@dataclass(frozen=True)
class ReadLog:
    """Which files of the snapshot a run read: the published corpus and one split's annotation file."""

    split: str
    annotation_namespace: str
    annotation_file: str
    annotation_sha256: str
    published_manifest_sha256: str
    test_namespace_read: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def read_annotations(root: Path, split: str) -> tuple[tuple[GoldRecord, ...], ReadLog]:
    """The gold records of one runnable split, read from that split's file alone, with the log of the read."""
    if split not in RUNNABLE_SPLITS:
        raise TrackAError("the locked test split needs the sealed run of B08; Track A runs smoke or dev")
    layout = Layout(root)
    namespace = Namespace.DEV_ANNOTATIONS
    path = layout.path(namespace) / f"questions_{Split(split).value}.jsonl"
    if not path.is_file():
        raise TrackAError(f"{path.name} does not exist for split {split}")
    digest = sha256_hex(path.read_bytes().decode("utf-8"))
    records = read_gold(path, expected_sha256=digest)
    if any(r.split.value != split for r in records):
        raise TrackAError("the annotation file holds records of another split")
    log = ReadLog(split, namespace.value, path.name, digest, manifest_digest(layout.path(Namespace.PUBLISHED)), False)
    return records, log


def build_request(
    record: GoldRecord, identity: IdentityManifest, *, k: int, budget: int, condition: Condition
) -> RetrievalRequest:
    """What an arm may see of a question: text, principal, snapshot, times and the access attributes."""
    principal = next((p for p in identity.principals if p.principal_id == record.principal_id), None)
    if principal is None:
        raise TrackAError(f"principal {record.principal_id} is not in the identity manifest")
    return RetrievalRequest(
        question_id=record.question_id,
        query=record.query,
        principal_id=record.principal_id,
        corpus_snapshot_id=record.corpus_snapshot_id,
        evaluation_time=record.evaluation_time,
        event_time=record.event_time,
        filters={"tenant_id": principal.tenant_id, "role": principal.role_id, "metadata_condition": condition.value},
        limit=k,
        max_evidence_tokens=budget,
    )


# --------------------------------------------------------------------------- building the local arms


@dataclass
class _Shared:
    """The indexes that more than one arm uses, built once."""

    lexical: Bm25Arm | None = None
    dense: DenseArm | None = None
    hybrid: HybridArm | None = None


class UnavailableArm:
    """Stands in for an arm whose index could not be built: every call is a run state with the reason, not a score."""

    def __init__(self, arm_id: str, reason: str) -> None:
        self.arm_id = arm_id
        self.reason = reason

    def build_index(self, source_manifest_uri: str, index_namespace: str) -> None:
        raise ArmUnavailable(self.reason)

    def retrieve(self, request: RetrievalRequest) -> list[EvidenceCandidate]:
        raise ArmUnavailable(self.reason)

    def index_stats(self) -> dict[str, Any]:
        return {"arm": self.arm_id, "status": "FAILED", "reason": self.reason}

    def describe(self) -> dict[str, Any]:
        return {"arm": self.arm_id, "status": "FAILED", "reason": self.reason}


def load_pinned_models(config_dir: Path, models_dir: Path) -> tuple[Encoder, Reranker]:
    """The pinned embedding model and reranker from the local cache, digests verified; never downloads."""
    shared = load_all(config_dir).comparators.shared_models

    def snapshot(name: str, spec: ModelSpec) -> Path:
        found = sorted((models_dir / name).glob(f"models--*/snapshots/{spec.revision}"))
        if not found:
            raise TrackAError(f"the {name} model is not downloaded; the benchmark never downloads on its own")
        return found[0]

    embeddings, reranker = spec_from_pin(shared["embeddings"]), spec_from_pin(shared["reranker"])
    return (
        FastEmbedEncoder(snapshot("embeddings", embeddings), embeddings),
        FastEmbedReranker(snapshot("reranker", reranker), reranker),
    )


def build_local_arms(
    view: PublishedView,
    wanted: Sequence[str],
    *,
    condition: Condition,
    index_dir: Path,
    qdrant_url: str = DEFAULT_URL,
    encoder: Encoder | None = None,
    reranker: Reranker | None = None,
    chunk_words: int | None = None,
    expected_qdrant: str | None = None,
) -> tuple[dict[str, DescribedArm], list[dict[str, Any]]]:
    """R0 to R3 over shared indexes (one lexical and one dense index serve every arm that needs them).

    Returns the arms and one record per arm: its stats when built, or the error type when not. A failure is recorded and
    the arm becomes an ``UnavailableArm``; nothing is skipped silently.
    """
    unknown = sorted(set(wanted) - set(LOCAL_ARMS))
    if unknown:
        raise TrackAError(f"not a local arm: {', '.join(unknown)}")
    published = str(view.root)
    words = chunk_words or DEFAULT_CHUNK_WORDS
    records: list[dict[str, Any]] = []
    arms: dict[str, DescribedArm] = {}
    shared = _Shared()

    def attempt(arm_id: str, build: Callable[[], DescribedArm]) -> None:
        started = time.perf_counter()
        try:
            arm = build()
        except Exception as exc:
            arms[arm_id] = UnavailableArm(arm_id, f"index build failed: {type(exc).__name__}")
            records.append({"arm": arm_id, "status": "FAILED", "error": type(exc).__name__, "reason": str(exc)[:200]})
            return
        arms[arm_id] = arm
        records.append(
            {"arm": arm_id, "status": "BUILT", "seconds": time.perf_counter() - started, "stats": arm.index_stats()}
        )

    def lexical() -> Bm25Arm:
        if shared.lexical is None:
            arm = Bm25Arm(view, condition, words)
            arm.build_index(published, "track_a")
            shared.lexical = arm
        return shared.lexical

    def dense() -> DenseArm:
        if shared.dense is None:
            if encoder is None:
                raise AdapterError("the dense arms need the pinned embedding model")
            arm = DenseArm(view, encoder, index_dir, qdrant_url=qdrant_url, condition=condition, chunk_words=words)
            arm.build_index(published, "track_a")
            reported = arm.index_stats()["qdrant_server_version"]
            if expected_qdrant is not None and reported != expected_qdrant:
                raise AdapterError(f"the Qdrant server is {reported}, but the pin is {expected_qdrant}")
            shared.dense = arm
        return shared.dense

    def hybrid() -> HybridArm:
        if shared.hybrid is None:
            fused = HybridArm(lexical(), dense())
            fused.adopt_built_indexes()
            shared.hybrid = fused
        return shared.hybrid

    def reranked() -> RerankedArm:
        if reranker is None:
            raise AdapterError("R3 needs the pinned reranker")
        return RerankedArm(hybrid(), reranker)

    builders: dict[str, Callable[[], DescribedArm]] = {"R0": lexical, "R1": dense, "R2": hybrid, "R3": reranked}
    for arm_id in wanted:
        attempt(arm_id, builders[arm_id])
    return arms, records


# --------------------------------------------------------------------------- running


@dataclass(frozen=True)
class RunSpec:
    run_id: str
    split: str
    condition: Condition
    k: int
    budget_words: int
    root: Path  # the snapshot root; only the published namespace and the split's annotation file are read from it
    out: Path
    order_seed: int | None = None
    config_dir: Path = Path(__file__).resolve().parents[1] / "configs"


@dataclass(frozen=True)
class RunOutcome:
    summary: RunSummary
    run_dir: Path
    read_log: ReadLog
    questions: int
    arms: tuple[str, ...]


def _manifest(
    spec: RunSpec,
    arm_id: str,
    describe: Mapping[str, Any],
    settings: RunnerSettings,
    digests: Mapping[str, str],
    bundle: ConfigBundle,
    system: TreeState | None,
) -> RunManifest:
    shared = bundle.comparators.shared_models
    models: dict[str, str | None] = {}
    if arm_id in ("R1", "R2", "R3"):
        models["embeddings"] = f"{shared['embeddings'].value}@{shared['embeddings'].revision}"
    if arm_id in ("R1", "R2", "R3"):
        qdrant = shared["qdrant_server"]
        models["qdrant_server"] = f"{qdrant.value}@sha256:{next(iter(qdrant.digests.values()))}"
    if arm_id == "R3":
        models["reranker"] = f"{shared['reranker'].value}@{shared['reranker'].revision}"
    reasons = {
        "container_image_digest": "no container is used; arms run in the benchmark environment or a pinned worktree",
        "prompt_digest": "Track A calls no generative model",
        "pricing_snapshot": "no priced provider is called",
        "generator_assignment_sha256": "Track A has no generator assignment",
    }
    if system is None:
        reasons["system_under_test"] = "a benchmark-built arm, not the system under test"
    method: str | None = METHOD_VERSION
    if arm_id == "R7a":
        method = None
        reasons["method_version"] = "the system under test is identified by its commit in system_under_test"
    if arm_id in COMPARATOR_ARMS:
        method = None
        reasons["method_version"] = "a third-party comparator is identified by its pin in retrieval_config"
        reasons["container_image_digest"] = "the comparator runs in an isolated uv environment recorded by its pin"
        try:
            ComparatorPin.from_dict(describe.get("comparator", {}))
        except (KeyError, TypeError, ContractError) as exc:
            raise TrackAError(f"{arm_id} needs a valid comparator pin in its description: {exc}") from None
        models.update({str(k): str(v) for k, v in dict(describe.get("models", {})).items()})
    return RunManifest(
        run_id=spec.run_id,
        track=Track.RETRIEVAL_ONLY,
        arm=arm_id,
        split=spec.split,
        source_manifest_sha256=digests["source"],
        question_manifest_sha256=digests["questions"],
        gold_manifest_sha256=digests["gold"],
        benchmark=tree_state(Path(__file__).resolve().parents[1], label="benchmark"),
        system_under_test=system,
        container_image_digest=None,
        method_version=method,
        model_versions=models,
        retrieval_config={
            **describe,
            "k": spec.k,
            "budget_words": spec.budget_words,
            "metadata_condition": spec.condition.value,
        },
        prompt_digest=None,
        hardware=collect_hardware(),
        pricing_snapshot=None,
        seed=settings.order_seed,
        order_seed=settings.order_seed,
        cache_condition=CacheCondition.COLD,
        started_at_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        retry_policy=settings.retry_policy_dict(),
        generator_assignment_sha256=None,
        confirmatory=False,
        null_reasons=reasons,
    )


def execute(
    spec: RunSpec,
    adapters: Mapping[str, DescribedArm],
    *,
    builds: Sequence[Mapping[str, Any]] = (),
    system_trees: Mapping[str, TreeState] | None = None,
) -> RunOutcome:
    """Run every arm on every question of the split through the real Runner and write the run directory."""
    if spec.k < 1 or spec.budget_words < 1:
        raise TrackAError("K and the evidence budget are at least 1")
    bundle = load_all(spec.config_dir)
    records, read_log = read_annotations(spec.root, spec.split)
    identity = read_identity(Layout(spec.root).path(Namespace.PUBLISHED))
    requests = [
        build_request(r, identity, k=spec.k, budget=spec.budget_words, condition=spec.condition) for r in records
    ]
    digests = {
        "source": read_log.published_manifest_sha256,
        "gold": read_log.annotation_sha256,
        "questions": sha256_of([r.to_dict() for r in requests]),
    }
    settings = RunnerSettings.from_config(bundle.benchmark, order_seed=spec.order_seed)
    spec.out.mkdir(parents=True, exist_ok=True)
    system_trees = system_trees or {}
    bindings = []
    for arm_id, adapter in adapters.items():
        describe = adapter.describe()
        path = spec.out / f"manifest-{arm_id}.json"
        if path.exists():
            recorded = read_verified(path).retrieval_config
            if (recorded.get("k"), recorded.get("budget_words"), recorded.get("metadata_condition")) != (
                spec.k, spec.budget_words, spec.condition.value,
            ):  # fmt: skip
                raise TrackAError(f"manifest-{arm_id}.json was written under a different K, budget or condition")
        else:
            _manifest(spec, arm_id, describe, settings, digests, bundle, system_trees.get(arm_id)).write(path)
        bindings.append(ArmBinding(arm_id, adapter, path))
    runner = Runner(
        spec.run_id,
        settings,
        bindings,
        RunLedger(spec.out / "ledger.jsonl"),
        PlanRegistry(spec.out / "plans.jsonl"),
        default_registry(),
    )
    summary = runner.run([RunnerCase(r) for r in requests], split=spec.split)
    (spec.out / "read_log.json").write_text(json.dumps(read_log.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    (spec.out / "run_config.json").write_text(
        json.dumps(
            {
                "run_id": spec.run_id,
                "split": spec.split,
                "arms": sorted(adapters),
                "k": spec.k,
                "budget_words": spec.budget_words,
                "metadata_condition": spec.condition.value,
                "questions": len(requests),
                "builds": list(builds),
                "notice": FICTION,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (spec.out / "summary.json").write_text(json.dumps(asdict(summary), indent=2, sort_keys=True), encoding="utf-8")
    return RunOutcome(summary, spec.out, read_log, len(requests), tuple(sorted(adapters)))
