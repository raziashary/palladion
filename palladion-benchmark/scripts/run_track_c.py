"""Run Track C: native end-to-end systems E0 to E4 over episodes and mutation cases (B07-T08.01).

    uv run python scripts/run_track_c.py --root artifacts/fixtures/S --out artifacts/runs/c-smoke --run-id c-smoke \\
        --arms E0,E1,E2,E3,E4 --episodes 2 --mutations M01,M09 --generator scripted --start-qdrant

The default generator is the offline scripted provider (``benchmark/scripted_provider.py``): it makes no provider call
and says nothing about any model. A live run needs ``--generator live --enable-live`` and the owner's limits for this
run (BADR-0030, OQ14): ``--call-cap``, ``--token-cap`` and ``--pace-seconds`` are required with it. Every arm's model
calls go through its own counting proxy (``benchmark/llm_proxy.py``) and the counts reported are that book. The key is
read from the benchmark-local ``.env`` only for an enabled live run and is held by the proxy, never by an arm.

Episodes are scripted conversations (``benchmark/fixtures/episodes.py``); a Palladion arm gets one provisioned principal
per episode in the corpus case (BADR-0041) and a fresh session per episode. Mutation cases apply a protocol 16 change to
the arm through its own interface (``benchmark/mutations_apply.py``). The test split is refused.
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path
from typing import Any

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "scripts"))

import palladion_runtime  # noqa: E402
import run_track_a  # noqa: E402

import comparators  # noqa: E402
from benchmark import matched as matched_lists  # noqa: E402
from benchmark.adapters.common import AdapterError, Condition, PublishedView  # noqa: E402
from benchmark.adapters.langchain import build_langchain_arm  # noqa: E402
from benchmark.adapters.langgraph import build_langgraph_system  # noqa: E402
from benchmark.adapters.palladion import CASE, TABLE_FILE, PalladionArm, PrincipalMap  # noqa: E402
from benchmark.adapters.palladion_system import TOOL_SCHEMAS, PalladionSystem  # noqa: E402
from benchmark.config import ConfigBundle, load_all  # noqa: E402
from benchmark.contracts import CacheCondition, ContractError, RunStatus, Track  # noqa: E402
from benchmark.eval.normalize import PublishedCorpus  # noqa: E402
from benchmark.eval.observable import Measure, NotObservable, Rate  # noqa: E402
from benchmark.eval.tool_use import ToolExpectation, check_arguments, reported_calls  # noqa: E402
from benchmark.fixtures import FICTIONAL_NOTICE, sha256_hex  # noqa: E402
from benchmark.fixtures.artifacts import build_corpus, plan_from_config  # noqa: E402
from benchmark.fixtures.documents import Document  # noqa: E402
from benchmark.fixtures.episodes import Episode, EpisodeKind, build_episodes  # noqa: E402
from benchmark.fixtures.manifest import (  # noqa: E402
    Layout,
    ManifestRecord,
    Namespace,
    Split,
    build_records,
    snapshot_id,
)
from benchmark.fixtures.mutations import (  # noqa: E402
    MutationContext,
    MutationError,
    MutationInstance,
    instantiate,
    world_with_versions,
)
from benchmark.fixtures.question_gen import build_questions  # noqa: E402
from benchmark.fixtures.questions import GoldRecord  # noqa: E402
from benchmark.fixtures.world import S_SCALE, World, build_world, tier_seed  # noqa: E402
from benchmark.generator import (  # noqa: E402
    GenerationError,
    GeneratorPool,
    HttpxTransport,
    TransportResponse,
    assign_models,
    read_api_key,
)
from benchmark.llm_proxy import CountingProxy, ProxyLimits, ProxyServer, Refusal  # noqa: E402
from benchmark.matched import MatchedListError  # noqa: E402
from benchmark.mutations_apply import PalladionTarget  # noqa: E402
from benchmark.quota import QuotaError, remaining_today  # noqa: E402
from benchmark.registry import default_registry  # noqa: E402
from benchmark.run_manifest import RunManifest, collect_hardware, tree_state  # noqa: E402
from benchmark.runner import RunnerError, RunnerSettings  # noqa: E402
from benchmark.scripted_provider import ScriptedProvider  # noqa: E402
from benchmark.track_a import TrackAError, load_pinned_models  # noqa: E402
from benchmark.track_b import ControlledQaSystem  # noqa: E402
from benchmark.track_c import (  # noqa: E402
    Budget,
    Heat,
    Memory,
    RunCondition,
    TrackCArm,
    TrackCResult,
    TrackCRunner,
    TrackCSystem,
    planned_question_ids,
    score_conditions,
)

CONFIGS = PROJECT / "configs"
PRIMARY_MODEL = "qwen/qwen3.8-27b"
EMBEDDING_ARM_IDS = ("E0", "E1")
BASELINES = (Memory.NONE, Memory.LAST_N, Memory.ROLLING_SUMMARY, Memory.SCOPED_EPISODIC)
SNAPSHOT_CLOCK = "2026-10-18T03:00:00Z"
MUTATION_READER = "mutation-cases"
LIVE_TOOL = "lookup_live_data"  # Palladion's read of live state; the name its tool report uses
TOKENS_PER_QUESTION = 6000


class TrackCRunError(RuntimeError):
    """The run cannot be assembled as asked. The message names why."""


@dataclass(frozen=True)
class Fixture:
    world: World
    corpus: tuple[Document, ...]
    questions: tuple[GoldRecord, ...]
    snapshot: str
    seed: int


def rebuild_fixture(root: Path, bundle: ConfigBundle) -> Fixture:
    """The evaluator-side world, corpus and questions behind a published root, checked against that root's snapshot."""
    seed = tier_seed(bundle.benchmark.default_seed, "S")
    world = build_world(seed, S_SCALE)
    plan = plan_from_config(
        bundle.fixtures, 10, authoritative_drafts=sum(v.state.value == "draft" for v in world.knowledge.versions)
    )
    corpus = build_corpus(world, plan)
    snapshot = snapshot_id(build_records(world, corpus, seed))
    view = PublishedView.load(Layout(root).path(Namespace.PUBLISHED))
    published = snapshot_id(list(view.records))
    if snapshot != published:
        raise TrackCRunError(
            "the published root is not the S-tier fixture this seed builds; regenerate or pass the root"
        )
    targets = {Split.SMOKE: bundle.benchmark.splits.smoke}
    questions = build_questions(world, corpus, snapshot, seed, "S", targets, "")
    return Fixture(world, corpus, questions, snapshot, seed)


def pick_episodes(fixture: Fixture, count: int) -> tuple[Episode, ...]:
    """The first ``count`` episodes outside the locked test split, one kind each in rotation."""
    pool = [e for e in build_episodes(fixture.world, fixture.seed, 28) if e.split is not Split.TEST]
    by_kind: dict[EpisodeKind, list[Episode]] = {}
    for episode in pool:
        by_kind.setdefault(episode.kind, []).append(episode)
    chosen: list[Episode] = []
    while len(chosen) < count:
        added = False
        for kind in EpisodeKind:
            if by_kind.get(kind) and len(chosen) < count:
                chosen.append(by_kind[kind].pop(0))
                added = True
        if not added:
            raise TrackCRunError(f"only {len(chosen)} episodes outside the test split exist, not {count}")
    return tuple(chosen)


def pick_cases(fixture: Fixture, ids: Sequence[str]) -> tuple[tuple[MutationInstance, GoldRecord], ...]:
    ctx = MutationContext(fixture.world, fixture.corpus, fixture.questions, fixture.seed)
    cases = []
    for mutation_id in ids:
        instance = instantiate(ctx, mutation_id, "plain" if mutation_id == "M14" else "base")
        question = ctx.question(instance.base_question_id)
        if question.split is Split.TEST:
            raise TrackCRunError(f"{mutation_id} is based on a locked test question")
        cases.append((instance, question))
    return tuple(cases)


class ProxyTransport:
    """The shared generator's transport, routed through an arm's counting proxy so its calls are in the same book."""

    def __init__(self, proxy: CountingProxy) -> None:
        self._proxy = proxy

    def post(self, payload: Mapping[str, Any]) -> TransportResponse:
        reply = self._proxy.chat(json.dumps(payload).encode("utf-8"))
        if isinstance(reply, Refusal):
            body = json.dumps({"error": {"code": reply.code}}).encode("utf-8")
            return TransportResponse(reply.status, {}, body)
        return reply


@dataclass
class Resources:
    """What was started for a run, so it is always stopped."""

    servers: list[ProxyServer]
    runtimes: list[palladion_runtime.PalladionRuntime]
    workers: list[Any]
    qdrant_started: bool = False

    def close(self) -> None:
        for worker in self.workers:
            worker.close()
        for runtime in self.runtimes:
            runtime.stop()
        for server in self.servers:
            server.stop()
        if self.qdrant_started:
            run_track_a.run_qdrant("stop")


@dataclass(frozen=True)
class ArmContext:
    options: argparse.Namespace
    bundle: ConfigBundle
    fixture: Fixture
    view: PublishedView
    corpus_view: PublishedCorpus
    episodes: tuple[Episode, ...]
    cases: tuple[tuple[MutationInstance, GoldRecord], ...]
    transport_for: Callable[[str], Any]
    limits: ProxyLimits
    encoder: Any
    embedding_model: str
    out: Path
    resources: Resources


@dataclass(frozen=True)
class ProxyHandle:
    proxy: CountingProxy
    server: ProxyServer
    token: str


def start_proxy(ctx: ArmContext, arm_id: str) -> ProxyHandle:
    proxy = CountingProxy(
        ctx.transport_for(arm_id),
        ctx.limits,
        record_path=ctx.out / f"proxy-{arm_id}.jsonl",
        embedder=ctx.encoder.embed_documents if ctx.encoder is not None else None,
        embedding_model=ctx.embedding_model,
    )
    token = secrets.token_hex(16)
    server = ProxyServer(proxy, token=token)
    server.start()
    ctx.resources.servers.append(server)
    return ProxyHandle(proxy, server, token)


def framework_arm(ctx: ArmContext, arm_id: str) -> TrackCArm:
    """E0 (retrieve, then the shared generator) or E1 (a bounded LangGraph agent), both over the shared chunks."""
    handle = start_proxy(ctx, arm_id)
    interpreter = comparators.env_python(comparators.COMPARATORS_DIR / comparators.FRAMEWORKS[arm_id].environment)
    pin = comparators.build_framework_pin(arm_id, native_config={}, deviations=[])
    work = ctx.out / f"work-{arm_id}"
    system: TrackCSystem
    if arm_id == "E1":
        agent = build_langgraph_system(
            interpreter=interpreter,
            server=handle.server,
            pin=pin,
            view=ctx.view,
            work_dir=work,
            llm_model=PRIMARY_MODEL,
            embedding_model=ctx.embedding_model,
            run_id=ctx.options.run_id,
            condition=Condition.C2,
        )
        agent.build_index(str(ctx.view.root), "track_c")
        ctx.resources.workers.append(agent)
        system = agent
    else:
        retriever = build_langchain_arm(
            interpreter=interpreter,
            server=handle.server,
            pin=pin,
            view=ctx.view,
            work_dir=work,
            llm_model=PRIMARY_MODEL,
            embedding_model=ctx.embedding_model,
            condition=Condition.C2,
        )
        retriever.build_index(str(ctx.view.root), "track_c")
        ctx.resources.workers.append(retriever)
        generator = replace(ctx.bundle.benchmark.generator, models=(PRIMARY_MODEL,), allow_automatic_failover=False)
        ids = planned_question_ids(ctx.episodes, ctx.cases, ctx.fixture.snapshot)
        plan = assign_models(ids, generator, seed=ctx.fixture.seed, tokens_per_question=TOKENS_PER_QUESTION)
        pool = GeneratorPool(
            generator,
            ProxyTransport(handle.proxy),
            enabled=True,
            assignment=dict(plan.assigned),
            call_budget=ctx.options.call_cap,
            record_path=ctx.out / f"generation-{arm_id}.jsonl",
            pace_seconds=ctx.options.pace_seconds,
        )
        system = ControlledQaSystem(
            "E0",
            retriever,
            pool,
            ctx.corpus_view,
            k=10,
            run_id=ctx.options.run_id,
            case_deadline_seconds=RunnerSettings.from_config(ctx.bundle.benchmark).case_deadline_seconds,
        )
    return TrackCArm(
        arm_id,
        lambda episode, heat: system,
        handle.proxy.usage,
        frozenset(BASELINES),
        frozenset({Heat.COLD, Heat.WARM}),
        mutations_unavailable="the mutated corpus needs a full index rebuild per case, which the pilot does not run",
    )


def provision(
    runtime: palladion_runtime.PalladionRuntime, episodes: Sequence[Episode], heats: Sequence[Heat]
) -> dict[tuple[str, Heat], tuple[str, str]]:
    """One tenant-local principal per episode and heat, a member of the corpus case, with a token of its own.

    Returns (episode, heat) -> (Palladion principal id, bearer token). The tokens are written to the runtime's
    operator-owned token file so that servers started afterwards accept them.
    """
    wanted = [(episode.episode_id, heat) for episode in episodes for heat in heats]
    wanted.append((MUTATION_READER, Heat.COLD))  # mutation cases ask as a principal no episode used
    keys = {(episode_id, heat): f"{episode_id}-{heat.value}" for episode_id, heat in wanted}
    issued = palladion_runtime.provision_readers(runtime.base_url, list(keys.values()), case_id=CASE)
    return {pair: issued[key] for pair, key in keys.items()}


def palladion_arms(ctx: ArmContext, arm_ids: Sequence[str]) -> list[TrackCArm]:
    """E3 and E4 as evaluator-mode servers behind their own proxies, with the corpus loaded once."""
    heats = (Heat.COLD, Heat.WARM)
    table = palladion_runtime.RUNTIME_ROOT / TABLE_FILE
    with palladion_runtime.PalladionRuntime() as serving:
        loader = PalladionArm(ctx.view, serving.base_url, palladion_runtime.load_tokens(), condition=Condition.C1)
        try:
            if table.exists():
                loader.read_table(table)
            else:
                loader.load_corpus(table)
            issued = provision(serving, ctx.episodes, heats)
        finally:
            loader.close()
    tokens = {**palladion_runtime.load_tokens(), **{principal: token for principal, token in issued.values()}}
    readers = {key: principal for key, (principal, _) in issued.items()}
    world = world_with_versions(ctx.fixture.world, [v for instance, _ in ctx.cases for v in instance.versions])

    def record_for(doc: Document) -> ManifestRecord:
        return build_records(world, [doc], ctx.fixture.seed)[0]

    arms = []
    for arm_id in arm_ids:
        handle = start_proxy(ctx, arm_id)
        runtime = palladion_runtime.evaluator_runtime(
            arm_id,
            model=PRIMARY_MODEL,
            proxy_url=handle.server.base_url,
            token=handle.token,
            evaluation_time=SNAPSHOT_CLOCK,
            completion_cap=ctx.options.max_completion_tokens,
            model_timeout=ctx.options.model_timeout,
            request_timeout=ctx.options.request_timeout,
        )
        runtime.start()
        ctx.resources.runtimes.append(runtime)
        # A message takes up to Palladion's own deadline (several paced model calls); the client must outlast it.
        connection = PalladionArm(
            ctx.view, runtime.base_url, tokens, condition=Condition.C1, timeout=ctx.options.request_timeout + 30.0
        )
        connection.read_table(table)
        ctx.resources.workers.append(connection)
        binding = PalladionBinding(arm_id, handle.proxy, connection, readers)
        arms.append(
            TrackCArm(
                arm_id,
                binding.open_system,
                handle.proxy.usage,
                frozenset({Memory.NATIVE}),
                frozenset({Heat.COLD, Heat.WARM, Heat.HOT}),
                partial(PalladionTarget, binding.arm_id, binding.connection, record_for),
                live_tools=frozenset({LIVE_TOOL}),
                fixed_clock=SNAPSHOT_CLOCK,
            )
        )
    return arms


@dataclass(frozen=True)
class PalladionBinding:
    """One evaluator server: the shared connection and the reader provisioned for each (episode, heat)."""

    arm_id: str
    proxy: CountingProxy
    connection: PalladionArm
    readers: Mapping[tuple[str, Heat], str]

    def open_system(self, episode: Episode | None, heat: Heat) -> TrackCSystem:
        if episode is None:  # a mutation case has no episode: it asks as a principal of its own
            reader = self.readers[(MUTATION_READER, Heat.COLD)]
        else:  # a hot repeat is the cold pass again, with the same reader and so the same memory
            reader = self.readers[(episode.episode_id, Heat.COLD if heat is Heat.HOT else heat)]
        return PalladionSystem(
            self.arm_id,
            self.connection,
            self.proxy.usage,
            evaluation_time=SNAPSHOT_CLOCK,
            principals=PrincipalMap(reader=reader, case_id=CASE),
        )


def never_opened(episode: Episode | None, heat: Heat) -> TrackCSystem:
    raise TrackCRunError("an arm that is not run is never opened")


def forced_arm(arm_id: str) -> TrackCArm:
    """An arm the registry says cannot run (E2 without access): listed with its reason, nothing is started."""
    spec = default_registry().get(arm_id)
    if spec.forced_status is None or spec.forced_reason is None:
        raise TrackCRunError(f"{arm_id} is not forced out of the run")
    return TrackCArm(arm_id, never_opened, dict, frozenset(), forced=(spec.forced_status, spec.forced_reason))


def conditions_for(
    arms: Sequence[TrackCArm], heats: Sequence[Heat], memories: Sequence[Memory] | None = None
) -> list[RunCondition]:
    """The conditions to run: each arm's memory baselines (only ``memories`` when named) at each heat."""
    wanted: dict[RunCondition, None] = {}
    for arm in arms:
        for memory in arm.memories:
            if memories is not None and memory not in memories:
                continue
            for heat in heats:
                wanted[RunCondition(memory, heat, Budget.MATCHED)] = None
    return list(wanted)


def write_manifest(options: argparse.Namespace, fixture: Fixture, view: PublishedView, label: str, out: Path) -> str:
    settings = RunnerSettings.from_config(load_all(CONFIGS).benchmark, order_seed=options.order_seed)
    manifest = RunManifest(
        run_id=options.run_id,
        track=Track.NATIVE_END_TO_END,
        arm="track-c",
        split="pilot",
        source_manifest_sha256=sha256_hex((view.root / "corpus_manifest.jsonl").read_text(encoding="utf-8")),
        question_manifest_sha256=sha256_hex(json.dumps([q.question_id for q in fixture.questions])),
        gold_manifest_sha256=None,
        benchmark=tree_state(PROJECT, label="benchmark"),
        system_under_test=tree_state(palladion_runtime.application_dir(), label="palladion"),
        container_image_digest=None,
        method_version="track-c-1",
        model_versions={f"generator:{PRIMARY_MODEL}": "no provider-exposed revision"},
        retrieval_config={
            "generator": label,
            "arms": options.arms,
            "episodes": options.episodes,
            "mutations": options.mutations,
            "memories": options.memories,
            "matched_list_sha256": options.matched_sha256,
            "limits": {
                "call_cap": options.call_cap,
                "token_cap": options.token_cap,
                "pace_seconds": options.pace_seconds,
                "max_completion_tokens": options.max_completion_tokens,
                "model_timeout": options.model_timeout,
                "request_timeout": options.request_timeout,
            },
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
        null_reasons={
            "gold_manifest_sha256": "the runner scores from episodes and mutation expectations, not gold files",
            "container_image_digest": "no container is used",
            "prompt_digest": "each arm has its own prompts; they are kept in the run directory",
            "pricing_snapshot": "no priced provider is called (free tier or offline stand-in)",
            "generator_assignment_sha256": "each framework arm records its own generator assignment in its records",
        },
    )
    return manifest.write(out / "manifest.json")


def book_calls(path: Path) -> int:
    """Provider calls a proxy book records: every row but embeddings and refusals (those never reach the provider)."""
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return sum(row["outcome"] not in ("EMBEDDING", "REFUSED") for row in rows)


def check_books(out: Path, arms: Mapping[str, TrackCArm]) -> list[str]:
    """The proxy's in-memory totals against its saved rows. A difference is a call that was reserved but never recorded
    (one still in flight when the run ended), and is reported, not reconciled."""
    found = []
    for arm_id, arm in arms.items():
        book = out / f"proxy-{arm_id}.jsonl"
        if arm.forced is None and book.exists() and book_calls(book) != arm.usage().get("calls", 0):
            found.append(
                f"{arm_id}: the totals say {arm.usage().get('calls', 0)} calls, the saved rows {book_calls(book)}"
            )
    return found


def tool_argument_validity(result: TrackCResult) -> Measure:
    """Whether the arguments of every tool call a system reported fit the tool's declared shape."""
    expectation = ToolExpectation(frozenset(), TOOL_SCHEMAS)
    calls = [
        call
        for traces in ([r.trace for r in result.turns] + [m.traces for m in result.mutations])
        for entry in traces
        for call in reported_calls(entry.get("evaluator", {}))
    ]
    if not calls:
        return NotObservable("no system reported tool-call arguments")
    return Rate(sum(check_arguments(call, expectation) is None for call in calls), len(calls))


def write_outputs(
    out: Path,
    result: TrackCResult,
    episodes: Sequence[Episode],
    arms: Mapping[str, TrackCArm],
    label: str,
    estimates: Mapping[str, int],
    options: argparse.Namespace,
) -> dict[str, Any]:
    scores = score_conditions(result, episodes, arms)
    memory = {
        f"{arm}|{condition}": {name: str(measure) for name, measure in score.measures().items()}
        | {"turns": str(score.turns), "unanswered": str(score.unanswered)}
        for (arm, condition), score in sorted(scores.items())
    }
    summary: dict[str, Any] = {
        "notice": FICTIONAL_NOTICE,
        "generator": label,
        "turns": len(result.turns),
        "status_counts": {
            s.value: sum(r.status is s for r in result.turns)
            for s in RunStatus
            if any(r.status is s for r in result.turns)
        },
        "mutation_cases": [
            {
                "arm": m.arm_id,
                "instance": m.instance_id,
                "status": m.status.value,
                "application": m.application.outcome.value,
                "reasons": list(m.application.reasons),
                "asks": len(m.asks),
                "unauthorized_reads": sum(v.unauthorized_reads for _, v in m.asks),
            }
            for m in result.mutations
        ],
        "skipped": [
            {"arm": s.arm_id, "condition": s.condition, "status": s.status.value, "reason": s.reason}
            for s in result.skipped
        ],
        "divergences": [*result.divergences, *check_books(out, arms)],
        "tool_argument_validity": str(tool_argument_validity(result)),
        "residues": result.residues,
        "memory": memory,
        "dry_run_estimate": {
            arm_id: {
                "calls": arms[arm_id].usage().get("calls", 0),
                "prompt_tokens": prompt,
                "completion_token_ceiling": arms[arm_id].usage().get("calls", 0) * options.max_completion_tokens,
            }
            for arm_id, prompt in estimates.items()
            if arm_id in arms
        },
        "spend": {arm_id: dict(arm.usage()) for arm_id, arm in arms.items() if arm.forced is None},
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def apply_frozen_lists_and_caps(
    options: argparse.Namespace,
    episodes: Sequence[Episode],
    cases: Sequence[tuple[MutationInstance, GoldRecord]],
    arm_ids: Sequence[str],
    live: bool,
) -> None:
    """Check what the run will ask against the frozen lists and keep each arm inside what the books leave today.

    Sets ``options.matched_sha256`` (the list's digest, or None) and, for a live run with a daily cap, lowers
    ``options.token_cap`` to an arm's share of the tokens the saved books leave the model today.
    """
    matched = matched_lists.load(options.matched_list) if options.matched_list else None
    if matched is not None:
        matched.require("track_c_episodes", [e.episode_id for e in episodes])
        matched.require("track_c_cases", [i.spec_id for i, _ in cases])
    options.matched_sha256 = matched.digest if matched else None
    if live and options.daily_token_cap:
        left = remaining_today(options.ledger_root, [options.out], [PRIMARY_MODEL], options.daily_token_cap)
        spending = len([a for a in arm_ids if a != "E2"])
        options.token_cap = min(options.token_cap, left[PRIMARY_MODEL] // max(spending, 1))
        if options.token_cap < 1:
            raise TrackCRunError(f"the books leave no {PRIMARY_MODEL} tokens for today")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, required=True, help="the S-tier fixture root")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--arms", default="E0,E1,E2,E3,E4")
    parser.add_argument("--episodes", type=int, default=2)
    parser.add_argument("--mutations", default="")
    parser.add_argument("--heats", default="cold")
    parser.add_argument("--generator", choices=["scripted", "live"], default="scripted")
    parser.add_argument("--enable-live", action="store_true")
    parser.add_argument("--call-cap", type=int, default=None, help="per arm; required for a live run")
    parser.add_argument("--token-cap", type=int, default=None, help="per arm; required for a live run")
    parser.add_argument("--pace-seconds", type=float, default=None, help="between calls; required for a live run")
    parser.add_argument("--max-completion-tokens", type=int, default=700)
    parser.add_argument("--model-timeout", type=float, default=60.0, help="seconds one model request may take")
    parser.add_argument("--request-timeout", type=int, default=240, help="Palladion's per-message deadline, 1 to 300")
    parser.add_argument("--order-seed", type=int, default=7)
    parser.add_argument("--env-file", type=Path, default=PROJECT / ".env")
    parser.add_argument("--models-dir", type=Path, default=PROJECT / "artifacts" / "models")
    parser.add_argument("--start-qdrant", action="store_true")
    parser.add_argument("--matched-list", type=Path, default=None, help="the frozen lists this run must match")
    parser.add_argument("--memories", default=None, help="only these memory baselines (comma-separated), default all")
    parser.add_argument(
        "--daily-token-cap", type=int, default=None,
        help="tokens the model may spend per day; each arm's token cap is its share of what the books leave today",
    )  # fmt: skip
    parser.add_argument(
        "--ledger-root", type=Path, default=PROJECT / "artifacts" / "runs",
        help="run directories whose saved books count against --daily-token-cap",
    )  # fmt: skip
    options = parser.parse_args(argv)
    live = options.generator == "live"
    unset = [n for n in ("call_cap", "token_cap", "pace_seconds") if getattr(options, n) is None]
    if live and (not options.enable_live or unset):
        print(
            "refused: a live run needs --enable-live and the owner's --call-cap, --token-cap and --pace-seconds",
            file=sys.stderr,
        )
        return 2
    if options.enable_live and not live:
        print("refused: --enable-live applies only with --generator live", file=sys.stderr)
        return 2
    options.call_cap = 100_000 if options.call_cap is None else options.call_cap  # the scripted provider costs nothing
    options.token_cap = 100_000_000 if options.token_cap is None else options.token_cap
    options.pace_seconds = 0.0 if options.pace_seconds is None else options.pace_seconds
    arm_ids = [a for a in options.arms.split(",") if a]
    if len([a for a in arm_ids if a in ("E3", "E4")]) > 1:
        print(
            "refused: E3 and E4 would share one Palladion state (principals, private memory and every mutation); "
            "run them one at a time, each on a freshly prepared runtime",
            file=sys.stderr,
        )
        return 2
    heats = [Heat(h) for h in options.heats.split(",") if h]
    resources = Resources([], [], [])
    try:
        bundle = load_all(CONFIGS)
        fixture = rebuild_fixture(options.root, bundle)
        episodes = pick_episodes(fixture, options.episodes)
        cases = pick_cases(fixture, [m for m in options.mutations.split(",") if m])
        apply_frozen_lists_and_caps(options, episodes, cases, arm_ids, live)
        view = PublishedView.load(Layout(options.root).path(Namespace.PUBLISHED))
        encoder = None
        if any(a in EMBEDDING_ARM_IDS for a in arm_ids):
            encoder, _ = load_pinned_models(CONFIGS, options.models_dir)
        if options.start_qdrant:
            if run_track_a.run_qdrant("start") != 0:
                print("refused: the benchmark's Qdrant could not be started", file=sys.stderr)
                return 2
            resources.qdrant_started = True
        live_transport = (
            HttpxTransport(read_api_key(options.env_file, enabled=True), timeout_seconds=120.0) if live else None
        )
        scripted: dict[str, ScriptedProvider] = {}

        def transport_for(arm_id: str) -> Any:
            return live_transport if live_transport is not None else scripted.setdefault(arm_id, ScriptedProvider())

        label = "groq" if live else "scripted-offline"
        limits = ProxyLimits(
            max_calls=options.call_cap,
            max_tokens=options.token_cap,
            max_completion_tokens=options.max_completion_tokens,
            pace_seconds=options.pace_seconds,
            models=(PRIMARY_MODEL,),
            max_tool_calls=len(episodes) * 6 * 8 + len(cases) * 16,
        )
        options.out.mkdir(parents=True, exist_ok=False)
        ctx = ArmContext(
            options,
            bundle,
            fixture,
            view,
            PublishedCorpus.load(view.root),
            episodes,
            cases,
            transport_for,
            limits,
            encoder,
            comparators_embedding(bundle),
            options.out,
            resources,
        )
        arms: list[TrackCArm] = []
        for arm_id in arm_ids:
            if arm_id == "E2":
                arms.append(forced_arm("E2"))
            elif arm_id in EMBEDDING_ARM_IDS:
                arms.append(framework_arm(ctx, arm_id))
        palladion_ids = [a for a in arm_ids if a in ("E3", "E4")]
        if palladion_ids:
            arms += palladion_arms(ctx, palladion_ids)
        digest = write_manifest(options, fixture, view, label, options.out)
        identity = {p.principal_id: p for p in view.identity.principals}

        def filters_for(principal_id: str) -> Mapping[str, Any]:
            principal = identity[principal_id]
            return {"tenant_id": principal.tenant_id, "role": principal.role_id, "metadata_condition": "C2"}

        runner = TrackCRunner(
            options.run_id,
            options.out,
            manifest_sha256=digest,
            snapshot_id=fixture.snapshot,
            order_seed=options.order_seed,
            filters_for=filters_for,
            base_corpus=fixture.corpus,
        )
        mutations = {i.spec_id: i for i, _ in cases}
        memories = [Memory(m) for m in options.memories.split(",") if m] if options.memories else None
        result = runner.run(arms, episodes, conditions_for(arms, heats, memories), mutations, cases=cases)
        estimates = {arm_id: provider.estimated_prompt_tokens for arm_id, provider in scripted.items()}
        summary = write_outputs(options.out, result, episodes, {a.arm_id: a for a in arms}, label, estimates, options)
        print(
            json.dumps(
                {k: summary[k] for k in ("generator", "turns", "status_counts", "divergences", "spend")}, indent=2
            )
        )
        return 0
    except (
        AdapterError,
        TrackAError,
        TrackCRunError,
        MatchedListError,
        QuotaError,
        MutationError,
        GenerationError,
        RunnerError,
        ContractError,
        palladion_runtime.PalladionRuntimeError,
    ) as exc:
        print(f"refused: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    finally:
        resources.close()


def comparators_embedding(bundle: ConfigBundle) -> str:
    shared = bundle.comparators.shared_models["embeddings"]
    return f"{shared.value}@{shared.revision}"


if __name__ == "__main__":
    raise SystemExit(main())
