"""Track C: native end-to-end systems over multi-turn episodes and mutation cases (B07-T08.01, protocol 3 and 7.1).

The runner owns what must be the same for every system and nothing else:

* **Isolation.** Every episode gets its own system binding from the arm (``open_system``): its own principal and case
  for a system with private memory (BADR-0039), its own history for the baselines. State is never reset *inside* an
  episode and is always fresh between episodes, so a fact stated in one episode cannot be recalled in the next; the
  leakage measure in ``benchmark/eval/memory.py`` is the check that this held.
* **Memory baselines at an equal context budget.** A system without memory of its own is given the conversation by the
  harness in one of four deterministic forms (none, last N exchanges, a rolling extractive summary, scoped episodic
  retrieval), each cut to the same number of words. A system with its own memory (Palladion's continuity) gets none of
  them: its own settings are the condition.
* **Matched or native budgets.** Under ``MATCHED`` every system is held to the same ceiling per turn (model calls and
  tool calls); a turn over it is flagged, never clipped. Under ``NATIVE`` the system's own limits are the only limits.
* **Counts from the counting proxy.** Per-turn usage is the difference of the arm's proxy book before and after the
  call. The system's own report is kept beside it and a difference is recorded, not reconciled.
* **Every outcome is a result.** A timeout, an unavailable arm, an unsupported condition or an unhandled fault is a
  ledger record with its status and a fixed code. The oracle policy-tool condition is NOT_RUN for every arm (BADR-0039).

Mutation cases run a protocol 16 mutation against a system through ``benchmark/mutations_apply.py`` and ask the base
question (once, or before and after the change), then score what the answer cited and showed.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from benchmark.contracts import (
    CaseRequest,
    CaseResponse,
    ErrorOrigin,
    RunStatus,
    UsageReport,
    classify_exception,
)
from benchmark.eval.memory import EpisodeRun, MemoryScore, TurnObservation, score_memory
from benchmark.fixtures import sha256_hex
from benchmark.fixtures.documents import Document
from benchmark.fixtures.episodes import Episode, Turn
from benchmark.fixtures.mutations import AskPattern, MutationInstance, Op, OpKind
from benchmark.fixtures.questions import GoldRecord
from benchmark.mutations_apply import (
    Application,
    MutationTarget,
    Outcome,
    Violations,
    apply_instance,
    unsupported_reasons,
    violations,
)
from benchmark.runner import LedgerRecord, RunLedger, derived_rng

MATCHED_MODEL_CALLS = 5  # including the final answer; Palladion's main budget and E1's ceiling
MATCHED_TOOL_CALLS = 8
CONTEXT_WORDS = 120  # the equal budget of every memory baseline, label included
LINE_END = chr(10)
FIXED_CLOCK_REASON = "the arm runs at one fixed evaluation time, so freshness after a gap cannot be tested (BR46)"
SUMMARY_LABEL = "Summary of the conversation so far:"
EPISODE_LABEL = "Earlier in this conversation:"
LAST_N = 2
ORACLE_REASON = "the oracle policy-tool condition is deferred to B08 and not run in this pilot (BADR-0039)"
_STOP = frozenset(
    [
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "for",
        "is",
        "are",
        "was",
        "were",
        "be",
        "it",
        "this",
        "that",
        "with",
        "as",
        "at",
        "by",
        "from",
        "what",
        "which",
        "who",
    ]
)


class Memory(StrEnum):
    NATIVE = "native"  # the system's own continuity
    NONE = "none"
    LAST_N = "last_n"
    ROLLING_SUMMARY = "rolling_summary"
    SCOPED_EPISODIC = "scoped_episodic"


class Heat(StrEnum):
    COLD = "cold"  # fresh principal and case on a freshly opened system
    WARM = "warm"  # a second pass of the episode on warm caches, with a fresh principal and case
    HOT = "hot"  # a repeat of the cold pass with the same principal and case: memory retained


class Budget(StrEnum):
    MATCHED = "matched"
    NATIVE = "native"


@dataclass(frozen=True)
class RunCondition:
    memory: Memory
    heat: Heat = Heat.COLD
    budget: Budget = Budget.MATCHED

    @property
    def label(self) -> str:
        return f"{self.memory.value}.{self.heat.value}.{self.budget.value}"


class TrackCSystem(Protocol):
    def answer(self, case: CaseRequest) -> CaseResponse: ...

    def reset_case(self, case_id: str) -> None: ...

    def report_usage(self) -> UsageReport: ...

    def report_trace(self) -> list[dict[str, Any]]: ...

    def call_flags(self) -> tuple[str, ...]: ...


@dataclass(frozen=True)
class TrackCArm:
    """One system under test and what it supports.

    ``open_system`` returns the system bound to an episode (its principal and case) for a heat; ``usage`` is the
    counting proxy's running book for this arm; ``mutation_target`` builds the target a mutation is applied to. A
    ``fixed_clock`` arm cannot follow an episode's clock: its requests are moved to that time and flagged.
    """

    arm_id: str
    open_system: Callable[[Episode | None, Heat], TrackCSystem]
    usage: Callable[[], Mapping[str, int]]
    memories: frozenset[Memory]
    heats: frozenset[Heat] = frozenset({Heat.COLD, Heat.WARM})
    mutation_target: Callable[[], MutationTarget] | None = None
    live_tools: frozenset[str] | None = None
    forced: tuple[RunStatus, str] | None = None  # NOT_RUN or FEATURE_NOT_SUPPORTED, with the reason
    fixed_clock: str | None = None  # the one evaluation time the system can run at; every request is moved to it
    mutations_unavailable: str = "the arm declares no mutation interface"


# --------------------------------------------------------------------------- the memory baselines


@dataclass(frozen=True)
class Exchange:
    utterance: str
    reply: str


def _words(text: str) -> list[str]:
    return text.split()


def _first_sentence(text: str) -> str:
    return re.split(r"(?<=[.!?])\s+|\n+", text.strip(), maxsplit=1)[0]


def _tail(words: Sequence[str], budget: int) -> str:
    return " ".join(words[-budget:]) if budget > 0 else ""


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9-]+", text.lower()) if len(w) > 2 and w not in _STOP}


def context_for(memory: Memory, history: Sequence[Exchange], query: str, budget_words: int = CONTEXT_WORDS) -> str:
    """What the harness hands a system that has no memory of its own, cut to ``budget_words`` words in all, its label
    included (most recent words kept).

    All four forms are deterministic and use only this episode's exchanges, so none can carry another episode's facts.
    """
    if memory in (Memory.NONE, Memory.NATIVE) or not history:
        return ""
    if memory is Memory.ROLLING_SUMMARY:
        label = SUMMARY_LABEL
        room = budget_words - len(_words(label))
        summary: list[str] = []
        for exchange in history:
            summary += _words(f"{_first_sentence(exchange.utterance)} -> {_first_sentence(exchange.reply)}")
            summary = summary[-room:]
        return f"{label} {' '.join(summary)}"
    label = EPISODE_LABEL
    if memory is Memory.LAST_N:
        chosen = history[-LAST_N:]
    else:
        wanted = _tokens(query)
        ranked = sorted(
            range(len(history)), key=lambda i: (-len(wanted & _tokens(history[i].utterance + history[i].reply)), -i)
        )
        chosen = [
            history[i] for i in sorted(ranked[:LAST_N]) if wanted & _tokens(history[i].utterance + history[i].reply)
        ]
        if not chosen:
            return ""
    text = " ".join(_words(" ".join(f"User: {e.utterance} Assistant: {e.reply}" for e in chosen)))
    return f"{label} {_tail(_words(text), budget_words - len(_words(label)))}"


def with_context(query: str, context: str) -> str:
    return f"{context}\n\nCurrent question: {query}" if context else query


# --------------------------------------------------------------------------- records


@dataclass(frozen=True)
class TurnRecord:
    arm_id: str
    condition: RunCondition
    episode_id: str
    turn_index: int
    question_id: str
    status: RunStatus
    code: str | None
    response: CaseResponse | None
    usage_delta: Mapping[str, int]
    reported: UsageReport | None
    duration_ms: float
    flags: tuple[str, ...]
    context_words: int
    mutation: Application | None = None
    trace: tuple[
        Mapping[str, Any], ...
    ] = ()  # what the system reported about this answer, for the metrics that read it


@dataclass(frozen=True)
class MutationRecord:
    arm_id: str
    instance_id: str
    status: RunStatus
    code: str | None
    application: Application
    asks: tuple[tuple[CaseResponse, Violations], ...]
    usage_delta: Mapping[str, int]
    flags: tuple[str, ...]
    traces: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class Skipped:
    arm_id: str
    condition: str
    reason: str
    status: RunStatus


@dataclass
class TrackCResult:
    run_id: str
    turns: list[TurnRecord] = field(default_factory=list)
    mutations: list[MutationRecord] = field(default_factory=list)
    skipped: list[Skipped] = field(default_factory=list)
    divergences: list[str] = field(default_factory=list)
    residues: list[str] = field(default_factory=list)  # what a mutation left behind that could not be undone

    def episode_runs(self, episodes: Iterable[Episode]) -> dict[tuple[str, str], list[EpisodeRun]]:
        """Observations grouped by (arm, condition label), ready for ``score_memory``."""
        by_episode = {e.episode_id: e for e in episodes}
        grouped: dict[tuple[str, str, str], list[TurnRecord]] = {}
        for record in self.turns:
            grouped.setdefault((record.arm_id, record.condition.label, record.episode_id), []).append(record)
        runs: dict[tuple[str, str], list[EpisodeRun]] = {}
        for (arm, label, episode_id), records in grouped.items():
            episode = by_episode[episode_id]
            ordered = {r.turn_index: r for r in records}
            observations = tuple(
                TurnObservation(t, ordered[t.index].response if t.index in ordered else None) for t in episode.turns
            )
            runs.setdefault((arm, label), []).append(EpisodeRun(episode, observations))
        return runs


def score_conditions(
    result: TrackCResult, episodes: Sequence[Episode], arms: Mapping[str, TrackCArm]
) -> dict[tuple[str, str], MemoryScore]:
    """The memory score of every (arm, condition) that ran at least one episode."""
    return {
        key: score_memory(
            runs,
            live_tools=arms[key[0]].live_tools,
            live_unobservable=FIXED_CLOCK_REASON if arms[key[0]].fixed_clock is not None else None,
        )
        for key, runs in result.episode_runs(episodes).items()
    }


# --------------------------------------------------------------------------- the runner


def _origin(record: MutationRecord) -> ErrorOrigin | None:
    if record.status is RunStatus.OK:
        return None
    return ErrorOrigin.HARNESS if record.application.outcome is Outcome.FAILED else ErrorOrigin.ARM


def question_id_for(episode_id: str, turn_index: int, label: str) -> str:
    return "q-" + sha256_hex(f"{episode_id}:{turn_index}:{label}")[:16]


def planned_question_ids(
    episodes: Sequence[Episode], cases: Sequence[tuple[MutationInstance, GoldRecord]], snapshot_id: str
) -> list[str]:
    """Every question id the runner will send, so a generator pool can be assigned a model for each before the run."""
    ids = [r.question_id for e in episodes for r in e.requests(snapshot_id)]
    for instance, question in cases:
        phases = ("before", "after") if instance.ask is AskPattern.BEFORE_AFTER else ("after",)
        for phase in phases:
            ids.append(question_id_for(instance.instance_id, 0, f"{question.question_id}:{phase}"))
            if phase == "after":  # the patch, and so the claim, is in place for the second ask only
                ids += [
                    question_id_for(instance.instance_id, 0, f"{question.question_id}:{phase}:claim{n}")
                    for n, op in enumerate(o for o in instance.patch if o.kind is OpKind.CHAT_CLAIM)
                ]
    return ids


_APPLICATION_STATUS = {
    Outcome.NOT_RUN: RunStatus.NOT_RUN,
    Outcome.FEATURE_NOT_SUPPORTED: RunStatus.FEATURE_NOT_SUPPORTED,
    Outcome.FAILED: RunStatus.INVALID_RUN,  # the harness could not apply a mutation it believed it could
}


class TrackCRunner:
    def __init__(
        self,
        run_id: str,
        out: Path,
        *,
        manifest_sha256: str,
        snapshot_id: str,
        order_seed: int,
        filters_for: Callable[[str], Mapping[str, Any]],
        base_corpus: Sequence[Document] = (),
        max_evidence_tokens: int = 4000,
    ) -> None:
        self.run_id = run_id
        self._base = tuple(base_corpus)
        self._applied_in_episode: list[tuple[str, MutationTarget]] = []
        out.mkdir(parents=True, exist_ok=True)
        self._out = out
        self.ledger = RunLedger(out / "ledger.jsonl")
        self._manifest = manifest_sha256
        self._snapshot = snapshot_id
        self._seed = order_seed
        self._filters_for = filters_for
        self._budget = max_evidence_tokens
        self.result = TrackCResult(run_id)

    # -- planning -----------------------------------------------------------------------------------------------

    def run(
        self,
        arms: Sequence[TrackCArm],
        episodes: Sequence[Episode],
        conditions: Sequence[RunCondition],
        mutations: Mapping[str, MutationInstance] | None = None,
        *,
        cases: Sequence[tuple[MutationInstance, GoldRecord]] = (),
    ) -> TrackCResult:
        """Run every arm on every episode under every condition it supports, then the mutation cases.

        Order is randomized from the seed; arms that cannot run a condition are listed with the reason and nothing is
        run for them there.
        """
        shuffled = list(arms)
        derived_rng(self._seed, "arms").shuffle(shuffled)
        for arm in shuffled:
            self._skip(arm.arm_id, "oracle_policy_tool", ORACLE_REASON, RunStatus.NOT_RUN)
            if arm.forced is not None:
                forced_status, forced_reason = arm.forced
                self._skip(arm.arm_id, "all", forced_reason, forced_status)
                continue
            for condition in conditions:
                reason = self._unsupported(arm, condition)
                if reason is not None:
                    self._skip(arm.arm_id, condition.label, reason, RunStatus.FEATURE_NOT_SUPPORTED)
                    continue
                self._run_condition(arm, episodes, condition, mutations or {})
        for arm in shuffled:
            if arm.forced is not None or not cases:
                continue
            if arm.mutation_target is None:
                self._skip(arm.arm_id, "mutation_cases", arm.mutations_unavailable, RunStatus.NOT_RUN)
                continue
            for instance, question in cases:
                self._run_mutation(arm, instance, question)
        return self.result

    @staticmethod
    def _unsupported(arm: TrackCArm, condition: RunCondition) -> str | None:
        if condition.memory not in arm.memories:
            return f"{arm.arm_id} does not support the {condition.memory.value} memory condition"
        if condition.heat not in arm.heats:
            return f"{arm.arm_id} does not support the {condition.heat.value} condition"
        return None

    def _skip(self, arm_id: str, label: str, reason: str, status: RunStatus) -> None:
        self.result.skipped.append(Skipped(arm_id, label, reason, status))

    # -- episodes -----------------------------------------------------------------------------------------------

    def _run_condition(
        self,
        arm: TrackCArm,
        episodes: Sequence[Episode],
        condition: RunCondition,
        mutations: Mapping[str, MutationInstance],
    ) -> None:
        order = list(episodes)
        derived_rng(self._seed, f"{arm.arm_id}:{condition.label}").shuffle(order)
        for episode in order:
            system = arm.open_system(episode, condition.heat)
            if condition.heat is not Heat.HOT:
                system.reset_case(episode.episode_id)  # once, before the first turn: never inside an episode
            history: list[Exchange] = []
            started = dict(arm.usage())
            for turn, request in zip(episode.turns, episode.requests(self._snapshot, self._budget), strict=True):
                record = self._turn(arm, system, condition, episode, turn, request, history, mutations)
                self.result.turns.append(record)
                self._log(record)
                if record.response is not None:
                    history.append(Exchange(turn.utterance, record.response.answer_text))
            self._check_book(arm, condition, episode, started)
            self._restore_after(episode)

    def _turn(
        self,
        arm: TrackCArm,
        system: TrackCSystem,
        condition: RunCondition,
        episode: Episode,
        turn: Turn,
        request: CaseRequest,
        history: Sequence[Exchange],
        mutations: Mapping[str, MutationInstance],
    ) -> TurnRecord:
        application: Application | None = None
        if turn.before is not None:
            application = self._apply_before(arm, mutations.get(turn.before), turn.before)
        context = context_for(condition.memory, history, turn.utterance)
        asked = replace(
            request,
            query=with_context(request.query, context),
            filters=self._filters_for(request.principal_id),
        )
        clock_flags: list[str] = []
        if arm.fixed_clock is not None and asked.evaluation_time != arm.fixed_clock:
            asked = replace(asked, evaluation_time=arm.fixed_clock)
            clock_flags.append("CLOCK_FIXED_BY_ARM")
        before = dict(arm.usage())
        started = time.perf_counter()
        response: CaseResponse | None = None
        status, origin, code = RunStatus.OK, None, None
        reported: UsageReport | None = None
        try:
            response = system.answer(asked)
        except Exception as exc:
            status, origin, code = classify_exception(exc)
        duration = (time.perf_counter() - started) * 1000.0
        after = dict(arm.usage())
        delta = {key: after.get(key, 0) - before.get(key, 0) for key in after}
        flags = [*clock_flags, *(system.call_flags() if response is not None else ())]
        trace: tuple[Mapping[str, Any], ...] = ()
        if response is not None:
            reported = system.report_usage()
            trace = tuple(system.report_trace()[-1:])
        if condition.budget is Budget.MATCHED:
            flags += self._over_budget(delta)
        if application is not None and application.outcome is not Outcome.APPLIED:
            flags.append(f"MUTATION_{application.outcome.value.upper()}")
        record = TurnRecord(
            arm.arm_id, condition, episode.episode_id, turn.index, request.question_id, status, code, response,
            delta, reported, duration, tuple(flags), len(_words(context)), application, trace,
        )  # fmt: skip
        if origin is not None:
            record = replace(record, flags=(*record.flags, f"ORIGIN={origin.value}"))
        return record

    def _restore_after(self, episode: Episode) -> None:
        """Undo the mutations the episode applied, so the next one starts from the base state."""
        for arm_id, target in self._applied_in_episode:
            self.result.residues += [f"{arm_id}/{episode.episode_id}: {why}" for why in target.restore()]
        self._applied_in_episode = []

    def _apply_before(self, arm: TrackCArm, instance: MutationInstance | None, name: str) -> Application:
        if instance is None or arm.mutation_target is None:
            reason = f"{name} was not supplied" if instance is None else f"{arm.arm_id} has no mutation interface"
            return Application(name, arm.arm_id, Outcome.NOT_RUN, (reason,))
        target = arm.mutation_target()
        application = apply_instance(target, instance, self._base)
        self._applied_in_episode.append((arm.arm_id, target))
        return application

    @staticmethod
    def _over_budget(delta: Mapping[str, int]) -> list[str]:
        flags = []
        if delta.get("calls", 0) > MATCHED_MODEL_CALLS:
            flags.append(f"OVER_MATCHED_MODEL_CALLS={delta['calls']}")
        if delta.get("tool_calls", 0) > MATCHED_TOOL_CALLS:
            flags.append(f"OVER_MATCHED_TOOL_CALLS={delta['tool_calls']}")
        return flags

    def _check_book(
        self, arm: TrackCArm, condition: RunCondition, episode: Episode, started: Mapping[str, int]
    ) -> None:
        """The arm's own report of an episode against the proxy's book: a difference is recorded, never reconciled."""
        mine = [
            r
            for r in self.result.turns
            if (r.arm_id, r.condition, r.episode_id) == (arm.arm_id, condition, episode.episode_id)
        ]
        spent = {k: arm.usage().get(k, 0) - started.get(k, 0) for k in ("calls", "prompt_tokens", "completion_tokens")}
        summed = {k: sum(r.usage_delta.get(k, 0) for r in mine) for k in spent}
        if spent != summed:
            self.result.divergences.append(
                f"{arm.arm_id}/{condition.label}/{episode.episode_id}: turns sum to {summed}, the book moved by {spent}"
            )

    # -- mutation cases -------------------------------------------------------------------------------------------

    def _run_mutation(self, arm: TrackCArm, instance: MutationInstance, question: GoldRecord) -> None:
        assert arm.mutation_target is not None
        target = arm.mutation_target()
        system = arm.open_system(None, Heat.COLD)
        system.reset_case(question.question_id)
        before = dict(arm.usage())
        flags: list[str] = []
        asks: list[tuple[CaseResponse, Violations]] = []
        traces: list[Mapping[str, Any]] = []
        status: RunStatus = RunStatus.OK
        code: str | None = None
        if instance.ask is AskPattern.BEFORE_AFTER and not unsupported_reasons(target, instance):
            first, status, code = self._ask(arm, system, instance, question, "before", ())
            if first is not None:
                asks.append(
                    (first, violations(instance, first.used_evidence_ids, first.answer_text, first.evidence_status))
                )
                traces += system.report_trace()[-1:]
        application = apply_instance(target, instance, self._base)
        flags.append(f"APPLICATION={application.outcome.value}")
        if application.outcome is Outcome.APPLIED and status is RunStatus.OK:
            second, status, code = self._ask(arm, system, instance, question, "after", application.carried)
            if second is not None:
                asks.append(
                    (second, violations(instance, second.used_evidence_ids, second.answer_text, second.evidence_status))
                )
                traces += system.report_trace()[-1:]
        elif application.outcome is not Outcome.APPLIED:
            status = _APPLICATION_STATUS[application.outcome]
            code = application.outcome.value.upper()
        flags += [f"NOT_RESTORED={why}" for why in target.restore()]  # the next case starts from the base state
        after = dict(arm.usage())
        record = MutationRecord(
            arm.arm_id, instance.instance_id, status, code, application, tuple(asks),
            {k: after.get(k, 0) - before.get(k, 0) for k in after}, tuple(flags), tuple(traces),
        )  # fmt: skip
        self.result.mutations.append(record)
        self._log_mutation(record)

    def _ask(
        self,
        arm: TrackCArm,
        system: TrackCSystem,
        instance: MutationInstance,
        question: GoldRecord,
        phase: str,
        carried: Sequence[Op],
    ) -> tuple[CaseResponse | None, RunStatus, str | None]:
        query, evaluation_time = question.query, arm.fixed_clock or question.evaluation_time
        claims = [op.value for op in carried if op.kind is OpKind.CHAT_CLAIM]
        for op in carried:
            if op.kind is OpKind.SET_QUERY:
                query = op.value
            elif op.kind is OpKind.SET_CLOCK:
                evaluation_time = op.value

        def request(label: str, text: str) -> CaseRequest:
            return CaseRequest(
                question_id=question_id_for(instance.instance_id, 0, f"{question.question_id}:{label}"),
                query=text,
                principal_id=question.principal_id,
                corpus_snapshot_id=question.corpus_snapshot_id,
                evaluation_time=evaluation_time,
                event_time=question.event_time,
                filters=self._filters_for(question.principal_id),
                max_evidence_tokens=self._budget,
                episode_id=None,
                turn_index=0,
            )

        try:
            for number, claim in enumerate(claims):  # a claim is said in the conversation before the question
                system.answer(request(f"{phase}:claim{number}", claim))
            return system.answer(request(phase, query)), RunStatus.OK, None
        except Exception as exc:
            status, _, code = classify_exception(exc)
            return None, status, code

    # -- ledger -------------------------------------------------------------------------------------------------

    def _keep(self, name: str, row: Mapping[str, Any]) -> None:
        """Append what a record cannot hold in the ledger (answers, self-reports, traces) to a run file."""
        with (self._out / name).open("a", encoding="utf-8", newline=LINE_END) as handle:
            handle.write(json.dumps(row, sort_keys=True, default=str) + LINE_END)

    def _log(self, record: TurnRecord) -> None:
        self._keep(
            "turns.jsonl",
            {
                "arm": record.arm_id,
                "condition": record.condition.label,
                "episode_id": record.episode_id,
                "turn_index": record.turn_index,
                "question_id": record.question_id,
                "status": record.status.value,
                "response": None if record.response is None else record.response.to_dict(),
                "reported": None if record.reported is None else asdict(record.reported),
                "trace": list(record.trace),
            },
        )
        self.ledger.append(
            LedgerRecord(
                run_id=self.run_id,
                manifest_sha256=self._manifest,
                arm=f"{record.arm_id}|{record.condition.label}",
                question_id=record.question_id,
                attempt=1,
                is_final=True,
                status=record.status,
                origin=ErrorOrigin.ARM if record.status is not RunStatus.OK else None,
                code=record.code,
                started_at_utc=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                duration_ms=record.duration_ms,
                initial_status=record.status,
                attempts=1,
                payload={
                    "episode_id": record.episode_id,
                    "turn_index": record.turn_index,
                    "usage_delta": dict(record.usage_delta),
                    "context_words": record.context_words,
                    "answer_chars": None if record.response is None else len(record.response.answer_text),
                    "evidence_status": None if record.response is None else record.response.evidence_status.value,
                },
                flags=record.flags,
            )
        )

    def _log_mutation(self, record: MutationRecord) -> None:
        self._keep(
            "mutations.jsonl",
            {
                "arm": record.arm_id,
                "instance": record.instance_id,
                "status": record.status.value,
                "application": {
                    "outcome": record.application.outcome.value,
                    "reasons": list(record.application.reasons),
                },
                "asks": [
                    {"response": response.to_dict(), "unauthorized_reads": found.unauthorized_reads}
                    for response, found in record.asks
                ],
                "traces": list(record.traces),
            },
        )
        self.ledger.append(
            LedgerRecord(
                run_id=self.run_id,
                manifest_sha256=self._manifest,
                arm=f"{record.arm_id}|mutation|{record.instance_id}",
                question_id=question_id_for(record.instance_id, 0, "case"),
                attempt=1,
                is_final=True,
                status=record.status,
                origin=_origin(record),
                code=record.code,
                started_at_utc=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                duration_ms=None,
                initial_status=record.status,
                attempts=1,
                payload={
                    "application": record.application.outcome.value,
                    "reasons": list(record.application.reasons),
                    "mismatches": list(record.application.mismatches),
                    "asks": len(record.asks),
                    "unauthorized_reads": sum(v.unauthorized_reads for _, v in record.asks),
                    "usage_delta": dict(record.usage_delta),
                },
                flags=record.flags,
            )
        )
