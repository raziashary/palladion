"""Necessary-condition gate with exact attribution/typed facts; no semantic proof claim."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from evidence_agent.agent.draft import Draft
from evidence_agent.core.errors import EvidenceAgentError
from evidence_agent.retrieval.coverage import claim_requirements, quote_policy_families
from evidence_agent.retrieval.evidence import RequestLedger, public_citation

_SAFE_HYPOTHESES = {"A reconciliation delay is possible; this is unverified."}


def release(draft: Draft, ledger: RequestLedger) -> dict[str, Any]:
    verified: list[dict[str, Any]] = []
    blocked: list[str] = []
    hypotheses: list[dict[str, str]] = []
    citations: dict[str, dict[str, Any]] = {}
    conflicts: dict[str, dict[str, Any]] = {}
    gaps: set[str] = set()
    conflict = False
    unavailable = bool(ledger.failures)
    current: dict[str, dict[str, Any]] = {}
    # Revalidate ALL evidence, including requirements omitted from the final model proposal.
    for identifier in ledger.records:
        try:
            item = ledger.read(identifier)
        except (EvidenceAgentError, ValueError):
            unavailable = True
            continue
        current[identifier] = item
        if item["kind"] == "POLICY_DECISION":
            gaps.update(str(s) for s in item["missing_fields"])
            conflict |= item["status"] == "POLICY_CONFLICT"
            unavailable |= item["status"] in {"UNVERIFIED_INPUT", "VERIFICATION_UNAVAILABLE"}
            if item["status"] == "NO_APPLICABLE_POLICY":
                gaps.add("applicable_policy")
            if item["status"] == "POLICY_CONFLICT":
                conflicts[identifier] = item
        elif item["kind"] == "LIVE_OBSERVATION" and not item["valid"] and item["status"] != "NOT_FOUND":
            unavailable = True
    for claim in draft.claims:
        if len(verified) >= (11 if conflicts else 12):
            blocked.append(claim.id)
            continue
        if claim.type == "HYPOTHESIS":
            if claim.text in _SAFE_HYPOTHESES and draft.answer_kind != "OPERATIONAL_GUIDANCE":
                hypotheses.append({"text": claim.text, "verification_status": "UNVERIFIED"})
            else:
                blocked.append(claim.id)
            continue
        items = [current[i] for i in claim.evidence_ids if i in current]
        text = None
        if len(items) == len(claim.evidence_ids) == 1:
            item = items[0]
            if claim.type == "SOURCE_QUOTE" and item["kind"] == "DOCUMENT" and claim.text in str(item["text"]):
                families = quote_policy_families(ledger.search.registry, ledger.principal, ledger.case_id, item, claim.text)
                if families:
                    available = {r["family_id"] for r in current.values() if r["kind"] == "POLICY_DECISION"}
                    if not families.issubset(available):
                        gaps.add("applicable_policy")
                    gaps.add("mandatory_critic_review")
                    unavailable = True
                text = "Approved source states: “" + claim.text + "” (attribution only; no action permission)."
            elif claim.type == "OBSERVED_FACT" and item["kind"] == "LIVE_OBSERVATION":
                data = item["data"]
                if isinstance(data, dict) and claim.field in data and type(data[claim.field]) is type(claim.value) and data[claim.field] == claim.value:
                    instant = datetime.fromisoformat(item.get("data_as_of") or item["observed_at"])
                    if claim.temporal_use == "CURRENT" and item.get("valid"):
                        text = f"Last observed {item['source_system']} {claim.field}: {claim.value} at {item['observed_at']}."
                    elif (claim.temporal_use == "HISTORICAL" and item["status"] in {"OK", "STALE_DATA"}
                          and claim.snapshot_as_of == instant):
                        text = (f"Historical {item['source_system']} snapshot as of {instant.isoformat()} reported "
                                f"{claim.field}: {claim.value}; this does not establish current state or another system's state.")
            elif claim.type == "RULE_REQUIREMENT" and item["kind"] == "POLICY_DECISION":
                if claim.field in item["required_fields"]:
                    text = f"Applicable policy requires {claim.field}; a requirement is not an action authorization."
            elif claim.type == "POLICY_RESULT" and item["kind"] == "POLICY_DECISION":
                # An executed result still cannot bypass mandatory independent normative review.
                gaps.add("mandatory_critic_review")
                unavailable = True
        if text is None:
            blocked.append(claim.id)
        else:
            verified.append({"claim_id": claim.id, "text": text, "evidence_ids": list(claim.evidence_ids)})
            citations.update({i: current[i] for i in claim.evidence_ids})
    if draft.answer_kind == "OPERATIONAL_GUIDANCE":
        gaps.add("mandatory_critic_review")
        unavailable = True
    # No model-proposed slot can erase trusted policy requirements, nor become a claimed policy requirement.
    if blocked:
        gaps.add("claim_support_not_established")
    for identifier, item in conflicts.items():
        if len(citations) >= 12:
            break
        citations[identifier] = item
    if conflict:
        disposition = "CONFLICT"
    elif verified and (gaps or unavailable or blocked):
        disposition = "PARTIALLY_SUPPORTED"
    elif unavailable:
        disposition = "VERIFICATION_UNAVAILABLE"
    elif verified:
        disposition = "SUPPORTED"
    else:
        disposition = "NOT_ESTABLISHED"
    search_status = ledger.tool_status.get("search_knowledge")
    if search_status is None:
        searched_scope = "No source search was performed."
    elif search_status == "OK":
        searched_scope = "Current authorized case and supplied index searched; inventory completeness is not attested."
    elif search_status == "DEGRADED":
        searched_scope = "Source search reported degraded coverage in the current authorized case; inventory completeness is not attested."
    else:
        searched_scope = "Source search could not complete for the current authorized case."
    absence = ("The request does not establish the requested conclusion. No source search was performed."
        if search_status is None else
        "The available results from the scoped source search do not establish the requested conclusion.")
    introductions = {
        "SUPPORTED": "The following attributed information is verified within this case scope.",
        "PARTIALLY_SUPPORTED": "Some information is verified; the available evidence does not establish operational eligibility.",
        "CONFLICT": "Applicable evidence conflicts; no policy winner or operational instruction can be established.",
        "NOT_ESTABLISHED": absence,
        "VERIFICATION_UNAVAILABLE": "Required verification could not complete; no operational instruction is established."}
    return {"case_id": ledger.case_id, "trace_id": ledger.trace_id, "disposition": disposition,
        "answer": introductions[disposition], "verified_claims": verified, "hypotheses": hypotheses,
        "missing_requirements": sorted(gaps), "requirement_origins": {
            r.slot: r.origin.value for r in claim_requirements(current.values(), draft.required_slots)},
        "citations": [public_citation(item) for item in list(citations.values())[:12]],
        "tool_status": ledger.tool_status, "searched_scope": searched_scope,
        "inventory_attested": False, "review_status": "UNAVAILABLE_UNTIL_P06",
        "next_steps": ["Obtain missing scoped evidence or request authorized human review."],
        "_blocked_claim_ids": blocked}
