"""Demo identities. Palladion's synthetic tokens stay on this server; the browser only ever holds a persona name."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Persona:
    id: str
    tenant_id: str
    roles: tuple[str, ...]
    grants: tuple[str, ...]
    case_ids: tuple[str, ...]

    def public(self) -> dict[str, object]:
        return {"id": self.id, "tenant_id": self.tenant_id, "roles": list(self.roles),
                "grants": list(self.grants), "case_ids": list(self.case_ids),
                "can_upload": "document:upload" in self.grants,
                "can_approve": "document:approve" in self.grants and "admin" in self.roles}


@dataclass(frozen=True)
class CaseInfo:
    id: str
    tenant_id: str
    product: str
    transaction_class: str
    transaction_id: str
    opened_at: str
    principal_ids: tuple[str, ...]

    def public(self) -> dict[str, object]:
        return {"id": self.id, "tenant_id": self.tenant_id, "product": self.product,
                "transaction_class": self.transaction_class, "transaction_id": self.transaction_id,
                "opened_at": self.opened_at}


@dataclass
class Directory:
    """Who exists and which token speaks for them, read from the files Palladion's seed wrote."""

    data_root: Path
    fixtures_root: Path
    _tokens: dict[str, str] = field(default_factory=dict)
    _personas: dict[str, Persona] = field(default_factory=dict)
    _cases: dict[str, CaseInfo] = field(default_factory=dict)
    _stamp: tuple[float, float] = (0.0, 0.0)

    def _files(self) -> tuple[Path, Path]:
        return self.data_root / "demo_auth.json", self.fixtures_root / "sample_cases.json"

    def refresh(self) -> None:
        auth, fixtures = self._files()
        try:
            stamp = (auth.stat().st_mtime, fixtures.stat().st_mtime)
        except FileNotFoundError:
            self._tokens, self._personas, self._cases, self._stamp = {}, {}, {}, (0.0, 0.0)
            return
        if stamp == self._stamp:
            return
        by_token: dict[str, str] = json.loads(auth.read_text(encoding="utf-8"))
        document = json.loads(fixtures.read_text(encoding="utf-8"))
        self._tokens = {principal: token for token, principal in by_token.items()}
        self._personas = {p["principal_id"]: Persona(
            id=p["principal_id"], tenant_id=p["tenant_id"], roles=tuple(p["roles"]), grants=tuple(p["grants"]),
            case_ids=tuple(p["allowed_case_ids"])) for p in document["principals"] if p["principal_id"] in self._tokens}
        self._cases = {c["case_id"]: CaseInfo(
            id=c["case_id"], tenant_id=c["tenant_id"], product=c["product"],
            transaction_class=c["transaction_class"], transaction_id=c["transaction_id"], opened_at=c["opened_at"],
            principal_ids=tuple(c["allowed_principal_ids"])) for c in document["cases"]}
        self._stamp = stamp

    def personas(self) -> list[Persona]:
        self.refresh()
        return sorted(self._personas.values(), key=lambda p: (p.tenant_id, p.id))

    def persona(self, persona_id: str | None) -> Persona | None:
        self.refresh()
        return self._personas.get(persona_id or "")

    def token(self, persona_id: str) -> str:
        """Used only to call Palladion; never returned to a client or written to a log."""
        self.refresh()
        return self._tokens[persona_id]

    def cases_for(self, persona: Persona) -> list[CaseInfo]:
        self.refresh()
        return [c for c in self._cases.values() if persona.id in c.principal_ids]

    def case(self, case_id: str) -> CaseInfo | None:
        self.refresh()
        return self._cases.get(case_id)
