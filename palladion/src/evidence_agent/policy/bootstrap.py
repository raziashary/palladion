"""Explicit trusted fictional setup for policy/live domain tests and local smoke."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from evidence_agent.core.clock import utc_clock
from evidence_agent.core.fixtures import load_fixtures
from evidence_agent.core.models import TimeBasis
from evidence_agent.live.contracts import CaseScope
from evidence_agent.live.gateway import register_scope
from evidence_agent.policy.registry import Clause, PolicyRegistry, PolicySpec, RequiredFact, Rule
from evidence_agent.storage.registry import Registry


def seed_policy_fixture(registry: Registry, root: Path, *,
                        clock: Callable[[], datetime] = utc_clock) -> dict[str, str]:
    """No resets, Qdrant/model loads or external services; current revocations stay revoked."""
    bundle = load_fixtures(root)
    for principal in bundle.principals:
        registry.bootstrap_principal(principal)
    for case in bundle.cases:
        registry.bootstrap_case(case.tenant_id, case.case_id)
        for identifier in case.allowed_principal_ids:
            registry.bootstrap_membership(registry.access.authenticate(identifier), case.case_id)
        admin = registry.access.authenticate("admin-a" if case.tenant_id == "tenant-a" else "admin-b")
        suffix = case.transaction_id.removeprefix("TX-")
        register_scope(registry, admin, case.case_id, CaseScope(
            product=case.product, transaction_class=case.transaction_class,
            targets={"get_transaction_status": case.transaction_id,
                     "get_settlement_status": "SET-"+suffix,
                     "get_incident_status": "INC-"+suffix,
                     "get_merchant_summary": "MERCHANT-"+suffix},
            domain_events={"dispute_submitted": case.opened_at}), clock())
    revisions = {}
    for source in bundle.sources:
        actor = registry.access.authenticate("uploader-a" if source.tenant_id == "tenant-a" else "uploader-b")
        revision = registry.register_source(actor, tenant_id=source.tenant_id,
            case_id=source.case_ids[0], family_id=source.family_id,
            content=(root/source.path).read_bytes(), source_path=source.path,
            owner_id=source.approved_by or actor.principal_id, allowed_principal_ids=source.allowed_principal_ids,
            valid_from=source.valid_from.isoformat() if source.valid_from else None,
            valid_to=source.valid_to.isoformat() if source.valid_to else None)
        revisions[source.source_id] = revision
        if source.approval_state == "APPROVED":
            admin = registry.access.authenticate(source.approved_by or "")
            if registry.source_metadata(admin, revision)["approval_status"] == "DRAFT":
                registry.approve_source(admin, revision)
    policies = PolicyRegistry(registry, clock=clock)
    raw = bundle.policy

    def clause(data: dict[str, Any]) -> Clause:
        return Clause(revision_id=revisions[data["source_id"]], section_id=data["clause_id"],
                      start_byte=data["span_start"], end_byte=data["span_end"], sha256=data["text_sha256"])

    for version in [*raw.versions, raw.evaluation_policy]:
        applicability = version["applicability"]
        spec = PolicySpec(version_id=version["policy_version_id"],
            family_id="DEMO.HANDLING" if version is raw.evaluation_policy else raw.policy_family_id,
            author_id="uploader-a", product=applicability["product"],
            transaction_class=applicability["transaction_class"], allowed_case_ids=("case-42", "case-43"),
            time_basis=TimeBasis(applicability["time_basis"]), timestamp_source=applicability["timestamp_source"],
            valid_from=datetime.fromisoformat(applicability["valid_from"]),
            valid_to=datetime.fromisoformat(applicability["valid_to"]) if applicability["valid_to"] else None,
            clauses=tuple(clause(c) for c in version["source_clauses"]),
            required_facts=tuple(RequiredFact(name=f["name"], type=f["type"],
                operation="get_transaction_status" if f["name"] == "transaction_state" else "get_settlement_status",
                field="state" if f["name"] == "transaction_state" else "settlement_state",
                allowed_values=tuple(f["allowed_values"]), max_age_seconds=f["max_age_seconds"])
                for f in version["required_facts"]),
            rules=tuple(Rule(id=r["id"], predicate={k: r[k] for k in ("all", "any", "not") if k in r},
                             outcome=r["outcome"], clause=clause(r["source_clause"])) for r in version["rule_rows"]),
            default_outcome=version["default_outcome"])
        policies.register(registry.access.authenticate("admin-a"), spec)
    return revisions
