"""Application-generated continuity; historical observations always require a new read."""
from __future__ import annotations

import json

from evidence_agent.core.errors import EvidenceAgentError
from evidence_agent.core.models import (
    ContinuityPacket,
    GateDisposition,
    Hypothesis,
    LiveOperationStatus,
    ReportedFact,
    SourceRef,
    VerifiedObservation,
)
from evidence_agent.live.gateway import read_observation
from evidence_agent.memory.store import CaseStore


def build_packet(store: CaseStore, query: str, *, max_chars: int = 6000) -> ContinuityPacket:
    if not 1500 <= max_chars <= 12000:
        raise ValueError("Packet compression bound exceeded")
    store.authorize()
    memory = store.memory()
    if memory.closed():
        return ContinuityPacket(case_id=store.case_id, tenant_id=store.principal.tenant_id,
            agent_role="investigator", current_goal=query[:512], generated_at=store.registry.clock())
    events = store.recent(limit=20)
    release = store.registry.database.connection.execute(
        "SELECT payload_json FROM case_events WHERE tenant_id=? AND case_id=? "
        "AND event_id IN (SELECT event_id FROM memory_event_sessions WHERE session_id=?) "
        "AND event_kind='RUNTIME_RELEASE' ORDER BY occurred_at DESC,event_id DESC LIMIT 1",
        (store.principal.tenant_id, store.case_id,store.session_id)).fetchone()
    prior = store._safe_payload("RUNTIME_RELEASE", json.loads(release[0])) if release else {}
    handles = [SourceRef.model_validate_json(json.dumps(h)) for h in prior.get("evidence_handles", [])][:3]
    # Category reservations prevent repeated tool/turn events starving durable preferences.
    memories = (memory.recall(category="SEMANTIC",limit=4)+memory.recall(category="EPISODIC",limit=4))
    procedures = memory.recall(category="PROCEDURAL",limit=2)
    reported = [ReportedFact(fact_id=m["original_event_id"] or m["memory_id"], statement=m["content"][:512],
        source=m["owner_id"], validity_policy_id=m["validity_policy_id"],
        provenance=(m["original_event_id"] or m["source_event_id"],)) for m in memories if m["claim_kind"] == "REPORTED"][:4]
    # Explicitly controlled facts replace raw prior-query reminders, even after revocation.
    controlled = store.registry.database.connection.execute(
        "SELECT 1 FROM memory_provenance p JOIN memory_entries e USING(memory_id) "
        "WHERE e.tenant_id=? AND p.origin_case_id=? AND p.owner_id=? "
        "AND NOT EXISTS(SELECT 1 FROM memory_promotion_links l WHERE l.memory_id=e.memory_id) LIMIT 1",
        (store.principal.tenant_id, store.case_id, store.principal.principal_id)).fetchone()
    if not reported and not controlled:
        reported = [f.model_copy(update={"statement": f.statement[:512]}) for f in store.own_reported_facts()]
    hypotheses = [Hypothesis(hypothesis_id=m["memory_id"], statement=m["content"][:256])
                  for m in memories if m["claim_kind"] == "HYPOTHESIS"][:2]
    for index, item in enumerate(prior.get("hypotheses", [])[:2]):
        hypotheses.append(Hypothesis(hypothesis_id="prior-"+str(index), statement=item["text"]))
    observations = []
    rows = store.registry.database.connection.execute(
        "SELECT event_id FROM case_events WHERE tenant_id=? AND case_id=? "
        "AND event_kind='LIVE_OBSERVATION' ORDER BY occurred_at DESC,event_id DESC LIMIT 32",
        (store.principal.tenant_id, store.case_id)).fetchall()
    seen = set()
    for row in rows:
        try:
            observed = read_observation(store.registry, store.principal, store.case_id, row[0])
        except (EvidenceAgentError, ValueError):
            continue
        if observed.operation_id in seen:
            continue
        seen.add(observed.operation_id)
        if observed.operation_status not in {LiveOperationStatus.OK, LiveOperationStatus.STALE_DATA}:
            continue
        for field in ("state", "settlement_state", "result"):
            if field in observed.data and len(str(observed.data[field])) <= 128:
                observations.append(VerifiedObservation(fact_id=observed.lookup_id+":"+field,
                    predicate=field, value=observed.data[field], evidence_id=observed.lookup_id,
                    observed_at=observed.observed_at, freshness_status="RECHECK_FOR_CURRENT_DECISION"))
    turns, omitted, truncated = store.conversation(suppress_queries=bool(controlled))
    packet = ContinuityPacket(case_id=store.case_id, tenant_id=store.principal.tenant_id,
        agent_role="investigator", current_goal=query[:512],
        verified_observations=tuple(observations[:3]), reported_facts=tuple(reported),
        hypotheses=tuple(hypotheses[:2]), open_questions=store.unresolved_questions(),
        evidence_handles=tuple(handles), last_disposition=GateDisposition(prior["disposition"]) if prior else None,
        conversation_turns=turns, conversation_omitted=omitted, conversation_truncated=truncated,
        previous_attempts=tuple({"kind":"UNAPPROVED_PROCEDURAL_EXPERIENCE", "authority":"NONE",
            "at":m["set_at"], "payload":{"status":"UNAPPROVED_CONTEXT", "memory_id":m["memory_id"],
            "content":m["content"],"original_event_id":m["original_event_id"]}}
            for m in procedures)+tuple(e for e in events if e["kind"] in {"RUNTIME_ATTEMPT", "RUNTIME_TOOL_RESULT"})[-2:],
        generated_at=store.registry.clock())
    # Keep critical unresolved slots first; omit lower-priority context explicitly in metrics.
    while len(packet.model_dump_json()) > max_chars and packet.conversation_turns:
        packet = packet.model_copy(update={"conversation_turns": packet.conversation_turns[1:],
            "conversation_omitted": packet.conversation_omitted + 1, "conversation_truncated": True})
    for field in ("previous_attempts", "evidence_handles", "reported_facts", "hypotheses", "verified_observations"):
        while len(packet.model_dump_json()) > max_chars and getattr(packet, field):
            packet = packet.model_copy(update={field: getattr(packet, field)[:-1]})
    if len(packet.model_dump_json()) > max_chars:
        packet = packet.model_copy(update={"current_goal": query[:128]})
    return packet
