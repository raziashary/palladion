"""Stage spans and call-budget instrumentation (protocol sections 7.5 and 11.3).

Spans record what happened at each pipeline stage; absent measurements stay ``None`` and are never
turned into zero. Budgets have two distinct semantics. Calls the harness controls are refused before
dispatch and the refusal is recorded as a violation. Counts that a system under test reports about
itself are recorded as unverified and flagged when over budget; they are never clamped.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from benchmark.contracts import (
    ContractError,
    classify_exception,
    optional_int,
    require_ident,
    require_int,
)


class Stage(StrEnum):
    """Protocol section 7.5 stage list, in pipeline order."""

    DOCUMENT_PARSE = "document_parse"
    CHUNKING = "chunking"
    EMBED = "embed"
    SPARSE_INDEX = "sparse_index"
    GRAPH_EXTRACT = "graph_extract"
    GRAPH_COMMIT = "graph_commit"
    QUERY_PREFLIGHT = "query_preflight"
    DENSE_RETRIEVE = "dense_retrieve"
    BM25_RETRIEVE = "bm25_retrieve"
    FUSE = "fuse"
    RERANK = "rerank"
    METADATA_VALIDATE = "metadata_validate"
    GRAPH_EXPAND = "graph_expand"
    EVIDENCE_BUNDLE = "evidence_bundle"
    MAIN_MODEL = "main_model"
    CRITIC = "critic"
    FINAL_GATE = "final_gate"
    RESPONSE = "response"


@dataclass(frozen=True)
class Span:
    event_id: str
    stage: Stage
    started_at_utc: str
    wall_ms: float
    prompt_tokens: int | None
    completion_tokens: int | None
    retries: int
    error_type: str | None
    cache_hit: bool | None
    source_version_ids: tuple[str, ...]
    model_revision: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "stage": self.stage.value,
            "started_at_utc": self.started_at_utc,
            "wall_ms": self.wall_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "retries": self.retries,
            "error_type": self.error_type,
            "cache_hit": self.cache_hit,
            "source_version_ids": list(self.source_version_ids),
            "model_revision": self.model_revision,
        }


@dataclass
class SpanHandle:
    """Mutable view handed to the code inside a span; frozen into a :class:`Span` on exit."""

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    retries: int = 0
    cache_hit: bool | None = None
    source_version_ids: tuple[str, ...] = ()
    model_revision: str | None = None
    _error_type: str | None = field(default=None, repr=False)

    def set_tokens(self, prompt: int | None, completion: int | None) -> None:
        self.prompt_tokens = optional_int("prompt_tokens", prompt)
        self.completion_tokens = optional_int("completion_tokens", completion)

    def add_retry(self) -> None:
        self.retries += 1

    def set_cache_hit(self, hit: bool) -> None:
        if type(hit) is not bool:
            raise ContractError("cache_hit must be a boolean")
        self.cache_hit = hit

    def set_source_versions(self, ids: tuple[str, ...]) -> None:
        self.source_version_ids = tuple(require_ident("source_version_id", i) for i in ids)

    def set_model_revision(self, revision: str) -> None:
        self.model_revision = require_ident("model_revision", revision)


class Tracer:
    """Collects spans for one trace. The clock is injectable so tests can fix wall time exactly."""

    def __init__(
        self,
        trace_id: str,
        *,
        monotonic: Callable[[], float] = time.perf_counter,
        wall_clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.trace_id = require_ident("trace_id", trace_id)
        self._monotonic = monotonic
        self._wall_clock = wall_clock or (lambda: datetime.now(UTC))
        self._spans: list[Span] = []
        self._lock = threading.Lock()

    @property
    def spans(self) -> tuple[Span, ...]:
        with self._lock:
            return tuple(self._spans)

    @contextmanager
    def span(self, stage: Stage) -> Iterator[SpanHandle]:
        if not isinstance(stage, Stage):
            raise ContractError("stage must be a Stage value")
        handle = SpanHandle()
        started = self._wall_clock().astimezone(UTC).isoformat().replace("+00:00", "Z")
        begin = self._monotonic()
        try:
            yield handle
        except BaseException as exc:
            handle._error_type = classify_exception(exc)[2]  # fixed label, never exception text
            raise
        finally:
            elapsed_ms = (self._monotonic() - begin) * 1000.0
            with self._lock:
                self._spans.append(
                    Span(
                        event_id=f"{self.trace_id}:{len(self._spans) + 1:06d}",
                        stage=stage,
                        started_at_utc=started,
                        wall_ms=elapsed_ms,
                        prompt_tokens=handle.prompt_tokens,
                        completion_tokens=handle.completion_tokens,
                        retries=handle.retries,
                        error_type=handle._error_type,
                        cache_hit=handle.cache_hit,
                        source_version_ids=handle.source_version_ids,
                        model_revision=handle.model_revision,
                    )
                )

    def to_records(self) -> list[dict[str, Any]]:
        return [span.to_dict() for span in self.spans]


# --------------------------------------------------------------------------- call budgets

PROTOCOL_MAX_CALLS: Mapping[str, int] = {"main": 5, "critic": 3}


class BudgetExceededError(ContractError):
    """A harness-controlled call was refused before dispatch because its budget is spent."""


@dataclass(frozen=True)
class BudgetViolation:
    role: str
    observed: int
    limit: int
    source: str  # "harness_refused" or "self_reported_unverified"

    def to_dict(self) -> dict[str, Any]:
        return {"role": self.role, "observed": self.observed, "limit": self.limit, "source": self.source}


@dataclass(frozen=True)
class ReportedBudgetCheck:
    """Result of checking counts a system reported about itself. Always ``verified=False``."""

    verified: bool
    reported: Mapping[str, int | None]
    unobserved: tuple[str, ...]
    violations: tuple[BudgetViolation, ...]

    @property
    def within_budget(self) -> bool:
        return not self.violations


class CallBudget:
    """Per-role call limits. ``charge`` is for calls the harness controls and refuses before dispatch."""

    def __init__(self, limits: Mapping[str, int]) -> None:
        if not limits:
            raise ContractError("a budget needs at least one role")
        self._limits = {
            require_ident("role", role): require_int(f"limit[{role}]", n, minimum=1) for role, n in limits.items()
        }
        for role, cap in PROTOCOL_MAX_CALLS.items():
            if role in self._limits and self._limits[role] > cap:
                raise ContractError(f"{role} limit {self._limits[role]} exceeds the protocol maximum {cap}")
        self._counts = dict.fromkeys(self._limits, 0)
        self._violations: list[BudgetViolation] = []
        self._lock = threading.Lock()

    @classmethod
    def protocol(cls) -> CallBudget:
        return cls(PROTOCOL_MAX_CALLS)

    def charge(self, role: str) -> int:
        """Count one dispatched call, or record a violation and refuse. Returns the new count."""
        with self._lock:
            if role not in self._limits:
                raise ContractError(f"unknown budget role: {role}")
            if self._counts[role] >= self._limits[role]:
                self._violations.append(
                    BudgetViolation(role, self._counts[role] + 1, self._limits[role], "harness_refused")
                )
                raise BudgetExceededError(f"{role} budget of {self._limits[role]} call(s) is spent")
            self._counts[role] += 1
            return self._counts[role]

    def count(self, role: str) -> int:
        with self._lock:
            return self._counts[role]

    @property
    def violations(self) -> tuple[BudgetViolation, ...]:
        with self._lock:
            return tuple(self._violations)

    def check_reported(self, **reported: int | None) -> ReportedBudgetCheck:
        """Validate self-reported counts. Over-budget values are flagged and kept as reported, never clamped."""
        violations: list[BudgetViolation] = []
        unobserved: list[str] = []
        clean: dict[str, int | None] = {}
        for role, value in reported.items():
            if role not in self._limits:
                raise ContractError(f"unknown budget role: {role}")
            count = optional_int(f"reported[{role}]", value)
            clean[role] = count
            if count is None:
                unobserved.append(role)
            elif count > self._limits[role]:
                violations.append(BudgetViolation(role, count, self._limits[role], "self_reported_unverified"))
        return ReportedBudgetCheck(False, clean, tuple(unobserved), tuple(violations))
