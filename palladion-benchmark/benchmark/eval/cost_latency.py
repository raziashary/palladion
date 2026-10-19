"""Latency and cost accounting from ledger records (B03-T05.01, protocol 8.5 and 10, BADR-0024).

Two rules hold throughout. A timed-out call is censored: its duration is "at least the deadline", never an observed
latency, so percentiles are computed over completed calls and the timeouts are reported beside them. A missing cost
stays missing: nothing is summed as zero unless the system reported zero. Offline (index build) cost comes from the
index record an arm writes and is spread over an amortization horizon the caller states.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from benchmark.contracts import RunStatus
from benchmark.eval.statistics import StatisticsError, quantile
from benchmark.runner import LedgerRecord

LATENCY_LEVELS = (0.50, 0.90, 0.95, 0.99)


@dataclass(frozen=True)
class LatencySummary:
    """Percentiles over completed calls, and the censored timeouts reported beside them."""

    completed: int
    percentiles: Mapping[str, float]
    timeouts: int
    deadline_ms: float | None
    percentiles_with_timeouts_at_deadline: Mapping[str, float] | None  # a lower bound, not an observation


@dataclass(frozen=True)
class CostSummary:
    """Self-reported cost over the records that reported one. ``total_usd`` is None when no record did."""

    observed: int
    missing: int
    total_usd: float | None
    mean_usd: float | None


def level_name(level: float) -> str:
    return f"p{round(level * 100)}"


def _percentiles(values: Sequence[float]) -> dict[str, float]:
    return {level_name(level): quantile(values, level) for level in LATENCY_LEVELS}


def final_records(records: Sequence[LedgerRecord]) -> list[LedgerRecord]:
    return [r for r in records if r.is_final]


def latency_summary(records: Sequence[LedgerRecord], *, deadline_ms: float | None) -> LatencySummary:
    """Latency of the final records: completed calls give percentiles; a TIMEOUT is counted, never read as a latency."""
    finals = final_records(records)
    completed = [r.duration_ms for r in finals if r.status is RunStatus.OK and r.duration_ms is not None]
    timeouts = sum(r.status is RunStatus.TIMEOUT for r in finals)
    with_deadline: dict[str, float] | None = None
    if timeouts:
        if deadline_ms is None:
            raise StatisticsError("timed-out calls cannot be reported without the deadline that cut them off")
        with_deadline = _percentiles([*completed, *([deadline_ms] * timeouts)])
    return LatencySummary(
        completed=len(completed),
        percentiles=_percentiles(completed) if completed else {},
        timeouts=timeouts,
        deadline_ms=deadline_ms,
        percentiles_with_timeouts_at_deadline=with_deadline,
    )


def _reported_cost(record: LedgerRecord) -> float | None:
    payload = record.payload
    if not isinstance(payload, Mapping):
        return None
    value = payload.get("cost_usd")
    return None if value is None else float(value)


def online_cost(records: Sequence[LedgerRecord]) -> CostSummary:
    """Cost reported across the final records, whatever their state: spend on a failed call is still spend.

    A record that reported no cost is counted as missing, never as zero, so a run state cannot hide unknown cost.
    """
    costs = [_reported_cost(r) for r in final_records(records)]
    seen = [c for c in costs if c is not None]
    total = sum(seen) if seen else None
    return CostSummary(
        observed=len(seen),
        missing=len(costs) - len(seen),
        total_usd=total,
        mean_usd=None if total is None else total / len(seen),
    )


@dataclass(frozen=True)
class OfflineCost:
    """What an arm recorded about building its index. Either value may be unknown."""

    build_ms: float | None
    cost_usd: float | None

    @classmethod
    def from_index_stats(cls, stats: Mapping[str, object]) -> OfflineCost:
        def number(key: str) -> float | None:
            value = stats.get(key)
            if value is None:
                return None
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise StatisticsError(f"index record field {key} must be a number or null")
            return float(value)

        return cls(number("build_ms"), number("build_cost_usd"))


def amortized_cost_per_query(
    offline: OfflineCost, online_mean_usd: float | None, *, amortization_queries: int
) -> float | None:
    """Online mean plus the build cost spread over the stated number of queries; unknown if either part is unknown."""
    if amortization_queries < 1:
        raise StatisticsError("an amortization horizon needs at least one query")
    if offline.cost_usd is None or online_mean_usd is None:
        return None
    return online_mean_usd + offline.cost_usd / amortization_queries
