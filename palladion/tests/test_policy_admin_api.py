"""Admin policy routes: the HTTP writer and the engine's reader are checked against each other."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from evidence_agent.core.models import PolicyDecisionStatus
from evidence_agent.main import create_app
from evidence_agent.policy.engine import PolicyEngine
from evidence_agent.policy.registry import PolicySpec

from .test_agent_budget import UnavailableIndex

ADMIN = {"Authorization": "Bearer admin-test"}
READER = {"Authorization": "Bearer reader-test"}
UPLOADER = {"Authorization": "Bearer uploader-test"}
OTHER_TENANT = {"Authorization": "Bearer admin-b-test"}


@pytest.fixture
def api(p03):
    root = Path(p03.registry.database.path).parent
    tokens = {"admin-test": "admin-a", "reader-test": "reader-a", "uploader-test": "uploader-a",
              "admin-b-test": "admin-b"}
    with TestClient(create_app(root, UnavailableIndex(), tokens)) as client:
        yield client


def clause(p03) -> dict:
    """A real approved clause: the one the seeded 2026 reversal policy cites."""
    row = p03.registry.database.connection.execute(
        "SELECT decision_table_json FROM policy_versions WHERE version_id='demo-reversal-2026-b'").fetchone()
    return PolicySpec.model_validate_json(row[0]).clauses[0].model_dump(exclude={"schema_version"})


def body(p03, version="demo-ui-a", **changes) -> dict:
    created = {"version_id": version, "family_id": "DEMO.UI.CHECK", "case_ids": ["case-42"],
               "time_basis": "EVALUATION_AT", "valid_from": "2026-01-01T00:00:00Z",
               "clauses": [clause(p03)], "default_outcome": "FOLLOW_CURRENT_HANDLING_SOP"}
    return {**created, **changes}


FACT = {"name": "transaction_state", "type": "enum", "operation": "get_transaction_status", "field": "state",
        "allowed_values": ["FAILED", "PENDING", "SUCCEEDED"], "max_age_seconds": 300}
RULE = {"id": "failed-needs-review", "outcome": "FOLLOW_INVESTIGATION_SOP", "clause_index": 0,
        "predicate": {"all": [{"field": "transaction_state", "operator": "eq", "value": "FAILED"}]}}


def listed(api, case_id="case-42"):
    response = api.get("/v1/admin/policies", params={"case_id": case_id}, headers=ADMIN)
    assert response.status_code == 200, response.text
    return {p["version_id"]: p for p in response.json()["policies"]}


def test_http_registration_is_what_the_engine_reads(api, p03):
    created = api.post("/v1/admin/policies", headers=ADMIN, json=body(p03))
    assert created.status_code == 201, created.text
    assert created.json() == {"version_id": "demo-ui-a", "state": "APPROVED"}
    decision = PolicyEngine(p03.policies, clock=lambda: p03.now).evaluate(p03.reader, "case-42", "DEMO.UI.CHECK", ())
    assert decision.status is PolicyDecisionStatus.DETERMINED
    assert decision.version_id == "demo-ui-a" and decision.outcome == "FOLLOW_CURRENT_HANDLING_SOP"
    # The server filled what the client did not name: the cited source's uploader and the case's scope.
    stored = listed(api)["demo-ui-a"]
    assert stored["author_id"] == "uploader-a"
    assert (stored["product"], stored["transaction_class"]) == ("QR_DEMO", "DEMO_STANDARD")
    assert stored["state"] == "APPROVED" and stored["clauses"][0]["section_id"] == clause(p03)["section_id"]


def test_facts_rules_and_the_seeded_policies_are_listed(api, p03):
    created = api.post("/v1/admin/policies", headers=ADMIN, json=body(
        p03, version="demo-ui-facts", required_facts=[FACT], rules=[RULE]))
    assert created.status_code == 201, created.text
    policies = listed(api)
    assert {"demo-reversal-2025-a", "demo-reversal-2026-b"} <= set(policies)
    mine = policies["demo-ui-facts"]
    assert mine["required_facts"][0]["name"] == "transaction_state"
    assert mine["rules"] == [{"id": "failed-needs-review", "outcome": "FOLLOW_INVESTIGATION_SOP",
                              "predicate": RULE["predicate"], "clause_index": 0}]
    assert mine["case_ids"] == ["case-42"]  # listed only for the case it was registered for


def test_repeat_is_idempotent_and_a_changed_definition_conflicts(api, p03):
    assert api.post("/v1/admin/policies", headers=ADMIN, json=body(p03)).status_code == 201
    assert api.post("/v1/admin/policies", headers=ADMIN, json=body(p03)).status_code == 201
    changed = api.post("/v1/admin/policies", headers=ADMIN, json=body(p03, default_outcome="SOMETHING_ELSE"))
    assert changed.status_code == 409


def test_only_a_current_case_admin_may_write_or_list(api, p03):
    for headers in (READER, UPLOADER, OTHER_TENANT):
        assert api.post("/v1/admin/policies", headers=headers, json=body(p03)).status_code == 403
        assert api.get("/v1/admin/policies", params={"case_id": "case-42"}, headers=headers).status_code == 403
    assert api.post("/v1/admin/policies", json=body(p03)).status_code == 403  # no token is no identity


def test_bad_definitions_are_refused_for_the_right_reason(api, p03):
    tampered = {**clause(p03), "sha256": "0" * 64}
    assert api.post("/v1/admin/policies", headers=ADMIN, json=body(p03, clauses=[tampered])).status_code == 409
    unknown = {**clause(p03), "revision_id": "rev_does_not_exist"}
    assert api.post("/v1/admin/policies", headers=ADMIN, json=body(p03, clauses=[unknown])).status_code == 403
    assert api.post("/v1/admin/policies", headers=ADMIN, json=body(
        p03, required_facts=[FACT], rules=[{**RULE, "clause_index": 3}])).status_code == 400
    bad_field = {**RULE, "predicate": {"all": [{"field": "not_a_declared_fact", "operator": "eq", "value": "x"}]}}
    assert api.post("/v1/admin/policies", headers=ADMIN, json=body(
        p03, required_facts=[FACT], rules=[bad_field])).status_code == 400
    mismatch = api.post("/v1/admin/policies", headers=ADMIN, json=body(p03, time_basis="DOMAIN_EVENT_AT"))
    assert mismatch.status_code == 400  # a domain-event basis must name its event
    assert "demo-ui-a" not in listed(api)  # nothing half-written


def test_revoked_version_is_no_longer_selected(api, p03):
    assert api.post("/v1/admin/policies", headers=ADMIN, json=body(p03)).status_code == 201
    revoked = api.post("/v1/admin/policies/demo-ui-a/revoke", headers=ADMIN)
    assert revoked.status_code == 200 and revoked.json()["state"] == "REVOKED"
    assert listed(api)["demo-ui-a"]["state"] == "REVOKED"
    decision = PolicyEngine(p03.policies, clock=lambda: p03.now).evaluate(p03.reader, "case-42", "DEMO.UI.CHECK", ())
    assert decision.status is PolicyDecisionStatus.NO_APPLICABLE_POLICY
    assert api.post("/v1/admin/policies/demo-ui-a/revoke", headers=READER).status_code == 403


def test_overlap_conflicts_until_a_reasoned_supersession_is_recorded(api, p03):
    assert api.post("/v1/admin/policies", headers=ADMIN, json=body(p03, version="demo-ui-v1")).status_code == 201
    newer = body(p03, version="demo-ui-v2", valid_from="2026-03-01T00:00:00Z", default_outcome="FOLLOW_NEW_RULE")
    assert api.post("/v1/admin/policies", headers=ADMIN, json=newer).status_code == 201
    engine = PolicyEngine(p03.policies, clock=lambda: p03.now)
    before = engine.evaluate(p03.reader, "case-42", "DEMO.UI.CHECK", ())
    assert before.status is PolicyDecisionStatus.POLICY_CONFLICT  # both windows contain the instant
    replace = {"predecessor_version_id": "demo-ui-v1", "case_id": "case-42",
               "valid_from": "2026-03-01T00:00:00Z", "reason": "v2 replaces v1 from March"}
    assert api.post("/v1/admin/policies/demo-ui-v2/supersede", headers=READER, json=replace).status_code == 403
    done = api.post("/v1/admin/policies/demo-ui-v2/supersede", headers=ADMIN, json=replace)
    assert done.status_code == 200, done.text
    after = engine.evaluate(p03.reader, "case-42", "DEMO.UI.CHECK", ())
    assert after.status is PolicyDecisionStatus.DETERMINED and after.version_id == "demo-ui-v2"
    policies = listed(api)
    assert policies["demo-ui-v2"]["supersedes"] == ["demo-ui-v1"]
    assert policies["demo-ui-v1"]["superseded_by"] == ["demo-ui-v2"]
    assert api.post("/v1/admin/policies/demo-ui-v2/supersede", headers=ADMIN,
                    json={**replace, "reason": "  "}).status_code == 400


def test_supersession_across_families_is_refused(api, p03):
    assert api.post("/v1/admin/policies", headers=ADMIN, json=body(p03, version="demo-ui-a")).status_code == 201
    other = body(p03, version="demo-ui-other", family_id="DEMO.UI.OTHER")
    assert api.post("/v1/admin/policies", headers=ADMIN, json=other).status_code == 201
    mixed = api.post("/v1/admin/policies/demo-ui-other/supersede", headers=ADMIN, json={
        "predecessor_version_id": "demo-ui-a", "case_id": "case-42",
        "valid_from": "2026-03-01T00:00:00Z", "reason": "wrong family"})
    assert mixed.status_code == 409
