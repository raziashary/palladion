import pytest

from evidence_agent.core.errors import PermissionDenied
from evidence_agent.core.models import Principal
from evidence_agent.security.access import AccessController


@pytest.fixture
def profiles() -> dict[str, Principal]:
    return {
        "alice": Principal(
            principal_id="alice",
            tenant_id="tenant-a",
            roles=("investigator",),
            allowed_case_ids=("case-1",),
            grants=("knowledge:read",),
        ),
    }


def make_controller(profiles: dict[str, Principal], memberships: set[tuple[str, str, str]]):
    return AccessController(
        lookup_principal=profiles.get,
        lookup_membership=lambda tenant_id, case_id, principal_id: (
            tenant_id,
            case_id,
            principal_id,
        )
        in memberships,
    )


def test_authenticated_principal_can_read_authorized_case(profiles: dict[str, Principal]) -> None:
    memberships = {("tenant-a", "case-1", "alice")}
    access = make_controller(profiles, memberships)
    principal = access.authenticate("alice")
    assert principal == profiles["alice"]
    access.authorize(
        principal,
        tenant_id="tenant-a",
        case_id="case-1",
        role="investigator",
        grant="knowledge:read",
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"tenant_id": "tenant-b"},
        {"tenant_id": "tenant-a", "case_id": "case-2"},
        {"tenant_id": "tenant-a", "case_id": "case-1", "role": "approver"},
        {"tenant_id": "tenant-a", "case_id": "case-1", "grant": "document:approve"},
    ],
)
def test_wrong_tenant_case_role_or_grant_is_denied_without_detail(
    profiles: dict[str, Principal], kwargs: dict
) -> None:
    access = make_controller(profiles, {("tenant-a", "case-1", "alice")})
    with pytest.raises(PermissionDenied, match="Access denied") as denied:
        access.authorize(profiles["alice"], **kwargs)
    assert str(denied.value) == "Access denied."


def test_swapped_principal_context_and_revoked_grant_are_denied(
    profiles: dict[str, Principal],
) -> None:
    original = profiles["alice"]
    profiles["alice"] = original.model_copy(update={"grants": ("knowledge:read", "document:approve")})
    access = make_controller(profiles, {("tenant-a", "case-1", "alice")})
    with pytest.raises(PermissionDenied):
        access.authorize(
            original,
            tenant_id="tenant-a",
            case_id="case-1",
            grant="knowledge:read",
        )

    profiles["alice"] = original.model_copy(update={"grants": ()})
    current = access.authenticate("alice")
    with pytest.raises(PermissionDenied):
        access.authorize(current, tenant_id="tenant-a", grant="knowledge:read")


def test_case_requires_both_principal_allowlist_and_current_membership(
    profiles: dict[str, Principal],
) -> None:
    access = make_controller(profiles, set())
    with pytest.raises(PermissionDenied):
        access.authorize(profiles["alice"], tenant_id="tenant-a", case_id="case-1")

    profiles["alice"] = profiles["alice"].model_copy(update={"allowed_case_ids": ()})
    access = make_controller(profiles, {("tenant-a", "case-1", "alice")})
    with pytest.raises(PermissionDenied):
        access.authorize(profiles["alice"], tenant_id="tenant-a", case_id="case-1")


def test_unknown_principal_has_same_permission_failure() -> None:
    access = AccessController(lambda _: None, lambda *_: True)
    with pytest.raises(PermissionDenied, match="Access denied"):
        access.authenticate("missing")
