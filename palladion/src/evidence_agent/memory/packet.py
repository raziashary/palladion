"""Regenerate a bounded packet from authorized persisted events, never model grants."""
from __future__ import annotations

import json

from evidence_agent.core.models import ContinuityPacket, GateDisposition, SourceRef
from evidence_agent.live.gateway import utc_clock
from evidence_agent.memory.store import CaseStore


def build_packet(store: CaseStore, query: str) -> ContinuityPacket:
    events = store.recent()
    disposition = None
    handles: list[SourceRef] = []
    for event in events:
        payload = event["payload"]
        if event["kind"] == "RUNTIME_RELEASE":
            disposition = GateDisposition(payload["disposition"])
            handles.extend(SourceRef.model_validate_json(json.dumps(h)) for h in payload["evidence_handles"])
    return ContinuityPacket(case_id=store.case_id, tenant_id=store.principal.tenant_id,
        agent_role="investigator", current_goal=query, reported_facts=store.own_reported_facts(),
        previous_attempts=tuple(e for e in events if e["kind"] in {"RUNTIME_ATTEMPT", "RUNTIME_TOOL_RESULT"}),
        evidence_handles=tuple(handles[-12:]), last_disposition=disposition, generated_at=utc_clock())
