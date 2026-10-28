"""A deterministic stand-in for Palladion's HTTP API, with the same response shapes the UI reads.

It exists so the UI can be tested, and shown, without a model, Qdrant or a quota. It is not a model of Palladion's
behavior: the real system is exercised by the live checks in docs/TESTING.md.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

AGENT_STEPS = ("TOOL_RESULT", "TOOL_RESULT", "TOOL_RESULT", "RELEASED_RESPONSE")


def create_fake(data_root: Path, *, step_delay: float = 0.12, agent: bool = True) -> FastAPI:
    app = FastAPI()
    auth = json.loads((data_root / "demo_auth.json").read_text(encoding="utf-8"))
    state: dict[str, Any] = {"n": 0, "timeline": {}, "sources": {}, "policies": {}, "calls": []}
    roles = {"admin-a": "admin", "uploader-a": "uploader", "reader-a": "reader", "reader-a-limited": "reader"}

    def next_id(prefix: str) -> str:
        state["n"] += 1
        return f"{prefix}{state['n']:032x}"[: len(prefix) + 32]

    def who(authorization: str | None) -> str:
        token = (authorization or "").removeprefix("Bearer ")
        if token not in auth:
            raise HTTPException(403, "Denied")
        return str(auth[token])

    @app.exception_handler(HTTPException)
    async def _(_: Request, error: HTTPException) -> JSONResponse:
        return JSONResponse({"detail": error.detail}, status_code=error.status_code)

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready() -> Any:
        if not agent:
            raise HTTPException(503, "Required dependency or runtime configuration unavailable")
        return {"status": "ready", "model_boundary": "enabled"}

    @app.post("/v1/cases/{case_id}/sessions", status_code=201)
    def start(case_id: str, authorization: str | None = Header(default=None)) -> dict[str, str]:
        who(authorization)
        return {"session_id": next_id("sess_"), "status": "ACTIVE"}

    @app.post("/v1/cases/{case_id}/sessions/{session_id}/close")
    def close(case_id: str, session_id: str, authorization: str | None = Header(default=None)) -> dict[str, str]:
        who(authorization)
        return {"session_id": session_id, "status": "CLOSED"}

    @app.get("/v1/cases/{case_id}/timeline")
    def timeline(case_id: str, authorization: str | None = Header(default=None)) -> list[dict[str, Any]]:
        who(authorization)
        return list(reversed(state["timeline"].get(case_id, [])))

    @app.post("/v1/cases/{case_id}/messages")
    async def message(case_id: str, body: dict[str, Any], authorization: str | None = Header(default=None)) -> Any:
        who(authorization)
        if not agent:
            raise HTTPException(503, "Agent runtime explicitly disabled")
        state["calls"].append(("message", body))
        trace = next_id("trace_")
        for step, kind in enumerate(AGENT_STEPS):
            await asyncio.sleep(step_delay)
            state["timeline"].setdefault(case_id, []).append({
                "event_id": next_id("evt_"), "kind": kind, "at": f"2026-10-28T10:00:{step:02d}Z", "trace_id": trace,
                "status": "SUCCEEDED" if kind == "TOOL_RESULT" else "PARTIALLY_SUPPORTED"})
        return answer(case_id, body["query"], body.get("session_id") or next_id("sess_"), trace)

    def answer(case_id: str, query: str, session_id: str, trace: str) -> dict[str, Any]:
        q = query.lower()
        base: dict[str, Any] = {
            "case_id": case_id, "session_id": session_id, "trace_id": trace, "hypotheses": [],
            "missing_requirements": [], "requirement_origins": {}, "citations": [], "verified_claims": [],
            "tool_status": {"search_knowledge": "OK"}, "verification_failures": [], "inventory_attested": False,
            "searched_scope": "Current authorized case and supplied index searched; inventory completeness is "
                              "not attested.",
            "review_status": "PASS", "budget": {"main_used": 3, "critic_used": 1},
            "next_steps": ["Obtain missing scoped evidence or request authorized human review."]}
        doc = {"evidence_id": "chunk_sop2026", "kind": "DOCUMENT", "revision_id": "rev_sop2026", "section_id": "3",
               "generation": "gen-1", "start_byte": 705, "end_byte": 1124}
        if "reverse" in q:
            return {**base, "disposition": "PARTIALLY_SUPPORTED",
                    "answer": "Some information is verified; the available evidence does not establish "
                              "operational eligibility.",
                    "verified_claims": [
                        {"claim_id": "C1", "text": "Last observed mock_transaction_api state: FAILED at "
                                                   "2026-10-28T06:42:00Z.", "evidence_ids": ["live_tx1"]},
                        {"claim_id": "C2", "text": "Applicable policy requires settlement_state; a requirement is not "
                                                   "an action authorization.", "evidence_ids": ["policy_p1"]}],
                    "missing_requirements": ["settlement_state", "authorized_human_review"],
                    "requirement_origins": {"settlement_state": "POLICY_SCHEMA"},
                    "citations": [doc, {"evidence_id": "live_tx1", "kind": "LIVE_OBSERVATION",
                                        "operation": "get_transaction_status", "source_system": "mock_transaction_api",
                                        "observed_at": "2026-10-28T06:42:00Z", "status": "OK"},
                                  {"evidence_id": "policy_p1", "kind": "POLICY_DECISION", "status": "INCOMPLETE_INPUT",
                                   "family_id": "DEMO.REVERSAL.CHECK", "version_id": "demo-reversal-2026-b",
                                   "time_basis": "TRANSACTION_OCCURRED_AT", "as_of": "2026-08-15T10:20:00Z"}],
                    "tool_status": {"search_knowledge": "OK", "lookup_live_data": "TIMEOUT",
                                    "evaluate_policy": "VERIFICATION_UNAVAILABLE"},
                    "verification_failures": ["LIVE_UNAVAILABLE"]}
        if "conflict" in q or "overlap" in q:
            return {**base, "disposition": "CONFLICT",
                    "answer": "Applicable evidence conflicts; no policy winner or operational instruction can be "
                              "established.",
                    "citations": [{"evidence_id": "policy_p2", "kind": "POLICY_DECISION", "status": "POLICY_CONFLICT",
                                   "family_id": "DEMO.REVERSAL.CHECK", "time_basis": "TRANSACTION_OCCURRED_AT"}]}
        if "atm" in q or "unknown" in q:
            return {**base, "disposition": "NOT_ESTABLISHED",
                    "answer": "The available results from the scoped source search do not establish the requested "
                              "conclusion."}
        return {**base, "disposition": "SUPPORTED",
                "answer": "The following attributed information is verified within this case scope.",
                "verified_claims": [{"claim_id": "C1", "text": "Approved source states: “check both transaction and "
                                     "settlement status.” (attribution only; no action permission).",
                                     "evidence_ids": ["chunk_sop2026"]}],
                "citations": [doc]}

    @app.get("/v1/evidence/{evidence_id}")
    def evidence(evidence_id: str, case_id: str, authorization: str | None = Header(default=None)) -> Any:
        who(authorization)
        if evidence_id.startswith("chunk_"):
            return {"evidence_id": evidence_id, "kind": "DOCUMENT", "revision_id": "rev_sop2026", "section_id": "3",
                    "generation": "gen-1", "start_byte": 705, "end_byte": 1124,
                    "text": "[CLAUSE: S26-REVERSAL] A reversal review may proceed only when the transaction is "
                            "FAILED and settlement is UNSETTLED."}
        if evidence_id.startswith("live_"):
            return {"evidence_id": evidence_id, "kind": "LIVE_OBSERVATION", "operation": "get_transaction_status",
                    "source_system": "mock_transaction_api", "observed_at": "2026-10-28T06:42:00Z", "status": "OK",
                    "data": {"state": "FAILED"}, "valid": True}
        if evidence_id.startswith("policy_"):
            return {"evidence_id": evidence_id, "kind": "POLICY_DECISION", "status": "INCOMPLETE_INPUT",
                    "family_id": "DEMO.REVERSAL.CHECK", "version_id": "demo-reversal-2026-b",
                    "time_basis": "TRANSACTION_OCCURRED_AT", "as_of": "2026-08-15T10:20:00Z", "clause_count": 1,
                    "clause_refs": [{"version_id": "demo-reversal-2026-b", "clause_index": 0,
                                     "revision_id": "rev_sop2026", "section_id": "S26-REVERSAL",
                                     "applicability": "SELECTED"}], "action_permission": False}
        raise HTTPException(403, "Denied")

    @app.get("/v1/evidence/{evidence_id}/clauses/{index}")
    def clause(evidence_id: str, index: int, case_id: str, version_id: str,
               authorization: str | None = Header(default=None)) -> dict[str, Any]:
        who(authorization)
        return {"evidence_id": evidence_id, "version_id": version_id, "revision_id": "rev_sop2026",
                "section_id": "S26-REVERSAL", "start_byte": 705, "end_byte": 1124,
                "text": "A reversal review may proceed only when ...", "action_permission": False}

    @app.get("/v1/traces/{trace_id}")
    def trace(trace_id: str, case_id: str, authorization: str | None = Header(default=None)) -> Any:
        if roles.get(who(authorization)) != "admin":
            raise HTTPException(403, "Denied")
        return {"trace_id": trace_id, "stages": []}

    @app.post("/search")
    def search(body: dict[str, Any], authorization: str | None = Header(default=None)) -> Any:
        who(authorization)
        return {"status": "OK", "mode": body["mode"], "trace_id": next_id("retrieval_"), "warnings": [],
                "excluded": {"NOT_ELIGIBLE": 2, "INTEGRITY_CONFLICT": 0}, "elapsed_ms": 812.0,
                "passages": [{"citation_id": "chunk_sop2026", "revision_id": "rev_sop2026", "generation": "gen-1",
                              "section_id": "demo.dispute.sop-revision-2026.2/3.-current-reversal-review",
                              "start_byte": 705, "end_byte": 1124, "line_start": 12, "line_end": 14,
                              "text": "## 3. Current reversal review [CLAUSE: S26-REVERSAL] ...", "sha256": "a" * 64,
                              "heading_path": ["DEMO.DISPUTE.SOP", "3. Current reversal review"]}],
                "coverage": {"index_coverage": True, "accepted_source_count": 2, "indexed_source_count": 2}}

    @app.get("/index-health")
    def health(case_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        who(authorization)
        return {"index_coverage": True, "inventory_attested": False, "accepted_source_count": 2,
                "indexed_source_count": 2, "warnings": []}

    @app.get("/v1/cases/{case_id}/sources")
    def sources(case_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        me = who(authorization)
        rows = [s for s in state["sources"].values() if s["case_id"] == case_id
                and (roles.get(me) == "admin" or s["state"] == "APPROVED" or s["uploader_id"] == me)]
        return {"sources": [{k: v for k, v in s.items() if k != "case_id"} | {"mine": s["uploader_id"] == me}
                            for s in rows]}

    @app.post("/sources", status_code=201)
    def upload(body: dict[str, Any], authorization: str | None = Header(default=None)) -> dict[str, str]:
        me = who(authorization)
        if roles.get(me) != "uploader":
            raise HTTPException(403, "Denied")
        revision = next_id("rev_")
        state["sources"][revision] = {"revision_id": revision, "case_id": body["case_id"], "family_id": body["family_id"],
                                      "filename": body["filename"], "state": "DRAFT", "index_state": "STORED",
                                      "valid_from": body.get("valid_from"), "valid_to": body.get("valid_to"),
                                      "uploader_id": me, "owner_id": body["owner_id"], "registered_at": "now"}
        state["calls"].append(("upload", body))
        return {"revision_id": revision, "state": "STORED"}

    @app.post("/sources/import-pdf", status_code=201)
    def import_pdf(body: dict[str, Any], authorization: str | None = Header(default=None)) -> dict[str, Any]:
        made = upload({**body, "filename": body["filename"] + ".txt"}, authorization)
        return {**made, "page_count": 3, "offset_basis": "EXTRACTED_UTF8"}

    @app.post("/sources/{revision_id}/approve")
    def approve(revision_id: str, body: dict[str, Any] | None = None,
                authorization: str | None = Header(default=None)) -> dict[str, Any]:
        me = who(authorization)
        source = state["sources"].get(revision_id)
        if source is None or roles.get(me) != "admin" or source["uploader_id"] == me:
            raise HTTPException(403, "Denied")
        source.update(state="APPROVED", index_state="READY")
        return {"revision_id": revision_id, "generation": "gen-1", "state": "READY",
                "aliases": {"registered": 2, "truncated": False}}

    @app.post("/sources/{revision_id}/revoke")
    def revoke(revision_id: str, authorization: str | None = Header(default=None)) -> dict[str, str]:
        if roles.get(who(authorization)) != "admin" or revision_id not in state["sources"]:
            raise HTTPException(403, "Denied")
        state["sources"][revision_id]["state"] = "REVOKED"
        return {"revision_id": revision_id, "state": "REVOKED"}

    @app.get("/v1/admin/policies")
    def list_policies(case_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        if roles.get(who(authorization)) != "admin":
            raise HTTPException(403, "Denied")
        return {"policies": [p for p in state["policies"].values() if case_id in p["case_ids"]]}

    @app.post("/v1/admin/policies", status_code=201)
    def register(body: dict[str, Any], authorization: str | None = Header(default=None)) -> dict[str, str]:
        if roles.get(who(authorization)) != "admin":
            raise HTTPException(403, "Denied")
        state["calls"].append(("policy", body))
        state["policies"][body["version_id"]] = {**body, "state": "APPROVED", "supersedes": [], "superseded_by": [],
                                                 "author_id": "uploader-a", "product": "QR_DEMO",
                                                 "transaction_class": "DEMO_STANDARD"}
        return {"version_id": body["version_id"], "state": "APPROVED"}

    @app.post("/v1/admin/policies/{version_id}/revoke")
    def revoke_policy(version_id: str, authorization: str | None = Header(default=None)) -> dict[str, str]:
        if roles.get(who(authorization)) != "admin" or version_id not in state["policies"]:
            raise HTTPException(403, "Denied")
        state["policies"][version_id]["state"] = "REVOKED"
        return {"version_id": version_id, "state": "REVOKED"}

    @app.post("/v1/admin/policies/{version_id}/supersede")
    def supersede(version_id: str, body: dict[str, Any], authorization: str | None = Header(default=None)) -> dict[str, str]:
        if roles.get(who(authorization)) != "admin":
            raise HTTPException(403, "Denied")
        old = body["predecessor_version_id"]
        state["policies"][version_id]["supersedes"].append(old)
        state["policies"][old]["superseded_by"].append(version_id)
        return {"version_id": version_id, "supersedes": old}

    app.state.fake = state
    return app
