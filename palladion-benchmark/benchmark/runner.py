"""Paired, bounded, randomized runner with intention-to-treat records.

Rules enforced here, each with a test:

* every arm runs every case (pairing); arm order inside a case and case order are randomized
  from a seed that is stored in the manifests;
* every (arm, case) pair ends with exactly one final record, whatever happened (no pair is dropped);
* a retry is allowed only for a classified transient fault under a policy fixed in the manifest, and
  every attempt stays in the ledger beside the final outcome;
* nothing is ever re-run: a finished pair is skipped, and a second run id on the same plan is refused;
* run-level limits apply between cases only, so a case is measured on all arms or on none;
* an arm that overran its deadline is marked unusable; its late result is discarded and counted.

Arms see only the request object. No gold, split or label is passed to them (BI01, BI03).
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import threading
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from benchmark.config import BenchmarkConfig, RetryPolicy
from benchmark.contracts import (
    ArmUnavailable,
    CapabilityUnsupported,
    CaseRequest,
    CaseResponse,
    ContractError,
    ErrorOrigin,
    EvidenceCandidate,
    RetrievalRequest,
    RetrieverAdapter,
    RunStatus,
    SystemAdapter,
    TransientInfrastructureError,
    classify_exception,
    require_ident,
    require_question_id,
)
from benchmark.registry import ArmRegistry, Capability
from benchmark.run_manifest import RunManifest, read_verified, sha256_of
from benchmark.tracing import CallBudget


class RunnerError(ContractError):
    """The run cannot start or continue without breaking a protocol rule."""


class DuplicatePairError(RunnerError):
    """A pair already has a final outcome; re-running it would be a selective rerun."""


class PlanAlreadyRunError(RunnerError):
    """A different run id already executed this exact plan."""


# --------------------------------------------------------------------------- ledger


@dataclass(frozen=True)
class LedgerRecord:
    run_id: str
    manifest_sha256: str
    arm: str
    question_id: str
    attempt: int
    is_final: bool
    status: RunStatus
    origin: ErrorOrigin | None
    code: str | None
    started_at_utc: str
    duration_ms: float | None  # None when no call was made (for example a censored or blocked pair)
    initial_status: RunStatus | None  # set on final records: the first attempt's status
    attempts: int | None  # set on final records
    payload: Any
    flags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "manifest_sha256": self.manifest_sha256,
            "arm": self.arm,
            "question_id": self.question_id,
            "attempt": self.attempt,
            "is_final": self.is_final,
            "status": self.status.value,
            "origin": self.origin.value if self.origin else None,
            "code": self.code,
            "started_at_utc": self.started_at_utc,
            "duration_ms": self.duration_ms,
            "initial_status": self.initial_status.value if self.initial_status else None,
            "attempts": self.attempts,
            "payload": self.payload,
            "flags": list(self.flags),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> LedgerRecord:
        origin = data["origin"]
        initial = data["initial_status"]
        return cls(
            run_id=data["run_id"],
            manifest_sha256=data["manifest_sha256"],
            arm=data["arm"],
            question_id=data["question_id"],
            attempt=data["attempt"],
            is_final=data["is_final"],
            status=RunStatus(data["status"]),
            origin=ErrorOrigin(origin) if origin else None,
            code=data["code"],
            started_at_utc=data["started_at_utc"],
            duration_ms=data["duration_ms"],
            initial_status=RunStatus(initial) if initial else None,
            attempts=data["attempts"],
            payload=data["payload"],
            flags=tuple(data.get("flags", ())),
        )


class RunLedger:
    """Append-only JSON-lines ledger. There is no API to edit or delete a record."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._records: list[LedgerRecord] = []
        if path.exists():
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                try:
                    self._records.append(LedgerRecord.from_dict(json.loads(line)))
                except (ValueError, KeyError, TypeError) as exc:
                    raise RunnerError(f"ledger line {number} is not a valid record") from exc
        self._final_keys = {(r.arm, r.question_id) for r in self._records if r.is_final}
        self._attempt_keys = {(r.arm, r.question_id, r.attempt) for r in self._records}

    @property
    def records(self) -> tuple[LedgerRecord, ...]:
        with self._lock:
            return tuple(self._records)

    def has_final(self, arm: str, question_id: str) -> bool:
        with self._lock:
            return (arm, question_id) in self._final_keys

    def next_attempt(self, arm: str, question_id: str) -> int:
        """The attempt number to use next, so an interrupted retry resumes instead of colliding."""
        with self._lock:
            return 1 + max(
                (r.attempt for r in self._records if (r.arm, r.question_id) == (arm, question_id)), default=0
            )

    def first_status(self, arm: str, question_id: str) -> RunStatus | None:
        """Status of the first recorded attempt of a pair, if any."""
        with self._lock:
            first = [r for r in self._records if (r.arm, r.question_id, r.attempt) == (arm, question_id, 1)]
            return first[0].status if first else None

    def timed_out_arms(self) -> dict[str, str]:
        """Arms with a TIMEOUT outcome on record, with the question that timed them out."""
        with self._lock:
            return {r.arm: r.question_id for r in self._records if r.status is RunStatus.TIMEOUT}

    def append(self, record: LedgerRecord) -> None:
        with self._lock:
            key = (record.arm, record.question_id)
            if key in self._final_keys:
                raise DuplicatePairError(f"{record.arm}/{record.question_id} already has a final outcome")
            attempt_key = (record.arm, record.question_id, record.attempt)
            if attempt_key in self._attempt_keys:
                raise DuplicatePairError(f"{record.arm}/{record.question_id} attempt {record.attempt} already recorded")
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            self._records.append(record)
            self._attempt_keys.add(attempt_key)
            if record.is_final:
                self._final_keys.add(key)

    def verify_complete(self, planned: Sequence[tuple[str, str]]) -> None:
        """Intention to treat: every planned pair has exactly one final record and nothing else is final."""
        with self._lock:
            finals = Counter((r.arm, r.question_id) for r in self._records if r.is_final)
        missing = sorted(set(planned) - set(finals))
        extra = sorted(set(finals) - set(planned))
        duplicated = sorted(k for k, n in finals.items() if n > 1)
        if missing or extra or duplicated:
            raise RunnerError(
                f"ledger is not complete: missing {missing[:3]}, extra {extra[:3]}, duplicated {duplicated[:3]}"
            )


class PlanRegistry:
    """Remembers which run id executed which plan.

    Rules: the same run id may resume its own plan; a different run id may not repeat a plan unless it
    declares an exploratory repeat on a non-test split; on the test split no pair that another run has
    already covered may ever be run again, whatever the plan (no selective reruns, protocol 14.1).
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def _entries(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines()]

    def register(
        self,
        plan_digest: str,
        run_id: str,
        *,
        split: str,
        arms: Sequence[str],
        questions: Sequence[str],
        allow_exploratory_repeat: bool = False,
    ) -> None:
        others = [e for e in self._entries() if e["run_id"] != run_id]
        if split == "test":
            for entry in others:
                if (
                    entry["split"] == "test"
                    and set(entry["arms"]) & set(arms)
                    and set(entry["questions"]) & set(questions)
                ):
                    raise PlanAlreadyRunError(f"run {entry['run_id']} already covered part of this test plan")
        same = [e for e in self._entries() if e["plan_digest"] == plan_digest]
        if any(e["run_id"] == run_id for e in same):
            return  # the same run id resumes its own plan
        if same and not (allow_exploratory_repeat and split != "test"):
            raise PlanAlreadyRunError(f"plan {plan_digest[:12]} was already run as {same[0]['run_id']}")
        entry = {"plan_digest": plan_digest, "run_id": run_id, "split": split,
                 "arms": sorted(arms), "questions": sorted(questions)}  # fmt: skip
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())


def plan_digest(arm_ids: Sequence[str], question_ids: Sequence[str], order_seed: int, split: str) -> str:
    return sha256_of(
        {"arms": sorted(arm_ids), "questions": sorted(question_ids), "order_seed": order_seed, "split": split}
    )


def derived_rng(order_seed: int, label: str) -> random.Random:
    """A deterministic RNG that does not depend on Python's per-process hash randomization."""
    digest = hashlib.sha256(f"{order_seed}:{label}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


# --------------------------------------------------------------------------- runner


@dataclass(frozen=True)
class RunnerCase:
    """What the runner may hand to an arm: the request, nothing else."""

    request: RetrievalRequest | CaseRequest

    def __post_init__(self) -> None:
        if not isinstance(self.request, RetrievalRequest | CaseRequest):
            raise RunnerError("a runner case must hold a RetrievalRequest or a CaseRequest and nothing else")

    @property
    def question_id(self) -> str:
        return self.request.question_id


@dataclass(frozen=True)
class ArmBinding:
    arm_id: str
    adapter: RetrieverAdapter | SystemAdapter
    manifest_path: Path


@dataclass(frozen=True)
class RunnerSettings:
    order_seed: int
    case_deadline_seconds: float
    run_deadline_seconds: float | None
    retry: RetryPolicy

    @classmethod
    def from_config(cls, config: BenchmarkConfig, *, order_seed: int | None = None) -> RunnerSettings:
        return cls(
            order_seed=config.default_seed if order_seed is None else order_seed,
            case_deadline_seconds=config.case_deadline_seconds,
            run_deadline_seconds=config.run_deadline_seconds,
            retry=config.retry,
        )

    def retry_policy_dict(self) -> dict[str, Any]:
        return {
            "max_attempts": self.retry.max_attempts,
            "base_backoff_seconds": self.retry.base_backoff_seconds,
        }


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    planned_pairs: int
    executed_pairs: int
    skipped_pairs: int
    status_counts: Mapping[str, int]
    late_results_discarded: int
    unusable_arms: tuple[str, ...]
    censored_questions: tuple[str, ...]
    flag_counts: Mapping[str, int]


@dataclass
class _Outcome:
    status: RunStatus
    origin: ErrorOrigin | None
    code: str | None
    payload: Any
    duration_ms: float | None
    retryable: bool
    started_at_utc: str
    flags: tuple[str, ...] = ()


@dataclass
class _Holder:
    done: threading.Event = field(default_factory=threading.Event)
    abandoned: bool = False
    value: Any = None
    flags: tuple[str, ...] = ()
    error: BaseException | None = None


def _arm_flags(adapter: object) -> tuple[str, ...]:
    """Notes an arm made about its latest call (truncation, filtering, warnings), kept with the ledger record.

    An arm offers them through an optional ``call_flags()``; each must be a short non-empty string.
    """
    provider = getattr(adapter, "call_flags", None)
    if not callable(provider):
        return ()
    flags = provider()
    if not isinstance(flags, tuple) or not all(isinstance(f, str) and 0 < len(f) <= 80 for f in flags):
        raise ContractError("call_flags() must return a tuple of short non-empty strings")
    return flags


class Runner:
    def __init__(
        self,
        run_id: str,
        settings: RunnerSettings,
        arms: Sequence[ArmBinding],
        ledger: RunLedger,
        plans: PlanRegistry,
        registry: ArmRegistry,
        *,
        required_capabilities: Sequence[Capability] = (),
        allow_exploratory_repeat: bool = False,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        wall_clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.run_id = require_ident("run_id", run_id)
        self.settings = settings
        self.arms = list(arms)
        if not self.arms or len({a.arm_id for a in self.arms}) != len(self.arms):
            raise RunnerError("a run needs at least one arm and arm ids must be distinct")
        self.ledger = ledger
        self.plans = plans
        self.registry = registry
        self.required_capabilities = tuple(required_capabilities)
        self.allow_exploratory_repeat = allow_exploratory_repeat
        self._budget = CallBudget.protocol()
        self._monotonic = monotonic
        self._sleep = sleep
        self._wall_clock = wall_clock or (lambda: datetime.now(UTC))
        self._unusable: dict[str, str] = ledger.timed_out_arms()  # an arm that timed out stays unusable on resume
        self._late = 0
        self._late_lock = threading.Lock()

    @property
    def late_results_discarded(self) -> int:
        with self._late_lock:
            return self._late

    # -- ordering -----------------------------------------------------------

    def case_order(self, question_ids: Sequence[str]) -> list[str]:
        order = sorted(question_ids)
        derived_rng(self.settings.order_seed, "cases").shuffle(order)
        return order

    def arm_order(self, question_id: str) -> list[str]:
        order = sorted(a.arm_id for a in self.arms)
        derived_rng(self.settings.order_seed, f"arms:{question_id}").shuffle(order)
        return order

    # -- preflight ----------------------------------------------------------

    def _verified_manifests(self, split: str) -> dict[str, tuple[RunManifest, str]]:
        """Every arm's manifest must already exist on disk, agree with the runner, and carry the fixed retry policy."""
        verified: dict[str, tuple[RunManifest, str]] = {}
        for binding in self.arms:
            if not binding.manifest_path.exists():
                raise RunnerError(f"manifest for {binding.arm_id} must be written before the first arm runs")
            manifest = read_verified(binding.manifest_path)
            if manifest.arm != binding.arm_id or manifest.run_id != self.run_id:
                raise RunnerError(f"manifest for {binding.arm_id} names a different arm or run")
            if manifest.split != split:
                raise RunnerError(f"manifest for {binding.arm_id} declares split {manifest.split}, not {split}")
            if manifest.order_seed != self.settings.order_seed:
                raise RunnerError(f"manifest for {binding.arm_id} has a different order seed")
            if dict(manifest.retry_policy) != self.settings.retry_policy_dict():
                raise RunnerError(f"manifest for {binding.arm_id} does not fix the retry policy the runner uses")
            digest = manifest.digest()
            earlier = {r.manifest_sha256 for r in self.ledger.records if r.arm == binding.arm_id}
            if earlier - {digest}:
                raise RunnerError(f"manifest for {binding.arm_id} changed since the ledger recorded it")
            verified[binding.arm_id] = (manifest, digest)
        return verified

    def _blocked_arms(self) -> dict[str, tuple[RunStatus, ErrorOrigin, str]]:
        """Arms the registry refuses (unverified or unsupported capability, forced status), by recorded result."""
        blocked: dict[str, tuple[RunStatus, ErrorOrigin, str]] = {}
        for binding in self.arms:
            if binding.arm_id not in self.registry.ids():
                raise RunnerError(f"arm {binding.arm_id} is not in the registry")
            try:
                self.registry.require_runnable(binding.arm_id, self.required_capabilities)
            except (ArmUnavailable, CapabilityUnsupported) as exc:
                blocked[binding.arm_id] = classify_exception(exc)
        return blocked

    # -- one attempt --------------------------------------------------------

    def _call(self, binding: ArmBinding, case: RunnerCase) -> tuple[Any, tuple[str, ...]]:
        adapter = binding.adapter
        request = case.request
        if isinstance(request, RetrievalRequest):
            if not isinstance(adapter, RetrieverAdapter):
                raise ContractError(f"{binding.arm_id} is not a retriever")
            candidates = adapter.retrieve(request)
            if not isinstance(candidates, list) or not all(isinstance(c, EvidenceCandidate) for c in candidates):
                raise ContractError("retrieve() must return a list of EvidenceCandidate")
            if len(candidates) > request.limit:
                raise ContractError("retrieve() returned more candidates than the request limit")
            if [c.rank for c in candidates] != list(range(1, len(candidates) + 1)):
                raise ContractError("candidate ranks must be 1..n in order")
            return [c.to_dict() for c in candidates], _arm_flags(adapter)
        if not isinstance(request, CaseRequest) or not isinstance(adapter, SystemAdapter):
            raise ContractError(f"{binding.arm_id} is not a system arm")
        adapter.reset_case(request.question_id)
        response = adapter.answer(request)
        if not isinstance(response, CaseResponse) or response.question_id != request.question_id:
            raise ContractError("answer() must return the CaseResponse for the same question")
        payload = response.to_dict()
        invocations = response.model_invocations
        check = self._budget.check_reported(
            main=invocations.main if invocations else None, critic=invocations.critic if invocations else None
        )
        if check.violations:  # flagged, never clamped: the reported counts stay as reported
            payload["budget_check"] = {"verified": False, "violations": [v.to_dict() for v in check.violations]}
            return payload, ("BUDGET_VIOLATION_UNVERIFIED", *_arm_flags(adapter))
        return payload, _arm_flags(adapter)

    def _attempt(self, binding: ArmBinding, case: RunnerCase) -> _Outcome:
        holder = _Holder()
        started = self._wall_clock().astimezone(UTC).isoformat().replace("+00:00", "Z")
        begin = self._monotonic()

        def work() -> None:
            try:
                holder.value, holder.flags = self._call(binding, case)
            except BaseException as exc:
                holder.error = exc
            finally:
                with self._late_lock:
                    holder.done.set()
                    if holder.abandoned:
                        self._late += 1  # discarded: the ledger was closed for this attempt

        thread = threading.Thread(target=work, daemon=True, name=f"arm-{binding.arm_id}")
        thread.start()
        finished = holder.done.wait(self.settings.case_deadline_seconds)
        duration_ms = (self._monotonic() - begin) * 1000.0
        if not finished:
            with self._late_lock:
                holder.abandoned = True
                if holder.done.is_set():  # finished in the race window: still timed out, still discarded
                    self._late += 1
            self._unusable[binding.arm_id] = case.question_id
            return _Outcome(
                RunStatus.TIMEOUT,
                ErrorOrigin.ARM,
                "DEADLINE_EXCEEDED",
                None,
                duration_ms,
                False,  # a timeout is never retried
                started,
            )
        if holder.error is not None:
            status, origin, code = classify_exception(holder.error)
            retryable = isinstance(holder.error, TransientInfrastructureError)
            return _Outcome(status, origin, code, None, duration_ms, retryable, started)
        return _Outcome(RunStatus.OK, None, None, holder.value, duration_ms, False, started, holder.flags)

    # -- one pair -----------------------------------------------------------

    def _run_pair(self, binding: ArmBinding, case: RunnerCase, digest: str) -> RunStatus:
        arm, qid = binding.arm_id, case.question_id
        if arm in self._unusable:
            return self._final_without_call(
                arm, qid, digest, RunStatus.NOT_RUN, ErrorOrigin.HARNESS, "ARM_UNUSABLE_AFTER_TIMEOUT"
            )
        policy = self.settings.retry
        attempt = self.ledger.next_attempt(arm, qid)  # resumes an interrupted retry instead of colliding
        first_status = self.ledger.first_status(arm, qid)
        while True:
            outcome = self._attempt(binding, case)
            first_status = first_status or outcome.status
            can_retry = outcome.retryable and attempt < policy.max_attempts and outcome.status is not RunStatus.OK
            if outcome.status is RunStatus.TIMEOUT and arm in self._unusable:
                can_retry = False  # an arm that overran its deadline is never called again
            if can_retry and outcome.code == "TRANSIENT_FAULT_RETRIES_EXHAUSTED":
                outcome = replace(outcome, code="TRANSIENT_FAULT")  # not exhausted yet: another attempt follows
            self.ledger.append(self._record(arm, qid, digest, attempt, not can_retry, outcome, first_status, attempt))
            if not can_retry:
                return outcome.status
            self._sleep(policy.base_backoff_seconds * (2 ** (attempt - 1)))
            attempt += 1

    def _record(
        self,
        arm: str,
        qid: str,
        digest: str,
        attempt: int,
        is_final: bool,
        outcome: _Outcome,
        first_status: RunStatus,
        attempts: int,
    ) -> LedgerRecord:
        return LedgerRecord(
            run_id=self.run_id,
            manifest_sha256=digest,
            arm=arm,
            question_id=qid,
            attempt=attempt,
            is_final=is_final,
            status=outcome.status,
            origin=outcome.origin,
            code=outcome.code,
            started_at_utc=outcome.started_at_utc,
            duration_ms=outcome.duration_ms,
            initial_status=first_status if is_final else None,
            attempts=attempts if is_final else None,
            payload=outcome.payload,
            flags=outcome.flags,
        )

    def _final_without_call(
        self, arm: str, qid: str, digest: str, status: RunStatus, origin: ErrorOrigin, code: str
    ) -> RunStatus:
        now = self._wall_clock().astimezone(UTC).isoformat().replace("+00:00", "Z")
        outcome = _Outcome(status, origin, code, None, None, False, now)
        attempt = self.ledger.next_attempt(arm, qid)
        first = self.ledger.first_status(arm, qid) or status
        self.ledger.append(self._record(arm, qid, digest, attempt, True, outcome, first, attempt))
        return status

    # -- the run ------------------------------------------------------------

    def run(self, cases: Sequence[RunnerCase], *, split: str) -> RunSummary:
        by_id: dict[str, RunnerCase] = {}
        for case in cases:
            require_question_id("question_id", case.question_id)
            if case.question_id in by_id:
                raise RunnerError(f"duplicate question {case.question_id}")
            by_id[case.question_id] = case
        manifests = self._verified_manifests(split)
        blocked = self._blocked_arms()
        arm_ids = [a.arm_id for a in self.arms]
        self.plans.register(
            plan_digest(arm_ids, list(by_id), self.settings.order_seed, split),
            self.run_id,
            split=split,
            arms=arm_ids,
            questions=list(by_id),
            allow_exploratory_repeat=self.allow_exploratory_repeat,
        )
        bindings = {a.arm_id: a for a in self.arms}
        started = self._monotonic()
        executed = skipped = 0
        counts: Counter[str] = Counter()
        censored: list[str] = []
        for qid in self.case_order(list(by_id)):
            over = (
                self.settings.run_deadline_seconds is not None
                and self._monotonic() - started >= self.settings.run_deadline_seconds
            )
            pending = [arm for arm in self.arm_order(qid) if not self.ledger.has_final(arm, qid)]
            skipped += len(arm_ids) - len(pending)
            if over and pending:
                censored.append(qid)
            for arm in pending:
                digest = manifests[arm][1]
                if over:
                    status = self._final_without_call(
                        arm, qid, digest, RunStatus.NOT_RUN, ErrorOrigin.HARNESS, "RUN_DEADLINE"
                    )
                elif arm in blocked:
                    status = self._final_without_call(arm, qid, digest, *blocked[arm])
                else:
                    status = self._run_pair(bindings[arm], by_id[qid], digest)
                counts[status.value] += 1
                executed += 1
        planned = [(arm, qid) for qid in by_id for arm in arm_ids]
        self.ledger.verify_complete(planned)
        with self._late_lock:
            late = self._late
        flag_counts = Counter(f for r in self.ledger.records if r.is_final and r.run_id == self.run_id for f in r.flags)
        return RunSummary(
            self.run_id,
            len(planned),
            executed,
            skipped,
            dict(counts),
            late,
            tuple(sorted(self._unusable)),
            tuple(sorted(censored)),
            dict(flag_counts),
        )
