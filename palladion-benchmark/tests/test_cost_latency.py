"""Latency percentiles with censored timeouts, and cost that never turns an unknown into zero (B03-T05.01)."""

from __future__ import annotations

from typing import Any

import pytest

from benchmark.contracts import RunStatus
from benchmark.eval.cost_latency import (
    OfflineCost,
    amortized_cost_per_query,
    latency_summary,
    level_name,
    online_cost,
)
from benchmark.eval.statistics import StatisticsError
from benchmark.runner import LedgerRecord


def record(
    index: int,
    status: RunStatus = RunStatus.OK,
    duration_ms: float | None = 100.0,
    payload: Any = None,
    *,
    final: bool = True,
) -> LedgerRecord:
    return LedgerRecord(
        run_id="run-0001",
        manifest_sha256="0" * 64,
        arm="arm",
        question_id=f"q-{index:08x}",
        attempt=1 if final else 0,
        is_final=final,
        status=status,
        origin=None,
        code=None,
        started_at_utc="2026-10-18T03:00:00Z",
        duration_ms=duration_ms,
        initial_status=status if final else None,
        attempts=1 if final else None,
        payload=payload,
    )


def test_percentiles_match_hand_computation() -> None:
    records = [record(i, duration_ms=float(i * 10)) for i in range(1, 11)]  # 10, 20, ..., 100
    got = latency_summary(records, deadline_ms=1000.0)
    assert got.completed == 10 and got.timeouts == 0
    assert got.percentiles["p50"] == pytest.approx(55.0)
    assert got.percentiles["p90"] == pytest.approx(91.0)
    assert got.percentiles["p95"] == pytest.approx(95.5)
    assert got.percentiles["p99"] == pytest.approx(99.1)
    assert got.percentiles_with_timeouts_at_deadline is None
    assert [level_name(x) for x in (0.5, 0.9, 0.95, 0.99)] == ["p50", "p90", "p95", "p99"]


def test_a_timeout_is_not_read_as_an_observed_latency() -> None:
    fast = [record(i, duration_ms=100.0) for i in range(1, 5)]
    slow = [record(5, RunStatus.TIMEOUT, duration_ms=30000.0)]
    got = latency_summary(fast + slow, deadline_ms=30000.0)
    assert got.completed == 4 and got.timeouts == 1
    assert got.percentiles["p99"] == 100.0, "the censored call must not enter the observed percentiles"
    assert got.percentiles_with_timeouts_at_deadline is not None
    assert got.percentiles_with_timeouts_at_deadline["p99"] > 20000.0
    assert got.percentiles_with_timeouts_at_deadline["p50"] == 100.0


def test_timeouts_need_their_deadline() -> None:
    with pytest.raises(StatisticsError):
        latency_summary([record(1, RunStatus.TIMEOUT, duration_ms=5.0)], deadline_ms=None)


def test_only_ok_final_records_with_a_duration_are_observed() -> None:
    records = [
        record(1, duration_ms=40.0),
        record(2, duration_ms=None),  # no call was made
        record(3, RunStatus.NOT_RUN, duration_ms=10.0),
        record(4, duration_ms=9999.0, final=False),  # a retry attempt, superseded by its final record
    ]
    got = latency_summary(records, deadline_ms=100.0)
    assert got.completed == 1 and got.percentiles["p50"] == 40.0
    empty = latency_summary([record(1, RunStatus.NOT_RUN, duration_ms=None)], deadline_ms=100.0)
    assert empty.completed == 0 and empty.percentiles == {}


def test_missing_cost_is_never_summed_as_zero() -> None:
    records = [
        record(1, payload={"cost_usd": 0.02}),
        record(2, payload={"cost_usd": None}),
        record(3, payload={"cost_usd": 0.04}),
    ]
    got = online_cost(records)
    assert (got.observed, got.missing) == (2, 1)
    assert got.total_usd == pytest.approx(0.06)
    assert got.mean_usd == pytest.approx(0.03), "the mean is over reported costs, not diluted by the missing one"


def test_no_reported_cost_is_unknown_not_free() -> None:
    got = online_cost([record(1, payload={"cost_usd": None}), record(2, payload=[{"content": "x"}])])
    assert got.total_usd is None and got.mean_usd is None and got.missing == 2
    reported_zero = online_cost([record(1, payload={"cost_usd": 0.0})])
    assert reported_zero.total_usd == 0.0 and reported_zero.mean_usd == 0.0


def test_spend_on_a_failed_call_counts_and_a_failed_call_without_a_report_is_missing() -> None:
    got = online_cost(
        [
            record(1, RunStatus.TIMEOUT, payload={"cost_usd": 5.0}),
            record(2, payload={"cost_usd": 0.5}),
            record(3, RunStatus.NOT_RUN, duration_ms=None),
            record(4, payload={"cost_usd": 9.0}, final=False),  # a superseded attempt is not the final outcome
        ]
    )
    assert (got.observed, got.missing) == (2, 1)
    assert got.total_usd == pytest.approx(5.5)


def test_offline_cost_reads_the_index_record_strictly() -> None:
    got = OfflineCost.from_index_stats({"build_ms": 1500, "build_cost_usd": 0.3, "chunks": 90})
    assert got == OfflineCost(1500.0, 0.3)
    assert OfflineCost.from_index_stats({}) == OfflineCost(None, None)
    with pytest.raises(StatisticsError):
        OfflineCost.from_index_stats({"build_cost_usd": "free"})
    with pytest.raises(StatisticsError):
        OfflineCost.from_index_stats({"build_ms": True})


def test_amortization_formula_and_its_unknowns() -> None:
    offline = OfflineCost(1000.0, 3.0)
    assert amortized_cost_per_query(offline, 0.01, amortization_queries=1000) == pytest.approx(0.013)
    assert amortized_cost_per_query(offline, 0.01, amortization_queries=1) == pytest.approx(3.01)
    assert amortized_cost_per_query(OfflineCost(10.0, None), 0.01, amortization_queries=10) is None
    assert amortized_cost_per_query(offline, None, amortization_queries=10) is None
    with pytest.raises(StatisticsError):
        amortized_cost_per_query(offline, 0.01, amortization_queries=0)
