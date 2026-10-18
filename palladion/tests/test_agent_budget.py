"""Deterministic guards, explicitly separate from real Groq integration proof."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from evidence_agent.agent.draft import Draft
from evidence_agent.agent.llm import GroqModel, ModelFailure, ModelTurn
from evidence_agent.agent.loop import AgentRuntime, Budget, BudgetExceeded, new_trace
from evidence_agent.agent.preflight import preflight
from evidence_agent.agent.tools import Tools, definitions
from evidence_agent.core.errors import DependencyUnavailable
from evidence_agent.live.contracts import Snapshot
from evidence_agent.live.gateway import LiveGateway
from evidence_agent.live.mock import MockAdapter
from evidence_agent.memory.store import CaseStore
from evidence_agent.retrieval.evidence import RequestLedger
from evidence_agent.retrieval.hybrid import HybridSearch
from evidence_agent.settings import Settings
from evidence_agent.storage.catalog import Catalog


class UnavailableIndex:
    fingerprint = "a" * 64

    def query(self, *args, **kwargs):
        raise DependencyUnavailable

    def readback(self, *args, **kwargs):
        raise DependencyUnavailable


class ScriptedModel:
    """Invalid-output injection only; never a runtime or provider smoke substitute."""

    def __init__(self, turns, delay=0):
        self.turns, self.delay, self.calls, self.cancelled = list(turns), delay, [], False

    async def complete(self, messages, tools, *, final=False):
        self.calls.append(final)
        try:
            await asyncio.sleep(self.delay)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        item = self.turns.pop(0) if self.turns else {"content": Draft().model_dump_json()}
        if isinstance(item, Exception):
            raise item
        return ModelTurn(item, {"total_tokens": 1})


def make_runtime(p03, model=None, **settings):
    search = HybridSearch(Catalog(p03.registry), UnavailableIndex())
    store = CaseStore(p03.registry, p03.reader, "case-42")
    ledger = RequestLedger(
        search,
        p03.reader,
        "case-42",
        new_trace(),
        {k: v.max_age_seconds for k, v in p03.config.operations.items()},
    )
    adapter = MockAdapter(
        {
            ("get_transaction_status", "TX-DEMO-102"): (
                Snapshot(
                    status="OK",
                    data={
                        "transaction_id": "TX-DEMO-102",
                        "state": "FAILED",
                        "transaction_occurred_at": "2026-08-15T10:20:00Z",
                    },
                ),
            )
        }
    )
    gateway = LiveGateway(p03.registry, adapter, p03.config)
    tools = Tools(ledger, gateway, store)
    runtime = AgentRuntime(model, tools, store, Settings(**settings))
    return SimpleNamespace(
        runtime=runtime, tools=tools, ledger=ledger, store=store, adapter=adapter
    )


def tool_turn(name, args, number=1):
    return {
        "tool_calls": [
            {
                "id": "call" + str(number),
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }
        ]
    }


def test_budget_reserves_final_and_never_sixth():
    b = Budget()
    for _ in range(4):
        b.model()
    with pytest.raises(BudgetExceeded):
        b.model()
    b.model(final=True)
    with pytest.raises(BudgetExceeded):
        b.model(final=True)
    assert b.main_used == 5


def test_malformed_and_failed_attempts_count_and_finalize(p03):
    model = ScriptedModel(
        [
            {"content": "bad JSON"},
            {"content": "still invalid JSON"},
            {"content": "{} extra"},
            {"content": "bad"},
            {"content": "bad final"},
        ]
    )
    runtime = make_runtime(p03, model)
    result = asyncio.run(runtime.runtime.answer("Investigate this case"))
    assert model.calls == [False, False, False, False, True]
    assert result["budget"]["main_used"] == 5
    assert result["disposition"] == "VERIFICATION_UNAVAILABLE"
    assert result["verified_claims"] == []
    attempts = runtime.store.recent(limit=20)
    assert sum(e["payload"].get("status") == "STARTED" for e in attempts) == 5


def test_four_tools_and_nonexclusive_zero_call_preflight(p03):
    fixture = make_runtime(p03)
    assert {d["function"]["name"] for d in definitions()} == {
        "search_knowledge",
        "evaluate_policy",
        "lookup_live_data",
        "recall_memory",
    }
    greeting = preflight("thanks", fixture.store)
    mixed = preflight("TX-DEMO-102 rule and status", fixture.store)
    assert greeting["prefetched"] == greeting["suggestions"] == []
    assert mixed["llm_calls"] == 0 and not mixed["routing_is_exclusive"]
    assert mixed["authorized_targets"]["get_transaction_status"] == "TX-DEMO-102"


def test_parallel_tool_cap_and_missing_provider(p03):
    b = Budget(tool_max=3)

    async def run():
        async def reserve():
            try:
                b.tool()
                return True
            except BudgetExceeded:
                return False

        return await asyncio.gather(*(reserve() for _ in range(20)))

    assert sum(asyncio.run(run())) == 3 and b.tools_used == 3
    result = asyncio.run(make_runtime(p03).runtime.answer("Investigate"))
    assert result["budget"]["main_used"] == 0
    assert result["disposition"] == "VERIFICATION_UNAVAILABLE"


def test_deadline_cancels_model_and_persists(p03):
    model = ScriptedModel([], delay=5)
    fixture = make_runtime(p03, model, request_timeout_seconds=1)
    result = asyncio.run(fixture.runtime.answer("Investigate"))
    assert model.cancelled and len(model.calls) == 1
    assert result["disposition"] == "VERIFICATION_UNAVAILABLE"
    assert any(e["payload"].get("status") == "CANCELLED" for e in fixture.store.recent(limit=20))


def test_explicit_cancellation_stops_pending_adapter(p03):
    model = ScriptedModel(
        [
            tool_turn(
                "lookup_live_data",
                {"operation": "get_transaction_status", "target_id": "TX-DEMO-102"},
            )
        ]
    )
    fixture = make_runtime(p03, model)
    fixture.adapter.delay_seconds = 5

    async def run():
        task = asyncio.create_task(fixture.runtime.answer("Investigate"))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    assert fixture.adapter.cancelled == 1
    assert any(e["kind"] == "RUNTIME_CANCELLED" for e in fixture.store.recent(limit=20))


def test_credentials_not_read_until_enabled(tmp_path):
    with pytest.raises(PermissionError):
        GroqModel.from_env_file(tmp_path / "absent", enabled=False)


def test_provider_failure_stops_exploration_without_free_retry(p03):
    model = ScriptedModel([ModelFailure("PROVIDER_HTTP_429"), ModelFailure("PROVIDER_HTTP_429")])
    result = asyncio.run(make_runtime(p03, model).runtime.answer("Investigate"))
    assert model.calls == [False, True]
    assert result["budget"]["main_used"] == 2
    assert result["verification_failures"] == ["PROVIDER_HTTP_429"]
    assert result["disposition"] == "VERIFICATION_UNAVAILABLE"


def test_excess_parallel_proposals_are_persisted_rejections_not_free_dispatches(p03):
    calls = [tool_turn("recall_memory", {}, number)["tool_calls"][0] for number in range(4)]
    fixture = make_runtime(p03, ScriptedModel([{"tool_calls":calls}]), tool_max_calls=2)
    result = asyncio.run(fixture.runtime.answer("Recall this case"))
    assert result["budget"]["tools_used"] == 2
    assert result["budget"]["main_used"] == 2
    assert "TOOL_BUDGET_EXHAUSTED" in result["verification_failures"]
    failures = [event for event in fixture.store.recent(limit=20)
                if event["kind"] == "RUNTIME_TOOL_RESULT" and event["payload"]["status"] == "FAILED"]
    assert len(failures) == 2


def test_duplicate_native_tool_ids_rejected_before_any_dispatch(p03):
    call = tool_turn("recall_memory", {})["tool_calls"][0]
    fixture = make_runtime(p03, ScriptedModel([{"tool_calls":[call,call]}]))
    result = asyncio.run(fixture.runtime.answer("Recall"))
    assert result["budget"]["tools_used"] == 0
    assert "MODEL_OR_SCHEMA_FAILURE" in result["verification_failures"]


@pytest.mark.parametrize("function", [
    {"name": [], "arguments": "{}"}, {"name": "recall_memory", "arguments": {}},
    {"name": "x" * 101, "arguments": "{}"},
])
def test_malformed_native_function_types_are_counted_without_dispatch(p03, function):
    fixture = make_runtime(p03, ScriptedModel([{"tool_calls": [
        {"id": "bad-call", "type": "function", "function": function}]}]))
    response = asyncio.run(fixture.runtime.answer("Recall"))
    assert response["budget"]["tools_used"] == 0
    assert response["budget"]["main_used"] <= 5
    assert "MODEL_OR_SCHEMA_FAILURE" in response["verification_failures"]


def test_tool_result_returns_matching_native_name_and_id_to_model(p03):
    seen = []
    class RecordingModel(ScriptedModel):
        async def complete(self, messages, tools, *, final=False):
            seen.extend(m for m in messages if m.get("role") == "tool")
            return await super().complete(messages, tools, final=final)
    turn = tool_turn("recall_memory", {})
    model = RecordingModel([turn, {"content": "{}"}, {"content": "{}"}])
    fixture = make_runtime(p03, model)
    response = asyncio.run(fixture.runtime.answer("Recall"))
    assert response["budget"]["tools_used"] == 1
    assert seen and seen[0]["name"] == "recall_memory"
    assert seen[0]["tool_call_id"] == turn["tool_calls"][0]["id"]
    assert json.loads(seen[0]["content"])["status"] == "SUCCEEDED"
