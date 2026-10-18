"""Backend authorization against current persisted synthetic profiles and memberships."""

from __future__ import annotations

from collections.abc import Callable

from evidence_agent.core.errors import PermissionDenied
from evidence_agent.core.models import Principal

PrincipalLookup = Callable[[str], Principal | None]
MembershipLookup = Callable[[str, str, str], bool]


class AccessController:
    def __init__(
        self,
        lookup_principal: PrincipalLookup,
        lookup_membership: MembershipLookup,
        lookup_team: MembershipLookup | None = None,
    ) -> None:
        self._lookup_principal = lookup_principal
        self._lookup_membership = lookup_membership
        self._lookup_team = lookup_team

    def authenticate(self, principal_id: str) -> Principal:
        principal = self._lookup_principal(principal_id)
        if principal is None or principal.principal_id != principal_id:
            raise PermissionDenied
        return principal

    def authorize(
        self,
        principal: Principal,
        *,
        tenant_id: str,
        case_id: str | None = None,
        grant: str | None = None,
        role: str | None = None,
    ) -> None:
        current = self._lookup_principal(principal.principal_id)
        if current is None or current != principal:
            raise PermissionDenied
        if current.tenant_id != tenant_id:
            raise PermissionDenied
        if grant is not None and grant not in current.grants:
            raise PermissionDenied
        if role is not None and role not in current.roles:
            raise PermissionDenied
        if case_id is not None:
            if case_id not in current.allowed_case_ids:
                raise PermissionDenied
            if not self._lookup_membership(tenant_id, case_id, current.principal_id):
                raise PermissionDenied

    def memory_scope(self, principal: Principal, *, tenant_id: str, origin_case: str | None,
                     current_case: str, kind: str, scope_id: str, owner_id: str) -> None:
        self.authorize(principal, tenant_id=tenant_id, case_id=current_case, grant="case:read")
        if origin_case is not None:
            self.authorize(principal, tenant_id=tenant_id, case_id=origin_case, grant="case:read")
        if kind == "USER" and scope_id == principal.principal_id == owner_id:
            return
        if kind == "CASE" and scope_id == current_case:
            return
        if kind == "TEAM" and self._lookup_team and self._lookup_team(tenant_id, scope_id, principal.principal_id):
            return
        if kind == "ORGANIZATION" and scope_id == tenant_id:
            return
        raise PermissionDenied


__all__ = ["AccessController"]
