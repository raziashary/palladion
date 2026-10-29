"""What is on, what may be turned off, and what each choice does. The locked parts must stay locked."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from palladion_ui import stack as stack_module
from palladion_ui.power import (
    LOCKED,
    PowerOptions,
    dump_flat_yaml,
    load_flat_yaml,
    read_pins,
    report,
    supported_settings,
    write_settings,
)
from palladion_ui.settings import Settings
from palladion_ui.stack import palladion_command
from tests.conftest import MODEL
from tests.test_units import Rig

SETTINGS_YAML = """schema_version: "1.0"
provider: groq
model: qwen/qwen3.8-27b
enable_live_llm: false
qdrant_url: http://127.0.0.1:16333
qdrant_collection: knowledge_chunks_v1
bm25_profile: english
main_max_calls: 5
critic_max_calls: 3
tool_max_calls: 8
critic_search_max_calls: 2
graph_timeout_seconds: 2.0
request_timeout_seconds: 60
"""
SETTINGS_PY = """class Settings(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    continuity_enabled: StrictBool = True
    tool_max_calls: int = Field(default=8)
    critic_search_max_calls: int = Field(default=2)
    search_worker_mode: Literal["persistent", "per_request"] = "persistent"
"""
RERANK_PY = 'RERANKER_NAME = "Xenova/ms-marco-MiniLM-L-6-v2"\nDEFAULT_RERANK_CANDIDATES = 20\n'
EMBED_PY = 'MODEL_REPOSITORY = "Qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q"\n'


@pytest.fixture
def pal(tmp_path: Path) -> Settings:
    """A stand-in for the runtime's Palladion source tree: just the files the UI reads."""
    ui = Settings(runtime_dir=tmp_path, managed=True)
    for path, text in (("config/settings.yaml", SETTINGS_YAML), ("src/evidence_agent/settings.py", SETTINGS_PY),
                       ("src/evidence_agent/retrieval/rerank.py", RERANK_PY),
                       ("src/evidence_agent/retrieval/embeddings.py", EMBED_PY)):
        target = ui.app_dir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    return ui


# Options -----------------------------------------------------------------------------------------------------------

def test_the_default_is_full_power_and_nothing_is_called_reduced():
    options = PowerOptions()
    assert options.full and options.reductions() == []
    assert (options.rerank, options.critic, options.memory, options.persistent_search) == (True, True, True, True)
    assert (options.critic_searches, options.tool_budget) == (2, 8)


@pytest.mark.parametrize("bad", [{"critic_searches": 3}, {"critic_searches": -1}, {"tool_budget": 0}, {"tool_budget": 9},
                                 {"rerank": "yes"}, {"critic": 1}, {"tool_budget": True}, {"critic_searches": 1.5}])
def test_out_of_range_or_mistyped_options_are_refused(bad):
    with pytest.raises(ValueError):
        PowerOptions(**bad)


def test_unknown_options_are_refused_and_a_damaged_file_means_full_power(tmp_path):
    with pytest.raises(ValueError, match="Unknown option"):
        PowerOptions.from_dict({"critic": False, "disable_final_gate": True})  # there is no such switch
    path = tmp_path / "power.json"
    path.write_text("{ not json")
    assert PowerOptions.load(path).full
    path.write_text(json.dumps({"critic": False, "bogus": 1}))
    assert PowerOptions.load(path).full  # an invalid file is never a silently reduced setup
    PowerOptions(memory=False, tool_budget=3).save(path)
    assert PowerOptions.load(path) == PowerOptions(memory=False, tool_budget=3)


def test_reductions_name_exactly_what_is_turned_down():
    options = PowerOptions(rerank=False, critic=False, critic_searches=0, tool_budget=4)
    assert options.reductions() == ["reranker off", "independent review off", "critic counter-searches 0", "4 tool calls"]
    assert not options.full


# The command and the settings file ----------------------------------------------------------------------------------------

def test_cli_flags_follow_the_options_and_the_critic_arm_only_exists_with_a_model():
    assert PowerOptions().cli_args(MODEL) == ["--rerank"]
    assert PowerOptions(rerank=False).cli_args(MODEL) == []
    assert PowerOptions(critic=False).cli_args(MODEL) == ["--rerank", "--evaluator-arm", "B5", "--acknowledge-not-serving"]
    assert PowerOptions(critic=False).cli_args(None) == ["--rerank"]  # the arm needs a model; search-only has no critic


def test_the_launch_command_carries_the_settings_file_and_the_chosen_flags(tmp_path):
    ui = Settings(runtime_dir=tmp_path)
    command = palladion_command(ui, MODEL, PowerOptions(critic=False, rerank=False), tmp_path / "s.yaml")
    assert command[command.index("--settings") + 1] == str(tmp_path / "s.yaml")
    assert "--rerank" not in command and command[command.index("--evaluator-arm") + 1] == "B5"
    assert "--acknowledge-not-serving" in command and "--enable-live-llm" in command
    full = palladion_command(ui, MODEL, PowerOptions())
    assert "--rerank" in full and "--evaluator-arm" not in full  # full power is ordinary serving, no evaluator arm


def test_flat_yaml_round_trips_types_and_keeps_quoted_strings_as_strings(tmp_path):
    path = tmp_path / "flat.yaml"
    path.write_text(SETTINGS_YAML)
    values = load_flat_yaml(path)
    assert values["schema_version"] == "1.0" and values["enable_live_llm"] is False
    assert values["graph_timeout_seconds"] == 2.0 and values["main_max_calls"] == 5
    assert values["qdrant_url"] == "http://127.0.0.1:16333"
    path.write_text(dump_flat_yaml(values))
    assert load_flat_yaml(path) == values


def test_only_settings_this_palladion_accepts_are_written(pal):
    assert supported_settings(pal.app_dir) >= {"continuity_enabled", "tool_max_calls", "search_worker_mode"}
    options = PowerOptions(memory=False, tool_budget=3, critic_searches=1, persistent_search=False)
    written = load_flat_yaml(write_settings(pal, options))
    assert written["continuity_enabled"] is False and written["tool_max_calls"] == 3
    assert written["critic_search_max_calls"] == 1 and written["search_worker_mode"] == "per_request"
    assert written["qdrant_url"] == pal.qdrant_url and written["qdrant_collection"] == pal.collection
    assert written["main_max_calls"] == 5 and written["bm25_profile"] == "english"  # untouched Palladion values survive
    (pal.app_dir / "src/evidence_agent/settings.py").write_text("class Settings:\n    tool_max_calls: int = 8\n")
    older = load_flat_yaml(write_settings(pal, PowerOptions()))
    assert "search_worker_mode" not in older and "continuity_enabled" not in older  # an older Palladion forbids unknown keys


# The report ---------------------------------------------------------------------------------------------------------------

def items(rep, group):
    return {i["id"]: i for g in rep["groups"] if g["id"] == group for i in g["items"]}


def runtime(**overrides):
    return {"state": "ready", "model": MODEL, "qdrant": True, "api": True, **overrides}


def test_the_report_lists_the_real_models_and_marks_what_can_be_changed(pal):
    rep = report(pal, PowerOptions(), runtime(), neo4j_up=False)
    assert rep["full"] and rep["reductions"] == [] and rep["model"] == MODEL
    finding = items(rep, "finding")
    assert "paraphrase-multilingual-MiniLM" in finding["hybrid"]["detail"] and finding["hybrid"]["state"] == "locked"
    assert "ms-marco-MiniLM-L-6-v2" in finding["rerank"]["detail"] and "20 passages" in finding["rerank"]["detail"]
    assert finding["rerank"]["control"] == "toggle" and finding["rerank"]["state"] == "on"
    assert finding["graph"]["state"] == "unavailable" and "Neo4j" in finding["graph"]["detail"]
    thinking = items(rep, "thinking")
    assert thinking["critic"]["experiment"] is True and "not a serving mode" in thinking["critic"]["effect"]
    assert thinking["critic_searches"]["min"] == 0 and thinking["critic_searches"]["max"] == 2
    assert thinking["tool_budget"]["max"] == 8 and items(rep, "remembering")["memory"]["control"] == "toggle"


def test_every_control_says_what_turning_it_down_costs(pal):
    rep = report(pal, PowerOptions(), runtime(), neo4j_up=False)
    controls = [i for g in rep["groups"] for i in g["items"] if i.get("control")]
    assert {c["key"] for c in controls} == {"rerank", "persistent_search", "critic", "critic_searches", "tool_budget", "memory"}
    assert all(len(c["effect"]) > 20 for c in controls)


def test_the_locked_parts_have_no_control_and_match_palladions_own_list(pal):
    locked = items(report(pal, PowerOptions(), runtime(), neo4j_up=False), "locked")
    assert set(locked) == {key for key, _, _ in LOCKED}
    assert all(i["state"] == "locked" and "control" not in i for i in locked.values())
    experiments = Path(__file__).parents[2] / "palladion/src/evidence_agent/agent/experiments.py"
    if experiments.exists():  # Palladion's own statement of what it will not make optional
        source = experiments.read_text(encoding="utf-8")
        for key in ("final_gate", "current_acl", "canonical_source", "trusted_policy_time", "safe_parser"):
            assert f'"{key}"' in source, f"{key} is no longer in Palladion's mandatory boundaries"


def test_a_reduced_setup_is_called_reduced_and_search_only_has_no_agent(pal):
    rep = report(pal, PowerOptions(critic=False, memory=False), runtime(model=None), neo4j_up=True)
    assert not rep["full"] and rep["reductions"] == ["independent review off", "memory off"] and rep["model"] is None
    assert items(rep, "thinking")["model"]["state"] == "off"
    assert items(rep, "finding")["workers"]["state"] == "on" and "reachable here" in items(rep, "finding")["graph"]["detail"]
    old = Settings(runtime_dir=pal.runtime_dir / "empty")
    assert items(report(old, PowerOptions(), runtime(), False), "finding")["workers"]["state"] == "unavailable"


@pytest.mark.skipif(not (Settings().app_dir / "src/evidence_agent/settings.py").exists(), reason="no provisioned runtime")
def test_against_the_real_runtime_the_pins_and_settings_are_found():
    real = Settings()
    pins = read_pins(real.app_dir)
    assert pins["embedding"] and pins["reranker"] and pins["rerank_depth"]
    assert {"continuity_enabled", "tool_max_calls", "critic_search_max_calls"} <= supported_settings(real.app_dir)


# The process manager and the endpoints --------------------------------------------------------------------------------------

def test_a_restart_applies_persists_and_survives_a_new_manager(pal, monkeypatch):
    rig = Rig(pal.runtime_dir)
    monkeypatch.setattr(stack_module, "kill_tree", lambda process: rig.killed.append(process))
    rig.stack.settings = pal  # the settings with the stand-in source tree
    asyncio.run(rig.stack.start(MODEL, PowerOptions(critic=False, rerank=False, memory=False)))
    command = rig.spawned[0].command
    assert "--evaluator-arm" in command and "--rerank" not in command
    written = load_flat_yaml(Path(command[command.index("--settings") + 1]))
    assert written["continuity_enabled"] is False
    status = asyncio.run(rig.stack.status())
    assert status["options"]["critic"] is False and status["full_power"] is False
    assert "independent review off" in status["reductions"]
    assert stack_module.Stack(pal).options == PowerOptions(critic=False, rerank=False, memory=False)
    rig.up[f"{pal.upstream_url}/health/live"] = False
    asyncio.run(rig.stack.start(MODEL))  # no options given: what was chosen stays chosen
    assert "--evaluator-arm" in rig.spawned[1].command


def test_the_power_endpoint_and_a_partial_options_change(env):
    rep = env.client.get("/api/power").json()
    assert rep["full"] and [g["id"] for g in rep["groups"]] == ["finding", "thinking", "remembering", "locked", "health"]
    done = env.client.post("/api/runtime/options", json={"critic": False})
    assert done.status_code == 200
    model, options = env.stack.began[-1]
    assert model == MODEL and options == PowerOptions(critic=False)  # only what was sent changed
    env.client.post("/api/runtime/options", json={"rerank": False})
    assert env.stack.began[-1][1] == PowerOptions(critic=False, rerank=False)  # and earlier choices were kept
    again = env.client.get("/api/power").json()
    assert again["reductions"] == ["reranker off", "independent review off"]


@pytest.mark.parametrize("body", [{"critic_searches": 3}, {"tool_budget": 0}, {"disable_final_gate": True}, {"critic": "off"}])
def test_the_endpoint_refuses_bad_values_and_any_switch_for_a_locked_part(env, body):
    before = len(env.stack.began)
    assert env.client.post("/api/runtime/options", json=body).status_code == 422
    assert len(env.stack.began) == before
