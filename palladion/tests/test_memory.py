"""P04 event/packet skeleton only; does not close P05 semantic memory obligations."""

import asyncio
import json

import pytest

from evidence_agent.core.errors import PermissionDenied
from evidence_agent.memory.packet import build_packet
from evidence_agent.memory.store import CaseStore
from evidence_agent.storage.originals import OriginalStore
from evidence_agent.storage.registry import Registry
from evidence_agent.storage.sqlite import Database

from .test_agent_budget import make_runtime


def test_reopen_packet_preserves_reported_and_attempt_status(p03):
    store = CaseStore(p03.registry, p03.reader, "case-42")
    event = store.append(
        "REQUEST", "trace_memory", {"query": "User reports a debit; not a verified fact."}
    )
    store.append("ATTEMPT", "trace_memory", {"attempt": 1, "status": "FAILED", "role": "main"})
    path = p03.registry.database.path
    with Database(path) as db:
        reader = Registry(db, OriginalStore(p03.registry.originals.root))
        packet = build_packet(
            CaseStore(reader, reader.access.authenticate("reader-a"), "case-42"), "follow up"
        )
        assert packet.reported_facts[0].fact_id == event
        assert packet.reported_facts[0].validity_policy_id == "UNSPECIFIED"
        assert packet.reported_facts[0].verification_status.value == "UNVERIFIED"
        assert packet.previous_attempts[0]["payload"]["status"] == "FAILED"
        assert packet.verified_observations == ()


def test_packet_cannot_widen_case_or_promote(p03):
    with pytest.raises(PermissionDenied):
        build_packet(CaseStore(p03.registry, p03.reader, "foreign-case"), "question")
    with pytest.raises(ValueError):
        CaseStore(p03.registry, p03.reader, "case-42").append(
            "ORG_POLICY", "t", {"policy": "approve"}
        )


def test_prior_live_result_becomes_pointer_not_verified_fact(p03):
    fixture = make_runtime(p03)
    result = asyncio.run(fixture.tools.execute("lookup_live_data", json.dumps({
        "operation": "get_transaction_status", "target_id": "TX-DEMO-102"})))
    fixture.store.append("RELEASE", fixture.ledger.trace_id, {"disposition": "SUPPORTED",
        "citations": [result["data"]], "verified_claims": [{"text": "OLD_TEXT_CANARY"}]})
    packet = build_packet(fixture.store, "follow up")
    assert packet.evidence_handles[0].source_id == result["data"]["evidence_id"]
    assert packet.verified_observations == ()
    assert "OLD_TEXT_CANARY" not in str(fixture.store.recent())
