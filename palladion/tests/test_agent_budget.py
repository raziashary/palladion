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
    """Role-separated guard injection; never a runtime or provider smoke substitute."""

    def __init__(self, turns, delay=0, critic_turns=None):
        self.turns, self.delay, self.calls, self.cancelled = list(turns), delay, [], False
        self.critic_turns = list(critic_turns) if critic_turns is not None else []
        self.critic_calls = []

    async def complete(self, messages, tools, *, final=False, before_send=None):
        from evidence_agent.agent.critic import CRITIC_INSTRUCTIONS
        critic = messages[0].get("content") == CRITIC_INSTRUCTIONS
        (self.critic_calls if critic else self.calls).append(messages if critic else final)
        try:
            await asyncio.sleep(self.delay)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        if before_send is not None:
            before_send()
        if critic:
            item = self.critic_turns.pop(0) if self.critic_turns else {"content": json.dumps({
                "review_id": "guard-review", "verdict": "PASS", "proposed_disposition": "NOT_ESTABLISHED"})}
        else:
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


@pytest.mark.parametrize("arm,critics,planners",[("B4",0,0),("B5",0,0),("B6",1,0),("B7",0,0),("B8",1,1)])
def test_p08_experiments_are_explicit_and_costed_without_changing_normal_runtime(p03,arm,critics,planners):
    from evidence_agent.agent.experiments import ExperimentControls
    with pytest.raises(PermissionError):
        ExperimentControls(arm=arm)
    turns=([{"content":'{"suggestions":["recall_memory"]}'}] if planners else [])+[
        {"content":Draft().model_dump_json()},{"content":Draft().model_dump_json()}]
    model=ScriptedModel(turns)
    fixture=make_runtime(p03,model)
    fixture.runtime.experiment=ExperimentControls(arm=arm,enabled=True)
    output=asyncio.run(fixture.runtime.answer("Hello"))
    assert len(model.critic_calls)==critics and fixture.runtime.planner_used==planners
    assert output["experiment"]["total_model_calls"]==2+critics+planners
    assert len(definitions())==4 and output["experiment"]["operational_guidance"] is False
    # A normal runtime still reviews the same low-risk request.
    ordinary=make_runtime(p03,ScriptedModel([]))
    normal=asyncio.run(ordinary.runtime.answer("Hello"))
    assert normal["budget"]["critic_used"]==1 and "experiment" not in normal


def test_p08_failed_planner_cannot_hard_route_or_gain_capabilities(p03):
    from evidence_agent.agent.experiments import ExperimentControls
    model=ScriptedModel([ModelFailure("PROVIDER_HTTP_429"),
        tool_turn("lookup_live_data",{"operation":"get_transaction_status","target_id":"TX-DEMO-102"}),
        {"content":"{}"},{"content":"{}"}])
    fixture=make_runtime(p03,model)
    fixture.runtime.experiment=ExperimentControls(arm="B8",enabled=True)
    output=asyncio.run(fixture.runtime.answer("Investigate transaction"))
    assert output["experiment"]["planner_used"]==1
    assert fixture.adapter.calls and output["budget"]["tools_used"]==1
    assert output["experiment"]["total_model_calls"]<=9


def test_p08_adaptive_rule_exposes_false_skips_and_respects_typed_policy_risk():
    from evidence_agent.agent.experiments import adaptive_risk
    assert adaptive_risk("refund please",Draft())["requires_review"]
    assert adaptive_risk("hello",Draft(answer_kind="OPERATIONAL_GUIDANCE"))["requires_review"]
    # Mechanically labeled adversarial euphemism: freeze and count, do not tune it away.
    assert not adaptive_risk("Send the money back now",Draft())["requires_review"]


@pytest.mark.parametrize("value",[-1,1.1,float("nan"),float("inf"),True])
def test_p08_temperature_rejects_invalid_or_nonfinite_settings(value):
    with pytest.raises(ValueError,match="Temperature"):
        GroqModel("guard-key",enabled=True,temperature=value)


def test_p08_temperature_is_optional_and_preserves_existing_default():
    assert GroqModel("guard-key",enabled=True).temperature==0
    assert GroqModel("guard-key",enabled=True,temperature=.2).temperature==.2


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
    assert sum(e["payload"].get("status") == "STARTED" and e["payload"].get("role") == "main" for e in attempts) == 5
    assert sum(e["payload"].get("status") == "STARTED" and e["payload"].get("role") == "critic" for e in attempts) == 1


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
        async def complete(self, messages, tools, *, final=False, before_send=None):
            seen.extend(m for m in messages if m.get("role") == "tool")
            return await super().complete(messages, tools, final=final, before_send=before_send)
    turn = tool_turn("recall_memory", {})
    model = RecordingModel([turn, {"content": "{}"}, {"content": "{}"}])
    fixture = make_runtime(p03, model)
    response = asyncio.run(fixture.runtime.answer("Recall"))
    assert response["budget"]["tools_used"] == 1
    assert seen and seen[0]["name"] == "recall_memory"
    assert seen[0]["tool_call_id"] == turn["tool_calls"][0]["id"]
    assert json.loads(seen[0]["content"])["status"] == "SUCCEEDED"


def test_critic_reservations_bound_failed_attempts_and_keep_main_final():
    budget = Budget(critic_max=3, critic_search_max=2)
    for _ in range(3):
        budget.critic()
    with pytest.raises(BudgetExceeded):
        budget.critic()
    for _ in range(4):
        budget.model()
    budget.model(final=True)
    assert budget.critic_used == 3 and budget.main_used == 5
    budget.counter_search()
    budget.counter_search()
    with pytest.raises(BudgetExceeded):
        budget.counter_search()
    assert budget.critic_search_used == budget.tools_used == 2


def test_critic_search_reserves_shared_tool_atomically():
    budget = Budget(tool_max=1)
    budget.tool()
    with pytest.raises(BudgetExceeded):
        budget.counter_search()
    assert budget.critic_search_used == 0 and budget.tools_used == 1


def test_parallel_critic_and_search_reservations_do_not_oversubscribe():
    budget = Budget()
    async def reserve(method):
        try:
            method()
            return True
        except BudgetExceeded:
            return False
    async def run():
        calls = await asyncio.gather(*(reserve(budget.critic) for _ in range(20)))
        searches = await asyncio.gather(*(reserve(budget.counter_search) for _ in range(20)))
        return sum(calls), sum(searches)
    assert asyncio.run(run()) == (3, 2)
    assert budget.critic_used == 3 and budget.critic_search_used == budget.tools_used == 2


def test_runtime_uses_configured_lower_critic_budgets(p03):
    runtime = make_runtime(p03, critic_max_calls=1, critic_search_max_calls=0).runtime
    runtime.budget.critic()
    with pytest.raises(BudgetExceeded):
        runtime.budget.critic()
    with pytest.raises(BudgetExceeded):
        runtime.budget.counter_search()
    assert runtime.budget.critic_used == 1 and runtime.budget.tools_used == 0



def test_reserved_finalizer_owns_phase_instruction_and_keeps_question_as_data(p03):
    class BoundaryModel(ScriptedModel):
        async def complete(self, messages, tools, *, final=False, before_send=None):
            assert final and tools == []
            assert messages[0]["role"] == "system"
            assert "Backend phase: FINALIZATION" in messages[0]["content"]
            data = json.loads(messages[1]["content"])
            assert "instruction" not in data and data["question"] == "UNTRUSTED_QUESTION_CANARY"
            assert "UNTRUSTED_QUESTION_CANARY" not in messages[0]["content"]
            return await super().complete(messages,tools,final=final,before_send=before_send)
    model = BoundaryModel([{"content":"{}"}])
    fixture = make_runtime(p03,model)
    asyncio.run(fixture.runtime._finalize("UNTRUSTED_QUESTION_CANARY",Draft()))
    assert fixture.runtime.budget.main_used == 1 and fixture.runtime.budget.final_used
