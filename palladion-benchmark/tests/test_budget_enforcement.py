"""Tracing and call budgets: violations are recorded as failures, nothing is clamped or zero-filled."""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime

import pytest

from benchmark.contracts import ArmUnavailable, ContractError
from benchmark.tracing import (
    PROTOCOL_MAX_CALLS,
    BudgetExceededError,
    CallBudget,
    Stage,
    Tracer,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


FIXED_WALL = datetime(2026, 10, 18, 3, 0, tzinfo=UTC)


def make_tracer(clock: FakeClock) -> Tracer:
    return Tracer("trace-1", monotonic=clock, wall_clock=lambda: FIXED_WALL)


# ----------------------------------------------------------------------------- stages and spans


def test_stage_list_matches_protocol_section_7_5_in_order() -> None:
    assert [s.value for s in Stage] == [
        "document_parse", "chunking", "embed", "sparse_index", "graph_extract", "graph_commit",
        "query_preflight", "dense_retrieve", "bm25_retrieve", "fuse", "rerank", "metadata_validate",
        "graph_expand", "evidence_bundle", "main_model", "critic", "final_gate", "response",
    ]  # fmt: skip


def test_span_records_wall_time_exactly_and_uses_a_utc_start() -> None:
    clock = FakeClock()
    tracer = make_tracer(clock)
    with tracer.span(Stage.RERANK):
        clock.now += 0.25
    (span,) = tracer.spans
    assert span.wall_ms == pytest.approx(250.0)
    assert span.started_at_utc == "2026-10-18T03:00:00Z"
    assert span.event_id == "trace-1:000001"


def test_absent_measurements_stay_null_and_are_not_zero() -> None:
    tracer = make_tracer(FakeClock())
    with tracer.span(Stage.FUSE):
        pass
    record = tracer.to_records()[0]
    for key in ("prompt_tokens", "completion_tokens", "cache_hit", "model_revision", "error_type"):
        assert record[key] is None, key
    assert record["retries"] == 0 and record["source_version_ids"] == []


def test_recorded_measurements_are_kept() -> None:
    tracer = make_tracer(FakeClock())
    with tracer.span(Stage.MAIN_MODEL) as handle:
        handle.set_tokens(120, 30)
        handle.add_retry()
        handle.add_retry()
        handle.set_cache_hit(False)
        handle.set_source_versions(("SOP-7@v3",))
        handle.set_model_revision("qwen/qwen3.8-27b")
    record = json.loads(json.dumps(tracer.to_records()[0]))
    assert (record["prompt_tokens"], record["completion_tokens"], record["retries"]) == (120, 30, 2)
    assert record["cache_hit"] is False and record["source_version_ids"] == ["SOP-7@v3"]


def test_an_observed_zero_is_distinct_from_not_observed() -> None:
    tracer = make_tracer(FakeClock())
    with tracer.span(Stage.EMBED) as handle:
        handle.set_tokens(0, 0)
    assert tracer.spans[0].prompt_tokens == 0


@pytest.mark.parametrize("bad", [-1, True, 1.5, "3"])
def test_invalid_token_counts_are_rejected(bad: object) -> None:
    tracer = make_tracer(FakeClock())
    with pytest.raises(ContractError), tracer.span(Stage.EMBED) as handle:
        handle.set_tokens(bad, None)  # type: ignore[arg-type]


def test_an_exception_is_recorded_with_a_fixed_code_never_its_text_and_is_reraised() -> None:
    tracer = make_tracer(FakeClock())
    secret = "gsk_" + "z" * 30
    with pytest.raises(ArmUnavailable), tracer.span(Stage.DENSE_RETRIEVE):
        raise ArmUnavailable(secret)
    (span,) = tracer.spans
    assert span.error_type == "ARM_UNAVAILABLE"
    assert secret not in json.dumps(tracer.to_records())


def test_spans_are_numbered_in_order_and_unknown_stage_is_refused() -> None:
    tracer = make_tracer(FakeClock())
    for stage in (Stage.CHUNKING, Stage.EMBED):
        with tracer.span(stage):
            pass
    assert [s.event_id for s in tracer.spans] == ["trace-1:000001", "trace-1:000002"]
    with pytest.raises(ContractError), tracer.span("nonsense"):  # type: ignore[arg-type]
        pass


# ----------------------------------------------------------------------------- harness-controlled budgets


def test_protocol_limits_are_five_main_and_three_critic() -> None:
    assert dict(PROTOCOL_MAX_CALLS) == {"main": 5, "critic": 3}


def test_a_sixth_main_call_is_refused_and_recorded_as_a_violation_not_truncated_silently() -> None:
    budget = CallBudget.protocol()
    assert [budget.charge("main") for _ in range(5)] == [1, 2, 3, 4, 5]
    with pytest.raises(BudgetExceededError):
        budget.charge("main")
    assert budget.count("main") == 5  # the refused call never dispatched
    (violation,) = budget.violations
    assert (violation.role, violation.observed, violation.limit, violation.source) == ("main", 6, 5, "harness_refused")


def test_a_fourth_critic_call_is_refused_independently_of_main() -> None:
    budget = CallBudget.protocol()
    for _ in range(3):
        budget.charge("critic")
    with pytest.raises(BudgetExceededError):
        budget.charge("critic")
    assert budget.charge("main") == 1


def test_limits_above_the_protocol_maximum_are_refused_at_construction() -> None:
    with pytest.raises(ContractError, match="exceeds the protocol maximum"):
        CallBudget({"main": 6})
    with pytest.raises(ContractError):
        CallBudget({"critic": 4})
    assert CallBudget({"main": 2}).charge("main") == 1
    with pytest.raises(ContractError):
        CallBudget({})
    with pytest.raises(ContractError):
        CallBudget({"main": 0})


def test_unknown_role_is_refused() -> None:
    with pytest.raises(ContractError, match="unknown budget role"):
        CallBudget.protocol().charge("planner")


def test_concurrent_callers_cannot_oversubscribe_the_budget() -> None:
    budget = CallBudget({"main": 5})
    results: list[bool] = []
    lock = threading.Lock()

    def worker() -> None:
        for _ in range(20):
            try:
                budget.charge("main")
                outcome = True
            except BudgetExceededError:
                outcome = False
            with lock:
                results.append(outcome)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results.count(True) == 5 and budget.count("main") == 5
    assert len(budget.violations) == len(results) - 5


# ----------------------------------------------------------------------------- self-reported counts


def test_over_budget_self_report_is_flagged_unverified_and_not_clamped() -> None:
    check = CallBudget.protocol().check_reported(main=6, critic=1)
    assert check.verified is False and not check.within_budget
    assert check.reported == {"main": 6, "critic": 1}  # kept as reported
    (violation,) = check.violations
    assert violation.source == "self_reported_unverified" and (violation.observed, violation.limit) == (6, 5)


def test_in_budget_self_report_is_still_marked_unverified() -> None:
    check = CallBudget.protocol().check_reported(main=5, critic=3)
    assert check.within_budget and check.verified is False


def test_missing_self_report_is_unobserved_not_zero_and_not_a_violation() -> None:
    check = CallBudget.protocol().check_reported(main=None, critic=2)
    assert check.unobserved == ("main",) and check.reported["main"] is None
    assert check.within_budget


def test_invalid_self_reports_are_rejected() -> None:
    budget = CallBudget.protocol()
    with pytest.raises(ContractError):
        budget.check_reported(main=-1)
    with pytest.raises(ContractError):
        budget.check_reported(main=True)
    with pytest.raises(ContractError):
        budget.check_reported(planner=1)
