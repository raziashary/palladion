"""Track C runner (B07-T08.01): isolation, baselines at an equal budget, run states, counts from the book, mutations."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from benchmark.contracts import (
    ArmUnavailable,
    CapabilityUnsupported,
    CaseRequest,
    CaseResponse,
    ErrorOrigin,
    EvidenceStatus,
    RunStatus,
    UsageReport,
)
from benchmark.eval.observable import NotObservable, Rate
from benchmark.fixtures.documents import Document
from benchmark.fixtures.episodes import Episode, EpisodeKind, build_episodes
from benchmark.fixtures.mutations import MutationContext, MutationError, MutationInstance, Op, instantiate
from benchmark.fixtures.world import World
from benchmark.mutations_apply import Outcome, RebuildTarget
from benchmark.track_c import (
    CONTEXT_WORDS,
    MATCHED_MODEL_CALLS,
    Budget,
    Exchange,
    Heat,
    Memory,
    RunCondition,
    TrackCArm,
    TrackCRunner,
    context_for,
    planned_question_ids,
    score_conditions,
    with_context,
)

MANIFEST = "0" * 64
ROOT = Path(__file__).resolve().parents[1]


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("run_track_c", ROOT / "scripts" / "run_track_c.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # a dataclass in the script resolves its module through sys.modules
    spec.loader.exec_module(module)
    return module


run_track_c = load_script()
TOKEN = re.compile(r"\b(?:RC|NT)-[0-9A-F]{6}\b")


@pytest.fixture(scope="module")
def episodes(s_world: World) -> tuple[Episode, ...]:
    return build_episodes(s_world, 7, 28)


def pick(episodes: tuple[Episode, ...], *kinds: EpisodeKind) -> list[Episode]:
    return [next(e for e in episodes if e.kind is kind) for kind in kinds]


class Book:
    """A stand-in for one arm's counting proxy: every answer adds one call and fixed tokens."""

    def __init__(self, calls_per_answer: int = 1) -> None:
        self.totals = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "tool_calls": 0}
        self.per_answer = calls_per_answer

    def usage(self) -> Mapping[str, int]:
        return dict(self.totals)

    def spend(self) -> None:
        self.totals["calls"] += self.per_answer
        self.totals["prompt_tokens"] += 100 * self.per_answer
        self.totals["completion_tokens"] += 20 * self.per_answer


class Remembering:
    """A system with memory: it repeats the case reference and notes it was told, only from its own namespace."""

    def __init__(self, store: dict[str, list[str]], namespace: str, book: Book, log: Log) -> None:
        self.store, self.namespace, self.book, self.log = store, namespace, book, log

    def reset_case(self, case_id: str) -> None:
        self.log.resets.append(case_id)

    def answer(self, case: CaseRequest) -> CaseResponse:
        self.log.queries.append(case.query)
        self.book.spend()
        memory = self.store.setdefault(self.namespace, [])
        memory += [t for t in TOKEN.findall(case.query) if t not in memory]
        return response(case, " ".join(f"noted {t}" for t in memory) or "ok")

    def report_usage(self) -> UsageReport:
        return UsageReport(1, 0, 0, 100, 20, None)

    def report_trace(self) -> list[dict[str, Any]]:
        return []

    def call_flags(self) -> tuple[str, ...]:
        return ()


class Log:
    def __init__(self) -> None:
        self.resets: list[str] = []
        self.queries: list[str] = []


def response(case: CaseRequest, text: str) -> CaseResponse:
    return CaseResponse(
        question_id=case.question_id, run_id="run-1", answer_text=text, evidence_status=EvidenceStatus.SUPPORTED,
        claims=(), used_evidence_ids=(), tool_calls=(), critic=None, model_invocations=None, latency_ms=None,
        cost_usd=None, abstention_reason=None,
    )  # fmt: skip


def memory_arm(
    arm_id: str = "E4", *, shared: bool = False, book: Book | None = None, memories: frozenset[Memory] | None = None
) -> tuple[TrackCArm, Book, Log, dict[str, list[str]]]:
    book = book or Book()
    log = Log()
    store: dict[str, list[str]] = {}

    def open_system(episode: Episode | None, heat: Heat) -> Remembering:
        namespace = "everyone" if shared or episode is None else f"{episode.episode_id}:{heat.value}"
        return Remembering(store, namespace, book, log)

    arm = TrackCArm(arm_id, open_system, book.usage, memories or frozenset({Memory.NATIVE}),
                    frozenset({Heat.COLD, Heat.WARM, Heat.HOT}), None, frozenset({"get_live_state"}))  # fmt: skip
    return arm, book, log, store


def runner(tmp_path: Path, corpus: tuple[Document, ...] = ()) -> TrackCRunner:
    return TrackCRunner(
        "run-c", tmp_path, manifest_sha256=MANIFEST, snapshot_id="snap-1", order_seed=3, filters_for=lambda _: {},
        base_corpus=corpus,
    )  # fmt: skip


COLD = RunCondition(Memory.NATIVE, Heat.COLD, Budget.MATCHED)

# --------------------------------------------------------------------------- the memory baselines


HISTORY = [
    Exchange(f"Case RC-{i:06X} asks about refund window {i}.", f"Noted RC-{i:06X}. Window {i}.") for i in range(6)
]


def test_each_baseline_is_deterministic_and_cut_to_the_equal_budget() -> None:
    query = "What about RC-000002 refund window?"
    contexts = {m: context_for(m, HISTORY, query) for m in Memory}
    assert contexts[Memory.NONE] == "" and contexts[Memory.NATIVE] == ""
    for memory in (Memory.LAST_N, Memory.ROLLING_SUMMARY, Memory.SCOPED_EPISODIC):
        text = contexts[memory]
        assert text and text == context_for(memory, HISTORY, query)
        assert len(text.split()) <= CONTEXT_WORDS, "the label is inside the budget"
    assert "RC-000005" in contexts[Memory.LAST_N] and "RC-000000" not in contexts[Memory.LAST_N]
    assert "RC-000002" in contexts[Memory.SCOPED_EPISODIC], "retrieval picks the exchange that matches the question"
    assert contexts[Memory.ROLLING_SUMMARY].startswith("Summary of the conversation so far")


def test_the_budget_binds_and_keeps_the_most_recent_words() -> None:
    long = [Exchange("word " * 300 + f"RC-{i:06X}", "reply") for i in range(3)]
    for memory in (Memory.LAST_N, Memory.ROLLING_SUMMARY):
        text = context_for(memory, long, "q", budget_words=50)
        assert len(text.split()) <= 50
    assert "RC-000002" in context_for(Memory.LAST_N, long, "q", budget_words=50)


def test_a_baseline_with_nothing_to_use_adds_nothing() -> None:
    assert (
        context_for(Memory.LAST_N, [], "q") == ""
        and context_for(Memory.SCOPED_EPISODIC, HISTORY, "zzz unrelated") == ""
    )
    assert with_context("Q?", "") == "Q?" and with_context("Q?", "C").endswith("Current question: Q?")


# --------------------------------------------------------------------------- isolation


def test_a_fact_stated_in_one_episode_is_absent_from_the_next_and_a_global_memory_is_caught(
    tmp_path: Path, episodes: tuple[Episode, ...]
) -> None:
    chosen = pick(episodes, EpisodeKind.ADD_FACT, EpisodeKind.DISTRACTOR, EpisodeKind.CORRECTION)
    isolated, _, _, _ = memory_arm("E4")
    shared, _, _, _ = memory_arm("E3", shared=True)
    result = runner(tmp_path).run([isolated, shared], chosen, [COLD])
    scores = score_conditions(result, chosen, {"E4": isolated, "E3": shared})
    assert scores[("E4", COLD.label)].cross_episode_leaks.hits == 0
    assert scores[("E3", COLD.label)].cross_episode_leaks.hits > 0, "the control with one shared memory must leak"


def test_state_is_reset_once_per_episode_before_the_first_turn_and_never_for_a_hot_repeat(
    tmp_path: Path, episodes: tuple[Episode, ...]
) -> None:
    chosen = pick(episodes, EpisodeKind.ADD_FACT, EpisodeKind.CORRECTION)
    arm, _, log, _ = memory_arm()
    hot = RunCondition(Memory.NATIVE, Heat.HOT, Budget.MATCHED)
    runner(tmp_path).run([arm], chosen, [COLD, hot])
    assert sorted(log.resets) == sorted(e.episode_id for e in chosen), "one reset per cold episode, none for hot"


def test_the_cold_and_warm_passes_use_separate_namespaces(tmp_path: Path, episodes: tuple[Episode, ...]) -> None:
    chosen = pick(episodes, EpisodeKind.ADD_FACT)
    arm, _, _, store = memory_arm()
    warm = RunCondition(Memory.NATIVE, Heat.WARM, Budget.MATCHED)
    runner(tmp_path).run([arm], chosen, [COLD, warm])
    assert {key.split(":")[1] for key in store} == {"cold", "warm"}


# --------------------------------------------------------------------------- baselines in the loop


def test_a_system_without_memory_receives_the_baseline_context_and_the_native_one_receives_none(
    tmp_path: Path, episodes: tuple[Episode, ...]
) -> None:
    chosen = pick(episodes, EpisodeKind.ADD_FACT)
    arm, _, log, _ = memory_arm("E0", memories=frozenset({Memory.LAST_N, Memory.NONE}))
    last_n = RunCondition(Memory.LAST_N)
    result = runner(tmp_path).run([arm], chosen, [last_n, RunCondition(Memory.NONE)])
    queries = log.queries
    assert len(queries) == 2 * len(chosen[0].turns)
    first_pass = [r for r in result.turns if r.condition == last_n]
    assert first_pass[0].context_words == 0 and all(r.context_words > 0 for r in first_pass[1:])
    assert not any(r.context_words for r in result.turns if r.condition.memory is Memory.NONE)
    assert sum("Earlier in this conversation" in q for q in queries) == len(chosen[0].turns) - 1


def test_a_condition_the_arm_does_not_support_is_reported_with_its_reason_and_not_run(
    tmp_path: Path, episodes: tuple[Episode, ...]
) -> None:
    chosen = pick(episodes, EpisodeKind.ADD_FACT)
    arm, _, log, _ = memory_arm("E0", memories=frozenset({Memory.NONE}))
    result = runner(tmp_path).run([arm], chosen, [RunCondition(Memory.LAST_N), RunCondition(Memory.NONE)])
    skipped = {s.condition: s for s in result.skipped}
    assert skipped["last_n.cold.matched"].status is RunStatus.FEATURE_NOT_SUPPORTED
    assert "does not support the last_n memory condition" in skipped["last_n.cold.matched"].reason
    assert skipped["oracle_policy_tool"].status is RunStatus.NOT_RUN and "B08" in skipped["oracle_policy_tool"].reason
    assert {r.condition.label for r in result.turns} == {"none.cold.matched"}
    assert len(log.queries) == len(chosen[0].turns), "nothing was sent for the unsupported condition"


def test_an_arm_forced_out_of_the_run_is_listed_once_with_its_reason(
    tmp_path: Path, episodes: tuple[Episode, ...]
) -> None:
    arm, _, _, _ = memory_arm("E2")
    forced = TrackCArm("E2", arm.open_system, arm.usage, arm.memories, forced=(RunStatus.NOT_RUN, "no access (OQ07)"))
    result = runner(tmp_path).run([forced], pick(episodes, EpisodeKind.ADD_FACT), [COLD])
    assert result.turns == [] and any(s.arm_id == "E2" and s.reason == "no access (OQ07)" for s in result.skipped)


# --------------------------------------------------------------------------- counts and run states


def test_turn_counts_are_the_difference_of_the_proxys_book_and_sum_to_it(
    tmp_path: Path, episodes: tuple[Episode, ...]
) -> None:
    chosen = pick(episodes, EpisodeKind.ADD_FACT, EpisodeKind.CORRECTION)
    arm, book, _, _ = memory_arm()
    result = runner(tmp_path).run([arm], chosen, [COLD])
    turns = sum(len(e.turns) for e in chosen)
    assert all(
        r.usage_delta == {"calls": 1, "prompt_tokens": 100, "completion_tokens": 20, "tool_calls": 0}
        for r in result.turns
    )
    assert book.totals["calls"] == turns and result.divergences == []


def test_spend_outside_the_turns_is_recorded_as_a_divergence(tmp_path: Path, episodes: tuple[Episode, ...]) -> None:
    chosen = pick(episodes, EpisodeKind.ADD_FACT)

    class Background(Book):
        def usage(self) -> Mapping[str, int]:
            self.totals["calls"] += 1  # the book moves between the readings, as if something else were calling
            return dict(self.totals)

    quiet, _, _, _ = memory_arm("E4")
    noisy, _, _, _ = memory_arm("E3", book=Background())
    clean = runner(tmp_path / "quiet").run([quiet], chosen, [COLD])
    assert clean.divergences == [], "no spend outside the turns, no divergence"
    outcome = runner(tmp_path / "noisy").run([noisy], chosen, [COLD])
    assert outcome.divergences and "E3/native.cold.matched" in outcome.divergences[0]


def test_a_turn_over_the_matched_ceiling_is_flagged_and_a_native_turn_is_not(
    tmp_path: Path, episodes: tuple[Episode, ...]
) -> None:
    chosen = pick(episodes, EpisodeKind.ADD_FACT)
    arm, _, _, _ = memory_arm(book=Book(calls_per_answer=MATCHED_MODEL_CALLS + 1))
    native = RunCondition(Memory.NATIVE, Heat.COLD, Budget.NATIVE)
    result = runner(tmp_path).run([arm], chosen, [COLD, native])
    matched = [r for r in result.turns if r.condition == COLD]
    own = [r for r in result.turns if r.condition == native]
    assert all(f"OVER_MATCHED_MODEL_CALLS={MATCHED_MODEL_CALLS + 1}" in r.flags for r in matched)
    assert not any(any(f.startswith("OVER_MATCHED") for f in r.flags) for r in own)


class Failing(Remembering):
    def __init__(self, error: Exception, *args: Any) -> None:
        super().__init__(*args)
        self.error = error

    def answer(self, case: CaseRequest) -> CaseResponse:
        raise self.error


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (TimeoutError("late"), RunStatus.TIMEOUT, "DEADLINE_EXCEEDED"),
        (ArmUnavailable("down"), RunStatus.NOT_RUN, "ARM_UNAVAILABLE"),
        (CapabilityUnsupported("no"), RunStatus.FEATURE_NOT_SUPPORTED, "CAPABILITY_UNSUPPORTED"),
        (ZeroDivisionError("bug"), RunStatus.INVALID_RUN, "UNHANDLED_ZeroDivisionError"),
    ],
)
def test_a_failed_turn_is_a_recorded_run_state_and_the_episode_goes_on(
    tmp_path: Path, episodes: tuple[Episode, ...], error: Exception, status: RunStatus, code: str
) -> None:
    chosen = pick(episodes, EpisodeKind.ADD_FACT)
    book, log = Book(), Log()
    arm = TrackCArm("E4", lambda e, h: Failing(error, {}, "x", book, log), book.usage, frozenset({Memory.NATIVE}))
    run = runner(tmp_path)
    result = run.run([arm], chosen, [COLD])
    assert len(result.turns) == len(chosen[0].turns)
    assert all(r.status is status and r.code == code and r.response is None for r in result.turns)
    ledger = run.ledger.records
    assert len(ledger) == len(result.turns) and all(r.is_final and r.status is status for r in ledger)
    score = score_conditions(result, chosen, {"E4": arm})[("E4", COLD.label)]
    assert score.unanswered == len(chosen[0].turns), "failed turns are counted, not scored"


# --------------------------------------------------------------------------- mutation cases


@pytest.fixture(scope="module")
def mutation_ctx(s_world: World, s_corpus: tuple[Document, ...], s_questions: Any) -> MutationContext:
    return MutationContext(s_world, s_corpus, s_questions, 7)


class Rebuilds:
    def __init__(self) -> None:
        self.builds = 0

    def __call__(self, corpus: tuple[Document, ...]) -> None:
        self.builds += 1


def retriever_arm(ctx: MutationContext, rebuilds: Rebuilds) -> tuple[TrackCArm, Book, Log]:
    arm, book, log, _ = memory_arm("R2", memories=frozenset({Memory.NONE}))
    return (
        TrackCArm(
            "R2",
            arm.open_system,
            arm.usage,
            arm.memories,
            mutation_target=lambda: RebuildTarget("R2", ctx.corpus, rebuilds),
        ),
        book,
        log,
    )


def test_a_mutation_case_applies_the_patch_asks_and_scores_the_answer(
    tmp_path: Path, mutation_ctx: MutationContext
) -> None:
    rebuilds = Rebuilds()
    arm, _, log = retriever_arm(mutation_ctx, rebuilds)
    instance = instantiate(mutation_ctx, "M01")
    question = mutation_ctx.question(instance.base_question_id)
    run = runner(tmp_path, mutation_ctx.corpus)
    result = run.run([arm], [], [], cases=[(instance, question)])
    (record,) = result.mutations
    assert record.status is RunStatus.OK and record.application.verified and rebuilds.builds == 2
    assert len(record.asks) == 1 and log.queries == [question.query]
    assert record.asks[0][1].unauthorized_reads == 0
    assert run.ledger.records[-1].payload["application"] == "applied"


def test_a_before_after_mutation_is_asked_twice_around_the_change(
    tmp_path: Path, mutation_ctx: MutationContext
) -> None:
    arm, _, log = retriever_arm(mutation_ctx, Rebuilds())
    instance = instantiate(mutation_ctx, "M09")
    question = mutation_ctx.question(instance.base_question_id)
    result = runner(tmp_path, mutation_ctx.corpus).run([arm], [], [], cases=[(instance, question)])
    (record,) = result.mutations
    assert len(record.asks) == 2 and len(log.queries) == 2


def test_a_carried_query_change_reaches_the_system(tmp_path: Path, mutation_ctx: MutationContext) -> None:
    arm, _, log = retriever_arm(mutation_ctx, Rebuilds())
    instance = instantiate(mutation_ctx, "M17")
    question = mutation_ctx.question(instance.base_question_id)
    runner(tmp_path, mutation_ctx.corpus).run([arm], [], [], cases=[(instance, question)])
    assert log.queries and log.queries != [question.query] and log.queries[0] == instance.patch[0].value


def test_a_mutation_the_arm_cannot_take_is_recorded_and_the_question_is_not_asked(
    tmp_path: Path, mutation_ctx: MutationContext
) -> None:
    arm, _, log = retriever_arm(mutation_ctx, Rebuilds())
    instance: MutationInstance = instantiate(mutation_ctx, "M08")
    question = mutation_ctx.question(instance.base_question_id)
    result = runner(tmp_path, mutation_ctx.corpus).run([arm], [], [], cases=[(instance, question)])
    (record,) = result.mutations
    assert record.application.outcome is Outcome.FEATURE_NOT_SUPPORTED and record.asks == () and log.queries == []
    assert record.status is RunStatus.FEATURE_NOT_SUPPORTED and record.code == "FEATURE_NOT_SUPPORTED"


def test_an_episode_turn_that_names_a_mutation_applies_it_or_records_why_not(
    tmp_path: Path, episodes: tuple[Episode, ...], mutation_ctx: MutationContext
) -> None:
    (supersede,) = pick(episodes, EpisodeKind.SUPERSEDE)
    rebuilds = Rebuilds()
    arm, _, _ = retriever_arm(mutation_ctx, rebuilds)
    plain = TrackCArm("R2", arm.open_system, arm.usage, frozenset({Memory.NONE}), mutation_target=arm.mutation_target)
    none = RunCondition(Memory.NONE)
    applied = runner(tmp_path, mutation_ctx.corpus).run(
        [plain], [supersede], [none], {"M10": instantiate(mutation_ctx, "M10")}
    )
    last = applied.turns[-1]
    assert last.mutation is not None and last.mutation.outcome is Outcome.APPLIED and rebuilds.builds == 2
    absent = runner(tmp_path / "m", mutation_ctx.corpus).run([plain], [supersede], [none], {})
    assert absent.turns[-1].mutation is not None and absent.turns[-1].mutation.outcome is Outcome.NOT_RUN
    assert "MUTATION_NOT_RUN" in absent.turns[-1].flags


def test_a_before_after_case_the_arm_cannot_take_is_not_asked_even_once(
    tmp_path: Path, mutation_ctx: MutationContext
) -> None:
    arm, _, log = retriever_arm(mutation_ctx, Rebuilds())
    instance = instantiate(mutation_ctx, "M09")  # asked before and after the change
    unsupported = replace(instance, patch=instantiate(mutation_ctx, "M08").patch)  # which a rebuild arm cannot make
    question = mutation_ctx.question(unsupported.base_question_id)
    result = runner(tmp_path, mutation_ctx.corpus).run([arm], [], [], cases=[(unsupported, question)])
    assert result.mutations[0].asks == () and log.queries == []


def test_an_arm_with_a_fixed_clock_is_moved_to_it_and_flagged(tmp_path: Path, episodes: tuple[Episode, ...]) -> None:
    chosen = pick(episodes, EpisodeKind.STALE_LIVE)
    arm, _, _, _ = memory_arm()
    fixed = replace(arm, fixed_clock="2026-10-18T03:00:00Z")
    result = runner(tmp_path).run([fixed], chosen, [COLD])
    assert all(r.status is RunStatus.OK for r in result.turns)
    assert sum("CLOCK_FIXED_BY_ARM" in r.flags for r in result.turns) == len(chosen[0].turns) - 1
    free = runner(tmp_path / "free").run([arm], chosen, [COLD])
    assert not any("CLOCK_FIXED_BY_ARM" in r.flags for r in free.turns)


def test_an_arm_without_a_mutation_interface_is_listed_not_skipped_silently(
    tmp_path: Path, mutation_ctx: MutationContext
) -> None:
    arm, _, _, _ = memory_arm("E0", memories=frozenset({Memory.NONE}))
    instance = instantiate(mutation_ctx, "M01")
    question = mutation_ctx.question(instance.base_question_id)
    result = runner(tmp_path, mutation_ctx.corpus).run([arm], [], [], cases=[(instance, question)])
    assert result.mutations == []
    assert any(s.condition == "mutation_cases" and s.status is RunStatus.NOT_RUN for s in result.skipped)


def test_every_question_id_the_runner_sends_is_planned_in_advance(
    tmp_path: Path, episodes: tuple[Episode, ...], mutation_ctx: MutationContext
) -> None:
    chosen = pick(episodes, EpisodeKind.ADD_FACT)
    cases = []
    for name in ("M01", "M09"):
        instance = instantiate(mutation_ctx, name)
        cases.append((instance, mutation_ctx.question(instance.base_question_id)))
    planned = set(planned_question_ids(chosen, cases, "snap-1"))
    arm, _, _, _ = memory_arm("R2", memories=frozenset({Memory.NONE}))
    rebuilds = Rebuilds()
    full = replace(arm, mutation_target=lambda: RebuildTarget("R2", mutation_ctx.corpus, rebuilds))
    seen: list[str] = []
    original = full.open_system

    def spy(episode: Episode | None, heat: Heat) -> Any:
        system = original(episode, heat)
        answer = system.answer

        def record(case: CaseRequest) -> CaseResponse:
            seen.append(case.question_id)
            return answer(case)

        system.answer = record  # type: ignore[method-assign]
        return system

    runner(tmp_path, mutation_ctx.corpus).run(
        [replace(full, open_system=spy)], chosen, [RunCondition(Memory.NONE)], cases=cases
    )
    assert seen and set(seen) == planned and len(seen) == len(planned)


def test_a_chat_claim_is_said_in_the_conversation_before_the_question(
    tmp_path: Path, mutation_ctx: MutationContext
) -> None:
    arm, _, log, _ = memory_arm("R2", memories=frozenset({Memory.NONE}))
    full = replace(arm, mutation_target=lambda: RebuildTarget("R2", mutation_ctx.corpus, Rebuilds()))
    instance = instantiate(mutation_ctx, "M13")
    question = mutation_ctx.question(instance.base_question_id)
    claim = instance.patch[0].value

    class Conversational(RebuildTarget):
        def unsupported(self, op: Op) -> str | None:
            return None  # this stand-in takes a chat claim, as Palladion does

    chat = replace(full, mutation_target=lambda: Conversational("R2", mutation_ctx.corpus, Rebuilds()))
    result = runner(tmp_path, mutation_ctx.corpus).run([chat], [], [], cases=[(instance, question)])
    assert log.queries == [claim, question.query], "the claim first, then the question, in one conversation"
    assert len(result.mutations[0].asks) == 1
    planned = planned_question_ids([], [(instance, question)], "snap-1")
    assert len(planned) == 2 and len(set(planned)) == 2


def test_a_case_leaves_the_arm_in_its_base_state_and_says_what_it_could_not_undo(
    tmp_path: Path, mutation_ctx: MutationContext
) -> None:
    rebuilds = Rebuilds()
    arm, _, _ = retriever_arm(mutation_ctx, rebuilds)
    instance = instantiate(mutation_ctx, "M01")
    question = mutation_ctx.question(instance.base_question_id)
    result = runner(tmp_path, mutation_ctx.corpus).run([arm], [], [], cases=[(instance, question)])
    assert rebuilds.builds == 2, "built with the patch, then built again from the base corpus"
    assert result.mutations[0].flags == ("APPLICATION=applied",)

    class Residue(RebuildTarget):
        def restore(self) -> tuple[str, ...]:
            return ("a document stays revoked",)

    stubborn = replace(arm, mutation_target=lambda: Residue("R2", mutation_ctx.corpus, Rebuilds()))
    leftover = runner(tmp_path / "two", mutation_ctx.corpus).run([stubborn], [], [], cases=[(instance, question)])
    assert "NOT_RESTORED=a document stays revoked" in leftover.mutations[0].flags


def test_an_episode_mutation_is_undone_when_the_episode_ends_and_the_residue_is_listed(
    tmp_path: Path, episodes: tuple[Episode, ...], mutation_ctx: MutationContext
) -> None:
    (supersede,) = pick(episodes, EpisodeKind.SUPERSEDE)
    arm, _, _ = retriever_arm(mutation_ctx, Rebuilds())

    class Residue(RebuildTarget):
        def restore(self) -> tuple[str, ...]:
            return ("a document stays revoked",)

    stubborn = TrackCArm(
        "R2", arm.open_system, arm.usage, frozenset({Memory.NONE}),
        mutation_target=lambda: Residue("R2", mutation_ctx.corpus, Rebuilds()),
    )  # fmt: skip
    result = runner(tmp_path, mutation_ctx.corpus).run(
        [stubborn], [supersede], [RunCondition(Memory.NONE)], {"M10": instantiate(mutation_ctx, "M10")}
    )
    assert result.residues == [f"R2/{supersede.episode_id}: a document stays revoked"]


def test_the_entry_point_refuses_two_palladion_arms_and_a_live_run_without_limits(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = ["--root", str(tmp_path), "--out", str(tmp_path / "out"), "--run-id", "c-x"]
    assert run_track_c.main([*base, "--arms", "E3,E4"]) == 2
    assert "share one Palladion state" in capsys.readouterr().err
    live = [*base, "--generator", "live", "--enable-live", "--call-cap", "10", "--token-cap", "1000"]
    assert run_track_c.main(live) == 2, "a live run names its pace too"
    assert "needs --enable-live and the owner's" in capsys.readouterr().err
    assert run_track_c.main([*base, "--generator", "live", "--enable-live"]) == 2
    assert run_track_c.main([*base, "--enable-live"]) == 2
    assert "applies only with --generator live" in capsys.readouterr().err


def test_live_freshness_is_not_observable_for_an_arm_that_cannot_follow_the_clock(
    tmp_path: Path, episodes: tuple[Episode, ...]
) -> None:
    chosen = pick(episodes, EpisodeKind.STALE_LIVE)
    arm, _, _, _ = memory_arm()
    fixed = replace(arm, fixed_clock="2026-10-18T03:00:00Z")
    result = runner(tmp_path).run([fixed], chosen, [COLD])
    score = score_conditions(result, chosen, {"E4": fixed})[("E4", COLD.label)]
    assert isinstance(score.live_freshness, NotObservable) and "fixed evaluation time" in score.live_freshness.reason
    free = score_conditions(result, chosen, {"E4": arm})[("E4", COLD.label)]
    assert isinstance(free.live_freshness, Rate)


def test_what_a_system_reported_about_each_answer_is_kept_in_the_run_directory(
    tmp_path: Path, episodes: tuple[Episode, ...]
) -> None:
    chosen = pick(episodes, EpisodeKind.ADD_FACT)
    arm, book, log, store = memory_arm()

    class Tracing(Remembering):
        def report_trace(self) -> list[dict[str, Any]]:
            return [{"evaluator": {"tool_calls": []}, "turn": len(self.log.queries)}]

    traced = replace(arm, open_system=lambda e, h: Tracing(store, "x", book, log))
    run = runner(tmp_path)
    result = run.run([traced], chosen, [COLD])
    rows = [json.loads(line) for line in (tmp_path / "turns.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == len(result.turns) == len(chosen[0].turns)
    assert rows[0]["response"]["answer_text"] and rows[0]["trace"] == [{"evaluator": {"tool_calls": []}, "turn": 1}]
    assert rows[0]["reported"]["prompt_tokens"] == 100


def test_a_mutation_the_harness_could_not_apply_is_an_invalid_run_of_the_harness_not_an_unrun_case(
    tmp_path: Path, mutation_ctx: MutationContext
) -> None:
    class Broken(RebuildTarget):
        def apply(self, ops: Sequence[Op]) -> None:
            raise MutationError("the rebuild failed")

    arm, _, _ = retriever_arm(mutation_ctx, Rebuilds())
    broken = replace(arm, mutation_target=lambda: Broken("R2", mutation_ctx.corpus, Rebuilds()))
    instance = instantiate(mutation_ctx, "M01")
    run = runner(tmp_path, mutation_ctx.corpus)
    result = run.run([broken], [], [], cases=[(instance, mutation_ctx.question(instance.base_question_id))])
    (record,) = result.mutations
    assert record.status is RunStatus.INVALID_RUN and record.application.outcome is Outcome.FAILED
    assert run.ledger.records[-1].origin is ErrorOrigin.HARNESS


def test_the_saved_book_is_checked_against_the_proxys_totals(tmp_path: Path) -> None:
    rows = [
        {"outcome": "OK"},
        {"outcome": "RATE_LIMITED"},
        {"outcome": "ERROR"},
        {"outcome": "REFUSED"},
        {"outcome": "EMBEDDING"},
    ]
    book = tmp_path / "proxy-E3.jsonl"
    book.write_text("".join(json.dumps(r) + chr(10) for r in rows), encoding="utf-8")
    assert run_track_c.book_calls(book) == 3
    arm, _, _, _ = memory_arm("E3")
    honest = replace(arm, usage=lambda: {"calls": 3})
    short = replace(arm, usage=lambda: {"calls": 4})  # one call reserved and never recorded
    assert run_track_c.check_books(tmp_path, {"E3": honest}) == []
    assert run_track_c.check_books(tmp_path, {"E3": short}) == ["E3: the totals say 4 calls, the saved rows 3"]


def test_tool_argument_validity_reads_the_traces_of_a_run(tmp_path: Path, episodes: tuple[Episode, ...]) -> None:
    good = {"role": "main", "name": "search_knowledge", "arguments": '{"query": "q"}', "status": "SUCCEEDED"}
    bad = {"role": "main", "name": "search_knowledge", "arguments": "{}", "status": "SUCCEEDED"}
    chosen = pick(episodes, EpisodeKind.ADD_FACT)
    arm, book, log, store = memory_arm()

    class Tracing(Remembering):
        def report_trace(self) -> list[dict[str, Any]]:
            return [{"evaluator": {"tool_calls": [good, bad]}}]

    traced = replace(arm, open_system=lambda e, h: Tracing(store, "x", book, log))
    result = runner(tmp_path).run([traced], chosen, [COLD])
    assert run_track_c.tool_argument_validity(result) == Rate(len(chosen[0].turns), 2 * len(chosen[0].turns))
    bare = runner(tmp_path / "bare").run([arm], chosen, [COLD])
    assert isinstance(run_track_c.tool_argument_validity(bare), NotObservable)


# ----------------------------------------------------------- a limit that stopped a call is not the system's failure


class Stopped(Book):
    """A book whose proxy refuses every call for a limit: the system answers, but a call was stopped on the way."""

    def spend(self) -> None:
        super().spend()
        self.totals["quota_refused"] = self.totals.get("quota_refused", 0) + 1


def test_a_turn_a_limit_stopped_is_not_run_and_not_the_systems_failure(tmp_path: Path, s_world: World) -> None:
    episode = build_episodes(s_world, 7, 28)[0]
    stopped_arm, _, _, _ = memory_arm(book=Stopped())
    result = runner(tmp_path / "stopped").run([stopped_arm], [episode], [COLD], {})
    turns = [t for t in result.turns if t.episode_id == episode.episode_id]
    assert turns and {(t.status, t.code) for t in turns} == {(RunStatus.NOT_RUN, "QUOTA_BLOCKED")}
    assert all("ORIGIN=HARNESS" in t.flags for t in turns)
    healthy_arm, _, _, _ = memory_arm()
    healthy = runner(tmp_path / "healthy").run([healthy_arm], [episode], [COLD], {})
    assert {t.status for t in healthy.turns} == {RunStatus.OK}


def test_a_mutation_case_a_limit_stopped_is_not_run_with_the_same_code(
    tmp_path: Path, mutation_ctx: MutationContext
) -> None:
    stopped = Stopped()
    base, _, _, _ = memory_arm("R2", book=stopped, memories=frozenset({Memory.NONE}))
    arm = TrackCArm(
        "R2", base.open_system, stopped.usage, base.memories,
        mutation_target=lambda: RebuildTarget("R2", mutation_ctx.corpus, Rebuilds()),
    )  # fmt: skip
    instance = instantiate(mutation_ctx, "M01")
    question = mutation_ctx.question(instance.base_question_id)
    result = runner(tmp_path, mutation_ctx.corpus).run([arm], [], [], cases=[(instance, question)])
    (record,) = result.mutations
    assert (record.status, record.code) == (RunStatus.NOT_RUN, "QUOTA_BLOCKED")


# ------------------------------------------------------------------ frozen lists and the daily cap (B08-T08.04)


def _options(tmp_path: Path, **over: Any) -> Any:
    import argparse

    base = {
        "matched_list": None, "daily_token_cap": None, "ledger_root": tmp_path / "books", "out": tmp_path / "out",
        "token_cap": 150_000,
    }  # fmt: skip
    return argparse.Namespace(**{**base, **over})


def _frozen(tmp_path: Path, episodes: tuple[str, ...], cases: tuple[str, ...]) -> Path:
    from benchmark.matched import MatchedLists, freeze

    path = tmp_path / "matched-c.json"
    freeze(path, MatchedLists(7, {"track_c_episodes": episodes, "track_c_cases": cases}, {}))
    return path


def test_a_run_must_ask_exactly_the_frozen_episodes_and_cases(tmp_path: Path, mutation_ctx: MutationContext) -> None:
    from benchmark.matched import MatchedListError

    episodes = build_episodes(mutation_ctx.world, 7, 28)[:1]
    instance = instantiate(mutation_ctx, "M01")
    cases = [(instance, mutation_ctx.question(instance.base_question_id))]
    frozen = _frozen(tmp_path, tuple(e.episode_id for e in episodes), ("M01",))
    options = _options(tmp_path, matched_list=frozen)
    run_track_c.apply_frozen_lists_and_caps(options, episodes, cases, ["E4"], live=False)
    assert len(options.matched_sha256) == 64
    with pytest.raises(MatchedListError, match="track_c_cases"):
        run_track_c.apply_frozen_lists_and_caps(options, episodes, [], ["E4"], live=False)
    with pytest.raises(MatchedListError, match="track_c_episodes"):
        run_track_c.apply_frozen_lists_and_caps(options, [], cases, ["E4"], live=False)
    plain = _options(tmp_path)
    run_track_c.apply_frozen_lists_and_caps(plain, episodes, cases, ["E4"], live=False)
    assert plain.matched_sha256 is None


def test_each_arm_gets_its_share_of_what_the_books_leave_the_model_today(tmp_path: Path) -> None:
    from datetime import UTC, datetime

    books = tmp_path / "books" / "earlier"
    books.mkdir(parents=True)
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    row = {"at": now, "model": run_track_c.PRIMARY_MODEL, "prompt_tokens": 80_000, "completion_tokens": 10_000}
    (books / "proxy-E3.jsonl").write_text(json.dumps(row) + chr(10), encoding="utf-8")
    options = _options(tmp_path, daily_token_cap=190_000)
    run_track_c.apply_frozen_lists_and_caps(options, [], [], ["E3", "E4"], live=True)
    assert options.token_cap == 50_000, "100,000 left today, shared by two arms"
    run_track_c.apply_frozen_lists_and_caps(
        options := _options(tmp_path, daily_token_cap=190_000), [], [], ["E3"], True
    )
    assert options.token_cap == 100_000
    scripted = _options(tmp_path, daily_token_cap=190_000)
    run_track_c.apply_frozen_lists_and_caps(scripted, [], [], ["E3"], live=False)
    assert scripted.token_cap == 150_000, "a scripted run spends nothing, so no cap applies"
    spent = _options(tmp_path, daily_token_cap=90_000)
    with pytest.raises(run_track_c.TrackCRunError, match=r"no .* tokens for today"):
        run_track_c.apply_frozen_lists_and_caps(spent, [], [], ["E3"], live=True)


def test_a_run_can_be_limited_to_named_memory_baselines() -> None:
    arm, _, _, _ = memory_arm("E0", memories=frozenset({Memory.NONE, Memory.LAST_N, Memory.SCOPED_EPISODIC}))
    everything = run_track_c.conditions_for([arm], [Heat.COLD])
    assert {c.memory for c in everything} == {Memory.NONE, Memory.LAST_N, Memory.SCOPED_EPISODIC}
    chosen = run_track_c.conditions_for([arm], [Heat.COLD], [Memory.SCOPED_EPISODIC])
    assert [c.memory for c in chosen] == [Memory.SCOPED_EPISODIC]
    assert run_track_c.conditions_for([arm], [Heat.COLD], [Memory.NATIVE]) == [], (
        "a baseline the arm lacks is not invented"
    )


def test_the_request_ceiling_option_reaches_the_proxy_limits() -> None:
    options = argparse.Namespace(
        call_cap=250, token_cap=190_000, max_completion_tokens=700, pace_seconds=30.0, max_request_tokens=6800
    )
    limits = run_track_c.proxy_limits(options, 1, 2)
    assert limits.max_request_tokens == 6800 and limits.max_tool_calls == 1 * 48 + 2 * 16
    options.max_request_tokens = None
    assert run_track_c.proxy_limits(options, 1, 2).max_request_tokens is None


def test_the_entry_point_accepts_the_request_ceiling_option(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    base = ["--root", str(tmp_path), "--out", str(tmp_path / "out"), "--run-id", "c-x", "--arms", "E3,E4"]
    assert run_track_c.main([*base, "--max-request-tokens", "6800"]) == 2  # refused for the two arms, after parsing it
    assert "share one Palladion state" in capsys.readouterr().err
