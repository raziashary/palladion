"""Pure logic: policy drafts, streaming helpers, the process manager and the store."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from palladion_ui import policies
from palladion_ui import stack as stack_module
from palladion_ui.settings import Settings
from palladion_ui.stack import KEY_VARIABLE, Stack, StackError, palladion_command, read_groq_key
from palladion_ui.store import Store
from palladion_ui.streaming import Progress, reveal, sse, text_chunks
from tests.conftest import MODEL

CLAUSE = {"revision_id": "rev_a", "section_id": "s", "start_byte": 1, "end_byte": 9, "sha256": "a" * 64}


def draft(**changes: Any) -> dict[str, Any]:
    base = {"version_id": "v1", "family_id": "F.CHECK", "case_ids": ["case-42"], "time_basis": "EVALUATION_AT",
            "valid_from": "2026-01-01", "clauses": [CLAUSE], "default_outcome": "ESCALATE", "facts": [], "rules": []}
    return {**base, **changes}


# Policies -------------------------------------------------------------------------------------------------------

def fact(**changes: Any) -> dict[str, Any]:
    return {"name": "settlement_state", "operation": "get_settlement_status", "field": "settlement_state",
            "type": "enum", "allowed_values": [], "max_age_seconds": 300, **changes}


def rule(**changes: Any) -> dict[str, Any]:
    return {"id": "r1", "match": "all", "clause_index": 0, "outcome": "STOP",
            "conditions": [{"fact": "settlement_state", "operator": "eq", "value": "SETTLED"}], **changes}


def messages(d: dict[str, Any]) -> list[str]:
    return [p["message"] for p in policies.validate_draft(d)]


def test_a_complete_draft_has_no_problems():
    assert policies.validate_draft(draft(facts=[fact()], rules=[rule()])) == []


@pytest.mark.parametrize("changes,fragment", [
    ({"version_id": "no spaces"}, "Version ID"),
    ({"case_ids": []}, "case"),
    ({"time_basis": "WHENEVER"}, "date decides"),
    ({"time_basis": "DOMAIN_EVENT_AT"}, "Name the event"),
    ({"domain_event": "dispute_submitted"}, "Name the event"),
    ({"valid_from": "soon"}, "first day"),
    ({"valid_from": "2026-05-01", "valid_to": "2026-04-01"}, "after the first day"),
    ({"clauses": []}, "source"),
    ({"default_outcome": " "}, "no rule matches"),
])
def test_basic_mistakes_are_named_in_plain_words(changes, fragment):
    assert any(fragment in m for m in messages(draft(**changes))), messages(draft(**changes))


@pytest.mark.parametrize("facts,rules,fragment", [
    ([fact(name="Bad Name")], [], "lowercase name"),
    ([fact(), fact()], [], "used twice"),
    ([fact(operation="get_nothing")], [], "system and one of its fields"),
    ([fact(type="int")], [], "enum field"),
    ([fact(allowed_values=["BOGUS"])], [], "Not a value"),
    ([fact(max_age_seconds=0)], [], "between 1 second and 24 hours"),
    ([fact()], [rule(id="r1"), rule(id="r1")], "used twice"),
    ([fact()], [rule(conditions=[])], "at least one condition"),
    ([fact()], [rule(clause_index=4)], "source passage"),
    ([fact()], [rule(conditions=[{"fact": "ghost", "operator": "eq", "value": "x"}])], "not listed"),
    ([fact()], [rule(conditions=[{"fact": "settlement_state", "operator": "gt", "value": "x"}])], "cannot compare"),
    ([fact()], [rule(conditions=[{"fact": "settlement_state", "operator": "eq", "value": "MAYBE"}])], "can only be one of"),
    ([fact()], [rule(outcome="")], "what the rule decides"),
])
def test_fact_and_rule_mistakes_are_named_in_plain_words(facts, rules, fragment):
    found = messages(draft(facts=facts, rules=rules))
    assert any(fragment in m for m in found), found


def test_payload_types_values_by_their_fact_and_defaults_enum_values_to_all():
    payload = policies.to_payload(draft(
        facts=[fact(), fact(name="age", operation="get_incident_status", field="state", allowed_values=["OPEN"])],
        rules=[rule(match="any", conditions=[
            {"fact": "settlement_state", "operator": "in", "value": "SETTLED, PENDING"},
            {"fact": "age", "operator": "eq", "value": "OPEN"}])],
        valid_to="2027-01-01", time_basis="DOMAIN_EVENT_AT", domain_event=" dispute_submitted "))
    assert payload["required_facts"][0]["allowed_values"] == ["UNSETTLED", "PENDING", "SETTLED"]
    assert payload["required_facts"][1]["allowed_values"] == ["OPEN"]
    assert payload["rules"][0]["predicate"] == {"any": [
        {"field": "settlement_state", "operator": "in", "value": ["SETTLED", "PENDING"]},
        {"field": "age", "operator": "eq", "value": "OPEN"}]}
    assert payload["valid_to"] == "2027-01-01T00:00:00Z" and payload["domain_event"] == "dispute_submitted"
    assert set(payload["clauses"][0]) == {"revision_id", "section_id", "start_byte", "end_byte", "sha256"}


def test_every_operation_offers_only_fields_palladion_defines():
    assert {k: [f["name"] for f in v["fields"]] for k, v in policies.OPERATIONS.items()} == {
        "get_transaction_status": ["state"], "get_settlement_status": ["settlement_state"],
        "get_incident_status": ["state"], "get_merchant_summary": ["result"]}


# Streaming ------------------------------------------------------------------------------------------------------

def test_text_chunks_reassemble_exactly():
    text = "Approved source states:  “check both”  (attribution only)."
    assert "".join(text_chunks(text)) == text and len(text_chunks(text)) > 1 and text_chunks("") == []


def test_reveal_orders_the_verdict_first_and_the_details_last():
    response = {"disposition": "SUPPORTED", "answer": "Fine.", "verified_claims": [
        {"claim_id": "C1", "text": "One two three.", "evidence_ids": ["e1"]}], "hypotheses": [],
        "missing_requirements": ["gap"], "requirement_origins": {"gap": "POLICY_SCHEMA"},
        "citations": [{"evidence_id": "e1"}], "tool_status": {}, "review_status": "PASS"}

    async def collect() -> list[str]:
        return [e async for e in reveal(response, 0)]

    events = asyncio.run(collect())
    kinds = [e.split("\n")[0] for e in events]
    assert events[0].startswith('event: part\ndata: {"id": "verdict"') and '"SUPPORTED"' in events[0]
    assert kinds.count("event: delta") >= 3 and events[-1].startswith("event: part") and '"meta"' in events[-1]
    assert sse("x", {"a": "é"}) == 'event: x\ndata: {"a": "é"}\n\n'


def test_progress_shows_each_event_once_oldest_first_and_ignores_what_came_before():
    progress = Progress()
    progress.prime([{"event_id": "old", "kind": "TOOL_RESULT", "at": "1"}])
    batch = [{"event_id": "b", "kind": "TOOL_RESULT", "at": "3", "status": "SUCCEEDED"},
             {"event_id": "a", "kind": "TOOL_RESULT", "at": "2"}, {"event_id": "old", "kind": "X", "at": "0"}]
    first = progress.fresh(batch)
    assert [s["id"] for s in first] == ["a", "b"] and first[1]["detail"] == "SUCCEEDED"
    assert progress.fresh(batch) == []


# Process manager --------------------------------------------------------------------------------------------------

class FakeProcess:
    def __init__(self, command: list[str], **options: Any) -> None:
        self.command, self.options, self.dead, self.pid = command, options, False, 4242

    def poll(self) -> int | None:
        return 1 if self.dead else None


class Rig:
    def __init__(self, tmp: Path, *, live: bool = False, managed: bool = True) -> None:
        tmp.mkdir(parents=True, exist_ok=True)
        (tmp / ".env").write_text("OTHER=1\nGROQ_API_KEY =secret-value-123\n")
        self.settings = Settings(runtime_dir=tmp, managed=managed, env_file=tmp / ".env")
        self.spawned: list[FakeProcess] = []
        self.killed: list[FakeProcess] = []
        self.up = {self.settings.qdrant_url: True, f"{self.settings.upstream_url}/health/live": live,
                   f"{self.settings.upstream_url}/health/ready": live}

        def spawn(command: list[str], **options: Any) -> FakeProcess:
            process = FakeProcess(command, **options)
            self.spawned.append(process)
            self.up[f"{self.settings.upstream_url}/health/live"] = True
            self.up[f"{self.settings.upstream_url}/health/ready"] = True
            return process

        async def probe(url: str) -> bool:
            return self.up.get(url, False)

        self.stack = Stack(self.settings, spawn=spawn, probe=probe)  # type: ignore[arg-type]


@pytest.fixture
def rig(tmp_path, monkeypatch) -> Rig:
    made = Rig(tmp_path)
    monkeypatch.setattr(stack_module, "kill_tree", lambda process: made.killed.append(process))
    return made


def test_the_command_enables_a_model_only_when_one_is_chosen_and_never_carries_the_key(tmp_path):
    settings = Settings(runtime_dir=tmp_path)
    search_only = palladion_command(settings, None)
    assert "--enable-live-llm" not in search_only and "--model" not in search_only and "--rerank" in search_only
    live = palladion_command(settings, MODEL)
    assert live[live.index("--model") + 1] == MODEL and live[live.index("--key-env") + 1] == KEY_VARIABLE
    assert not any("secret" in part for part in live)
    assert str(settings.upstream_port) in live and settings.collection in live


def test_the_key_is_read_from_the_env_file_and_a_missing_one_explains_without_leaking(tmp_path):
    env = tmp_path / ".env"
    env.write_text("OTHER=1\nGROQ_API_KEY =  'abc123'  \n")
    assert read_groq_key(env) == "abc123"
    env.write_text("OTHER=1\n")
    with pytest.raises(StackError, match="No GROQ_API_KEY"):
        read_groq_key(env)
    with pytest.raises(StackError, match="could not be read"):
        read_groq_key(tmp_path / "missing")


def test_search_only_start_gets_no_key_and_a_model_start_gets_it_only_in_the_child_environment(rig):
    asyncio.run(rig.stack.start(None))
    assert rig.stack.state == "ready" and rig.stack.model is None
    assert KEY_VARIABLE not in rig.spawned[0].options["env"]
    rig.up[f"{rig.settings.upstream_url}/health/live"] = False  # the old process is gone before the new one starts
    asyncio.run(rig.stack.start(MODEL))
    assert rig.stack.state == "ready" and rig.stack.model == MODEL
    assert rig.spawned[1].options["env"][KEY_VARIABLE] == "secret-value-123"
    assert "secret-value-123" not in " ".join(rig.spawned[1].command)
    assert rig.killed == [rig.spawned[0]]  # a switch stops what this UI started, and only that


def test_an_unknown_model_or_an_unmanaged_ui_never_starts_anything(rig, tmp_path):
    with pytest.raises(StackError, match="not one Palladion allows"):
        asyncio.run(rig.stack.start("gpt-5"))
    with pytest.raises(StackError, match="not one Palladion allows"):
        rig.stack.begin("gpt-5")
    unmanaged = Rig(tmp_path / "u", managed=False)
    with pytest.raises(StackError, match="does not manage"):
        asyncio.run(unmanaged.stack.start(None))
    assert rig.spawned == [] and unmanaged.spawned == []


def test_a_port_held_by_someone_else_is_refused_not_taken_over(rig):
    rig.up[f"{rig.settings.upstream_url}/health/live"] = True  # a Palladion this UI did not start
    with pytest.raises(StackError, match="already in use"):
        asyncio.run(rig.stack.start(None))
    assert rig.stack.state == "error" and rig.spawned == []


def test_a_missing_key_is_an_error_state_with_a_reason_and_no_process(tmp_path):
    made = Rig(tmp_path)
    (tmp_path / ".env").write_text("NOTHING=1\n")
    with pytest.raises(StackError):
        asyncio.run(made.stack.start(MODEL))
    status = asyncio.run(made.stack.status())
    assert status["state"] == "error" and "GROQ_API_KEY" in status["error"] and made.spawned == []


def test_a_process_that_dies_while_starting_is_reported_not_waited_on(tmp_path, monkeypatch):
    made = Rig(tmp_path)
    monkeypatch.setattr(stack_module, "kill_tree", lambda process: made.killed.append(process))
    original = made.stack._spawn

    def dying(command, **options):
        process = original(command, **options)
        process.dead = True
        made.up[f"{made.settings.upstream_url}/health/live"] = False
        return process

    made.stack._spawn = dying
    with pytest.raises(StackError, match="stopped while starting"):
        asyncio.run(made.stack.start(None))
    assert made.stack.state == "error" and len(made.killed) == 1


def test_begin_reports_starting_immediately(rig):
    async def run() -> str:
        rig.stack.begin(MODEL)
        immediate = rig.stack.state
        await rig.stack._task
        return immediate

    assert asyncio.run(run()) == "starting" and rig.stack.state == "ready" and rig.stack.model == MODEL


def test_shutdown_stops_what_it_started(rig):
    asyncio.run(rig.stack.start(None))
    asyncio.run(rig.stack.shutdown())
    assert rig.killed == [rig.spawned[0]] and rig.stack.state == "stopped"


# Store ------------------------------------------------------------------------------------------------------------

def test_store_keeps_conversations_per_person_and_survives_a_restart(tmp_path):
    path = tmp_path / "state.json"
    store = Store(path)
    store.add_session("reader-a", "case-42", "sess_1")
    store.append_message("reader-a", "sess_1", {"role": "user", "text": "x" * 100})
    assert store.session("admin-a", "sess_1") is None
    assert store.sessions("reader-a")[0]["title"].endswith("…") and store.sessions("reader-a")[0]["message_count"] == 1
    again = Store(path)
    assert again.session("reader-a", "sess_1")["messages"][0]["text"] == "x" * 100


def test_a_damaged_state_file_is_set_aside_not_fatal(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{ not json")
    assert Store(path).sessions("reader-a") == []
    assert list(tmp_path.glob("state.damaged-*"))


def test_model_steps_and_requests_get_plain_progress_labels():
    from palladion_ui.streaming import describe
    assert describe({"kind": "RUNTIME_REQUEST"})["label"] == "Question received"
    assert describe({"kind": "RUNTIME_ATTEMPT", "status": "STARTED"})["label"] == "Asking the model"
    assert describe({"kind": "RUNTIME_ATTEMPT", "status": "RECEIVED"})["label"] == "Model replied"
    failed = describe({"kind": "RUNTIME_ATTEMPT", "status": "FAILED"})
    assert (failed["label"], failed["detail"]) == ("Model step", "FAILED")
    assert describe({"kind": "TOOL_RESULT", "status": "SUCCEEDED"})["detail"] == "SUCCEEDED"
