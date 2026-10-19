"""Backend-owned private session lifecycle; canonical case evidence remains separate."""

from __future__ import annotations

import re
import uuid
from typing import Any

from evidence_agent.core.errors import PermissionDenied
from evidence_agent.core.models import Principal
from evidence_agent.storage.registry import Registry
from evidence_agent.storage.sqlite import utc_now


class Sessions:
    def __init__(self, registry: Registry, principal: Principal, case_id: str) -> None:
        self.registry, self.principal, self.case_id = registry, principal, case_id

    def authorize(self) -> None:
        self.registry.access.authorize(
            self.principal,
            tenant_id=self.principal.tenant_id,
            case_id=self.case_id,
            grant="case:read",
        )

    def read(self, identifier: str, *, allow_closed: bool = False) -> dict[str, Any]:
        self.authorize()
        if not re.fullmatch(r"sess_[0-9a-f]{32}", identifier):
            raise PermissionDenied
        row = self.registry.database.connection.execute(
            "SELECT * FROM memory_sessions WHERE session_id=? "
            "AND tenant_id=? AND case_id=? AND owner_id=?",
            (identifier, self.principal.tenant_id, self.case_id, self.principal.principal_id),
        ).fetchone()
        if row is None or row["closed_at"] is not None and not allow_closed:
            raise PermissionDenied
        return dict(row)

    def resolve(self, identifier: str | None = None) -> str:
        """Omitted ID reuses this user's active case session, preserving old clients."""
        if identifier is not None:
            self.read(identifier)
            return identifier
        self.authorize()
        with self.registry.database.transaction() as db:
            self.authorize()
            row = db.execute(
                "SELECT session_id FROM memory_sessions WHERE tenant_id=? AND case_id=? "
                "AND owner_id=? AND closed_at IS NULL",
                (self.principal.tenant_id, self.case_id, self.principal.principal_id),
            ).fetchone()
            if row is not None:
                return str(row[0])
            identifier = "sess_" + uuid.uuid4().hex
            db.execute(
                "INSERT INTO memory_sessions VALUES(?,?,?,?,?,NULL)",
                (
                    identifier,
                    self.principal.tenant_id,
                    self.case_id,
                    self.principal.principal_id,
                    utc_now(),
                ),
            )
        return identifier

    def start(self) -> str:
        """Explicit new conversation closes the old active session, retaining its audit."""
        self.authorize()
        identifier = "sess_" + uuid.uuid4().hex
        with self.registry.database.transaction() as db:
            self.authorize()
            now = utc_now()
            db.execute(
                "UPDATE memory_sessions SET closed_at=? WHERE tenant_id=? AND case_id=? AND owner_id=? "
                "AND closed_at IS NULL",
                (now, self.principal.tenant_id, self.case_id, self.principal.principal_id),
            )
            db.execute(
                "INSERT INTO memory_sessions VALUES(?,?,?,?,?,NULL)",
                (
                    identifier,
                    self.principal.tenant_id,
                    self.case_id,
                    self.principal.principal_id,
                    now,
                ),
            )
        return identifier

    def close(self, identifier: str) -> None:
        self.read(identifier, allow_closed=True)
        with self.registry.database.transaction() as db:
            self.authorize()
            db.execute(
                "UPDATE memory_sessions SET closed_at=coalesce(closed_at,?) WHERE session_id=? "
                "AND tenant_id=? AND case_id=? AND owner_id=?",
                (
                    utc_now(),
                    identifier,
                    self.principal.tenant_id,
                    self.case_id,
                    self.principal.principal_id,
                ),
            )
