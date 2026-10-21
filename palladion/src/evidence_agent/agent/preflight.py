"""Cheap, deterministic, nonexclusive hints; zero model calls and no inferred grants."""
from __future__ import annotations

import re
from typing import Any

from evidence_agent.core.errors import PermissionDenied
from evidence_agent.core.models import ContinuityPacket
from evidence_agent.live.gateway import read_scope
from evidence_agent.memory.packet import build_packet
from evidence_agent.memory.store import CaseStore
from evidence_agent.policy.registry import PolicyRegistry, PolicySpec


def preflight(query: str, store: CaseStore, *, include_memory: bool = True,
              packet_max_chars: int = 6000) -> dict[str, Any]:
    if not query.strip() or len(query) > 2048:
        raise ValueError("Question bounds exceeded")
    store.authorize()
    packet = (build_packet(store, query, max_chars=packet_max_chars) if include_memory else
        ContinuityPacket(case_id=store.case_id, tenant_id=store.principal.tenant_id,
            agent_role="investigator", current_goal=query, generated_at=store.registry.clock()))
    identifiers = re.findall(r"\b(?:TX|SET|INC|MERCHANT|SOP|ERR)-[A-Z0-9-]{2,80}\b", query)
    scope = read_scope(store.registry, store.principal, store.case_id)
    families: set[str] = set()
    rows = store.registry.database.connection.execute(
        "SELECT decision_table_json FROM policy_versions WHERE tenant_id=? AND status='APPROVED' LIMIT 129",
        (store.principal.tenant_id,)).fetchall()
    for row in rows[:128]:
        spec = PolicySpec.model_validate_json(row[0])
        if (store.case_id not in spec.allowed_case_ids or spec.product != scope.product or
                spec.transaction_class != scope.transaction_class):
            continue
        try:
            for clause in spec.clauses:
                PolicyRegistry(store.registry).clause(store.principal, clause)
        except PermissionDenied:
            continue
        families.add(spec.family_id)
    return {"packet": packet.model_dump(mode="json"), "identifiers": identifiers[:8],
        "authorized_targets": scope.targets,
        "known_approved_policy_families": sorted(families),
        "family_discovery_truncated": len(rows) > 128,
        "suggestions": [] if query.strip().lower() in {"hi", "hello", "thanks", "thank you"}
                         else ["search_knowledge"],
        "prefetched": [], "llm_calls": 0, "routing_is_exclusive": False}
