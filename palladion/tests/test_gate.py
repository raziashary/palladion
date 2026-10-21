"""Claim/eligibility controls; exact attribution is not general semantic entailment."""

import asyncio
import json
from datetime import timedelta

import pytest

from evidence_agent.agent.draft import Claim, Draft
from evidence_agent.agent.gate import release
from evidence_agent.core.clock import utc_clock
from evidence_agent.core.errors import PermissionDenied

from .test_agent_budget import make_runtime


def live_fixture(p03):
    fixture = make_runtime(p03)
    result = asyncio.run(
        fixture.tools.execute(
            "lookup_live_data",
            json.dumps({"operation": "get_transaction_status", "target_id": "TX-DEMO-102"}),
        )
    )
    assert result["status"] == "SUCCEEDED"
    identifier = result["data"]["evidence_id"]
    claim = Claim(
        id="C1",
        type="OBSERVED_FACT",
        text="arbitrary prose cannot be rendered",
        evidence_ids=(identifier,),
        field="state",
        value="FAILED",
    )
    return fixture, identifier, claim


def test_typed_observation_is_supported_without_repeating_proposal(p03):
    fixture, identifier, claim = live_fixture(p03)
    result = release(Draft(claims=(claim,)), fixture.ledger)
    assert result["disposition"] == "SUPPORTED"
    assert result["verified_claims"][0]["evidence_ids"] == [identifier]
    assert "FAILED" in result["verified_claims"][0]["text"]
    assert "arbitrary prose" not in str(result)


@pytest.mark.parametrize("kind", ["POLICY_RESULT", "HYPOTHESIS", "SOURCE_QUOTE", "OBSERVED_FACT"])
def test_mislabeled_action_or_unknown_evidence_never_released(p03, kind):
    fixture = make_runtime(p03)
    claim = Claim(
        id="evil",
        type=kind,
        text="reverse immediately SECRET_CANARY",
        evidence_ids=("made-up",),
        field="state",
        value="FAILED",
    )
    result = release(Draft(claims=(claim,), answer_kind="INFORMATIONAL"), fixture.ledger)
    assert result["verified_claims"] == []
    assert result["disposition"] != "SUPPORTED"
    assert "reverse immediately" not in str(result) and "SECRET_CANARY" not in str(result)


def test_missing_policy_slots_survive_model_omission_and_gate_reads_trace(p03):
    fixture, identifier, claim = live_fixture(p03)
    result = asyncio.run(
        fixture.tools.execute(
            "evaluate_policy",
            json.dumps({"family_id": "DEMO.REVERSAL.CHECK", "evidence_ids": [identifier]}),
        )
    )
    assert result["data"]["status"] == "INCOMPLETE_INPUT"
    policy_id = result["data"]["evidence_id"]
    requirement = Claim(
        id="C2",
        type="RULE_REQUIREMENT",
        text="settlement is required",
        evidence_ids=(policy_id,),
        field="settlement_state",
    )
    response = release(Draft(claims=(claim, requirement), required_slots=()), fixture.ledger)
    assert response["disposition"] == "PARTIALLY_SUPPORTED"
    assert "settlement_state" in response["missing_requirements"]
    assert len(response["verified_claims"]) == 2
    assert fixture.ledger.read(policy_id)["rule_trace"] == []
    assert "rule_trace" not in response["citations"][1]
    assert response["citations"][1]["version_id"] == "demo-reversal-2026-b"


def test_stale_and_mid_request_revocation_are_rechecked(p03, monkeypatch):
    fixture, identifier, claim = live_fixture(p03)
    monkeypatch.setattr(p03.registry, "clock", lambda: utc_clock() + timedelta(seconds=1000))
    response = release(Draft(claims=(claim,)), fixture.ledger)
    assert response["verified_claims"] == []
    p03.registry.revoke_membership(p03.admin, p03.reader.principal_id, "case-42")
    with pytest.raises(PermissionDenied):
        fixture.ledger.read(identifier)


def test_operational_review_cannot_be_skipped_by_pass_or_kind(p03):
    fixture, _, claim = live_fixture(p03)
    result = release(Draft(claims=(claim,), answer_kind="OPERATIONAL_GUIDANCE"), fixture.ledger)
    assert result["disposition"] == "PARTIALLY_SUPPORTED"
    assert "mandatory_critic_review" in result["missing_requirements"]
    assert result["review_status"] == "UNAVAILABLE_UNTIL_P06"


def test_no_evidence_and_outage_are_distinct(p03):
    fixture = make_runtime(p03)
    absent = release(Draft(), fixture.ledger)
    assert absent["disposition"] == "NOT_ESTABLISHED"
    assert "No source search was performed" in absent["answer"]
    fixture.ledger.failures.append("INDEX_UNAVAILABLE")
    result = release(Draft(), fixture.ledger)
    assert result["disposition"] == "VERIFICATION_UNAVAILABLE"
    assert result["searched_scope"] == "No source search was performed."
    assert not result["inventory_attested"]


@pytest.mark.parametrize("review_state", ["absent", "unavailable", "stale", "pass"])
def test_complete_policy_requirement_requires_current_review(p03, monkeypatch, review_state):
    from datetime import datetime, timezone

    from evidence_agent.agent.critic import ReviewResult, evidence_digest
    from evidence_agent.core.models import CriticReview, GateDisposition

    from .test_policy_engine import engine, observations
    p03.now = datetime.now(timezone.utc)
    fixture = make_runtime(p03)
    decision = engine(p03).evaluate(p03.reader, "case-42", "DEMO.REVERSAL.CHECK",
        tuple(item.lookup_id for item in observations(p03)))
    assert decision.status.value == "DETERMINED" and not decision.missing_fields
    fixture.ledger.add(decision.audit_id)
    draft = Draft(claims=(Claim(id="requirement", type="RULE_REQUIREMENT",
        text="settlement is required", evidence_ids=(decision.audit_id,), field="settlement_state"),))
    review = None
    if review_state == "unavailable":
        review = ReviewResult()
    elif review_state in {"stale", "pass"}:
        review = ReviewResult("PASS", CriticReview(review_id="review-complete", verdict="PASS",
            proposed_disposition=GateDisposition.SUPPORTED),
            evidence_digest(draft.model_dump(mode="json")),
            evidence_digest(fixture.ledger.records) if review_state == "pass" else "stale")
    result = release(draft, fixture.ledger, review=review)
    assert len(result["verified_claims"]) == 1  # Known facts survive unavailable review.
    assert "settlement_state" in result["verified_claims"][0]["text"]
    assert result["disposition"] == ("SUPPORTED" if review_state == "pass" else "PARTIALLY_SUPPORTED")
    assert ("mandatory_critic_review" in result["missing_requirements"]) == (review_state != "pass")


def test_conflict_keeps_exact_invocation_and_candidate_sources_then_revalidates(p03):
    from evidence_agent.policy.engine import PolicyEngine
    from evidence_agent.policy.registry import PolicyRegistry, PolicySpec
    from evidence_agent.storage.originals import OriginalStore
    from evidence_agent.storage.registry import Registry
    from evidence_agent.storage.sqlite import Database
    fixture, identifier, _ = live_fixture(p03)
    row = p03.registry.database.connection.execute(
        "SELECT decision_table_json FROM policy_versions WHERE version_id='demo-reversal-2026-b'").fetchone()
    spec = PolicySpec.model_validate_json(row[0])
    policies = PolicyRegistry(p03.registry)
    for number in (1,2):
        policies.register(p03.admin, spec.model_copy(update={"version_id":f"gate-conflict-{number}",
            "family_id":"GATE.CONFLICT", "allowed_case_ids":("case-42",)}))
    result = asyncio.run(fixture.tools.execute("evaluate_policy", json.dumps({
        "family_id":"GATE.CONFLICT", "evidence_ids":[identifier]})))
    assert result["status"] == "SUCCEEDED", result
    assert result["data"]["status"] == "POLICY_CONFLICT"
    policy_id = result["data"]["evidence_id"]
    assert fixture.ledger.read(policy_id)["temporal_input_refs"] == [identifier]
    with Database(p03.registry.database.path) as database:
        reopened = Registry(database, OriginalStore(p03.registry.originals.root))
        decision = PolicyEngine(PolicyRegistry(reopened)).replay(
            reopened.access.authenticate("reader-a"), "case-42", policy_id)
        assert decision.temporal_input_refs == (identifier,)
        assert decision.input_evidence_refs == ()
    response = release(Draft(), fixture.ledger)
    assert response["disposition"] == "CONFLICT"
    refs = response["citations"][0]["clause_refs"]
    assert {r["version_id"] for r in refs} == {"gate-conflict-1", "gate-conflict-2"}
    assert all(r["applicability"] == "UNRESOLVED_CANDIDATE" for r in refs)
    policies.supersede(p03.admin, "gate-conflict-1", "gate-conflict-2", case_id="case-42",
        valid_from=spec.valid_from, reason="Explicit synthetic test precedence")
    with pytest.raises(PermissionDenied):
        fixture.ledger.read(policy_id)
    assert release(Draft(), fixture.ledger)["disposition"] == "VERIFICATION_UNAVAILABLE"


def test_exact_policy_quote_cannot_bypass_review_with_informational_label(p03, monkeypatch):
    from evidence_agent.policy.registry import PolicySpec
    fixture = make_runtime(p03)
    row = p03.registry.database.connection.execute(
        "SELECT decision_table_json FROM policy_versions WHERE version_id='demo-reversal-2026-b'").fetchone()
    clause = PolicySpec.model_validate_json(row[0]).clauses[0]
    original = p03.registry.read_source(p03.reader, clause.revision_id)
    text = original[clause.start_byte:clause.end_byte].decode()
    item = {"evidence_id":"chunk_guard", "kind":"DOCUMENT", "text":text,
        "revision_id":clause.revision_id, "start_byte":clause.start_byte, "end_byte":clause.end_byte}
    # Inject only the canonical-reader result for this isolated gate guard; actual original
    # readers are separately exercised through real Qdrant/HTTP in test_end_to_end.
    fixture.ledger.records[item["evidence_id"]] = item
    monkeypatch.setattr(fixture.ledger, "read", lambda identifier:item)
    response = release(Draft(answer_kind="INFORMATIONAL", claims=(Claim(id="quote", type="SOURCE_QUOTE",
        text=text, evidence_ids=(item["evidence_id"],)),)), fixture.ledger)
    assert response["disposition"] == "PARTIALLY_SUPPORTED"
    assert {"applicable_policy","mandatory_critic_review"}.issubset(response["missing_requirements"])
    assert "no action permission" in response["verified_claims"][0]["text"]
