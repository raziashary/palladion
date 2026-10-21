"""Evaluator-only observation of one case runtime; ordinary serving never constructs it (ADR-0100).

The log records what the runtime did: each model call with the provider's reported tokens, each tool call with its
arguments, the initial draft before any review, the critic's findings and counter-search queries. It decides nothing
and is not read by the runtime; the report it produces is attached to the message response only when the server was
started in evaluator mode.
"""
from __future__ import annotations

import hashlib
from typing import Any

from evidence_agent.agent.draft import Draft
from evidence_agent.core.models import CriticReview

MAX_ARGUMENT_CHARS = 2048


def _claims(draft: Draft) -> list[dict[str, Any]]:
    return [{"claim_id": c.id, "type": c.type, "field": c.field, "evidence_ids": list(c.evidence_ids),
             "text": c.text} for c in draft.claims]


class EvaluatorLog:
    def __init__(self, arm: str) -> None:
        self.arm = arm
        self.model_calls: list[dict[str, Any]] = []
        self.tool_calls: list[dict[str, Any]] = []
        self.initial: dict[str, Any] | None = None
        self.reviews: list[dict[str, Any]] = []

    def model_call(self, role: str, stage: str, status: str, usage: dict[str, int], error_code: str | None) -> None:
        self.model_calls.append({"role": role, "stage": stage, "status": status,
            "prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"),
            "error_code": error_code})

    def tool_call(self, role: str, name: str, arguments: str, status: str) -> None:
        self.tool_calls.append({"role": role, "name": name, "arguments": arguments[:MAX_ARGUMENT_CHARS],
            "arguments_truncated": len(arguments) > MAX_ARGUMENT_CHARS, "status": status})

    def initial_draft(self, draft: Draft, origin: str) -> None:
        digest = hashlib.sha256(draft.model_dump_json().encode()).hexdigest()
        self.initial = {"origin": origin, "sha256": digest, "answer_kind": draft.answer_kind,
                        "claims": _claims(draft)}

    def critic_review(self, review: CriticReview) -> None:
        self.reviews.append({"verdict": review.verdict, "proposed_disposition": review.proposed_disposition,
            "claim_reviews": [{"claim_id": f.claim_id, "finding": f.finding, "evidence_ids": list(f.evidence_ids),
                               "missing_slots": list(f.missing_slots)} for f in review.claim_reviews],
            "missing_slots": list(review.missing_slots),
            "contradiction_count": len(review.contradictions),
            "counter_search_queries": [s.query for s in review.counter_searches]
                                      + list(review.suggested_counter_searches)})

    def report(self, final: Draft, response: dict[str, Any]) -> dict[str, Any]:
        """The block added to the message response: facts about this one case, never a score."""
        return {"arm": self.arm, "model_calls": self.model_calls, "tool_calls": self.tool_calls,
            "initial_draft": self.initial, "critic_reviews": self.reviews,
            "final_claims": _claims(final),
            "released_claim_ids": [c["claim_id"] for c in response.get("verified_claims", [])]}
