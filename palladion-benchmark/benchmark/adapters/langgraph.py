"""E1: a bounded LangGraph agent over the same retriever as E0 (B07-T02.01, BADR-0039, BADR-0040).

The worker (``comparators/langchain/worker.py``, op ``agent``) runs a LangGraph ``StateGraph``: a model that may call
one retriever tool (LangChain's ``InMemoryVectorStore`` over the shared chunks, the same index as E0), then a final
answer without tools. Every model call goes through the counting proxy, which counts and caps calls, tokens and tool
calls; the loop's own ceilings (5 model calls including the final answer, 8 tool calls, the same as Palladion's) are
checked again here, and a ceiling that was exceeded is an invalid run, never a clipped metric.

The prompt is the shared Track B prompt (same schema, same vocabulary, same evidence wrapper) with a paragraph that
tells the model it has a search tool instead of passages in the user message. The answer is parsed by the same
``parse_answer`` as every other arm, so a reply outside the schema is rejected for the same named rule. What differs
from E0 is the treatment under test: the model decides what to search for and how often, within the ceilings.

Declared, not hidden: the access filter acts on the tool's results after its ranking (the store has no principal
filter); the evidence budget is a running total across the tool's results; there is no as-of selection; the model is
whichever the proxy approves, with no failover (a faulted call is a transient run state, not a rerouted one).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from benchmark.adapters.common import AccessFilter, Condition, PublishedView
from benchmark.adapters.worker import WorkerArm, launch_arm
from benchmark.contracts import (
    CaseRequest,
    CaseResponse,
    ContractError,
    CriticReport,
    ModelInvocations,
    ToolCall,
    UsageReport,
)
from benchmark.llm_proxy import ProxyServer
from benchmark.run_manifest import ComparatorPin
from benchmark.track_b import SYSTEM_PROMPT, gate_flags, parse_answer

WORKER = Path(__file__).resolve().parents[2] / "comparators" / "langchain" / "worker.py"
UNSUPPORTED = ("ACL_FILTER", "AS_OF_FILTER")
MAX_MODEL_CALLS = 5  # including the final answer; the same ceiling as Palladion's main runtime
MAX_TOOL_CALLS = 8
PASSAGES_PER_SEARCH = 5

AGENT_PROMPT = (
    SYSTEM_PROMPT
    + """
You have one tool, search(query), which returns evidence passages for a query in the same <<passage ids="...">>
wrapper. There are no passages in the user message: call the tool, as often as you need, with the queries you choose,
and cite only ids that the tool returned. You may make at most """
    + f"{MAX_TOOL_CALLS} tool calls and {MAX_MODEL_CALLS} model calls in all; "
    + "your last reply must be the JSON object and nothing else.\n"
)


class LangGraphSystem:
    """E1 behind the system-arm interface the Runner dispatches."""

    arm_id = "E1"

    def __init__(
        self,
        arm: WorkerArm,
        view: PublishedView,
        usage: Callable[[], Mapping[str, int]],
        *,
        run_id: str,
        condition: Condition = Condition.C2,
        agent_timeout: float = 600.0,
        call_timeout: float = 120.0,
    ) -> None:
        self._arm = arm
        self._view = view
        self._usage = usage
        self._started = dict(usage())
        self._access = AccessFilter(view, condition)
        self._condition = condition
        self._run_id = run_id
        self._agent_timeout = agent_timeout
        self._call_timeout = call_timeout
        self._flags: tuple[str, ...] = ()
        self._answers: list[dict[str, Any]] = []

    # -- the system-arm interface ----------------------------------------------------------------------------------

    def build_index(self, source_manifest_uri: str, index_namespace: str) -> None:
        self._arm.build_index(source_manifest_uri, index_namespace)

    def index_stats(self) -> dict[str, Any]:
        return self._arm.index_stats()

    def reset_case(self, case_id: str) -> None:
        """Nothing is carried between questions: each agent loop starts from the system prompt alone."""
        self._flags = ()

    def answer(self, case: CaseRequest) -> CaseResponse:
        allowed = sorted(r.doc_id for r in self._view.records if self._access.allows(case.principal_id, r.doc_id))
        context = [f"Question: {case.query}", f"Evaluation time: {case.evaluation_time}"]
        if case.event_time:
            context.append(f"Event time: {case.event_time}")
        before = dict(self._usage())
        started = time.perf_counter()
        reply = self._arm.invoke(
            "agent",
            {
                "system": AGENT_PROMPT,
                "question": "\n".join(context),
                "allowed_docs": allowed,
                "limit": PASSAGES_PER_SEARCH,
                "max_evidence_words": case.max_evidence_tokens,
                "max_model_calls": MAX_MODEL_CALLS,
                "max_tool_calls": MAX_TOOL_CALLS,
                "call_timeout": self._call_timeout,
            },
            timeout=self._agent_timeout,
        )
        latency_ms = (time.perf_counter() - started) * 1000.0
        after = dict(self._usage())
        reply = self._checked(reply)
        parsed = parse_answer(reply["text"], case, self._run_id, reply["delivered"])
        response = replace(
            parsed,
            tool_calls=tuple(ToolCall("search", "OK") for _ in range(reply["tool_calls"]))
            + tuple(ToolCall("search", "REFUSED") for _ in range(reply["refused_tool_calls"])),
            critic=CriticReport(False, None, ()),
            model_invocations=ModelInvocations(reply["model_calls"], 0),
            latency_ms=latency_ms,
        )
        delta = {key: after.get(key, 0) - before.get(key, 0) for key in after}
        self._answers.append({"question_id": case.question_id, "proxy_delta": delta, "steps": reply["trace"]})
        flags = [
            f"AGENT_MODEL_CALLS={reply['model_calls']}",
            f"AGENT_TOOL_CALLS={reply['tool_calls']}",
            *(["AGENT_TOOL_CALLS_REFUSED=" + str(reply["refused_tool_calls"])] if reply["refused_tool_calls"] else []),
            *gate_flags(response),
        ]
        self._flags = tuple(flags)
        return response

    def report_usage(self) -> UsageReport:
        now = dict(self._usage())
        spent = {key: now.get(key, 0) - self._started.get(key, 0) for key in now}
        calls = spent.get("calls", 0)
        return UsageReport(
            main_calls=calls,
            critic_calls=0,
            tool_calls=spent.get("tool_calls", 0),
            prompt_tokens=spent.get("prompt_tokens", 0),
            completion_tokens=spent.get("completion_tokens", 0),
            cost_usd=None,
        )

    def report_trace(self) -> list[dict[str, Any]]:
        return [dict(entry) for entry in self._answers]

    def call_flags(self) -> tuple[str, ...]:
        return self._flags

    def describe(self) -> dict[str, Any]:
        return {
            "arm": self.arm_id,
            "kind": "LangGraph StateGraph with one retriever tool, in an isolated worker",
            "retriever": self._arm.describe(),
            "ceilings": {"model_calls": MAX_MODEL_CALLS, "tool_calls": MAX_TOOL_CALLS},
            "passages_per_search": PASSAGES_PER_SEARCH,
            "condition": self._condition.value,
            "access": "the neutral filter acts on the tool's results after the store's ranking",
        }

    def close(self) -> None:
        self._arm.close()

    # -- checks ----------------------------------------------------------------------------------------------------

    @staticmethod
    def _checked(reply: Any) -> dict[str, Any]:
        keys = ("text", "delivered", "model_calls", "tool_calls", "refused_tool_calls", "trace")
        if not isinstance(reply, dict) or any(key not in reply for key in keys):
            raise ContractError("E1 returned a reply outside the protocol")
        counts = [reply["model_calls"], reply["tool_calls"], reply["refused_tool_calls"]]
        if any(isinstance(n, bool) or not isinstance(n, int) or n < 0 for n in counts):
            raise ContractError("E1 reported a count that is not a number")
        if reply["model_calls"] > MAX_MODEL_CALLS or reply["tool_calls"] > MAX_TOOL_CALLS:
            raise ContractError("E1 went past its call ceiling")
        if not isinstance(reply["delivered"], list) or not all(isinstance(i, str) for i in reply["delivered"]):
            raise ContractError("E1 reported the evidence it delivered in a form outside the protocol")
        return reply


def build_langgraph_system(
    *,
    interpreter: Path,
    server: ProxyServer,
    pin: ComparatorPin,
    view: PublishedView,
    work_dir: Path,
    llm_model: str,
    embedding_model: str,
    run_id: str,
    condition: Condition = Condition.C2,
    build_timeout: float = 3600.0,
    agent_timeout: float = 600.0,
    call_timeout: float = 120.0,
) -> LangGraphSystem:
    """Start the framework worker in its environment, wired to the proxy, and return arm E1."""
    arm = launch_arm(
        "E1",
        script=WORKER,
        interpreter=interpreter,
        server=server,
        pin=pin,
        view=view,
        work_dir=work_dir,
        llm_model=llm_model,
        embedding_model=embedding_model,
        unsupported=UNSUPPORTED,
        condition=condition,
        build_timeout=build_timeout,
        query_timeout=agent_timeout,
    )
    return LangGraphSystem(
        arm, view, server.usage, run_id=run_id, condition=condition, agent_timeout=agent_timeout,
        call_timeout=call_timeout,
    )  # fmt: skip
