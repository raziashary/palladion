"""Isolated HTTP guard/consumer checks; not live-provider transport proof."""
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from evidence_agent.agent.services import configure_agent
from evidence_agent.live.mock import MockAdapter
from evidence_agent.main import create_app
from evidence_agent.memory.packet import build_packet
from evidence_agent.memory.store import CaseStore
from evidence_agent.settings import Settings

from .test_agent_budget import ScriptedModel, UnavailableIndex, make_runtime


@pytest.fixture
def api(p03):
    root = Path(p03.registry.database.path).parent
    app = create_app(root, UnavailableIndex(), {"reader-test": "reader-a", "admin-test": "admin-a"})
    configure_agent(app, model=ScriptedModel([]), adapter=MockAdapter({}),
                    config=p03.config, settings=Settings())
    with TestClient(app) as client:
        yield client, app
    assert app.state.agent_services.database is None


def test_authenticated_message_to_persisted_timeline(api):
    client, _ = api
    headers = {"Authorization": "Bearer reader-test"}
    response = client.post("/v1/cases/case-42/messages", headers=headers, json={"query": "hello"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["disposition"] == "NOT_ESTABLISHED"
    assert data["searched_scope"] == "No source search was performed."
    assert data["budget"]["main_used"] == 2
    timeline = client.get("/v1/cases/case-42/timeline", headers=headers)
    assert timeline.status_code == 200
    assert any(e["status"] == "NOT_ESTABLISHED" for e in timeline.json())
    assert "hello" not in timeline.text and "proposal_sha256" not in timeline.text


def test_wrong_case_token_and_identity_override_do_not_dispatch(api):
    client, app = api
    assert client.post("/v1/cases/case-42/messages", json={"query": "hello"}).status_code == 403
    headers = {"Authorization": "Bearer reader-test"}
    assert client.post("/v1/cases/foreign/messages", headers=headers, json={"query": "hello"}).status_code == 403
    assert client.post("/v1/cases/case-42/messages", headers=headers,
                       json={"query": "hello", "principal_id": "admin-a"}).status_code == 422
    assert app.state.agent_services.model.calls == []
    assert client.get("/v1/cases/foreign/timeline", headers=headers).status_code == 403


def test_unconfigured_model_capability_is_not_enabled_by_existing_key(p03):
    root = Path(p03.registry.database.path).parent
    with TestClient(create_app(root, UnavailableIndex(), {"r": "reader-a"})) as client:
        response = client.post("/v1/cases/case-42/messages", headers={"Authorization": "Bearer r"},
                               json={"query": "hello"})
        assert response.status_code == 503


def test_trace_requires_current_admin_and_case_membership_and_redacts_content(api, p03):
    client, _ = api
    trace = "trace_guard"
    store = CaseStore(p03.registry, p03.reader, "case-42")
    store.append("REQUEST", trace, {"query": "PRIVATE_QUERY_CANARY"})
    store.append("DIAGNOSTIC", trace, {"rejected_prose": "PRIVATE_REJECTED_CANARY"})
    store.append("ATTEMPT", trace, {"role": "main", "attempt": 1, "status": "FAILED",
                                   "raw_prompt": "PRIVATE_PROMPT_CANARY"})
    route = f"/v1/traces/{trace}?case_id=case-42"
    assert client.get(route).status_code == 403
    assert client.get(route, headers={"Authorization": "Bearer reader-test"}).status_code == 403
    admin = {"Authorization": "Bearer admin-test"}
    response = client.get(route, headers=admin)
    assert response.status_code == 200
    assert len(response.json()["events"]) == 3
    assert any(e["metadata"].get("status") == "FAILED" for e in response.json()["events"])
    assert "PRIVATE_" not in response.text
    assert client.get(f"/v1/traces/{trace}?case_id=foreign", headers=admin).status_code == 403
    p03.registry.revoke_membership(p03.admin, "admin-a", "case-42")
    assert client.get(route, headers=admin).status_code == 403


def test_readiness_checks_sqlite_index_and_explicit_boundary_without_provider_call(api, tmp_path):
    client, app = api
    app.state.index = SimpleNamespace(ensure_collection=lambda: None)
    response = client.get("/ready")
    assert response.status_code == 200, response.text
    assert app.state.agent_services.model.calls == []
    assert client.get("/health/ready").status_code == 200
    root = app.state.runtime_root
    app.state.runtime_root = tmp_path / "missing"
    assert client.get("/ready").status_code == 503
    assert not app.state.runtime_root.exists()
    app.state.runtime_root = root
    agent = app.state.agent_services
    del app.state.agent_services
    assert client.get("/ready").status_code == 503
    app.state.agent_services = agent
    def failed_index():
        raise RuntimeError("PRIVATE_DEPENDENCY_CANARY")
    app.state.index = SimpleNamespace(ensure_collection=failed_index)
    response = client.get("/ready")
    assert response.status_code == 503
    assert "PRIVATE_" not in response.text
    assert client.get("/health").status_code == client.get("/health/live").status_code == 200
    assert agent.model.calls == []


def test_event_evidence_and_recall_redact_requests_but_own_packet_preserves_unverified_reports(api, p03):
    client, _ = api
    writer = CaseStore(p03.registry, p03.admin, "case-42")
    request_id = writer.append("REQUEST", "trace_private", {"query": "PRIVATE_QUESTION_CANARY"})
    attempt_id = writer.append("ATTEMPT", "trace_private", {
        "status": "FAILED", "raw_prompt": "PRIVATE_SYSTEM_PROMPT_CANARY"})
    viewer = {"Authorization": "Bearer reader-test"}
    timeline = client.get("/v1/cases/case-42/timeline", headers=viewer)
    assert timeline.status_code == 200
    assert request_id in timeline.text and "PRIVATE_" not in timeline.text
    for identifier in (request_id, attempt_id):
        for headers in (viewer, {"Authorization": "Bearer admin-test"}):
            response = client.get("/v1/evidence/" + identifier,
                                  params={"case_id": "case-42"}, headers=headers)
            assert response.status_code == 200
            assert "PRIVATE_" not in response.text
    fixture = make_runtime(p03)
    recalled = asyncio.run(fixture.tools.execute("recall_memory", '{"limit":20}'))
    assert recalled["status"] == "SUCCEEDED" and "PRIVATE_" not in str(recalled)
    own = build_packet(writer, "follow up")
    assert own.reported_facts[0].statement == "PRIVATE_QUESTION_CANARY"
    assert own.reported_facts[0].verification_status.value == "UNVERIFIED"
    other = build_packet(CaseStore(p03.registry, p03.reader, "case-42"), "follow up")
    assert other.reported_facts == ()


def test_p06_review_status_and_counts_reach_timeline_without_raw_review(api):
    client, app = api
    response = client.post("/v1/cases/case-42/messages", headers={"Authorization":"Bearer reader-test"}, json={"query":"hello"})
    assert response.status_code == 200 and response.json()["review_status"] == "PASS"
    assert response.json()["budget"]["critic_used"] == 1
    timeline = client.get("/v1/cases/case-42/timeline", headers={"Authorization":"Bearer reader-test"})
    release = next(e for e in reversed(timeline.json()) if e["kind"] == "RUNTIME_RELEASE")
    assert release["review_status"] == "PASS" and release["critic_used"] == 1
    assert "guard-review" not in timeline.text and "evidence_inventory" not in timeline.text



def test_actual_rejected_proposals_are_protected_from_all_public_readers(api):
    import json
    client,app = api
    bad = {"claims":[{"id":"bad", "type":"HYPOTHESIS", "text":"PRIVATE_DRAFT_CANARY"}]}
    app.state.agent_services.model = ScriptedModel([{"content":json.dumps(bad)},{"content":json.dumps(bad)}])
    headers = {"Authorization":"Bearer reader-test"}
    response = client.post("/v1/cases/case-42/messages",headers=headers,json={"query":"hello"})
    assert response.status_code == 200 and "PRIVATE_DRAFT_CANARY" not in response.text
    from evidence_agent.storage.sqlite import Database
    with Database(app.state.runtime_root / "registry.sqlite") as database:
        rows = database.connection.execute("SELECT event_id,payload_json FROM case_events WHERE event_kind='RUNTIME_DIAGNOSTIC'").fetchall()
    assert any("PRIVATE_DRAFT_CANARY" in row[1] for row in rows)
    for row in rows:
        for token in ("reader-test","admin-test"):
            read = client.get("/v1/evidence/"+row[0],params={"case_id":"case-42"},headers={"Authorization":"Bearer "+token})
            assert read.status_code == 403 and "PRIVATE_DRAFT_CANARY" not in read.text
    timeline = client.get("/v1/cases/case-42/timeline",headers=headers)
    trace = client.get("/v1/traces/"+response.json()["trace_id"],params={"case_id":"case-42"},headers={"Authorization":"Bearer admin-test"})
    assert "PRIVATE_DRAFT_CANARY" not in timeline.text + trace.text
