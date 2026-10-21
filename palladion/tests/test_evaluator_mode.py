"""Evaluator-only launcher mode (ADR-0100): the critic-off control arm and the evaluator report over HTTP.

The scripted model injects drafts to exercise the runtime and the report; it is not a provider or quality claim.
"""
import importlib.util
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from evidence_agent.agent.experiments import ExperimentControls, evaluator_capabilities
from evidence_agent.agent.services import configure_agent
from evidence_agent.api.schemas import MessageResponse
from evidence_agent.live.mock import MockAdapter
from evidence_agent.main import create_app
from evidence_agent.settings import Settings

from .test_agent_budget import ScriptedModel, UnavailableIndex

READER = {"Authorization": "Bearer reader-test"}


def client_for(p03, experiment=None, settings=None, critic_turns=None):
    root = Path(p03.registry.database.path).parent
    app = create_app(root, UnavailableIndex(), {"reader-test": "reader-a", "admin-test": "admin-a"})
    model = ScriptedModel([], critic_turns=critic_turns)
    configure_agent(app, model=model, adapter=MockAdapter({}), config=p03.config,
                    settings=settings or Settings(), experiment=experiment)
    return TestClient(app), app, model


def ask(client, query="hello"):
    response = client.post("/v1/cases/case-42/messages", headers=READER, json={"query": query})
    assert response.status_code == 200, response.text
    return response.json()


def test_ordinary_serving_has_the_critic_and_no_evaluator_fields(p03):
    client, app, model = client_for(p03)
    with client:
        data = ask(client)
    assert data["budget"]["critic_used"] == 1 and len(model.critic_calls) == 1
    assert set(data) == set(MessageResponse.model_fields) - {"experiment", "evaluator"}, "byte-identical field set"


def test_the_critic_off_arm_runs_no_critic_and_reports_what_it_did(p03):
    client, app, model = client_for(p03, ExperimentControls(arm="B5", enabled=True))
    with client:
        data = ask(client)
    assert data["budget"]["critic_used"] == 0 and model.critic_calls == []
    report = data["evaluator"]
    assert report["arm"] == "B5" and data["experiment"]["arm"] == "B5"
    assert [c["role"] for c in report["model_calls"]] == ["main", "main"]
    assert all(c["status"] == "RECEIVED" and c["prompt_tokens"] is None for c in report["model_calls"])
    assert report["critic_reviews"] == [] and report["initial_draft"]["origin"] in {"MODEL", "SAFE_TEMPLATE"}


def test_the_full_arm_runs_the_critic_and_reports_its_findings(p03):
    client, app, model = client_for(p03, ExperimentControls(arm="B6", enabled=True))
    with client:
        data = ask(client)
    assert data["budget"]["critic_used"] == 1 and len(model.critic_calls) == 1
    report = data["evaluator"]
    assert [c["role"] for c in report["model_calls"]] == ["main", "critic", "main"]
    [review] = report["critic_reviews"]
    assert review["verdict"] == "PASS" and review["proposed_disposition"] == "NOT_ESTABLISHED"


def test_the_report_carries_tool_calls_with_their_arguments_and_the_role_that_made_them(p03):
    queries = [{"content": None, "tool_calls": [{"id": "t1", "type": "function", "function": {
        "name": "search_knowledge", "arguments": json.dumps({"query": "refund exception", "limit": 3})}}]}]
    client, app, model = client_for(p03, ExperimentControls(arm="B5", enabled=True))
    model.turns = queries
    with client:
        data = ask(client, "refund exception")
    [call] = data["evaluator"]["tool_calls"]
    assert call["role"] == "main" and call["name"] == "search_knowledge"
    assert json.loads(call["arguments"]) == {"query": "refund exception", "limit": 3}
    assert call["arguments_truncated"] is False and call["status"] in {"SUCCEEDED", "FAILED"}


def test_a_rejected_tool_call_is_reported_with_its_reason(p03):
    client, app, model = client_for(p03, ExperimentControls(arm="B5", enabled=True),
                                    settings=Settings(tool_max_calls=1))
    model.turns = [{"content": None, "tool_calls": [
        {"id": "a", "type": "function", "function": {"name": "search_knowledge", "arguments": "{}"}},
        {"id": "b", "type": "function", "function": {"name": "search_knowledge", "arguments": "{}"}}]}]
    with client:
        data = ask(client)
    statuses = [c["status"] for c in data["evaluator"]["tool_calls"]]
    assert statuses.count("TOOL_BUDGET_EXHAUSTED") == 1 and len(statuses) == 2, "the over-budget call is visible"


@pytest.mark.parametrize("evaluator", [False, True])
def test_a_request_cannot_select_an_arm(p03, evaluator):
    client, app, model = client_for(p03, ExperimentControls(arm="B5", enabled=True) if evaluator else None)
    with client:
        for body in ({"query": "hello", "arm": "B4"}, {"query": "hello", "experiment": "B5"},
                     {"query": "hello", "evaluator": True}):
            response = client.post("/v1/cases/case-42/messages", headers=READER, json=body)
            assert response.status_code == 422
        assert model.calls == []


def test_the_capability_report_still_lists_every_bypass_as_unsupported():
    capabilities = evaluator_capabilities()
    assert capabilities["serving_bypass_supported"] is False
    assert set(capabilities["unsupported_controls"].values()) == {"FEATURE_NOT_SUPPORTED"}
    with pytest.raises(PermissionError):
        ExperimentControls(arm="B5")  # an arm needs explicit enablement
    with pytest.raises(PermissionError):
        ExperimentControls(arm="B3", enabled=True)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- the launcher


def load_serve():
    spec = importlib.util.spec_from_file_location("serve_script_p0", Path(__file__).parents[1] / "scripts/serve.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("argv", [
    ["--evaluator-arm", "B5"],
    ["--evaluator-arm", "B5", "--acknowledge-not-serving"],
    ["--evaluator-arm", "B5", "--enable-live-llm"],
    ["--acknowledge-not-serving"],
    ["--evaluator-arm", "B3", "--acknowledge-not-serving", "--enable-live-llm"],
])
def test_the_launcher_refuses_an_evaluator_arm_without_both_acknowledgements(argv):
    with pytest.raises(SystemExit) as caught:
        load_serve().parse_args(argv)
    assert caught.value.code == 2


def test_the_critic_free_memory_free_arm_also_turns_continuity_off():
    serve = load_serve()
    base = ["--enable-live-llm", "--acknowledge-not-serving"]
    assert serve.parse_args([*base, "--evaluator-arm", "B4"])[1].continuity_enabled is False
    assert serve.parse_args([*base, "--evaluator-arm", "B5"])[1].continuity_enabled is True
    assert serve.parse_args([])[1].continuity_enabled is True


def test_the_launcher_builds_the_app_with_the_fixed_arm_and_the_counted_transport(p03, monkeypatch):
    serve = load_serve()
    root = Path(p03.registry.database.path).parent
    (root / "demo_auth.json").write_text(json.dumps({"reader-test": "reader-a"}), encoding="utf-8")
    monkeypatch.setenv("BENCH_RUN_KEY", "run-token-canary")
    args, settings = serve.parse_args(["--root", str(root), "--enable-live-llm", "--key-env", "BENCH_RUN_KEY",
        "--model-base-url", "http://127.0.0.1:9/v1", "--evaluator-arm", "B5", "--acknowledge-not-serving"])
    app = serve.build_app(args, settings, UnavailableIndex(), None)
    services = app.state.agent_services
    assert services.experiment.arm == "B5" and services.model.endpoint == "http://127.0.0.1:9/v1/chat/completions"
    args, settings = serve.parse_args(["--root", str(root), "--enable-live-llm", "--key-env", "BENCH_RUN_KEY",
        "--model-base-url", "http://127.0.0.1:9/v1"])
    assert serve.build_app(args, settings, UnavailableIndex(), None).state.agent_services.experiment is None


def test_a_critic_counter_search_is_reported_as_the_critics_own_tool_call(p03):
    review = {"content": json.dumps({"review_id": "r1", "verdict": "PASS", "claim_reviews": [],
        "counter_searches": [{"query": "refund exception clause", "purpose": "concrete exception inquiry"}],
        "proposed_disposition": "NOT_ESTABLISHED"})}
    client, app, model = client_for(p03, ExperimentControls(arm="B6", enabled=True), critic_turns=[review])
    with client:
        data = ask(client)
    report = data["evaluator"]
    [search] = [c for c in report["tool_calls"] if c["role"] == "critic"]
    assert search["name"] == "search_knowledge" and "refund exception clause" in search["arguments"]
    assert report["critic_reviews"][0]["counter_search_queries"] == ["refund exception clause"]
    assert [c["role"] for c in report["model_calls"]].count("critic") == 2, "a new review follows the new evidence"
    assert data["budget"]["critic_search_used"] == 1
