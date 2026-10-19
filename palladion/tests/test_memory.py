"""Scoped memory, provenance, packet and invalidation consumers on synthetic state."""

import asyncio
import json

import pytest

from evidence_agent.core.errors import PermissionDenied
from evidence_agent.memory.packet import build_packet
from evidence_agent.memory.store import CaseStore, MemorySpec
from evidence_agent.storage.originals import OriginalStore
from evidence_agent.storage.registry import Registry
from evidence_agent.storage.sqlite import Database

from .test_agent_budget import make_runtime


def test_scoped_categories_fts_exact_and_explicit_promotion(p03):
    user = CaseStore(p03.registry, p03.reader, "case-42").memory()
    admin = CaseStore(p03.registry, p03.admin, "case-42").memory()
    private = user.write(MemorySpec(scope_id="reader-a", content="PRIVATE violet debit"))
    assert user.recall(query="violet")[0]["memory_id"] == private
    assert user.recall(memory_id=private)[0]["authority"] == "NONE"
    assert admin.recall(query="PRIVATE") == []
    for category in ("EPISODIC", "SEMANTIC", "PROCEDURAL"):
        identifier = admin.write(MemorySpec(scope_kind="CASE", scope_id="case-42",
            memory_kind=category, content="workflow "+category,
            claim_kind="PROCEDURE" if category == "PROCEDURAL" else "REPORTED"))
        if category == "EPISODIC":
            assert user.recall(memory_id=identifier, category=category) == []
            assert admin.recall(memory_id=identifier, category=category)[0]["kind"] == category
        else:
            assert user.recall(memory_id=identifier, category=category)[0]["kind"] == category
    with pytest.raises(PermissionDenied):
        user.write(MemorySpec(scope_kind="ORGANIZATION", scope_id="tenant-a", content="approve payment"))
    promoted = admin.write(MemorySpec(scope_kind="ORGANIZATION", scope_id="tenant-a", content="approved reminder"))
    assert user.read(promoted)["verification_status"] == "UNVERIFIED"
    with pytest.raises(ValueError):
        user.recall(query="x"*257)
    assert user.recall(query='" OR *') == []


def test_team_membership_and_origin_case_revocation_are_both_required(p03):
    admin = CaseStore(p03.registry, p03.admin, "case-42").memory()
    user = CaseStore(p03.registry, p03.reader, "case-42").memory()
    admin.team_membership("support", "admin-a")
    identifier = admin.write(MemorySpec(scope_kind="TEAM", scope_id="support", content="TEAM_PRIVATE_CANARY"))
    assert user.recall(query="TEAM_PRIVATE_CANARY") == []
    admin.team_membership("support", "reader-a")
    assert user.read(identifier)["content"] == "TEAM_PRIVATE_CANARY"
    admin.team_membership("support", "reader-a", revoke=True)
    with pytest.raises(PermissionDenied):
        user.read(identifier)
    admin.team_membership("support", "reader-a")
    p03.registry.revoke_membership(p03.admin, "reader-a", "case-42")
    with pytest.raises(PermissionDenied):
        user.recall(query="TEAM_PRIVATE_CANARY")


def test_correction_revoke_and_validity_history_survive_reopen(p03):
    import sqlite3
    from datetime import timedelta

    from evidence_agent.live.gateway import utc_clock
    user = CaseStore(p03.registry, p03.reader, "case-42").memory()
    first = user.write(MemorySpec(scope_id="reader-a", content="debit reported"))
    assert user.read(first)["validity_policy_id"] == "UNSPECIFIED"
    second = user.write(MemorySpec(scope_id="reader-a", content="debit corrected"), supersedes_id=first)
    assert user.recall(query="reported") == []
    assert user.read(second)["set_by"] == "reader-a"
    with pytest.raises(PermissionDenied):
        user.read(first)
    with pytest.raises(sqlite3.IntegrityError):
        p03.registry.database.connection.execute("UPDATE memory_entries SET content='poison' WHERE memory_id=?", (second,))
    with pytest.raises(ValueError):
        user.write(MemorySpec(scope_id="reader-a", content="bad", valid_until=utc_clock()-timedelta(seconds=1)))
    user.revoke(second)
    assert user.recall(query="debit") == []
    with Database(p03.registry.database.path) as db:
        registry = Registry(db, p03.registry.originals)
        reopened = CaseStore(registry, registry.access.authenticate("reader-a"), "case-42")
        assert reopened.memory().recall() == []
        assert build_packet(reopened, "follow up").reported_facts == ()
        assert db.connection.execute("SELECT count(*) FROM memory_entries").fetchone()[0] == 2
        assert db.connection.execute("SELECT count(*) FROM case_events WHERE event_kind LIKE 'MEMORY_%'").fetchone()[0] == 3


def test_packet_preserves_critical_gap_under_long_chatter_and_close(p03):
    from evidence_agent.core.models import ContinuityPacket
    store = CaseStore(p03.registry, p03.reader, "case-42")
    store.append("RELEASE", "gap", {"disposition": "PARTIALLY_SUPPORTED", "citations": [],
        "missing_requirements": ["settlement_state"],
        "hypotheses": [{"text": "A reconciliation delay is possible; this is unverified.", "verification_status": "UNVERIFIED"}]})
    for number in range(45):
        store.append("REQUEST", "chatter", {"query": "irrelevant "*150})
        store.append("ATTEMPT", "chatter", {"attempt": number, "status": "FAILED"})
    packet = build_packet(store, "follow up", max_chars=1500)
    assert packet.open_questions == ("settlement_state",)
    assert len(packet.model_dump_json()) <= 1500
    with pytest.raises(ValueError):
        ContinuityPacket.model_validate({**packet.model_dump(), "principal_id": "admin-a"})
    CaseStore(p03.registry, p03.admin, "case-42").memory().close_case()
    closed = build_packet(store, "follow up")
    assert closed.evidence_handles == closed.reported_facts == closed.hypotheses == ()


def test_memory_tool_reads_exact_scoped_item_as_context_never_authority(p03):
    fixture = make_runtime(p03)
    identifier = fixture.store.memory().write(MemorySpec(scope_id="reader-a", content="remember violet"))
    result = asyncio.run(fixture.tools.execute("recall_memory", json.dumps({"memory_id": identifier})))
    assert result["status"] == "SUCCEEDED"
    assert result["data"][0]["content"] == "remember violet"
    assert fixture.ledger.records[identifier]["authority"] == "NONE"


def test_admin_correction_preserves_private_owner_and_cannot_declassify_origin(p03):
    user = CaseStore(p03.registry, p03.reader, "case-42").memory()
    admin = CaseStore(p03.registry, p03.admin, "case-42").memory()
    first = user.write(MemorySpec(scope_id="reader-a", content="old report"))
    second = admin.write(MemorySpec(scope_id="reader-a", content="corrected report"), supersedes_id=first)
    assert user.read(second)["owner_id"] == "reader-a"
    assert user.read(second)["set_by"] == "admin-a"
    assert admin.recall(memory_id=second) == []
    promoted = admin.write(MemorySpec(scope_kind="ORGANIZATION", scope_id="tenant-a",
        content="explicitly shared report"), supersedes_id=second, general=True)
    assert user.read(promoted)["origin_case_id"] == "case-42"
    p03.registry.revoke_membership(p03.admin, "reader-a", "case-42")
    with pytest.raises(PermissionDenied):
        user.read(promoted)


def test_case_scope_cannot_be_recalled_from_another_case_and_general_org_is_explicit(p03):
    registry = p03.registry
    admin = CaseStore(registry, p03.admin, "case-42").memory()
    identifier = admin.write(MemorySpec(scope_kind="CASE", scope_id="case-42", content="CASE_ONLY_CANARY"))
    registry.bootstrap_case("tenant-a", "case-shared-memory")
    registry.bootstrap_membership(p03.admin, "case-shared-memory")
    current_admin = registry.access.authenticate("admin-a")
    other = CaseStore(registry, current_admin, "case-shared-memory").memory()
    admin = CaseStore(registry, current_admin, "case-42").memory()
    with pytest.raises(PermissionDenied):
        other.read(identifier)
    general = admin.write(MemorySpec(scope_kind="ORGANIZATION", scope_id="tenant-a", content="shared workflow"), general=True)
    assert other.read(general)["content"] == "shared workflow"


def test_passage_cache_bounds_ttl_scope_epoch_and_failure(p03):
    from evidence_agent.memory.hotcache import HotCache
    now = [0.0]
    cache = HotCache(capacity=1, ttl_seconds=1, clock=lambda: now[0])
    value = {"kind": "DOCUMENT", "text": "EXACT_CANARY", "content_sha256": "a"*64,
             "evidence_id": "chunk_a", "generation": "g"}
    calls = []
    def loader():
        calls.append(1)
        return dict(value)
    def get(epoch="0", principal=p03.reader):
        return cache.read(loader, principal=principal, case_id="case-42", epoch=epoch)
    get()
    result = get()
    assert cache.hits == 1 and len(calls) == 2  # A cache hit still validates its source.
    result["text"] = "poison"
    assert get()["text"] == "EXACT_CANARY"
    get(principal=p03.admin)
    assert cache.hits == 2  # Another principal cannot hit the earlier entry.
    get("correction")
    get("closed")
    assert cache.hits == 2
    now[0] = 2
    get("closed")
    assert cache.hits == 2 and len(cache.entries) == 1
    def denied():
        raise PermissionDenied
    with pytest.raises(PermissionDenied):
        cache.read(denied, principal=p03.reader, case_id="case-42", epoch="closed")
    assert not cache.entries


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
    assert packet.verified_observations[0].freshness_status == "RECHECK_FOR_CURRENT_DECISION"
    assert "OLD_TEXT_CANARY" not in str(fixture.store.recent())


def test_owner_can_correct_expired_validity_and_closed_case_rejects_writes(p03):
    from datetime import timedelta

    from evidence_agent.live.gateway import utc_clock
    memory = CaseStore(p03.registry, p03.reader, "case-42").memory()
    old = memory.write(MemorySpec(scope_id="reader-a", content="old report",
        valid_from=utc_clock()-timedelta(days=2), valid_until=utc_clock()-timedelta(days=1),
        validity_policy_id="owner-explicit"))
    assert memory.recall(memory_id=old) == []
    new = memory.write(MemorySpec(scope_id="reader-a", content="renewed report"), supersedes_id=old)
    assert memory.read(new)["valid_until"] is None
    CaseStore(p03.registry, p03.admin, "case-42").memory().close_case()
    with pytest.raises(PermissionDenied):
        memory.write(MemorySpec(scope_id="reader-a", content="post-close report"))


def test_runtime_consumes_corrected_packet_but_only_releases_new_live_read(p03):
    from evidence_agent.agent.draft import Draft
    from evidence_agent.agent.llm import ModelTurn
    from evidence_agent.live.contracts import Snapshot
    fixture = make_runtime(p03)
    first = asyncio.run(fixture.tools.execute("lookup_live_data", json.dumps({
        "operation": "get_transaction_status", "target_id": "TX-DEMO-102"})))
    fixture.store.append("RELEASE", "prior", {"disposition": "PARTIALLY_SUPPORTED",
        "citations": [first["data"]], "missing_requirements": ["settlement_state"]})
    old = fixture.store.memory().write(MemorySpec(scope_id="reader-a", content="OLD_REPORT_CANARY"))
    fixture.store.memory().write(MemorySpec(scope_id="reader-a", content="CORRECTED_REPORT"), supersedes_id=old)
    class GuardInputModel:
        """Typed proposal injection exercises consumer wiring; not provider proof."""
        def __init__(self):
            self.checked = False
        async def complete(self, messages, tools, *, final=False, before_send=None):
            if before_send is not None:
                before_send()
            if final:
                return ModelTurn({"content": messages[-1]["content"] and self.draft}, {})
            if len(messages) == 2:
                context = json.loads(messages[-1]["content"])["untrusted_case_context"]
                assert context["open_questions"] == ["settlement_state"]
                assert context["reported_facts"][0]["statement"] == "CORRECTED_REPORT"
                assert "OLD_REPORT_CANARY" not in str(context)
                assert context["verified_observations"][0]["freshness_status"] == "RECHECK_FOR_CURRENT_DECISION"
                self.checked = True
                return ModelTurn({"tool_calls": [{"id": "fresh", "type": "function", "function": {
                    "name": "lookup_live_data", "arguments": json.dumps({"operation": "get_transaction_status", "target_id": "TX-DEMO-102"})}}]}, {})
            observed = json.loads(messages[-1]["content"])["data"]
            assert observed["data"]["state"] == "PENDING"
            self.draft = Draft.model_validate_json(json.dumps({"claims": [{"id": "new", "type": "OBSERVED_FACT",
                "text": "fresh state", "evidence_ids": [observed["evidence_id"]], "field": "state", "value": "PENDING"}]})).model_dump_json()
            return ModelTurn({"content": self.draft}, {})
    model = GuardInputModel()
    resumed = make_runtime(p03, model=model)
    resumed.adapter.snapshots[("get_transaction_status", "TX-DEMO-102")] = (Snapshot(status="OK", data={
        "transaction_id": "TX-DEMO-102", "state": "PENDING", "transaction_occurred_at": "2026-08-15T10:20:00Z"}),)
    result = asyncio.run(resumed.runtime.answer("follow up"))
    assert model.checked and "PENDING" in result["verified_claims"][0]["text"]
    assert first["data"]["evidence_id"] not in str(result["citations"])


def test_private_candidate_flood_does_not_starve_authorized_fts_or_packet(p03):
    user = CaseStore(p03.registry, p03.reader, "case-42").memory()
    admin = CaseStore(p03.registry, p03.admin, "case-42").memory()
    wanted = user.write(MemorySpec(scope_id="reader-a", content="sharedterm authorized report"))
    for _ in range(501):
        admin.write(MemorySpec(scope_id="admin-a", content="sharedterm PRIVATE_FLOOD_CANARY"))
    # Negative control reproduces the old, wrongly ordered candidate window.
    legacy = p03.registry.database.connection.execute(
        "SELECT memory_id FROM memory_entries WHERE tenant_id='tenant-a' "
        "ORDER BY created_at DESC,memory_id DESC LIMIT 500").fetchall()
    assert wanted not in {r[0] for r in legacy}
    for query in (None, "sharedterm"):
        result = user.recall(query=query, limit=1)
        assert [r["memory_id"] for r in result] == [wanted]
        assert "PRIVATE_FLOOD_CANARY" not in str(result)
    packet = build_packet(user.case, "follow up")
    assert packet.reported_facts[0].statement == "sharedterm authorized report"
    assert "PRIVATE_FLOOD_CANARY" not in packet.model_dump_json()


def test_recall_reports_its_bounded_candidate_window_to_the_model(p03):
    fixture = make_runtime(p03)
    for _ in range(501):
        fixture.store.memory().write(MemorySpec(scope_id="reader-a", content="bounded candidate"))
    result = asyncio.run(fixture.tools.execute("recall_memory", '{"query":"bounded","limit":1}'))
    assert result["status"] == "SUCCEEDED" and len(result["data"]) == 1
    assert result["recall_coverage"] == {"candidate_window_incomplete": True,
                                        "exhaustive": False, "source_acl_rechecked": True}


def test_unresolved_policy_gap_survives_empty_failed_reply_until_executed_resolution(p03):
    from evidence_agent.live.contracts import Snapshot
    fixture = make_runtime(p03)
    async def incomplete():
        live = await fixture.tools.execute("lookup_live_data", json.dumps({
            "operation": "get_transaction_status", "target_id": "TX-DEMO-102"}))
        result = await fixture.tools.execute("evaluate_policy", json.dumps({
            "family_id": "DEMO.REVERSAL.CHECK", "evidence_ids": [live["data"]["evidence_id"]]}))
        assert result["data"]["status"] == "INCOMPLETE_INPUT"
        return live["data"]["evidence_id"]
    live_id = asyncio.run(incomplete())
    fixture.store.append("RELEASE", "partial", {"disposition": "PARTIALLY_SUPPORTED", "citations": [],
        "missing_requirements": ["settlement_state"]})
    fixture.store.append("RELEASE", "later-failure", {"disposition": "VERIFICATION_UNAVAILABLE",
        "citations": [], "missing_requirements": []})
    assert build_packet(fixture.store, "third follow up", max_chars=1500).open_questions == ("settlement_state",)
    fixture.adapter.snapshots[("get_settlement_status", "SET-DEMO-102")] = (Snapshot(status="OK", data={
        "settlement_id": "SET-DEMO-102", "settlement_state": "UNSETTLED"}),)
    async def resolve():
        settlement = await fixture.tools.execute("lookup_live_data", json.dumps({
            "operation": "get_settlement_status", "target_id": "SET-DEMO-102"}))
        result = await fixture.tools.execute("evaluate_policy", json.dumps({
            "family_id": "DEMO.REVERSAL.CHECK", "evidence_ids": [live_id, settlement["data"]["evidence_id"]]}))
        assert result["data"]["status"] == "DETERMINED"
    asyncio.run(resolve())
    assert build_packet(fixture.store, "resolved follow up").open_questions == ()


def test_unresolved_case_question_is_not_erased_by_an_empty_release(p03):
    store = CaseStore(p03.registry, p03.reader, "case-42")
    store.append("RELEASE", "gap", {"disposition": "PARTIALLY_SUPPORTED", "citations": [],
        "missing_requirements": ["settlement_state"]})
    store.append("RELEASE", "empty", {"disposition": "NOT_ESTABLISHED", "citations": [], "missing_requirements": []})
    assert build_packet(store, "follow up").open_questions == ("settlement_state",)
