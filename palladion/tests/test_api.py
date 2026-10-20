"""Approved provisioning consumers: isolated synthetic HTTP and persisted readers."""
import pytest

from evidence_agent.core.models import Principal

from .test_runtime_api import api as runtime_api


@pytest.fixture
def api(p03):
    yield from runtime_api.__wrapped__(p03)


def test_admin_provisioning_reopen_revoke_and_no_tokens(api, p03):
    client, app = api
    headers = {"Authorization": "Bearer admin-test"}
    body = {"principal_id": "new-reader", "grants": ["case:read", "source:read"]}
    created = client.post("/v1/admin/principals", headers=headers, json=body)
    assert created.status_code == 200, created.text
    canonical = created.json()["principal_id"]
    assert canonical.startswith("usr_") and canonical != "new-reader"
    assert created.json()["roles"] == ["reader"]
    assert "token" not in created.text and "secret" not in created.text
    assert canonical not in app.state.tokens.values()
    assert p03.registry.access.authenticate(canonical).grants == ("case:read", "source:read")
    case = client.post("/v1/admin/cases", headers=headers, json={"case_id": "new-case"})
    assert case.status_code == 200
    route = "/v1/admin/cases/new-case/memberships"
    assert client.post(route, headers=headers, json={"principal_id": canonical}).json()["active"]
    admin = p03.registry.access.authenticate("admin-a")
    p03.registry.revoke_membership(admin, canonical, "new-case")
    assert client.post(route, headers=headers, json={"principal_id": canonical}).json()["active"] is False
    p03.registry.revoke_grant(admin, canonical, "source:read")
    repeated = client.post("/v1/admin/principals", headers=headers, json=body)
    assert repeated.status_code == 200 and repeated.json()["grants"] == ["case:read"]
    p03.registry.revoke_membership(admin, "admin-a", "new-case")
    assert client.post("/v1/admin/cases", headers=headers, json={"case_id": "new-case"}).status_code == 403


def test_provisioning_denies_untrusted_scope_escalation_and_collisions(api, p03):
    client, _ = api
    admin = {"Authorization": "Bearer admin-test"}
    reader = {"Authorization": "Bearer reader-test"}
    route = "/v1/admin/principals"
    body = {"principal_id": "no-write", "grants": []}
    assert client.post(route, headers=reader, json=body).status_code == 403
    assert client.post(route, headers=admin, json={**body, "roles": ["admin"]}).status_code == 422
    assert client.post(route, headers=admin, json={**body, "tenant_id": "other"}).status_code == 422
    assert client.post(route, headers=admin, json={**body, "grants": ["root"]}).status_code == 422
    p03.registry.bootstrap_principal(Principal(principal_id="foreign", tenant_id="other"))
    scoped = client.post(route, headers=admin, json={**body, "principal_id": "foreign"})
    assert scoped.status_code == 200 and scoped.json()["principal_id"] != "foreign"
    assert p03.registry.access.authenticate("foreign").tenant_id == "other"
    assert client.post("/v1/admin/cases/case-42/memberships", headers=admin,
        json={"principal_id": "foreign"}).status_code == 403
    local = client.post(route, headers=admin, json={**body, "principal_id": "admin-a"})
    assert local.status_code == 200 and local.json()["roles"] == ["reader"]
    assert local.json()["principal_id"] != "admin-a"
    assert client.post(route, headers=admin, json={**body, "principal_id":"foreign", "grants":["source:read"]}).status_code == 409
    assert client.post(route, headers=admin, json={**body, "grants":["document:upload"]}).status_code == 403



def test_same_subject_in_two_tenants_has_distinct_canonical_ids(api,p03):
    client,app = api
    p03.registry.bootstrap_principal(Principal(principal_id="other-admin",tenant_id="other",
        roles=("admin",),grants=("document:approve","source:read")))
    app.state.tokens["other-test"] = "other-admin"
    body={"principal_id":"shared-local-subject","grants":["source:read"]}
    one=client.post("/v1/admin/principals",headers={"Authorization":"Bearer admin-test"},json=body)
    two=client.post("/v1/admin/principals",headers={"Authorization":"Bearer other-test"},json=body)
    assert one.status_code == two.status_code == 200
    assert one.json()["principal_id"] != two.json()["principal_id"]
    assert one.json()["tenant_id"] == "tenant-a" and two.json()["tenant_id"] == "other"
