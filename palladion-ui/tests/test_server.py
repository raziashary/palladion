"""The UI server against a fake Palladion: identity, conversations, streaming, evidence, ingestion, policies."""
from __future__ import annotations

import base64

import httpx
import pytest

from palladion_ui.upstream import UpstreamError
from tests.conftest import act_as, read_sse
from tests.fake_palladion import create_fake

QUESTION = {"case_id": "case-42", "query": "Can I reverse this payment?"}


# Identity -------------------------------------------------------------------------------------------------------

def test_bootstrap_never_carries_a_token_and_scopes_cases_to_the_person(env):
    body = env.client.get("/api/bootstrap")
    assert body.status_code == 200
    assert "tok-" not in body.text  # the browser holds a name, never Palladion's credential
    data = body.json()
    assert data["persona"]["id"] == "reader-a" and data["persona"]["can_approve"] is False
    assert [c["id"] for c in data["cases"]] == ["case-42"]
    assert {m["id"] for m in data["models"]} == {"openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b"}
    act_as(env, "admin-a")
    after = env.client.get("/api/bootstrap").json()
    assert after["persona"]["can_approve"] is True and {c["id"] for c in after["cases"]} == {"case-42", "case-43"}


def test_unknown_persona_is_refused_and_cross_site_writes_are_blocked(env):
    assert env.client.post("/api/persona", json={"persona": "root"}).status_code == 404
    assert env.client.post("/api/persona", json={"persona": "admin-a"}, headers={"X-Palladion-UI": ""}).status_code == 403
    assert env.client.get("/api/bootstrap", headers={"Host": "evil.example"}).status_code == 403


# Conversations and streaming ----------------------------------------------------------------------------------------

def test_a_turn_streams_progress_then_the_released_answer_in_order(env):
    with env.client.stream("POST", "/api/chat", json=QUESTION) as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        events = read_sse(response)
    names = [name for name, _ in events]
    assert names[0] == "start" and names[-1] == "done" and "error" not in names
    first_part = names.index("part")
    progress = [data for name, data in events[:first_part] if name == "progress"]
    assert len(progress) >= 3, "progress must arrive before the answer, while Palladion is still working"
    assert any(p["kind"] == "TOOL_RESULT" for p in progress)
    parts = [data for name, data in events if name == "part"]
    assert parts[0]["type"] == "disposition" and parts[0]["value"] == "PARTIALLY_SUPPORTED"
    assert [p["type"] for p in parts].count("claim") == 2
    assert {p["value"] for p in parts if p["type"] == "gap"} == {"settlement_state", "authorized_human_review"}
    assert parts[-1]["type"] == "meta" and parts[-1]["verification_failures"] == ["LIVE_UNAVAILABLE"]
    # The streamed sentences add up to exactly the released text.
    claim = next(p for p in parts if p["type"] == "claim")
    text = "".join(d["text"] for n, d in events if n == "delta" and d["id"] == f"claim:{claim['claim_id']}")
    assert text.startswith("Last observed mock_transaction_api state: FAILED")


def test_the_conversation_is_remembered_and_can_continue(env):
    with env.client.stream("POST", "/api/chat", json=QUESTION) as response:
        session_id = read_sse(response)[0][1]["session_id"]
    listed = env.client.get("/api/sessions", params={"case_id": "case-42"}).json()["sessions"]
    assert [s["id"] for s in listed] == [session_id] and listed[0]["title"] == "Can I reverse this payment?"
    saved = env.client.get(f"/api/sessions/{session_id}").json()
    assert [m["role"] for m in saved["messages"]] == ["user", "assistant"]
    assert saved["messages"][1]["response"]["disposition"] == "PARTIALLY_SUPPORTED"
    with env.client.stream("POST", "/api/chat", json={**QUESTION, "session_id": session_id}) as response:
        assert read_sse(response)[0][1]["session_id"] == session_id
    assert len(env.client.get(f"/api/sessions/{session_id}").json()["messages"]) == 4
    assert env.fake.state["calls"][-1][1]["session_id"] == session_id


def test_sessions_belong_to_one_person_and_one_of_their_cases(env):
    assert env.client.post("/api/chat", json={**QUESTION, "case_id": "case-43"}).status_code == 403
    assert env.client.post("/api/chat", json={**QUESTION, "session_id": "sess_" + "0" * 32}).status_code == 404
    created = env.client.post("/api/sessions", json={"case_id": "case-42"})
    assert created.status_code == 201
    session_id = created.json()["id"]
    act_as(env, "admin-a")
    assert env.client.get(f"/api/sessions/{session_id}").status_code == 404  # another person's conversation
    act_as(env, "reader-a")
    closed = env.client.post(f"/api/sessions/{session_id}/close", json={"case_id": "case-42"})
    assert closed.status_code == 200 and env.client.get(f"/api/sessions/{session_id}").json()["closed"] is True


def test_with_no_model_a_turn_is_a_plain_search_and_says_so(env):
    env.stack.model = None
    with env.client.stream("POST", "/api/chat", json=QUESTION) as response:
        events = read_sse(response)
    names = [n for n, _ in events]
    assert events[0][1]["mode"] == "search" and names == ["start", "search", "done"]
    assert events[1][1]["passages"][0]["citation_id"] == "chunk_sop2026"
    assert env.fake.state["calls"] == []  # no agent call was made


def test_a_refused_agent_turn_ends_with_a_readable_error_not_a_hang(env):
    # A Palladion started without a model answers 503 to messages, even if the UI believes an agent is ready.
    fake = create_fake(env.settings.data_root, agent=False)
    env.app.state.ctx.upstream.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=fake),
                                                          base_url="http://palladion")
    with env.client.stream("POST", "/api/chat", json=QUESTION) as response:
        events = read_sse(response)
    error = next(data for name, data in events if name == "error")
    assert error["status"] == 503 and "model menu" in error["message"]
    assert events[-1][0] == "done"
    saved = env.client.get("/api/sessions", params={"case_id": "case-42"}).json()["sessions"][0]["id"]
    assert env.client.get(f"/api/sessions/{saved}").json()["messages"][-1]["kind"] == "error"


# Evidence ---------------------------------------------------------------------------------------------------------

def test_evidence_is_read_through_palladion_under_the_callers_identity(env):
    document = env.client.get("/api/evidence/chunk_sop2026", params={"case_id": "case-42"})
    assert document.status_code == 200 and "S26-REVERSAL" in document.json()["text"]
    live = env.client.get("/api/evidence/live_tx1", params={"case_id": "case-42"}).json()
    assert live["data"] == {"state": "FAILED"} and live["valid"] is True
    assert env.client.get("/api/evidence/chunk_sop2026", params={"case_id": "case-43"}).status_code == 403
    denied = env.client.get("/api/evidence/mystery", params={"case_id": "case-42"})
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "FORBIDDEN"
    policy = env.client.get("/api/evidence/policy_p1/clauses/0",
                            params={"case_id": "case-42", "version_id": "demo-reversal-2026-b"})
    assert policy.json()["action_permission"] is False
    assert env.client.get("/api/trace/t1", params={"case_id": "case-42"}).status_code == 403  # reader: no trace
    act_as(env, "admin-a")
    assert env.client.get("/api/trace/t1", params={"case_id": "case-42"}).status_code == 200


# Ingestion --------------------------------------------------------------------------------------------------------

def upload(env, name="notes.md", content="# Notes\nHello", **extra):
    return env.client.post("/api/sources", json={"case_id": "case-42", "family_id": "DEMO.NOTES", "filename": name,
                                                  "content": content, **extra})


def test_upload_approve_and_see_the_state_move(env):
    act_as(env, "uploader-a")
    made = upload(env, valid_from="2026-01-01")
    assert made.status_code == 201, made.text
    revision = made.json()["revision_id"]
    assert env.fake.state["calls"][-1][1]["valid_from"] == "2026-01-01T00:00:00Z"
    assert env.fake.state["calls"][-1][1]["mime_type"] == "text/markdown"
    assert env.client.post(f"/api/sources/{revision}/approve", json={"case_id": "case-42"}).status_code == 403
    act_as(env, "admin-a")
    row = next(s for s in env.client.get("/api/sources", params={"case_id": "case-42"}).json()["sources"])
    assert row["state"] == "DRAFT" and row["filename"] == "notes.md" and row["size"] == len("# Notes\nHello")
    done = env.client.post(f"/api/sources/{revision}/approve", json={"case_id": "case-42"})
    assert done.status_code == 200 and done.json()["state"] == "READY"
    after = env.client.get("/api/sources", params={"case_id": "case-42"}).json()
    assert after["sources"][0]["state"] == "APPROVED" and after["listing"] == "palladion"
    assert after["coverage"]["indexed_source_count"] == 2
    assert env.client.post(f"/api/sources/{revision}/revoke", json={"case_id": "case-42"}).json()["state"] == "REVOKED"


def test_uploads_are_checked_before_palladion_is_asked(env):
    act_as(env, "uploader-a")
    assert upload(env, name="malware.exe").status_code == 400
    assert upload(env, content="   \n").status_code == 400
    too_long = upload(env, content="x" * 65537)
    assert too_long.status_code == 400 and "65,536" in too_long.json()["error"]["message"]
    bad_pdf = env.client.post("/api/sources", json={"case_id": "case-42", "family_id": "F", "filename": "a.pdf",
                                                    "content_base64": "not base64!!"})
    assert bad_pdf.status_code == 400
    assert env.fake.state["calls"] == []


def test_a_pdf_goes_to_the_pdf_importer_and_a_family_keeps_its_owner(env):
    act_as(env, "uploader-a")
    pdf = env.client.post("/api/sources", json={"case_id": "case-42", "family_id": "DEMO.PDF", "filename": "a.pdf",
                                                "content_base64": base64.b64encode(b"%PDF-1.4 fake").decode()})
    assert pdf.status_code == 201 and pdf.json()["revision_id"].startswith("rev_")
    first = upload(env).json()
    assert first["owner_id"] == "uploader-a"
    second = upload(env, content="# Notes v2").json()
    assert second["owner_id"] == first["owner_id"]  # Palladion binds a family to its first owner


def test_a_reader_cannot_upload_and_the_refusal_is_explained(env):
    refused = upload(env)
    assert refused.status_code == 403 and refused.json()["error"]["message"] == "Denied"


def test_an_older_palladion_without_a_listing_route_falls_back_to_what_this_ui_uploaded(env):
    act_as(env, "uploader-a")
    revision = upload(env).json()["revision_id"]
    real = env.app.state.ctx.upstream.call

    async def old_palladion(method, path, token, **options):
        if path.endswith("/sources") and method == "GET":
            raise UpstreamError(404, "Not Found")
        return await real(method, path, token, **options)

    env.app.state.ctx.upstream.call = old_palladion
    listed = env.client.get("/api/sources", params={"case_id": "case-42"}).json()
    assert listed["listing"] == "local" and [s["revision_id"] for s in listed["sources"]] == [revision]


# Policies ---------------------------------------------------------------------------------------------------------

def draft(**changes):
    base = {"version_id": "ui-policy-1", "family_id": "DEMO.UI.CHECK", "case_ids": ["case-42"],
            "time_basis": "EVALUATION_AT", "valid_from": "2026-01-01", "valid_to": "",
            "clauses": [{"revision_id": "rev_a", "section_id": "s", "start_byte": 1, "end_byte": 9, "sha256": "a" * 64}],
            "facts": [{"name": "settlement_state", "operation": "get_settlement_status", "field": "settlement_state",
                       "type": "enum", "allowed_values": [], "max_age_seconds": 300}],
            "rules": [{"id": "settled", "match": "all", "clause_index": 0, "outcome": "NOT_PERMITTED",
                       "conditions": [{"fact": "settlement_state", "operator": "eq", "value": "SETTLED"}]}],
            "default_outcome": "ESCALATE"}
    return {**base, **changes}


def test_the_form_is_validated_in_plain_words_before_anything_is_sent(env):
    act_as(env, "admin-a")
    assert env.client.post("/api/policies/validate", json=draft()).json() == {"ok": True, "problems": []}
    bad = env.client.post("/api/policies", json=draft(version_id="has space", clauses=[], rules=[]))
    assert bad.status_code == 400 and len(bad.json()["error"]["problems"]) == 2
    assert env.fake.state["calls"] == []


def test_a_valid_policy_is_converted_to_exactly_what_palladion_expects(env):
    act_as(env, "admin-a")
    made = env.client.post("/api/policies", json=draft())
    assert made.status_code == 201 and made.json() == {"version_id": "ui-policy-1", "state": "APPROVED"}
    sent = env.fake.state["calls"][-1][1]
    assert sent["valid_from"] == "2026-01-01T00:00:00Z" and "valid_to" not in sent
    assert sent["required_facts"][0]["allowed_values"] == ["UNSETTLED", "PENDING", "SETTLED"]  # not empty: empty = none
    assert sent["rules"] == [{"id": "settled", "outcome": "NOT_PERMITTED", "clause_index": 0, "predicate": {
        "all": [{"field": "settlement_state", "operator": "eq", "value": "SETTLED"}]}}]
    listed = env.client.get("/api/policies", params={"case_id": "case-42"}).json()["policies"]
    assert [p["version_id"] for p in listed] == ["ui-policy-1"]
    assert env.client.post("/api/policies/ui-policy-1/revoke", json={"case_id": "case-42"}).json()["state"] == "REVOKED"


def test_only_an_admin_gets_to_the_policy_screens_and_cases_are_enforced(env):
    assert env.client.get("/api/policies", params={"case_id": "case-42"}).status_code == 403
    act_as(env, "admin-a")
    assert env.client.post("/api/policies", json=draft(case_ids=["case-88"])).status_code == 403
    act_as(env, "reader-a")
    assert env.client.post("/api/policies", json=draft()).status_code == 403


@pytest.mark.parametrize("path", ["/api/bootstrap", "/api/runtime", "/api/health", "/api/policies/meta"])
def test_basic_reads_answer(env, path):
    assert env.client.get(path).status_code == 200
