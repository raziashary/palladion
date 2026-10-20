"""Runner: pairing, randomization, intention-to-treat records, retries, deadlines, no selective rerun."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from benchmark.config import RetryPolicy
from benchmark.contracts import (
    AbstentionReason,
    ArmUnavailable,
    CacheCondition,
    CapabilityUnsupported,
    CaseRequest,
    CaseResponse,
    ContractError,
    ErrorOrigin,
    EvidenceCandidate,
    EvidenceStatus,
    ModelInvocations,
    RetrievalRequest,
    RunStatus,
    Track,
    TransientInfrastructureError,
)
from benchmark.registry import Capability, default_registry
from benchmark.run_manifest import RunManifest, TreeState
from benchmark.runner import (
    ArmBinding,
    DuplicatePairError,
    LedgerRecord,
    PlanAlreadyRunError,
    PlanRegistry,
    RunLedger,
    Runner,
    RunnerCase,
    RunnerError,
    RunnerSettings,
    derived_rng,
)

RUN_ID = "run-0001"
SECRET = "gsk_" + "q" * 30


def qid(i: int) -> str:
    return f"q-{i:08x}"


def request(i: int, limit: int = 3) -> RetrievalRequest:
    return RetrievalRequest(
        question_id=qid(i),
        query=f"question {i}",
        principal_id="p1",
        corpus_snapshot_id="snap1",
        evaluation_time="2026-10-18T03:00:00Z",
        event_time=None,
        filters={},
        limit=limit,
        max_evidence_tokens=4000,
    )


def candidates(n: int = 2) -> list[EvidenceCandidate]:
    return [EvidenceCandidate(f"S{i}@v1", f"{i}", "text", i, 0.5, "dense", (), True, {}) for i in range(1, n + 1)]


# ----------------------------------------------------------------------------- fake arms


@dataclass
class Good:
    n: int = 2
    calls: int = 0
    seen: list[Any] = field(default_factory=list)

    def build_index(self, source_manifest_uri: str, index_namespace: str) -> None: ...

    def retrieve(self, request: RetrievalRequest) -> list[EvidenceCandidate]:
        self.calls += 1
        self.seen.append(request)
        return candidates(self.n)

    def index_stats(self) -> dict[str, Any]:
        return {}


@dataclass
class Scripted(Good):
    """Raises the scripted exceptions in order, then behaves like Good."""

    script: list[BaseException | None] = field(default_factory=list)

    def retrieve(self, request: RetrievalRequest) -> list[EvidenceCandidate]:
        self.calls += 1
        step = self.script.pop(0) if self.script else None
        if step is not None:
            raise step
        return candidates(self.n)


@dataclass
class Slow(Good):
    release: threading.Event = field(default_factory=threading.Event)
    finished: threading.Event = field(default_factory=threading.Event)

    def retrieve(self, request: RetrievalRequest) -> list[EvidenceCandidate]:
        self.calls += 1
        self.release.wait(5)
        self.finished.set()
        return candidates(self.n)


@dataclass
class BadRanks(Good):
    def retrieve(self, request: RetrievalRequest) -> list[EvidenceCandidate]:
        self.calls += 1
        return list(reversed(candidates(2)))


@dataclass
class TooMany(Good):
    def retrieve(self, request: RetrievalRequest) -> list[EvidenceCandidate]:
        self.calls += 1
        return candidates(5)


@dataclass
class System:
    log: list[str] = field(default_factory=list)
    wrong_question: bool = False

    def answer(self, case: CaseRequest) -> CaseResponse:
        self.log.append(f"answer:{case.question_id}")
        return CaseResponse(
            question_id=qid(999) if self.wrong_question else case.question_id,
            run_id=RUN_ID,
            answer_text="x",
            evidence_status=EvidenceStatus.NOT_ESTABLISHED,
            claims=(),
            used_evidence_ids=(),
            tool_calls=(),
            critic=None,
            model_invocations=None,
            latency_ms=None,
            cost_usd=None,
            abstention_reason=AbstentionReason.NO_KNOWN_SUPPORT,
        )

    def reset_case(self, case_id: str) -> None:
        self.log.append(f"reset:{case_id}")

    def report_usage(self) -> Any:
        return None

    def report_trace(self) -> list[dict[str, Any]]:
        return []


# ----------------------------------------------------------------------------- harness


RETRY = RetryPolicy(max_attempts=2, base_backoff_seconds=1.0)


def settings(**overrides: Any) -> RunnerSettings:
    values: dict[str, Any] = {
        "order_seed": 11,
        "case_deadline_seconds": 2.0,
        "run_deadline_seconds": None,
        "retry": RETRY,
    }
    values.update(overrides)
    return RunnerSettings(**values)


def write_manifest(
    path: Path,
    arm: str,
    cfg: RunnerSettings,
    run_id: str = RUN_ID,
    track: Track = Track.RETRIEVAL_ONLY,
    split: str = "pilot",
) -> None:
    reasons = {
        k: "not applicable in this test"
        for k in (
            "system_under_test",
            "container_image_digest",
            "method_version",
            "prompt_digest",
            "pricing_snapshot",
            "generator_assignment_sha256",
        )
    }
    RunManifest(
        run_id=run_id,
        track=track,
        arm=arm,
        split=split,
        source_manifest_sha256="a" * 64,
        question_manifest_sha256="b" * 64,
        gold_manifest_sha256="c" * 64,
        benchmark=TreeState("benchmark", "1" * 40, "d" * 64, ()),
        system_under_test=None,
        container_image_digest=None,
        method_version=None,
        model_versions={},
        retrieval_config={},
        prompt_digest=None,
        hardware={},
        pricing_snapshot=None,
        seed=1,
        order_seed=cfg.order_seed,
        cache_condition=CacheCondition.COLD,
        started_at_utc="2026-10-18T03:00:00Z",
        retry_policy=cfg.retry_policy_dict(),
        generator_assignment_sha256=None,
        confirmatory=False,
        null_reasons=reasons,
    ).write(path)


@dataclass
class World:
    runner: Runner
    ledger: RunLedger
    tmp: Path
    arms: dict[str, Any]
    sleeps: list[float]
    cfg: RunnerSettings

    def run(self, n: int = 4, split: str = "pilot", limit: int = 3) -> Any:
        return self.runner.run([RunnerCase(request(i, limit)) for i in range(1, n + 1)], split=split)


def build(
    tmp_path: Path,
    arms: dict[str, Any],
    *,
    run_id: str = RUN_ID,
    cfg: RunnerSettings | None = None,
    monotonic: Callable[[], float] | None = None,
    write: bool = True,
    plans: Path | None = None,
) -> World:
    cfg = cfg or settings()
    sleeps: list[float] = []
    bindings = []
    for arm_id, adapter in arms.items():
        path = tmp_path / f"manifest-{arm_id}.json"
        if write and not path.exists():
            write_manifest(path, arm_id, cfg, run_id)
        bindings.append(ArmBinding(arm_id, adapter, path))
    ledger = RunLedger(tmp_path / "ledger.jsonl")
    kwargs: dict[str, Any] = {"sleep": sleeps.append}
    if monotonic:
        kwargs["monotonic"] = monotonic
    runner = Runner(
        run_id, cfg, bindings, ledger, PlanRegistry(plans or tmp_path / "plans.jsonl"), default_registry(), **kwargs
    )
    return World(runner, ledger, tmp_path, arms, sleeps, cfg)


def finals(world: World) -> dict[tuple[str, str], LedgerRecord]:
    return {(r.arm, r.question_id): r for r in world.ledger.records if r.is_final}


# ----------------------------------------------------------------------------- pairing and ordering


def test_every_arm_runs_every_case_and_each_pair_has_one_final_record(tmp_path: Path) -> None:
    world = build(tmp_path, {"R0": Good(), "R1": Good()})
    summary = world.run(5)
    assert summary.planned_pairs == 10 and summary.executed_pairs == 10 and summary.skipped_pairs == 0
    assert summary.status_counts == {"OK": 10}
    final = finals(world)
    assert len(final) == 10 and all(r.status is RunStatus.OK for r in final.values())
    assert {r.manifest_sha256 for r in final.values() if r.arm == "R0"} != {
        r.manifest_sha256 for r in final.values() if r.arm == "R1"
    }
    assert all(len(r.manifest_sha256) == 64 for r in final.values())


def test_arm_order_is_seeded_stable_and_varies_by_case_and_seed(tmp_path: Path) -> None:
    arms = {f"R{i}": Good() for i in range(4)}
    world = build(tmp_path, arms)
    orders = [world.runner.arm_order(qid(i)) for i in range(1, 30)]
    assert orders == [world.runner.arm_order(qid(i)) for i in range(1, 30)]
    assert len({tuple(o) for o in orders}) > 1  # not one fixed order
    assert len({o[0] for o in orders}) > 1  # no arm always goes first
    assert all(sorted(o) == sorted(arms) for o in orders)
    (tmp_path / "other").mkdir()
    other = build(tmp_path / "other", arms, cfg=settings(order_seed=12))
    assert [other.runner.arm_order(qid(i)) for i in range(1, 30)] != orders
    ids = [qid(i) for i in range(1, 20)]
    assert sorted(world.runner.case_order(ids)) == sorted(ids) and world.runner.case_order(ids) != sorted(ids)


def test_derived_rng_is_independent_of_python_hash_randomisation() -> None:
    assert derived_rng(1, "x").random() == derived_rng(1, "x").random()
    assert derived_rng(1, "x").random() != derived_rng(2, "x").random()


def test_arms_receive_only_the_request_object(tmp_path: Path) -> None:
    spy = Good()
    world = build(tmp_path, {"R0": spy})
    world.run(2)
    assert spy.seen and all(type(s) is RetrievalRequest for s in spy.seen)
    allowed = {
        "question_id",
        "query",
        "principal_id",
        "corpus_snapshot_id",
        "evaluation_time",
        "event_time",
        "filters",
        "limit",
        "max_evidence_tokens",
    }
    assert all(set(s.to_dict()) == allowed for s in spy.seen)


# ----------------------------------------------------------------------------- failures are results


def test_a_crashing_arm_is_recorded_invalid_run_and_other_arms_continue(tmp_path: Path) -> None:
    crash = Scripted(script=[ZeroDivisionError(SECRET)] * 4)
    world = build(tmp_path, {"R0": Good(), "R1": crash})
    summary = world.run(4)
    assert summary.status_counts == {"OK": 4, "INVALID_RUN": 4}
    bad = [r for r in finals(world).values() if r.arm == "R1"]
    assert len(bad) == 4
    assert all(
        (r.status, r.origin, r.code) == (RunStatus.INVALID_RUN, ErrorOrigin.ARM, "UNHANDLED_ZeroDivisionError")
        for r in bad
    )
    assert SECRET not in world.ledger.path.read_text(encoding="utf-8")  # error text never reaches the ledger
    assert crash.calls == 4  # a non-transient error is not retried


def test_unavailable_and_unsupported_arms_are_not_run_and_feature_not_supported(tmp_path: Path) -> None:
    world = build(
        tmp_path,
        {"R0": Scripted(script=[ArmUnavailable("down")] * 2), "R1": Scripted(script=[CapabilityUnsupported("x")] * 2)},
    )
    summary = world.run(2)
    assert summary.status_counts == {"NOT_RUN": 2, "FEATURE_NOT_SUPPORTED": 2}


def test_bad_arm_output_is_a_contract_violation_not_a_crash(tmp_path: Path) -> None:
    world = build(tmp_path, {"R0": BadRanks(), "R1": TooMany()})
    world.run(2)
    assert {r.code for r in finals(world).values()} == {"CONTRACT_VIOLATION"}
    assert {r.status for r in finals(world).values()} == {RunStatus.INVALID_RUN}


# ----------------------------------------------------------------------------- retries keep both outcomes


def test_a_transient_fault_once_yields_two_readable_attempts_and_one_final_outcome(tmp_path: Path) -> None:
    arm = Scripted(script=[TransientInfrastructureError("503")])
    world = build(tmp_path, {"R0": arm})
    world.run(1)
    records = [r for r in world.ledger.records if r.arm == "R0"]
    assert [(r.attempt, r.is_final, r.status) for r in records] == [
        (1, False, RunStatus.INVALID_RUN),
        (2, True, RunStatus.OK),
    ]
    assert records[0].code == "TRANSIENT_FAULT" and records[0].origin is ErrorOrigin.PROVIDER
    final = records[1]
    assert (final.initial_status, final.attempts) == (RunStatus.INVALID_RUN, 2)
    assert final.payload and world.sleeps == [1.0]


def test_exhausted_retries_end_invalid_run_with_every_attempt_kept(tmp_path: Path) -> None:
    arm = Scripted(script=[TransientInfrastructureError("a"), TransientInfrastructureError("b")])
    world = build(tmp_path, {"R0": arm})
    world.run(1)
    records = list(world.ledger.records)
    assert [(r.attempt, r.is_final) for r in records] == [(1, False), (2, True)]
    assert records[1].status is RunStatus.INVALID_RUN and records[1].code == "TRANSIENT_FAULT_RETRIES_EXHAUSTED"
    assert arm.calls == 2


def test_backoff_doubles_between_attempts(tmp_path: Path) -> None:
    cfg = settings(retry=RetryPolicy(3, 0.5))
    arm = Scripted(script=[TransientInfrastructureError("a"), TransientInfrastructureError("b")])
    world = build(tmp_path, {"R0": arm}, cfg=cfg)
    world.run(1)
    assert world.sleeps == [0.5, 1.0] and finals(world)[("R0", qid(1))].status is RunStatus.OK


# ----------------------------------------------------------------------------- deadlines


def test_a_slow_arm_times_out_and_its_late_result_is_discarded_and_counted(tmp_path: Path) -> None:
    slow = Slow()
    world = build(tmp_path, {"R0": slow, "R1": Good()}, cfg=settings(case_deadline_seconds=0.05))
    summary = world.run(3)
    final = finals(world)
    first_slow = [r for r in final.values() if r.arm == "R0" and r.status is RunStatus.TIMEOUT]
    assert len(first_slow) == 1  # exactly one timeout; the arm is then unusable
    others = [r for r in final.values() if r.arm == "R0" and r.status is not RunStatus.TIMEOUT]
    assert len(others) == 2 and {r.code for r in others} == {"ARM_UNUSABLE_AFTER_TIMEOUT"}
    assert {r.status for r in others} == {RunStatus.NOT_RUN}
    assert slow.calls == 1 and summary.unusable_arms == ("R0",)
    before = world.ledger.path.read_bytes()
    slow.release.set()
    assert slow.finished.wait(5)
    for _ in range(100):
        if world.runner.late_results_discarded == 1:
            break
        threading.Event().wait(0.02)
    assert world.runner.late_results_discarded == 1
    assert world.ledger.path.read_bytes() == before  # the late result wrote nothing
    assert sum(1 for r in world.ledger.records if r.arm == "R0" and r.status is RunStatus.TIMEOUT) == 1


def test_timeouts_are_never_retried(tmp_path: Path) -> None:
    slow = Slow()
    world = build(tmp_path, {"R0": slow}, cfg=settings(case_deadline_seconds=0.05, retry=RetryPolicy(3, 0.0)))
    world.run(1)
    assert slow.calls == 1 and [r.attempt for r in world.ledger.records] == [1]
    slow.release.set()


class Ticker:
    """A monotonic clock that advances 10 seconds each time the runner reads it."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        self.now += 10.0
        return self.now


def test_run_level_limit_applies_between_cases_and_censors_whole_cases(tmp_path: Path) -> None:
    arms = {"R0": Good(), "R1": Good()}
    world = build(tmp_path, arms, cfg=settings(run_deadline_seconds=25.0), monotonic=Ticker())
    summary = world.run(5)
    final = finals(world)
    assert len(final) == 10  # nothing dropped
    assert summary.censored_questions
    for question in summary.censored_questions:
        assert {final[(a, question)].status for a in arms} == {RunStatus.NOT_RUN}  # all arms or none
        assert {final[(a, question)].code for a in arms} == {"RUN_DEADLINE"}
    measured = {q for (_, q), r in final.items() if r.status is RunStatus.OK}
    assert measured and measured.isdisjoint(summary.censored_questions)
    for question in measured:
        assert {final[(a, question)].status for a in arms} == {RunStatus.OK}


# ----------------------------------------------------------------------------- no selective rerun


def test_resuming_the_same_run_id_never_redispatches_a_finished_pair(tmp_path: Path) -> None:
    crash = Scripted(script=[ZeroDivisionError("x")] * 10)
    good = Good()
    world = build(tmp_path, {"R0": good, "R1": crash})
    world.run(3)
    snapshot = world.ledger.path.read_bytes()
    calls = (good.calls, crash.calls)
    again = build(tmp_path, {"R0": good, "R1": crash}).run(3)
    assert again.executed_pairs == 0 and again.skipped_pairs == 6
    assert world.ledger.path.read_bytes() == snapshot and (good.calls, crash.calls) == calls  # bad outcomes stay


def test_a_new_run_id_on_the_same_plan_is_refused(tmp_path: Path) -> None:
    arms = {"R0": Good()}
    build(tmp_path, arms).run(3)
    shared = tmp_path / "plans.jsonl"
    (tmp_path / "second").mkdir()
    second = build(tmp_path / "second", arms, run_id="run-0002", plans=shared)
    with pytest.raises(PlanAlreadyRunError):
        second.run(3)
    assert not second.ledger.path.exists()  # refused before any pair ran
    (tmp_path / "third").mkdir()
    different_plan = build(tmp_path / "third", arms, run_id="run-0003", plans=shared)
    assert different_plan.run(4).executed_pairs == 4  # a genuinely different plan is a different experiment


def test_the_ledger_refuses_duplicate_finals_and_attempts(tmp_path: Path) -> None:
    world = build(tmp_path, {"R0": Good()})
    world.run(1)
    record = next(iter(world.ledger.records))
    with pytest.raises(DuplicatePairError):
        world.ledger.append(record)


def test_the_ledger_survives_reopen_and_rejects_a_corrupt_line(tmp_path: Path) -> None:
    world = build(tmp_path, {"R0": Good()})
    world.run(2)
    reopened = RunLedger(world.ledger.path)
    assert reopened.records == world.ledger.records and reopened.has_final("R0", qid(1))
    with world.ledger.path.open("a", encoding="utf-8") as handle:
        handle.write("not json\n")
    with pytest.raises(RunnerError, match="not a valid record"):
        RunLedger(world.ledger.path)


def test_completeness_check_fails_when_a_pair_is_missing(tmp_path: Path) -> None:
    world = build(tmp_path, {"R0": Good()})
    world.run(2)
    with pytest.raises(RunnerError, match="not complete"):
        world.ledger.verify_complete([("R0", qid(1)), ("R0", qid(2)), ("R0", qid(3))])


# ----------------------------------------------------------------------------- preflight


def test_the_manifest_must_exist_before_the_first_arm_runs(tmp_path: Path) -> None:
    arm = Good()
    world = build(tmp_path, {"R0": arm}, write=False)
    with pytest.raises(RunnerError, match="written before the first arm"):
        world.run(2)
    assert arm.calls == 0 and not world.ledger.path.exists()


def test_manifest_must_agree_with_the_runner(tmp_path: Path) -> None:
    arm = Good()
    cfg = settings()
    write_manifest(tmp_path / "manifest-R0.json", "R9", cfg)  # wrong arm
    with pytest.raises(RunnerError, match="different arm or run"):
        build(tmp_path, {"R0": arm}, cfg=cfg).run(1)
    other = tmp_path / "b"
    other.mkdir()
    write_manifest(other / "manifest-R0.json", "R0", settings(order_seed=99))
    with pytest.raises(RunnerError, match="order seed"):
        build(other, {"R0": arm}).run(1)
    third = tmp_path / "c"
    third.mkdir()
    write_manifest(third / "manifest-R0.json", "R0", settings(retry=RetryPolicy(3, 1.0)))
    with pytest.raises(RunnerError, match="retry policy"):
        build(third, {"R0": arm}).run(1)
    assert arm.calls == 0


def test_a_manifest_changed_after_the_ledger_recorded_it_is_refused(tmp_path: Path) -> None:
    world = build(tmp_path, {"R0": Good()})
    world.run(1)
    (tmp_path / "manifest-R0.json").unlink()
    write_manifest(tmp_path / "manifest-R0.json", "R0", world.cfg, track=Track.CONTROLLED_QA)
    with pytest.raises(RunnerError, match="changed since the ledger"):
        build(tmp_path, {"R0": Good()}).run(2)


def test_duplicate_questions_and_empty_arm_lists_are_refused(tmp_path: Path) -> None:
    world = build(tmp_path, {"R0": Good()})
    with pytest.raises(RunnerError, match="duplicate question"):
        world.runner.run([RunnerCase(request(1)), RunnerCase(request(1))], split="pilot")
    with pytest.raises(RunnerError, match="at least one arm"):
        Runner(
            RUN_ID,
            settings(),
            [],
            RunLedger(tmp_path / "l2.jsonl"),
            PlanRegistry(tmp_path / "p2.jsonl"),
            default_registry(),
        )


# ----------------------------------------------------------------------------- system arms


def test_system_arm_is_reset_before_each_case_and_its_response_is_recorded(tmp_path: Path) -> None:
    system = System()
    cfg = settings()
    path = tmp_path / "manifest-E0.json"
    write_manifest(path, "E0", cfg, track=Track.NATIVE_END_TO_END)
    ledger = RunLedger(tmp_path / "ledger.jsonl")
    runner = Runner(
        RUN_ID,
        cfg,
        [ArmBinding("E0", system, path)],
        ledger,
        PlanRegistry(tmp_path / "plans.jsonl"),
        default_registry(),
    )
    cases = [
        RunnerCase(CaseRequest(qid(i), "q", "p1", "snap1", "2026-10-18T03:00:00Z", None, {}, 4000, None, 0))
        for i in (1, 2)
    ]
    runner.run(cases, split="pilot")
    order = runner.case_order([qid(1), qid(2)])
    assert system.log == [f"{op}:{q}" for q in order for op in ("reset", "answer")]
    payloads = [r.payload for r in ledger.records if r.is_final]
    assert all(p["latency_ms"] is None and p["cost_usd"] is None for p in payloads)  # null stays null
    assert json.loads(json.dumps(payloads))


def test_system_arm_answering_the_wrong_question_is_invalid(tmp_path: Path) -> None:
    system = System(wrong_question=True)
    cfg = settings()
    path = tmp_path / "manifest-E0.json"
    write_manifest(path, "E0", cfg, track=Track.NATIVE_END_TO_END)
    ledger = RunLedger(tmp_path / "ledger.jsonl")
    runner = Runner(
        RUN_ID,
        cfg,
        [ArmBinding("E0", system, path)],
        ledger,
        PlanRegistry(tmp_path / "plans.jsonl"),
        default_registry(),
    )
    runner.run(
        [RunnerCase(CaseRequest(qid(1), "q", "p1", "snap1", "2026-10-18T03:00:00Z", None, {}, 4000, None, 0))],
        split="pilot",
    )
    assert [r.code for r in ledger.records] == ["CONTRACT_VIOLATION"]


def test_a_second_final_record_for_a_finished_pair_is_refused_even_with_a_new_attempt_number(tmp_path: Path) -> None:
    world = build(tmp_path, {"R0": Good()})
    world.run(1)
    first = next(iter(world.ledger.records))
    extra = LedgerRecord(**{**first.__dict__, "attempt": 2})
    with pytest.raises(DuplicatePairError, match="final outcome"):
        world.ledger.append(extra)


def test_run_fails_when_the_ledger_holds_a_final_for_a_pair_outside_the_plan(tmp_path: Path) -> None:
    world = build(tmp_path, {"R0": Good()})
    world.run(1)
    stray = LedgerRecord(**{**next(iter(world.ledger.records)).__dict__, "question_id": qid(99)})
    world.ledger.append(stray)
    with pytest.raises(RunnerError, match="not complete"):
        world.run(1)


# ----------------------------------------------------------------------------- audit follow-ups


def test_the_registry_blocks_arms_with_unverified_capabilities_before_any_call(tmp_path: Path) -> None:
    arm = Good()
    world = build(tmp_path, {"R7": arm})
    world.runner.required_capabilities = (Capability.ACL_FILTER,)
    summary = world.run(2)
    assert arm.calls == 0 and summary.status_counts == {"NOT_RUN": 2}
    assert {(r.code, r.origin) for r in finals(world).values()} == {("ARM_UNAVAILABLE", ErrorOrigin.ARM)}
    assert all(r.duration_ms is None for r in finals(world).values())  # no call, so no duration (never 0)


def test_a_forced_registry_status_is_recorded_for_the_critic_arm(tmp_path: Path) -> None:
    system = System()
    cfg = settings()
    path = tmp_path / "manifest-E3.json"
    write_manifest(path, "E3", cfg, track=Track.NATIVE_END_TO_END)
    ledger = RunLedger(tmp_path / "ledger.jsonl")
    runner = Runner(RUN_ID, cfg, [ArmBinding("E3", system, path)], ledger, PlanRegistry(tmp_path / "p.jsonl"),
                    default_registry())  # fmt: skip
    runner.run([RunnerCase(CaseRequest(qid(1), "q", "p1", "snap1", "2026-10-18T03:00:00Z", None, {}, 4000, None, 0))],
               split="pilot")  # fmt: skip
    (record,) = ledger.records
    assert (record.status, record.code) == (RunStatus.FEATURE_NOT_SUPPORTED, "CAPABILITY_UNSUPPORTED")
    assert system.log == []


def test_an_arm_missing_from_the_registry_stops_the_run_before_anything_happens(tmp_path: Path) -> None:
    cfg = settings()
    path = tmp_path / "manifest-X9.json"
    write_manifest(path, "X9", cfg)
    runner = Runner(RUN_ID, cfg, [ArmBinding("X9", Good(), path)], RunLedger(tmp_path / "l.jsonl"),
                    PlanRegistry(tmp_path / "p.jsonl"), default_registry())  # fmt: skip
    with pytest.raises(RunnerError, match="not in the registry"):
        runner.run([RunnerCase(request(1))], split="pilot")
    assert not (tmp_path / "l.jsonl").exists()


def test_a_runner_case_holds_only_a_request_object() -> None:
    class Carrier:
        question_id = qid(1)
        gold_answer = "leak"

    with pytest.raises(RunnerError, match="nothing else"):
        RunnerCase(Carrier())  # type: ignore[arg-type]


def test_a_case_request_cannot_be_sent_to_a_retriever_and_vice_versa(tmp_path: Path) -> None:
    world = build(tmp_path, {"R0": Good()})
    case = RunnerCase(CaseRequest(qid(1), "q", "p1", "snap1", "2026-10-18T03:00:00Z", None, {}, 4000, None, 0))
    world.runner.run([case], split="pilot")
    assert [r.code for r in world.ledger.records] == ["CONTRACT_VIOLATION"]


def test_an_interrupted_retry_resumes_with_the_next_attempt_number(tmp_path: Path) -> None:
    arm = Good()
    world = build(tmp_path, {"R0": arm})
    digest = read_digest(tmp_path / "manifest-R0.json")
    interrupted = LedgerRecord(RUN_ID, digest, "R0", qid(1), 1, False, RunStatus.INVALID_RUN, ErrorOrigin.PROVIDER,
                               "TRANSIENT_FAULT", "2026-10-18T03:00:00Z", 5.0, None, None, None)  # fmt: skip
    world.ledger.append(interrupted)
    world.run(1)
    records = [r for r in world.ledger.records if r.arm == "R0"]
    assert [(r.attempt, r.is_final) for r in records] == [(1, False), (2, True)]
    assert records[1].initial_status is RunStatus.INVALID_RUN and records[1].attempts == 2


def read_digest(path: Path) -> str:
    from benchmark.run_manifest import read_verified

    return read_verified(path).digest()


def test_a_timed_out_arm_stays_unusable_after_a_restart(tmp_path: Path) -> None:
    slow = Slow()
    first = build(tmp_path, {"R0": slow}, cfg=settings(case_deadline_seconds=0.05))
    first.run(1)
    assert slow.calls == 1
    restarted = build(tmp_path, {"R0": slow}, cfg=settings(case_deadline_seconds=0.05))
    summary = restarted.run(3)
    assert slow.calls == 1  # never called again
    assert summary.unusable_arms == ("R0",)
    codes = [r.code for r in restarted.ledger.records if r.is_final]
    assert codes.count("ARM_UNUSABLE_AFTER_TIMEOUT") >= 2
    slow.release.set()


def test_on_the_test_split_no_pair_may_ever_be_run_twice_whatever_the_plan(tmp_path: Path) -> None:
    arms = {"R0": Good()}
    shared = tmp_path / "plans.jsonl"
    write_manifest(tmp_path / "manifest-R0.json", "R0", settings(), split="test")
    build(tmp_path, arms).run(3, split="test")
    (tmp_path / "second").mkdir()
    write_manifest(tmp_path / "second" / "manifest-R0.json", "R0", settings(), run_id="run-0002", split="test")
    second = build(tmp_path / "second", arms, run_id="run-0002", plans=shared)
    second.runner.allow_exploratory_repeat = True  # even a declared repeat cannot reopen the test split
    with pytest.raises(PlanAlreadyRunError, match="already covered"):
        second.run(2, split="test")  # a subset of the earlier questions
    assert not second.ledger.path.exists()


def test_an_exploratory_repeat_of_a_non_test_plan_needs_an_explicit_declaration(tmp_path: Path) -> None:
    arms = {"R0": Good()}
    shared = tmp_path / "plans.jsonl"
    build(tmp_path, arms).run(2)
    (tmp_path / "again").mkdir()
    refused = build(tmp_path / "again", arms, run_id="run-0002", plans=shared)
    with pytest.raises(PlanAlreadyRunError):
        refused.run(2)
    (tmp_path / "declared").mkdir()
    declared = build(tmp_path / "declared", arms, run_id="run-0003", plans=shared)
    declared.runner.allow_exploratory_repeat = True
    assert declared.run(2).executed_pairs == 2


def test_the_manifest_split_must_match_the_run_split(tmp_path: Path) -> None:
    arm = Good()
    world = build(tmp_path, {"R0": arm})  # manifest declares the pilot split
    with pytest.raises(RunnerError, match="declares split pilot, not dev"):
        world.run(2, split="dev")
    assert arm.calls == 0


def test_an_over_budget_self_report_is_flagged_in_the_ledger_and_not_clamped(tmp_path: Path) -> None:
    class Greedy(System):
        def answer(self, case: CaseRequest) -> CaseResponse:
            response = super().answer(case)
            return CaseResponse(**{**response.__dict__, "model_invocations": ModelInvocations(6, 1)})

    cfg = settings()
    path = tmp_path / "manifest-E0.json"
    write_manifest(path, "E0", cfg, track=Track.NATIVE_END_TO_END)
    ledger = RunLedger(tmp_path / "ledger.jsonl")
    runner = Runner(RUN_ID, cfg, [ArmBinding("E0", Greedy(), path)], ledger, PlanRegistry(tmp_path / "p.jsonl"),
                    default_registry())  # fmt: skip
    runner.run([RunnerCase(CaseRequest(qid(1), "q", "p1", "snap1", "2026-10-18T03:00:00Z", None, {}, 4000, None, 0))],
               split="pilot")  # fmt: skip
    (record,) = ledger.records
    assert record.status is RunStatus.OK and record.flags == ("BUDGET_VIOLATION_UNVERIFIED",)
    assert record.payload["model_invocations"] == {"main": 6, "critic": 1}  # as reported, not clamped
    assert record.payload["budget_check"]["verified"] is False
    assert record.payload["budget_check"]["violations"][0]["observed"] == 6


def test_a_no_call_final_after_an_interrupted_attempt_resumes_with_the_next_attempt_number(tmp_path: Path) -> None:
    arm = Good()
    world = build(tmp_path, {"R4": arm})
    world.runner.required_capabilities = (Capability.ACL_FILTER,)  # the registry will block this arm
    digest = read_digest(tmp_path / "manifest-R4.json")
    world.ledger.append(
        LedgerRecord(
            RUN_ID,
            digest,
            "R4",
            qid(1),
            1,
            False,
            RunStatus.INVALID_RUN,
            ErrorOrigin.PROVIDER,
            "TRANSIENT_FAULT",
            "2026-10-18T03:00:00Z",
            5.0,
            None,
            None,
            None,
        )
    )
    world.run(1)
    records = [r for r in world.ledger.records if r.arm == "R4"]
    assert [(r.attempt, r.is_final) for r in records] == [(1, False), (2, True)]
    assert records[1].initial_status is RunStatus.INVALID_RUN and arm.calls == 0


def test_adding_a_new_arm_for_questions_another_arm_covered_is_not_a_repeat_on_the_test_split(tmp_path: Path) -> None:
    shared = tmp_path / "plans.jsonl"
    write_manifest(tmp_path / "manifest-R0.json", "R0", settings(), split="test")
    build(tmp_path, {"R0": Good()}).run(2, split="test")
    (tmp_path / "second").mkdir()
    write_manifest(tmp_path / "second" / "manifest-R1.json", "R1", settings(), run_id="run-0002", split="test")
    second = build(tmp_path / "second", {"R1": Good()}, run_id="run-0002", plans=shared)
    assert second.run(2, split="test").executed_pairs == 2  # no (arm, question) pair repeats


def test_flagged_records_are_counted_in_the_summary(tmp_path: Path) -> None:
    class Greedy(System):
        def answer(self, case: CaseRequest) -> CaseResponse:
            response = super().answer(case)
            return CaseResponse(**{**response.__dict__, "model_invocations": ModelInvocations(7, 0)})

    cfg = settings()
    path = tmp_path / "manifest-E0.json"
    write_manifest(path, "E0", cfg, track=Track.NATIVE_END_TO_END)
    runner = Runner(RUN_ID, cfg, [ArmBinding("E0", Greedy(), path)], RunLedger(tmp_path / "l.jsonl"),
                    PlanRegistry(tmp_path / "p.jsonl"), default_registry())  # fmt: skip
    case = RunnerCase(CaseRequest(qid(1), "q", "p1", "snap1", "2026-10-18T03:00:00Z", None, {}, 4000, None, 0))
    summary = runner.run([case], split="pilot")
    assert summary.status_counts == {"OK": 1} and summary.flag_counts == {"BUDGET_VIOLATION_UNVERIFIED": 1}


@dataclass
class Flagged(Good):
    """A retriever that reports notes about its latest call, as the Track A arms do."""

    notes: Any = ("BUDGET_TRUNCATED", "FILTERED_AFTER_RANKING=3")

    def call_flags(self) -> Any:
        return self.notes


def test_an_arms_notes_about_a_call_are_kept_as_ledger_flags(tmp_path: Path) -> None:
    world = build(tmp_path, {"R0": Flagged()})
    summary = world.run(2)
    assert summary.status_counts == {"OK": 2}
    assert {r.flags for r in finals(world).values()} == {("BUDGET_TRUNCATED", "FILTERED_AFTER_RANKING=3")}
    assert summary.flag_counts == {"BUDGET_TRUNCATED": 2, "FILTERED_AFTER_RANKING=3": 2}


def test_malformed_notes_make_the_pair_invalid_instead_of_being_stored(tmp_path: Path) -> None:
    for bad in (["a list"], ("",), ("x" * 81,), "text", (1,)):
        sub = tmp_path / f"case{abs(hash(str(bad)))}"
        sub.mkdir()
        world = build(sub, {"R0": Flagged(notes=bad)})
        world.run(1)
        (record,) = finals(world).values()
        assert record.status is RunStatus.INVALID_RUN and record.code == "CONTRACT_VIOLATION", bad


@dataclass
class Refusing(Good):
    """A retriever whose failure carries notes through ``ledger_flags``."""

    notes: Any = ("ANSWER_REJECTED=NOT_JSON",)

    def retrieve(self, request: RetrievalRequest) -> list[EvidenceCandidate]:
        error = ContractError("bad")
        error.ledger_flags = self.notes  # type: ignore[attr-defined]
        raise error


def test_the_notes_an_exception_carries_are_kept_on_the_failure_record(tmp_path: Path) -> None:
    world = build(tmp_path, {"R0": Refusing()})
    world.run(1)
    (record,) = finals(world).values()
    assert record.status is RunStatus.INVALID_RUN and record.code == "CONTRACT_VIOLATION"
    assert record.flags == ("ANSWER_REJECTED=NOT_JSON",)


def test_malformed_failure_notes_are_dropped_and_the_failure_is_still_recorded(tmp_path: Path) -> None:
    for bad in (["list"], ("",), ("x" * 81,), "text", (1,)):
        sub = tmp_path / f"fail{abs(hash(str(bad)))}"
        sub.mkdir()
        refusing = Refusing()
        refusing.notes = bad
        world = build(sub, {"R0": refusing})
        world.run(1)
        (record,) = finals(world).values()
        assert record.status is RunStatus.INVALID_RUN and record.flags == (), bad
