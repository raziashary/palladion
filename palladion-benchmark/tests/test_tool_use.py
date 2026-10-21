"""Tool-use evaluation (B07-T06.02): over-budget calls fail, malformed calls are listed, NOT_OBSERVABLE is not zero."""

from __future__ import annotations

import json

import pytest

from benchmark.contracts import CaseResponse, EvidenceStatus, ModelInvocations
from benchmark.eval.observable import NotObservable, Rate
from benchmark.eval.tool_use import (
    ReportedCall,
    ToolExpectation,
    ToolObservation,
    ToolSchema,
    check_arguments,
    reported_calls,
    score_tool_use,
)

SCHEMAS = {
    "search_knowledge": ToolSchema({"query": "string"}, {"limit": "integer", "require_graph": "boolean"}),
    "lookup_live_data": ToolSchema({"operation": "string", "target_id": "string"}),
}

TWO_CALLS = ModelInvocations(2, 0)


def response(
    status: EvidenceStatus = EvidenceStatus.SUPPORTED,
    text: str = "ok",
    used: tuple[str, ...] = (),
    invocations: ModelInvocations | None = TWO_CALLS,
) -> CaseResponse:
    return CaseResponse(
        question_id="q-0123456789abcdef", run_id="r1", answer_text=text, evidence_status=status, claims=(),
        used_evidence_ids=used, tool_calls=(), critic=None, model_invocations=invocations, latency_ms=None,
        cost_usd=None, abstention_reason=None,
    )  # fmt: skip


def call(name: str, arguments: dict[str, object] | str | None, status: str = "SUCCEEDED") -> ReportedCall:
    text = arguments if isinstance(arguments, str) or arguments is None else json.dumps(arguments)
    return ReportedCall(name, status, text)


def expectation(**over: object) -> ToolExpectation:
    base: dict[str, object] = {"required_tools": frozenset({"search_knowledge"}), "schemas": SCHEMAS}
    return ToolExpectation(**{**base, **over})  # type: ignore[arg-type]


def observe(calls: list[ReportedCall], exp: ToolExpectation | None = None, **kwargs: object) -> ToolObservation:
    return ToolObservation("q-0123456789abcdef", tuple(calls), exp or expectation(), response(**kwargs), None)  # type: ignore[arg-type]


GOOD = call("search_knowledge", {"query": "refund window", "limit": 2})


def test_a_system_that_calls_exactly_the_required_tool_validly_scores_clean() -> None:
    score = score_tool_use([observe([GOOD])])
    assert score.selection_recall == Rate(1, 1) and score.unnecessary_invocation == Rate(0, 1)
    assert score.argument_validity == Rate(1, 1) and score.malformed == ()


def test_a_missing_required_tool_lowers_recall_and_an_extra_or_repeated_call_is_unnecessary() -> None:
    exp = expectation(required_tools=frozenset({"search_knowledge", "lookup_live_data"}))
    live = call("lookup_live_data", {"operation": "txn", "target_id": "T1"})
    score = score_tool_use([observe([GOOD, GOOD], exp), observe([GOOD, live], exp)])
    assert score.selection_recall == Rate(3, 4)
    assert score.unnecessary_invocation == Rate(1, 4), (
        "only the exact repeat is unnecessary when both tools are required"
    )
    plain = score_tool_use([observe([GOOD, live])])
    assert plain.unnecessary_invocation == Rate(1, 2), "a tool the question does not need is unnecessary"


def test_a_malformed_call_is_surfaced_with_its_reason() -> None:
    bad = [
        call("search_knowledge", "{not json"),
        call("search_knowledge", {"limit": 2}),
        call("search_knowledge", {"query": "x", "colour": "red"}),
        call("search_knowledge", {"query": "x", "limit": "2"}),
        call("search_knowledge", {"query": "x", "limit": True}),
        call("search_knowledge", "[1]"),
        call("delete_everything", {"query": "x"}),
    ]
    score = score_tool_use([observe(bad)])
    assert score.argument_validity == Rate(0, 7)
    assert [m.reason.split(" ")[0] for m in score.malformed] == [
        "the",
        "missing",
        "unknown",
        "limit",
        "limit",
        "the",
        "delete_everything",
    ]


def test_a_pinned_argument_must_match() -> None:
    exp = expectation(pinned={"lookup_live_data": {"target_id": "T1"}}, required_tools=frozenset({"lookup_live_data"}))
    right = call("lookup_live_data", {"operation": "txn", "target_id": "T1"})
    wrong = call("lookup_live_data", {"operation": "txn", "target_id": "T2"})
    assert check_arguments(right, exp) is None and "pinned" in (check_arguments(wrong, exp) or "")


def test_arguments_a_system_does_not_report_are_not_observable_and_not_zero() -> None:
    score = score_tool_use([observe([ReportedCall("search_knowledge", "SUCCEEDED", None)])])
    assert isinstance(score.argument_validity, NotObservable) and score.selection_recall == Rate(1, 1)
    partial = score_tool_use([observe([ReportedCall("search_knowledge", "SUCCEEDED", None), GOOD])])
    assert partial.argument_validity == Rate(1, 1), "only the calls that report arguments are judged"


def test_a_system_with_no_tool_report_is_not_observable_on_every_measure() -> None:
    score = score_tool_use([observe([])], reports_calls=False)
    values = list(score.measures().values())
    assert values and all(isinstance(v, NotObservable) for v in values)


def test_over_budget_calls_are_failures_and_counted() -> None:
    exp = expectation(max_model_calls=5, max_critic_calls=3, max_tool_calls=2)
    within = observe([GOOD, GOOD], exp, invocations=ModelInvocations(5, 3))
    over = observe([GOOD, GOOD, GOOD], exp, invocations=ModelInvocations(7, 4))
    score = score_tool_use([within, over])
    assert score.boundedness == Rate(1, 2) and score.over_budget_calls == 2 + 1 + 1


def test_a_cap_that_cannot_be_checked_is_not_observable() -> None:
    exp = expectation(max_model_calls=5)
    score = score_tool_use([observe([GOOD], exp, invocations=None)])
    assert isinstance(score.boundedness, NotObservable) and isinstance(score.over_budget_calls, NotObservable)


def test_result_utilization_needs_a_succeeded_required_tool_and_the_answer_to_use_its_evidence() -> None:
    exp = expectation(supporting_evidence=frozenset({"doc-1#c1"}))
    used = observe([GOOD], exp, used=("doc-1#c1",))
    ignored = observe([GOOD], exp, used=("doc-9#c1",))
    failed = observe([call("search_knowledge", {"query": "x"}, "FAILED")], exp)
    assert score_tool_use([used, ignored, failed]).result_utilization == Rate(1, 2), "a failed tool has nothing to use"


def test_discovery_reversal_needs_a_different_successful_tool_after_an_irrelevant_first_retrieval() -> None:
    exp = expectation(first_retrieval_irrelevant=True, required_tools=frozenset({"lookup_live_data"}))
    live = call("lookup_live_data", {"operation": "txn", "target_id": "T1"})
    switched = observe([GOOD, live], exp)
    stubborn = observe([GOOD, GOOD, GOOD], exp)
    broken = observe([GOOD, call("lookup_live_data", {"operation": "txn", "target_id": "T1"}, "FAILED")], exp)
    assert score_tool_use([switched, stubborn, broken]).discovery_reversal == Rate(1, 3)


def test_an_outage_read_as_an_absence_is_a_failure_of_interpretation() -> None:
    exp = expectation(negative_phrases=("no refund policy exists", "was not found"))
    failed = [call("search_knowledge", {"query": "x"}, "FAILED")]
    honest = observe(
        failed, exp, status=EvidenceStatus.VERIFICATION_UNAVAILABLE, text="I could not check; the service is down."
    )
    absent = observe(failed, exp, status=EvidenceStatus.NOT_ESTABLISHED, text="No refund policy exists for this case.")
    confident = observe(failed, exp, status=EvidenceStatus.SUPPORTED, text="Refund allowed.")
    healthy = observe([GOOD], exp, text="No refund policy exists")
    score = score_tool_use([honest, absent, confident, healthy])
    assert score.failure_interpretation == Rate(1, 3), "a healthy call is not eligible; only the honest outage is right"


def test_escalation_precision_and_recall_use_the_mandate_and_what_the_system_said() -> None:
    mandated, other = expectation(escalation_required=True), expectation(escalation_required=False)

    def with_escalation(exp: ToolExpectation, escalated: bool | None) -> ToolObservation:
        return ToolObservation("q-0123456789abcdef", (GOOD,), exp, response(), escalated)

    score = score_tool_use(
        [
            with_escalation(mandated, True),
            with_escalation(mandated, False),
            with_escalation(other, True),
            with_escalation(other, False),
        ]
    )
    assert score.escalation_precision == Rate(1, 2) and score.escalation_recall == Rate(1, 2)
    silent = score_tool_use([with_escalation(mandated, None)])
    assert isinstance(silent.escalation_recall, NotObservable) and isinstance(
        silent.escalation_precision, NotObservable
    )


def test_a_schema_must_use_known_types_and_distinct_names() -> None:
    with pytest.raises(ValueError, match="known JSON types"):
        ToolSchema({"a": "str"})
    with pytest.raises(ValueError, match="disjoint"):
        ToolSchema({"a": "string"}, {"a": "string"})


def test_reported_calls_keep_the_role_name_arguments_and_status_of_the_evaluator_block() -> None:
    block = {
        "tool_calls": [
            {"role": "main", "name": "search_knowledge", "arguments": '{"query": "q"}', "status": "SUCCEEDED"},
            {"role": "critic", "name": "search_knowledge", "arguments": '{"query": "r"}', "status": "SUCCEEDED"},
        ]
    }
    assert reported_calls(block) == (ReportedCall("search_knowledge", "SUCCEEDED", '{"query": "q"}'),)
    assert [c.arguments for c in reported_calls(block, "critic")] == ['{"query": "r"}']
    assert reported_calls({}) == ()


def test_an_argument_a_system_does_not_report_stays_unreported() -> None:
    block = {"tool_calls": [{"role": "main", "name": "search_knowledge", "status": "SUCCEEDED"}]}
    (call,) = reported_calls(block)
    assert call.arguments is None
    assert isinstance(score_tool_use([observe([call])]).argument_validity, NotObservable)
