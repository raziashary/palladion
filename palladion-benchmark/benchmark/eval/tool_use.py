"""Tool-use evaluation from a system's reported tool calls (B07-T06.02, protocol 11.3).

A tool call is what the system reports: a name, optionally its arguments as the JSON text it sent, and the status the
tool returned. Nothing here runs a tool. Gold says which tools the question needs, what their arguments must look like
and what the answer should have used; the measures are rates over those expectations.

* **selection recall**: required tools called at least once.
* **unnecessary invocation**: calls to a tool the question does not need, and exact repeats of an earlier call. A
  structural measure: whether a call returned "new evidence" is not visible from the call itself.
* **argument validity**: the arguments parse to an object, hold every required key and no unknown key, each value has
  the declared type, and every value gold pins is equal. Malformed calls are listed, not hidden. When no call reports
  its arguments the measure is NOT_OBSERVABLE.
* **result utilization**: for a question whose required tool succeeded, the answer used at least one of the evidence
  ids that tool should have surfaced.
* **discovery reversal**: when the first retrieval was irrelevant, a later successful call used a different tool.
* **boundedness**: model calls and tool calls stay within the caps. Calls beyond a cap are failures, counted.
* **failure interpretation**: when a tool failed, the answer is not a confident absence or negative status.
* **escalation**: escalation precision and recall against the questions that mandate it.

A system that reports no tool calls at all has every measure NOT_OBSERVABLE, never zero.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from benchmark.contracts import CaseResponse, EvidenceStatus
from benchmark.eval.normalize import fold
from benchmark.eval.observable import Measure, NotObservable, Rate

FAILED_STATUSES = frozenset({"FAILED", "UNAVAILABLE", "TIMEOUT", "DENIED", "CANCELLED", "TOOL_BUDGET_EXHAUSTED"})
OK_STATUSES = frozenset({"SUCCEEDED", "OK", "PARTIAL"})
HONEST_STATUSES = frozenset(
    {EvidenceStatus.VERIFICATION_UNAVAILABLE, EvidenceStatus.NOT_ESTABLISHED, EvidenceStatus.PARTIALLY_SUPPORTED}
)
NO_CALLS_REASON = "the system reports no tool calls"
NO_ARGUMENTS_REASON = "no call reports its arguments"
NO_INVOCATIONS_REASON = "no cap could be checked: the system reports no model invocation counts and no tool cap is set"
_TYPES: Mapping[str, type | tuple[type, ...]] = {
    "string": str, "integer": int, "number": (int, float), "boolean": bool, "array": list, "object": dict,
}  # fmt: skip


@dataclass(frozen=True)
class ToolSchema:
    """The arguments a tool takes: required and optional names with a JSON type for each."""

    required: Mapping[str, str]
    optional: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        bad = [t for t in (*self.required.values(), *self.optional.values()) if t not in _TYPES]
        if bad or set(self.required) & set(self.optional):
            raise ValueError(f"a tool schema needs known JSON types and disjoint names: {bad}")


@dataclass(frozen=True)
class ReportedCall:
    """``arguments`` is the JSON text the system sent, or None when it does not report it."""

    name: str
    status: str
    arguments: str | None = None


@dataclass(frozen=True)
class ToolExpectation:
    """Gold for one question. ``pinned`` fixes argument values per tool (an id, a scope, a time basis)."""

    required_tools: frozenset[str]
    schemas: Mapping[str, ToolSchema]
    pinned: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    supporting_evidence: frozenset[str] = frozenset()
    first_retrieval_irrelevant: bool = False
    negative_phrases: tuple[str, ...] = ()  # phrases that would turn an outage into an absence or a negative status
    escalation_required: bool | None = None
    max_model_calls: int | None = None
    max_critic_calls: int | None = None
    max_tool_calls: int | None = None


@dataclass(frozen=True)
class ToolObservation:
    """One question as run. ``escalated`` is whether the answer escalated (None when the system does not say)."""

    question_id: str
    calls: tuple[ReportedCall, ...]
    expectation: ToolExpectation
    response: CaseResponse
    escalated: bool | None = None


@dataclass(frozen=True)
class MalformedCall:
    question_id: str
    call: ReportedCall
    reason: str


@dataclass(frozen=True)
class ToolScore:
    questions: int
    selection_recall: Measure
    unnecessary_invocation: Measure
    argument_validity: Measure
    result_utilization: Measure
    discovery_reversal: Measure
    boundedness: Measure
    over_budget_calls: int | NotObservable
    failure_interpretation: Measure
    escalation_precision: Measure
    escalation_recall: Measure
    malformed: tuple[MalformedCall, ...]

    def measures(self) -> dict[str, Measure | int]:
        return {
            "tool_selection_recall": self.selection_recall,
            "unnecessary_invocation_rate": self.unnecessary_invocation,
            "argument_validity": self.argument_validity,
            "result_utilization": self.result_utilization,
            "discovery_reversal": self.discovery_reversal,
            "boundedness_compliance": self.boundedness,
            "over_budget_calls": self.over_budget_calls,
            "failure_interpretation": self.failure_interpretation,
            "escalation_precision": self.escalation_precision,
            "escalation_recall": self.escalation_recall,
        }


def reported_calls(evaluator: Mapping[str, Any], role: str = "main") -> tuple[ReportedCall, ...]:
    """The tool calls of one role from a system's evaluator block, with the arguments it sent and the status it saw."""
    return tuple(
        ReportedCall(str(call["name"]), str(call["status"]), call.get("arguments"))
        for call in evaluator.get("tool_calls", ())
        if call.get("role") == role
    )


def check_arguments(call: ReportedCall, expectation: ToolExpectation) -> str | None:
    """Why the call's arguments are invalid, or None when they are valid. The call must report its arguments."""
    schema = expectation.schemas.get(call.name)
    if schema is None:
        return f"{call.name} is not a tool of the system"
    try:
        parsed = json.loads(call.arguments or "")
    except json.JSONDecodeError:
        return "the arguments are not JSON"
    if not isinstance(parsed, dict):
        return "the arguments are not an object"
    missing = sorted(set(schema.required) - set(parsed))
    if missing:
        return f"missing {', '.join(missing)}"
    unknown = sorted(set(parsed) - set(schema.required) - set(schema.optional))
    if unknown:
        return f"unknown {', '.join(unknown)}"
    declared = {**schema.required, **schema.optional}
    for key, value in parsed.items():
        expected = _TYPES[declared[key]]
        if not isinstance(value, expected) or (isinstance(value, bool) and declared[key] in {"integer", "number"}):
            return f"{key} is not a {declared[key]}"
    for key, wanted in expectation.pinned.get(call.name, {}).items():
        if parsed.get(key) != wanted:
            return f"{key} is {parsed.get(key)!r}, not the pinned value"
    return None


def score_tool_use(observations: Sequence[ToolObservation], *, reports_calls: bool = True) -> ToolScore:
    """Score one system's tool use. ``reports_calls`` is False for a system with no tool-call report."""
    if not reports_calls:
        gone = NotObservable(NO_CALLS_REASON)
        return ToolScore(len(observations), gone, gone, gone, gone, gone, gone, gone, gone, gone, gone, ())
    required = [0, 0]
    unnecessary = [0, 0]
    valid = [0, 0]
    used = [0, 0]
    reversal = [0, 0]
    bounded = [0, 0]
    over = 0
    interpreted = [0, 0]
    flagged_right = flagged = mandated = mandated_met = 0
    escalation_known = False
    malformed: list[MalformedCall] = []
    for obs in observations:
        exp, calls = obs.expectation, obs.calls
        names = {c.name for c in calls}
        required[1] += len(exp.required_tools)
        required[0] += len(exp.required_tools & names)
        seen: set[tuple[str, str | None]] = set()
        for call in calls:
            unnecessary[1] += 1
            key = (call.name, call.arguments)
            unnecessary[0] += call.name not in exp.required_tools or key in seen
            seen.add(key)
            if call.arguments is not None:
                valid[1] += 1
                reason = check_arguments(call, exp)
                valid[0] += reason is None
                if reason is not None:
                    malformed.append(MalformedCall(obs.question_id, call, reason))
        succeeded = {c.name for c in calls if c.status in OK_STATUSES}
        if exp.supporting_evidence and exp.required_tools & succeeded:
            used[1] += 1
            used[0] += bool(exp.supporting_evidence & set(obs.response.used_evidence_ids))
        if exp.first_retrieval_irrelevant and calls:
            reversal[1] += 1
            reversal[0] += any(c.name != calls[0].name and c.status in OK_STATUSES for c in calls[1:])
        excess, checked = _over_budget(obs)
        if checked:
            bounded[1] += 1
            bounded[0] += excess == 0
            over += excess
        if any(c.status in FAILED_STATUSES for c in calls):
            interpreted[1] += 1
            text = "\n".join([obs.response.answer_text, *(c.text for c in obs.response.claims)])
            interpreted[0] += obs.response.evidence_status in HONEST_STATUSES and not any(
                fold(phrase) in fold(text) for phrase in exp.negative_phrases
            )
        if obs.escalated is not None:
            escalation_known = True
            flagged += obs.escalated
            flagged_right += obs.escalated and exp.escalation_required is True
        if exp.escalation_required is True and obs.escalated is not None:
            mandated += 1
            mandated_met += obs.escalated
    no_args = NotObservable(NO_ARGUMENTS_REASON)
    no_models = NotObservable(NO_INVOCATIONS_REASON)
    no_escalation = NotObservable("the system does not say whether it escalated")
    return ToolScore(
        questions=len(observations),
        selection_recall=Rate(*required),
        unnecessary_invocation=Rate(*unnecessary),
        argument_validity=Rate(*valid) if valid[1] else no_args,
        result_utilization=Rate(*used),
        discovery_reversal=Rate(*reversal),
        boundedness=Rate(*bounded) if bounded[1] else no_models,
        over_budget_calls=over if bounded[1] else no_models,
        failure_interpretation=Rate(*interpreted),
        escalation_precision=Rate(flagged_right, flagged) if escalation_known else no_escalation,
        escalation_recall=Rate(mandated_met, mandated) if escalation_known else no_escalation,
        malformed=tuple(malformed),
    )


def _over_budget(obs: ToolObservation) -> tuple[int, bool]:
    """Calls beyond each cap, and whether any cap could be checked."""
    exp, response = obs.expectation, obs.response
    excess, checked = 0, False
    invocations = response.model_invocations
    for cap, used in (
        (exp.max_model_calls, None if invocations is None else invocations.main),
        (exp.max_critic_calls, None if invocations is None else invocations.critic),
    ):
        if cap is not None and used is not None:
            checked, excess = True, excess + max(0, used - cap)
    if exp.max_tool_calls is not None:
        checked, excess = True, excess + max(0, len(obs.calls) - exp.max_tool_calls)
    return excess, checked
