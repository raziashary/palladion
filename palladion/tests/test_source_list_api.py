"""The source listing shows what a caller may know about, never more, and never source text."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from evidence_agent.main import create_app

from .test_agent_budget import UnavailableIndex

TOKENS = {"admin-test": "admin-a", "reader-test": "reader-a", "limited-test": "reader-a-limited",
          "uploader-test": "uploader-a", "admin-b-test": "admin-b"}


@pytest.fixture
def api(p03):
    root = Path(p03.registry.database.path).parent
    with TestClient(create_app(root, UnavailableIndex(), TOKENS)) as client:
        yield client


def families(api, who, case_id="case-42"):
    response = api.get(f"/v1/cases/{case_id}/sources", headers={"Authorization": f"Bearer {who}-test"})
    assert response.status_code == 200, response.text
    return response.json()["sources"]


def test_admin_sees_every_state_including_the_draft(api):
    rows = families(api, "admin")
    assert len(rows) == 4  # two SOP revisions, the appendix and the draft memo
    assert ("DEMO.DISPUTE.SOP.PROPOSALS", "DRAFT") in {(s["family_id"], s["state"]) for s in rows}
    assert {s["state"] for s in rows} == {"APPROVED", "DRAFT"}


def test_reader_sees_only_approved_sources_the_access_list_allows(api):
    reader = {s["family_id"] for s in families(api, "reader")}
    assert "DEMO.DISPUTE.SOP.PROPOSALS" not in reader  # a draft is not for readers
    assert "DEMO.DISPUTE.SOP.EXCEPTIONS" in reader  # reader-a is on the appendix's list
    limited = {s["family_id"] for s in families(api, "limited")}
    assert "DEMO.DISPUTE.SOP.EXCEPTIONS" not in limited  # reader-a-limited is not
    assert "DEMO.DISPUTE.SOP" in limited


def test_uploader_sees_their_own_drafts_and_the_listing_carries_no_text(api):
    mine = families(api, "uploader")
    assert any(s["state"] == "DRAFT" and s["mine"] for s in mine)
    for source in mine:
        assert set(source) == {"revision_id", "family_id", "filename", "state", "index_state", "valid_from",
                               "valid_to", "uploader_id", "owner_id", "registered_at", "mine"}


def test_scope_is_the_callers_case_and_tenant(api):
    assert api.get("/v1/cases/case-43/sources", headers={"Authorization": "Bearer reader-test"}).status_code == 403
    assert api.get("/v1/cases/case-42/sources", headers={"Authorization": "Bearer admin-b-test"}).status_code == 403
    assert api.get("/v1/cases/case-42/sources").status_code == 403
    assert "DEMO.DISPUTE.SOP.EXCEPTIONS" not in {s["family_id"] for s in families(api, "admin", "case-43")}
