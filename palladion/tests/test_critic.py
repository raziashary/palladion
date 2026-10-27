"""Advisory/ACL/budget controls; deterministic injections are not Groq integration proof."""
import asyncio
import json

import pytest
from pydantic import ValidationError

from evidence_agent.agent.critic import COUNTER_SEARCH_LIMIT, EvidenceCritic, validate_review
from evidence_agent.agent.draft import Claim, Draft
from evidence_agent.agent.gate import release
from evidence_agent.agent.llm import ModelFailure
from evidence_agent.core.models import CriticReview, GateDisposition
from evidence_agent.memory.store import MemorySpec

from .test_agent_budget import ScriptedModel, make_runtime
from .test_gate import live_fixture


def review(**fields):
    return {"review_id": "test-review", "verdict": "PASS", "proposed_disposition": "SUPPORTED", **fields}


def model_for(*reviews, delay=0):
    return ScriptedModel([], delay=delay, critic_turns=[
        value if isinstance(value, Exception) else {"content": json.dumps(value)} for value in reviews])


def run(fixture, model, draft=Draft(), **options):
    critic = EvidenceCritic(model, fixture.tools, fixture.runtime.budget)
    result = asyncio.run(critic.run("Investigate", {}, draft, **options))
    return result, critic


def test_legacy_review_roundtrip_and_structured_bounds():
    legacy = CriticReview(proposed_disposition=GateDisposition.PARTIALLY_SUPPORTED, finding_by_claim={"C1": "inquiry"})
    assert CriticReview.model_validate_json(legacy.model_dump_json()) == legacy
    assert legacy.verdict is None and legacy.claim_reviews == ()
    with pytest.raises(ValidationError):
        CriticReview.model_validate_json(json.dumps(review(counter_searches=[{"query": "x", "purpose": "y", "case_id": "foreign"}])))
    with pytest.raises(ValidationError):
        CriticReview.model_validate_json(json.dumps(review(counter_searches=[{"query": "x"*257, "purpose": "y"}])))


@pytest.mark.parametrize("payload", [
    review(claim_reviews=[{"claim_id": "invented", "finding": "SUPPORTED", "reason": "x"}]),
    review(verdict="CHALLENGE", contrary_evidence_refs=["invented-source"]),
    review(verdict="CHALLENGE", missing_slots=["invented_requirement"]),
    review(verdict="CHALLENGE", claim_reviews=[{"claim_id": "C1", "finding": "INVALID_ASSOCIATION", "reason": "no grounding"}]),
    review(verdict="CHALLENGE", claim_reviews=[{"claim_id": "C1", "finding": "CONTRARY_EVIDENCE", "reason": "x", "evidence_ids": ["made-up"]}]),
    review(contradictions=[{"evidence_ids": ["a", "b"], "reason": "invented"}]),
])
def test_unknown_or_ungrounded_challenges_are_rejected_and_repairs_count(p03, payload):
    fixture = make_runtime(p03)
    draft = Draft(claims=(Claim(id="C1", type="HYPOTHESIS", text="unverified"),))
    result, _ = run(fixture, model_for(payload, payload), draft)
    assert result.status == "UNAVAILABLE" and fixture.runtime.budget.critic_used == 2
    assert fixture.runtime.budget.main_used == 0
    assert "CRITIC_SCHEMA_OR_GROUNDING_FAILURE" in fixture.ledger.failures


def test_one_default_call_independent_context_and_no_native_tools(p03):
    fixture = make_runtime(p03)
    model = model_for(review())
    result, _ = run(fixture, model)
    assert result.status == "PASS" and fixture.runtime.budget.critic_used == 1
    messages = model.critic_calls[0]
    assert len(messages) == 2 and [m["role"] for m in messages] == ["system", "user"]
    context = json.loads(messages[1]["content"])
    assert context["inventory_attested"] is False
    assert context["allowed_missing_slots"] == []
    assert context["draft"] == Draft().model_dump(mode="json")
    assert "tool_calls" not in str(messages)


def test_unsupported_veto_does_not_erase_valid_typed_fact_or_create_conflict(p03):
    fixture, identifier, claim = live_fixture(p03)
    payload = review(verdict="CHALLENGE", proposed_disposition="CONFLICT", claim_reviews=[{
        "claim_id": claim.id, "finding": "CONTRARY_EVIDENCE", "reason": "UNSUPPORTED_VETO_CANARY",
        "evidence_ids": [identifier]}])
    result, _ = run(fixture, model_for(payload), Draft(claims=(claim,)))
    output = release(Draft(claims=(claim,)), fixture.ledger, review=result)
    assert output["disposition"] == "PARTIALLY_SUPPORTED" and len(output["verified_claims"]) == 1
    assert "unresolved_critic_challenge" in output["missing_requirements"]
    assert output["review_status"] == "CHALLENGE"
    assert "UNSUPPORTED_VETO_CANARY" not in str(output)


def test_pass_cannot_clear_canonical_missing_input(p03):
    fixture, identifier, claim = live_fixture(p03)
    asyncio.run(fixture.tools.execute("evaluate_policy", json.dumps({
        "family_id": "DEMO.REVERSAL.CHECK", "evidence_ids": [identifier]})))
    result, _ = run(fixture, model_for(review()), Draft(claims=(claim,)))
    output = release(Draft(claims=(claim,)), fixture.ledger, review=result)
    assert output["disposition"] == "PARTIALLY_SUPPORTED"
    assert "settlement_state" in output["missing_requirements"]


def test_counter_search_uses_shared_budget_and_actual_followup_review(p03, monkeypatch):
    fixture = make_runtime(p03)
    queries = []
    async def guarded(name, arguments):
        assert name == "search_knowledge"
        queries.append(json.loads(arguments))
        return {"status": "SUCCEEDED", "data": []}
    monkeypatch.setattr(fixture.tools, "execute", guarded)
    payload = review(verdict="CHALLENGE", counter_searches=[{"query": str(i), "purpose": "exception inquiry"} for i in range(3)])
    result, _ = run(fixture, model_for(payload, review()))
    assert result.status == "PASS" and fixture.runtime.budget.critic_used == 2
    assert len(queries) == fixture.runtime.budget.critic_search_used == fixture.runtime.budget.tools_used == 2
    assert all(set(q) == {"query", "limit"} for q in queries)
    assert all(q["limit"] == COUNTER_SEARCH_LIMIT == 6 for q in queries), "a counter-search sees enough passages"
    assert "CRITIC_SEARCH_BUDGET_EXHAUSTED" in fixture.ledger.failures


def test_fourth_review_rejected_with_no_dispatch(p03, monkeypatch):
    fixture = make_runtime(p03)
    async def guarded(*args):
        return {"status": "SUCCEEDED", "data": []}
    monkeypatch.setattr(fixture.tools, "execute", guarded)
    model = model_for(review(counter_searches=[{"query": "a", "purpose": "check"}]),
        review(counter_searches=[{"query": "b", "purpose": "check"}]), review())
    result, critic = run(fixture, model)
    assert result.status == "PASS" and len(model.critic_calls) == 3
    output = asyncio.run(critic.run("again", {}, Draft()))
    assert output.status == "UNAVAILABLE" and len(model.critic_calls) == 3
    assert "CRITIC_BUDGET_EXHAUSTED" in fixture.ledger.failures


def test_blind_requirements_withholds_draft_then_reviews_it(p03):
    fixture = make_runtime(p03)
    model = model_for(review(), review())
    result, _ = run(fixture, model, blind_requirements=True)
    assert result.status == "PASS" and len(model.critic_calls) == 2
    assert json.loads(model.critic_calls[0][1]["content"])["draft"] is None
    assert json.loads(model.critic_calls[1][1]["content"])["draft"] is not None


def test_provider_failure_no_hidden_retry_and_cancellation_counted(p03):
    fixture = make_runtime(p03)
    result, _ = run(fixture, model_for(ModelFailure("PROVIDER_HTTP_429")))
    assert result.status == "UNAVAILABLE" and fixture.runtime.budget.critic_used == 1
    fixture = make_runtime(p03)
    model = model_for(review(), delay=5)
    async def timeout():
        async with asyncio.timeout(0.02):
            await EvidenceCritic(model, fixture.tools, fixture.runtime.budget).run("q", {}, Draft())
    with pytest.raises(TimeoutError):
        asyncio.run(timeout())
    assert fixture.runtime.budget.critic_used == 1 and model.cancelled
    assert any(e["payload"].get("status") == "CANCELLED" for e in fixture.store.recent(limit=20))


def test_review_cannot_waive_later_revocation_or_changed_evidence(p03):
    fixture, identifier, claim = live_fixture(p03)
    result, _ = run(fixture, model_for(review()), Draft(claims=(claim,)))
    assert result.current(fixture.ledger.records)
    p03.registry.revoke_membership(p03.admin, p03.reader.principal_id, "case-42")
    output = release(Draft(claims=(claim,), answer_kind="OPERATIONAL_GUIDANCE"), fixture.ledger, review=result)
    assert output["verified_claims"] == [] and "mandatory_critic_review" in output["missing_requirements"]
    assert identifier not in {c["evidence_id"] for c in output["citations"]}


def test_recalled_fact_reaches_critic_as_unverified_context(p03):
    fixture = make_runtime(p03)
    fixture.store.memory().write(MemorySpec(scope_id="reader-a", content="own report"))
    asyncio.run(fixture.tools.execute("recall_memory", '{"query":"report"}'))
    result, _ = run(fixture, model_for(review()))
    assert result.status == "PASS" and fixture.ledger.records
    assert all(r["authority"] == "NONE" for r in fixture.ledger.records.values())


def test_unbound_legacy_review_is_not_runtime_pass(p03):
    fixture = make_runtime(p03)
    with pytest.raises(ValueError, match="identity/verdict"):
        validate_review(CriticReview(proposed_disposition=GateDisposition.SUPPORTED), Draft(), fixture.ledger)


def test_native_tool_verb_from_critic_never_dispatches(p03):
    fixture = make_runtime(p03)
    native = {"tool_calls":[{"id":"bad","type":"function","function":{"name":"lookup_live_data","arguments":"{}"}}]}
    model = ScriptedModel([],critic_turns=[native,native])
    result, _ = run(fixture,model)
    assert result.status == "UNAVAILABLE" and fixture.runtime.budget.critic_used == 2
    assert fixture.runtime.budget.tools_used == 0 and fixture.ledger.records == {}


def test_unsupported_pass_envelope_cannot_satisfy_review(p03):
    from evidence_agent.agent.critic import ReviewResult, evidence_digest
    fixture = make_runtime(p03)
    forged = ReviewResult("PASS",evidence_sha256=evidence_digest({}))
    output = release(Draft(answer_kind="OPERATIONAL_GUIDANCE"),fixture.ledger,review=forged)
    assert output["review_status"] == "UNAVAILABLE" and "mandatory_critic_review" in output["missing_requirements"]


@pytest.mark.parametrize("challenged,changed", [(False,False),(True,False),(False,True),(True,True)])
def test_executed_policy_literal_is_controlled_and_operational_adequacy_stays_qualified(p03,challenged,changed):
    from evidence_agent.live.contracts import Snapshot
    fixture,live_id,_ = live_fixture(p03)
    fixture.adapter.snapshots[("get_settlement_status","SET-DEMO-102")] = (Snapshot(status="OK",data={
        "settlement_id":"SET-DEMO-102","settlement_state":"UNSETTLED"}),)
    async def evaluate():
        live = await fixture.tools.execute("lookup_live_data",json.dumps({"operation":"get_settlement_status","target_id":"SET-DEMO-102"}))
        return await fixture.tools.execute("evaluate_policy",json.dumps({"family_id":"DEMO.REVERSAL.CHECK",
            "evidence_ids":[live_id,live["data"]["evidence_id"]]}))
    result = asyncio.run(evaluate())
    assert result["data"]["status"] == "DETERMINED"
    claim = Claim(id="P1",type="POLICY_RESULT",text="PAYMENT_PERMISSION_CANARY",evidence_ids=(result["data"]["evidence_id"],))
    draft = Draft(claims=(claim,))
    payload = review(verdict="CHALLENGE", claim_reviews=[{"claim_id":"P1",
        "finding":"CONTRARY_EVIDENCE","reason":"check conflict","evidence_ids":[live_id]}]) if challenged else review()
    assessment,_ = run(fixture,model_for(payload),draft)
    final = Draft(claims=(claim.model_copy(update={"text":"changed final proposal"}),)) if changed else draft
    output = release(final,fixture.ledger,review=assessment)
    assert output["disposition"] == ("PARTIALLY_SUPPORTED" if challenged or changed else "SUPPORTED")
    assert "FOLLOW_INVESTIGATION_SOP" in output["verified_claims"][0]["text"]
    assert ("unresolved_critic_challenge" in output["missing_requirements"]) is challenged
    assert ("revised_draft_requires_review" in output["missing_requirements"]) is changed
    assert "PAYMENT_PERMISSION_CANARY" not in str(output)
    qualified = release(Draft(claims=(claim,),answer_kind="OPERATIONAL_GUIDANCE"),fixture.ledger,review=assessment)
    assert qualified["disposition"] == "PARTIALLY_SUPPORTED" and "authorized_human_review" in qualified["missing_requirements"]


def test_repair_receives_allowlisted_cause_without_raw_exception_prose(p03):
    fixture = make_runtime(p03)
    model = model_for(review(verdict="CHALLENGE", missing_slots=["invented_requirement"]), review())
    result, _ = run(fixture, model)
    assert result.status == "PASS" and fixture.runtime.budget.critic_used == 2
    assert json.loads(model.critic_calls[1][1]["content"])["repair_hint"] == "Unknown critic requirement"
    assert "CRITIC_SCHEMA_OR_GROUNDING_FAILURE" in fixture.ledger.failures
    diagnostics = [json.loads(r[0]) for r in fixture.store.registry.database.connection.execute(
        "SELECT payload_json FROM case_events WHERE event_kind='RUNTIME_DIAGNOSTIC'")]
    assert any(d.get("critic_validation_issue") == "Unknown critic requirement" for d in diagnostics)
    assert "critic_validation_issue" not in str(fixture.store.recent(limit=20))



def test_unknown_repair_prose_never_enters_context_or_diagnostics(p03):
    fixture = make_runtime(p03)
    model = model_for(ValueError("PRIVATE_RAW_EXCEPTION_CANARY"), review())
    result, _ = run(fixture, model)
    assert result.status == "PASS" and fixture.runtime.budget.critic_used == 2
    assert "PRIVATE_RAW_EXCEPTION_CANARY" not in str(model.critic_calls)
    rows = fixture.store.registry.database.connection.execute("SELECT payload_json FROM case_events").fetchall()
    assert "PRIVATE_RAW_EXCEPTION_CANARY" not in str(rows)
    assert "critic_input_inventory" not in str(fixture.store.recent(limit=20))


def test_provider_code_survives_per_attempt_without_public_event_leak(p03):
    fixture = make_runtime(p03)
    result, _ = run(fixture, model_for(ModelFailure("PROVIDER_HTTP_400", "tool_use_failed")))
    assert result.status == "UNAVAILABLE"
    rows = fixture.store.registry.database.connection.execute(
        "SELECT payload_json FROM case_events WHERE event_kind='RUNTIME_ATTEMPT'").fetchall()
    assert any(json.loads(row[0]).get("provider_code") == "tool_use_failed" for row in rows)
    assert "tool_use_failed" not in str(fixture.store.recent(limit=20))



def test_requested_identifier_hints_are_bounded_and_not_existence_attestations(p03):
    fixture = make_runtime(p03)
    model = model_for(review())
    question = "Check " + " ".join("ERR-UNKNOWN-"+str(i) for i in range(12))
    result = asyncio.run(EvidenceCritic(model,fixture.tools,fixture.runtime.budget).run(question,{},Draft()))
    assert result.status == "PASS"
    context = json.loads(model.critic_calls[0][1]["content"])
    hints = context["requested_identifier_coverage"]
    assert len(hints) == 8 and all(h["represented_in_inventory"] is False for h in hints)
    assert context["inventory_attested"] is False
    assert all(set(h) == {"identifier","represented_in_inventory"} for h in hints)


def test_revised_final_fact_keeps_canonical_support_without_inheriting_review(p03):
    fixture, _, claim = live_fixture(p03)
    initial = Draft(claims=(claim,))
    assessment,_ = run(fixture,model_for(review()),initial)
    changed = Draft(claims=(claim.model_copy(update={"id":"new-final-claim"}),))
    output = release(changed,fixture.ledger,review=assessment)
    assert output["disposition"] == "PARTIALLY_SUPPORTED"
    assert output["verified_claims"][0]["claim_id"] == "new-final-claim"
    assert "revised_draft_requires_review" in output["missing_requirements"]
    assert "unresolved_critic_challenge" not in output["missing_requirements"]
    assert output["review_status"] == "PASS"
