"""Shared generator pool over the approved Groq models (BADR-0007, BADR-0008, BADR-0015).

* A model is assigned to each question before any arm runs; a call uses exactly that model.
* A classified rate limit waits for the provider's retry-after up to a recorded cap, then fails as a
  recorded result. There is no automatic switch unless ``allow_automatic_failover`` is set, and then
  every switch is written on the call record and the question is marked mixed-model.
* Live calls need an explicit enable flag, a benchmark-local ``.env`` and a call budget enforced
  before dispatch. A credential being present is never a reason to call.
* Errors carry fixed codes, never provider prose; the key exists only inside the transport.

Run ``python -m benchmark.generator --prove --enable-live`` for the one-call-per-model live proof.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import httpx

from benchmark.config import APPROVED_MODELS, GeneratorSettings, load_benchmark_config
from benchmark.contracts import (
    QUOTA_BLOCKED_CODE,
    ContractError,
    ErrorOrigin,
    RunStatus,
    TransientInfrastructureError,
    require_ident,
    require_question_id,
    require_text,
    screen_arm_visible,
)
from benchmark.runner import derived_rng
from benchmark.tracing import BudgetExceededError, CallBudget

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
KEY_NAME = "GROQ_API_KEY"
MAX_REQUEST_BYTES = 48 * 1024
MAX_RESPONSE_BYTES = 256 * 1024
MAX_ERROR_BYTES = 32 * 1024
MAX_RATE_LIMIT_RETRIES = 2
MAX_PROOF_COMPLETION_TOKENS = 256
PROOF_MAX_CALLS = 6
ROLES = frozenset({"system", "user", "assistant"})
_NUMERIC = re.compile(r"[0-9]{1,18}")
_DURATION = re.compile(r"(?:[0-9]{1,9}(?:\.[0-9]{1,6})?(?:ms|s|m|h|d))+")
_SECONDS = re.compile(r"[0-9]{1,6}(?:\.[0-9]{1,3})?")
_REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{1,100}")


# Where a generation failure belongs in the run ledger. A provider fault is the provider's, a refusal to start is the
# harness's; neither is a contract violation by the arm. Codes not listed keep the default classification.
_CLASSIFICATION: Mapping[str, tuple[RunStatus, ErrorOrigin]] = {
    "RATE_LIMITED": (RunStatus.INVALID_RUN, ErrorOrigin.PROVIDER),
    "MALFORMED_RESPONSE": (RunStatus.INVALID_RUN, ErrorOrigin.PROVIDER),
    "GENERATION_DEADLINE": (RunStatus.TIMEOUT, ErrorOrigin.PROVIDER),
    "BUDGET_EXHAUSTED": (RunStatus.NOT_RUN, ErrorOrigin.HARNESS),
    QUOTA_BLOCKED_CODE: (RunStatus.NOT_RUN, ErrorOrigin.HARNESS),
    "DISABLED": (RunStatus.NOT_RUN, ErrorOrigin.HARNESS),
    "NO_CREDENTIAL": (RunStatus.NOT_RUN, ErrorOrigin.HARNESS),
    "ASSIGNMENT_MISSING": (RunStatus.NOT_RUN, ErrorOrigin.HARNESS),
    "REQUEST_TOO_LARGE": (RunStatus.INVALID_RUN, ErrorOrigin.HARNESS),
    "MODEL_RESPONSE_TOO_LARGE": (RunStatus.INVALID_RUN, ErrorOrigin.PROVIDER),
}


def _classify(code: str) -> tuple[RunStatus, ErrorOrigin, str] | None:
    if code.startswith("PROVIDER_HTTP_"):
        return RunStatus.INVALID_RUN, ErrorOrigin.PROVIDER, code
    found = _CLASSIFICATION.get(code)
    return None if found is None else (found[0], found[1], code)


class GenerationError(ContractError):
    """A generation call failed. ``code`` is a fixed label; provider prose is never kept."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code
        classification = _classify(code)
        if classification is not None:
            self.classification = classification


class GenerationTransientError(TransientInfrastructureError):
    """A server-side or network fault that the runner's retry rule may retry."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


# --------------------------------------------------------------------------- credentials


def read_api_key(env_file: Path, *, enabled: bool) -> str:
    """Parse the one literal key without shell semantics. Refuses before reading unless enabled."""
    if not enabled:
        raise GenerationError("DISABLED")
    try:
        lines = env_file.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        raise GenerationError("NO_CREDENTIAL") from None
    key = ""
    for line in lines:
        match = re.fullmatch(rf"\s*(?:export\s+)?{KEY_NAME}\s*=\s*(.*?)\s*", line)
        if match:
            key = match[1].strip().strip("\"'")
    if not key or any(ch.isspace() for ch in key):
        raise GenerationError("NO_CREDENTIAL")
    return key


# --------------------------------------------------------------------------- transport


@dataclass(frozen=True)
class TransportResponse:
    status: int
    headers: Mapping[str, str]  # lower-case names
    body: bytes


class Transport(Protocol):
    def post(self, payload: Mapping[str, Any]) -> TransportResponse: ...


class HttpxTransport:
    """The real transport. No environment proxies, no redirects, bounded bodies, key kept private."""

    def __init__(self, api_key: str, *, timeout_seconds: float, url: str = GROQ_URL) -> None:
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._url = url

    def __repr__(self) -> str:
        return "HttpxTransport(<redacted>)"

    def post(self, payload: Mapping[str, Any]) -> TransportResponse:
        failed = False
        too_large = False
        status, headers, body = 0, {}, bytearray()
        try:
            with (
                httpx.Client(timeout=self._timeout, trust_env=False, follow_redirects=False) as client,
                client.stream(
                    "POST", self._url, headers={"Authorization": "Bearer " + self._api_key}, json=dict(payload)
                ) as response,
            ):
                status = response.status_code
                headers = {k.lower(): v for k, v in response.headers.items()}
                cap = MAX_RESPONSE_BYTES if status == 200 else MAX_ERROR_BYTES
                for piece in response.iter_bytes():
                    body.extend(piece)
                    if len(body) > cap:
                        too_large = status == 200
                        break
        except (httpx.HTTPError, OSError):
            failed = True
        if failed:  # raised outside the except block so the original error text is never chained
            raise GenerationTransientError("PROVIDER_UNAVAILABLE")
        if too_large:
            raise GenerationError("MODEL_RESPONSE_TOO_LARGE")
        return TransportResponse(status, headers, bytes(body))


# --------------------------------------------------------------------------- records


@dataclass(frozen=True)
class GenerationRecord:
    """One dispatched call. Holds a digest of the prompt, never the prompt, the key or provider prose."""

    record_id: str
    question_id: str
    arm_id: str | None
    requested_model: str
    served_model: str | None
    model_matches_request: bool | None
    attempt: int
    status: str
    error_code: str | None
    http_status: int | None
    started_at_utc: str
    latency_ms: float
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    temperature: float
    max_completion_tokens: int
    reasoning_effort: str
    response_format: str | None
    seed: None
    provider_exposes_revision: bool
    request_id: str | None
    rate_limits: Mapping[str, Any]
    retry_after_seconds: float | None
    quota_window: str | None
    failover_from: str | None
    cached: bool
    prompt_sha256: str

    def to_dict(self) -> dict[str, Any]:
        data = dict(self.__dict__)
        data["rate_limits"] = dict(self.rate_limits)
        return data


@dataclass(frozen=True)
class GenerationResult:
    text: str | None
    record: GenerationRecord


# --------------------------------------------------------------------------- assignment


@dataclass(frozen=True)
class AssignmentPlan:
    assigned: Mapping[str, str]
    unassigned: tuple[str, ...]

    def digest(self) -> str:
        canonical = json.dumps(
            {"assigned": dict(sorted(self.assigned.items())), "unassigned": list(self.unassigned)},
            sort_keys=True, separators=(",", ":"),
        )  # fmt: skip
        return hashlib.sha256(canonical.encode()).hexdigest()


def assign_models(
    question_ids: Sequence[str], settings: GeneratorSettings, *, seed: int, tokens_per_question: int
) -> AssignmentPlan:
    """Fix every question's model before any arm runs, from configured per-model token budgets.

    Questions are taken in a seeded random order. The primary model takes questions until its budget
    is spent, then the next model, and so on. A model without a stated budget takes questions only if
    it is the primary (unlimited); an unknown budget on a fallback model means it is never used.
    Questions beyond all capacity are returned unassigned and must be recorded NOT_RUN for every arm.
    """
    if type(tokens_per_question) is not int or tokens_per_question < 1:
        raise ContractError("tokens_per_question must be a positive integer")
    ids = sorted({require_question_id("question_id", q) for q in question_ids})
    derived_rng(seed, "assignment").shuffle(ids)
    capacity: dict[str, float] = {}
    for position, model in enumerate(settings.models):
        budget = settings.token_budgets.get(model)
        capacity[model] = (math.inf if position == 0 else 0) if budget is None else budget // tokens_per_question
    assigned: dict[str, str] = {}
    queue = iter(ids)
    for model in settings.models:
        taken = 0
        while taken < capacity[model]:
            question = next(queue, None)
            if question is None:
                return AssignmentPlan(assigned, ())
            assigned[question] = model
            taken += 1
    return AssignmentPlan(assigned, tuple(queue))


# --------------------------------------------------------------------------- the pool


def _bounded_headers(headers: Mapping[str, str]) -> tuple[dict[str, Any], float | None, str | None]:
    limits: dict[str, Any] = {}
    for name in ("limit-requests", "remaining-requests", "limit-tokens", "remaining-tokens"):
        value = headers.get("x-ratelimit-" + name, "")
        if _NUMERIC.fullmatch(value):
            limits[name] = int(value)
    for name in ("reset-requests", "reset-tokens"):
        value = headers.get("x-ratelimit-" + name, "")
        if len(value) <= 64 and _DURATION.fullmatch(value):
            limits[name] = value
    retry = headers.get("retry-after", "")
    request_id = headers.get("x-request-id", "")
    return (
        limits,
        float(retry) if _SECONDS.fullmatch(retry) else None,
        request_id if _REQUEST_ID.fullmatch(request_id) else None,
    )


_WINDOWS = (
    ("tokens per day", "TOKENS_DAILY"),
    ("tokens per minute", "TOKENS_MINUTE"),
    ("requests per day", "REQUESTS_DAILY"),
    ("requests per minute", "REQUESTS_MINUTE"),
)
DAILY_WINDOWS = frozenset({"TOKENS_DAILY", "REQUESTS_DAILY"})


def _quota_window(body: bytes) -> tuple[str, float | None]:
    """Classify a rate-limit body into a window label and a suggested wait, keeping no provider text."""
    try:
        message = str(json.loads(body).get("error", {}).get("message", "")).lower()
    except (ValueError, AttributeError):
        return "UNKNOWN", None
    window = next((label for needle, label in _WINDOWS if needle in message), "UNKNOWN")
    wait = re.search(r"try again in (?:(\d+)h)?(?:(\d+)m)?(\d+(?:\.\d+)?)s", message)
    seconds = int(wait[1] or 0) * 3600 + int(wait[2] or 0) * 60 + float(wait[3]) if wait else None
    return window, seconds


class GeneratorPool:
    def __init__(
        self,
        settings: GeneratorSettings,
        transport: Transport | None,
        *,
        enabled: bool,
        assignment: Mapping[str, str],
        call_budget: int,
        record_path: Path | None = None,
        prompt_path: Path | None = None,
        screen_prompts: bool = True,
        pace_seconds: float = 0.0,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], datetime] | None = None,
    ) -> None:
        for model in settings.models:
            if model not in APPROVED_MODELS:
                raise GenerationError("MODEL_NOT_APPROVED")
        for question, model in assignment.items():
            require_question_id("assignment question", question)
            if model not in settings.models:
                raise GenerationError("MODEL_NOT_APPROVED")
        self.settings = settings
        self.enabled = enabled
        self._transport = transport
        self._assignment = dict(assignment)
        self._budget = CallBudget({"generator": call_budget})
        self._record_path = record_path
        self._prompt_path = prompt_path
        self._screen_prompts = screen_prompts
        self._pace = max(0.0, pace_seconds)
        self._last_dispatch: float | None = None
        self._calls = 0
        self._sleep, self._monotonic = sleep, monotonic
        self._wall_clock = wall_clock or (lambda: datetime.now(UTC))
        self._records: list[GenerationRecord] = []
        self._mixed: set[str] = set()
        self._quota_blocked: set[str] = set()
        self._lock = threading.Lock()

    @classmethod
    def live(
        cls,
        settings: GeneratorSettings,
        env_file: Path,
        *,
        enabled: bool,
        assignment: Mapping[str, str],
        call_budget: int,
        record_path: Path | None = None,
        prompt_path: Path | None = None,
        screen_prompts: bool = True,
        pace_seconds: float = 0.0,
    ) -> GeneratorPool:
        """Build a pool with the real transport. Refuses before touching the env file unless enabled."""
        key = read_api_key(env_file, enabled=enabled)
        transport = HttpxTransport(key, timeout_seconds=settings.request_timeout_seconds)
        return cls(settings, transport, enabled=enabled, assignment=assignment, call_budget=call_budget,
                   record_path=record_path, prompt_path=prompt_path,
                   screen_prompts=screen_prompts, pace_seconds=pace_seconds)  # fmt: skip

    def _sequence(self) -> int:
        """A running call number, so a retry by the runner does not repeat a record id."""
        with self._lock:
            self._calls += 1
            return self._calls

    def now(self) -> float:
        """The pool's monotonic clock, the one ``deadline`` is measured on."""
        return self._monotonic()

    @property
    def records(self) -> tuple[GenerationRecord, ...]:
        with self._lock:
            return tuple(self._records)

    @property
    def mixed_model_questions(self) -> frozenset[str]:
        with self._lock:
            return frozenset(self._mixed)

    @property
    def quota_blocked_models(self) -> frozenset[str]:
        """Models a provider's daily limit stopped in this process; a later process asks the provider again."""
        with self._lock:
            return frozenset(self._quota_blocked)

    @property
    def budget_violations(self) -> int:
        return len(self._budget.violations)

    # -- one question ------------------------------------------------------

    def complete(
        self,
        question_id: str,
        messages: Sequence[Mapping[str, str]],
        *,
        arm_id: str | None = None,
        json_output: bool = False,
        max_completion_tokens: int | None = None,
        deadline: float | None = None,
        cancel: threading.Event | None = None,
    ) -> GenerationResult:
        """One generation. ``deadline`` is a point on the pool's monotonic clock by which the call must be finished;
        ``cancel`` stops a call the caller has abandoned. Neither lets a late worker dispatch or record anything."""
        if not self.enabled or self._transport is None:
            raise GenerationError("DISABLED")
        question_id = require_question_id("question_id", question_id)
        if arm_id is not None:
            arm_id = require_ident("arm_id", arm_id)
        model = self._assignment.get(question_id)
        if model is None:
            raise GenerationError("ASSIGNMENT_MISSING")
        if model in self.quota_blocked_models:  # no request is made for a model the provider has stopped for the day
            raise GenerationError(QUOTA_BLOCKED_CODE)
        cap = self.settings.max_completion_tokens if max_completion_tokens is None else max_completion_tokens
        if type(cap) is not int or not 1 <= cap <= self.settings.max_completion_tokens:
            raise ContractError("max_completion_tokens exceeds the configured cap")
        prompt = self._validated(messages)
        prompt_sha = hashlib.sha256(json.dumps(prompt, sort_keys=True).encode()).hexdigest()
        failover_from: str | None = None
        waits = 0
        attempt = 0
        while True:
            attempt += 1
            payload = self._payload(model, prompt, cap, json_output)
            if len(json.dumps(payload, ensure_ascii=False).encode()) > MAX_REQUEST_BYTES:
                raise GenerationError("REQUEST_TOO_LARGE")
            self._check_time(deadline, cancel, needs=self.settings.request_timeout_seconds)
            self._pace_before_dispatch(deadline)
            try:
                self._budget.charge("generator")
            except BudgetExceededError:
                raise GenerationError("BUDGET_EXHAUSTED") from None
            if attempt == 1:
                self._keep_prompt(question_id, arm_id, prompt_sha, prompt)  # only a call that is really made
            outcome = self._dispatch(question_id, arm_id, model, attempt, payload, cap, json_output, prompt_sha,
                                     failover_from)  # fmt: skip
            record, text, error = outcome
            if cancel is not None and cancel.is_set():  # abandoned while the call was in flight: write nothing
                raise GenerationError("GENERATION_DEADLINE")
            self._remember(record)
            if error is None:
                return GenerationResult(text, record)
            if record.error_code != "RATE_LIMITED":
                raise error
            wait = record.retry_after_seconds
            if (
                wait is not None
                and wait <= self.settings.rate_limit_max_wait_seconds
                and waits < MAX_RATE_LIMIT_RETRIES
                and self._fits(deadline, wait + self.settings.request_timeout_seconds)
            ):
                waits += 1
                self._sleep(wait)
                continue
            if self.settings.allow_automatic_failover:
                following = self._next_model(model)
                if following is not None:
                    failover_from, model, waits = model, following, 0
                    with self._lock:
                        self._mixed.add(question_id)
                    continue
            if record.quota_window in DAILY_WINDOWS:
                with self._lock:
                    self._quota_blocked.add(model)
                raise GenerationError(QUOTA_BLOCKED_CODE)
            raise error

    def _pace_before_dispatch(self, deadline: float | None) -> None:
        """Keep a minimum time between dispatches, so a call is not spent on a limit the spacing would have avoided."""
        if self._pace and self._last_dispatch is not None:
            wait = self._last_dispatch + self._pace - self._monotonic()
            if wait > 0:
                if not self._fits(deadline, wait + self.settings.request_timeout_seconds):
                    raise GenerationError("GENERATION_DEADLINE")
                self._sleep(wait)
        self._last_dispatch = self._monotonic()

    def _fits(self, deadline: float | None, seconds: float) -> bool:
        return deadline is None or self._monotonic() + seconds <= deadline

    def _check_time(self, deadline: float | None, cancel: threading.Event | None, *, needs: float) -> None:
        """Refuse to dispatch when the caller has given up or the call could not finish before its deadline."""
        if (cancel is not None and cancel.is_set()) or not self._fits(deadline, needs):
            raise GenerationError("GENERATION_DEADLINE")

    def _keep_prompt(self, question_id: str, arm_id: str | None, digest: str, prompt: list[dict[str, str]]) -> None:
        """The full prompt of each call, so a validator can scan what the generator was actually given."""
        if self._prompt_path is None:
            return
        entry = {"question_id": question_id, "arm_id": arm_id, "prompt_sha256": digest, "messages": prompt}
        with self._lock, self._prompt_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")

    def _next_model(self, current: str) -> str | None:
        models = self.settings.models
        position = models.index(current)
        return models[position + 1] if position + 1 < len(models) else None

    def _validated(self, messages: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
        if not messages:
            raise ContractError("messages must not be empty")
        checked = []
        for message in messages:
            if set(message) != {"role", "content"} or message["role"] not in ROLES:
                raise ContractError("each message needs exactly a valid role and content")
            content = require_text("message content", message["content"])
            if self._screen_prompts:
                screen_arm_visible("message content", content)
            checked.append({"role": message["role"], "content": content})
        return checked

    def _payload(self, model: str, prompt: list[dict[str, str]], cap: int, json_output: bool) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": prompt,
            "temperature": self.settings.temperature,
            "max_completion_tokens": cap,
            "reasoning_effort": self.settings.reasoning_effort[model],
        }
        if json_output:
            payload["response_format"] = {"type": "json_object"}
        return payload

    def _remember(self, record: GenerationRecord) -> None:
        with self._lock:
            self._records.append(record)
            if self._record_path is not None:
                with self._record_path.open("a", encoding="utf-8", newline="\n") as handle:
                    handle.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")

    def _dispatch(
        self, question_id: str, arm_id: str | None, model: str, attempt: int, payload: Mapping[str, Any], cap: int,
        json_output: bool, prompt_sha: str, failover_from: str | None,
    ) -> tuple[GenerationRecord, str | None, GenerationError | GenerationTransientError | None]:  # fmt: skip
        assert self._transport is not None
        started = self._wall_clock().astimezone(UTC).isoformat().replace("+00:00", "Z")
        begin = self._monotonic()
        response: TransportResponse | None = None
        raised: GenerationError | GenerationTransientError | None = None
        failed_unexpectedly = False
        try:
            response = self._transport.post(payload)
        except (GenerationError, GenerationTransientError) as exc:
            raised = exc
        except Exception:
            failed_unexpectedly = True
        if failed_unexpectedly:  # outside the except block: no chained exception text
            raised = GenerationTransientError("PROVIDER_UNAVAILABLE")
        latency_ms = (self._monotonic() - begin) * 1000.0
        base: dict[str, Any] = {
            "record_id": f"{question_id}:{model}:{attempt}:{self._sequence()}",
            "question_id": question_id, "arm_id": arm_id,
            "requested_model": model, "attempt": attempt, "started_at_utc": started, "latency_ms": latency_ms,
            "temperature": self.settings.temperature, "max_completion_tokens": cap,
            "reasoning_effort": self.settings.reasoning_effort[model],
            "response_format": "json_object" if json_output else None, "seed": None,
            "provider_exposes_revision": False, "failover_from": failover_from, "cached": False,
            "prompt_sha256": prompt_sha,
        }  # fmt: skip
        empty: dict[str, Any] = {
            "served_model": None, "model_matches_request": None, "http_status": None, "prompt_tokens": None,
            "completion_tokens": None, "total_tokens": None, "request_id": None, "rate_limits": {},
            "retry_after_seconds": None, "quota_window": None,
        }  # fmt: skip
        if raised is not None or response is None:
            error = raised or GenerationTransientError("PROVIDER_UNAVAILABLE")
            record = GenerationRecord(**base, **empty, status="ERROR", error_code=error.code)
            return record, None, error
        limits, retry_after, request_id = _bounded_headers(response.headers)
        common = {**empty, "http_status": response.status, "request_id": request_id, "rate_limits": limits}
        if response.status == 429:
            window, suggested = _quota_window(response.body)
            common.update(
                retry_after_seconds=retry_after if retry_after is not None else suggested, quota_window=window
            )
            error = GenerationError("RATE_LIMITED")
            return GenerationRecord(**base, **common, status="RATE_LIMITED", error_code="RATE_LIMITED"), None, error
        if response.status != 200:
            code = f"PROVIDER_HTTP_{response.status}"
            error = GenerationTransientError(code) if response.status >= 500 else GenerationError(code)
            return GenerationRecord(**base, **common, status="ERROR", error_code=code), None, error
        parsed = self._parse(response.body)
        if parsed is None:
            error = GenerationError("MALFORMED_RESPONSE")
            return GenerationRecord(**base, **common, status="ERROR", error_code="MALFORMED_RESPONSE"), None, error
        text, served, usage = parsed
        common.update(
            served_model=served, model_matches_request=served == model, prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"), total_tokens=usage.get("total_tokens"),
        )  # fmt: skip
        return GenerationRecord(**base, **common, status="OK", error_code=None), text, None

    @staticmethod
    def _parse(body: bytes) -> tuple[str | None, str | None, dict[str, int]] | None:
        try:
            data = json.loads(body)
            message = data["choices"][0]["message"]
            content = message.get("content")
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            return None
        if content is not None and not isinstance(content, str):
            return None
        served = data.get("model") if isinstance(data.get("model"), str) else None
        raw_usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        usage = {
            name: raw_usage[name]
            for name in ("prompt_tokens", "completion_tokens", "total_tokens")
            if type(raw_usage.get(name)) is int and raw_usage[name] >= 0
        }
        return content, served, usage


# --------------------------------------------------------------------------- live proof entry point


def prove(
    pool: GeneratorPool, models: Sequence[str], assignment_ids: Mapping[str, str], max_tokens: int
) -> list[dict[str, Any]]:
    """One call per model through the actual pool. Returns one result row per model."""
    rows: list[dict[str, Any]] = []
    messages = [
        {"role": "system", "content": "You are a connectivity check. Answer with one word."},
        {"role": "user", "content": "Reply with exactly the single word: ready"},
    ]
    for model in models:
        question = assignment_ids[model]
        try:
            result = pool.complete(question, messages, arm_id="proof", max_completion_tokens=max_tokens)
        except (GenerationError, GenerationTransientError) as exc:
            record = next((r for r in reversed(pool.records) if r.requested_model == model), None)
            rows.append({"model": model, "result": "FAIL", "code": exc.code,
                         "http_status": record.http_status if record else None,
                         "retry_after_seconds": record.retry_after_seconds if record else None,
                         "quota_window": record.quota_window if record else None})  # fmt: skip
            continue
        record = result.record
        text_returned = bool(result.text and result.text.strip())
        passed = record.status == "OK" and record.served_model == model and text_returned
        rows.append({"model": model, "result": "PASS" if passed else "FAIL", "code": record.error_code,
                     "served_model": record.served_model, "text_returned": text_returned,
                     "prompt_tokens": record.prompt_tokens, "completion_tokens": record.completion_tokens,
                     "latency_ms": round(record.latency_ms), "rate_limits": dict(record.rate_limits),
                     "request_id_present": record.request_id is not None})  # fmt: skip
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prove", action="store_true", help="run the one-call-per-model live proof")
    parser.add_argument("--enable-live", action="store_true", help="explicit permission to call the provider")
    parser.add_argument("--env-file", type=Path, default=Path(__file__).resolve().parents[1] / ".env")
    parser.add_argument(
        "--config", type=Path, default=Path(__file__).resolve().parents[1] / "configs" / "benchmark.yaml"
    )
    parser.add_argument("--models", nargs="+", default=list(APPROVED_MODELS))
    parser.add_argument("--max-completion-tokens", type=int, default=MAX_PROOF_COMPLETION_TOKENS)
    parser.add_argument("--max-calls", type=int, default=PROOF_MAX_CALLS)
    parser.add_argument("--out", type=Path, default=None, help="JSON-lines file for the call records")
    options = parser.parse_args(argv)
    if not options.prove:
        parser.print_help()
        return 2
    if not options.enable_live:
        print("REFUSED: live calls need --enable-live; no credential was read and no request was sent", file=sys.stderr)
        return 2
    if (
        not 1 <= options.max_completion_tokens <= MAX_PROOF_COMPLETION_TOKENS
        or not 1 <= options.max_calls <= PROOF_MAX_CALLS
    ):
        print("REFUSED: the proof allows 1 to 256 completion tokens and 1 to 6 calls (BADR-0015)", file=sys.stderr)
        return 2
    if any(m not in APPROVED_MODELS for m in options.models):
        print("REFUSED: only approved models may be called", file=sys.stderr)
        return 2
    settings = load_benchmark_config(options.config).generator
    ids = {model: f"q-{index:08x}" for index, model in enumerate(options.models, start=1)}
    out = options.out
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
    try:
        pool = GeneratorPool.live(settings, options.env_file, enabled=True,
                                  assignment={q: m for m, q in ids.items()}, call_budget=options.max_calls,
                                  record_path=out)  # fmt: skip
    except GenerationError as exc:
        print(f"REFUSED: {exc.code}", file=sys.stderr)
        return 2
    rows = prove(pool, options.models, ids, options.max_completion_tokens)
    for row in rows:
        print(json.dumps(row, sort_keys=True))
    passed = sum(1 for r in rows if r["result"] == "PASS")
    print(f"{'PASS' if passed == len(rows) else 'PARTIAL'}: {passed}/{len(rows)} model(s) returned a real response; "
          f"{len(pool.records)} call(s) made")  # fmt: skip
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
