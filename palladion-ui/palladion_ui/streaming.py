"""Server-sent events for a chat turn.

Two things stream, and they are different on purpose:

* progress, live, while Palladion works (read from the case timeline, which Palladion persists as it goes);
* the released answer, revealed piece by piece once the gate has released it.

A model's raw tokens are never streamed: until the gate has re-read the evidence, a sentence is a proposal, and
Palladion's rule is that an operator is not shown an unverified claim as if it were an answer.
"""
from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from typing import Any

_WORDS = re.compile(r"\S+\s*")
WORDS_PER_CHUNK = 2


def sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def text_chunks(text: str) -> list[str]:
    words = _WORDS.findall(text)
    return ["".join(words[i:i + WORDS_PER_CHUNK]) for i in range(0, len(words), WORDS_PER_CHUNK)]


async def _text(part_id: str, text: str, delay: float, **fields: Any) -> AsyncIterator[str]:
    yield sse("part", {"id": part_id, **fields})
    for chunk in text_chunks(text):
        yield sse("delta", {"id": part_id, "text": chunk})
        if delay:
            await asyncio.sleep(delay)


async def reveal(response: dict[str, Any], delay: float) -> AsyncIterator[str]:
    """The released response as ordered events: the verdict first, then sentences, gaps, evidence and details."""
    yield sse("part", {"id": "verdict", "type": "disposition", "value": response["disposition"],
                       "review_status": response.get("review_status")})
    async for event in _text("answer", response.get("answer", ""), delay, type="answer"):
        yield event
    for claim in response.get("verified_claims", []):
        async for event in _text(f"claim:{claim['claim_id']}", claim["text"], delay, type="claim",
                                 claim_id=claim["claim_id"], evidence_ids=claim.get("evidence_ids", [])):
            yield event
    for number, hypothesis in enumerate(response.get("hypotheses", [])):
        async for event in _text(f"hypothesis:{number}", hypothesis.get("text", ""), delay, type="hypothesis",
                                 verification_status=hypothesis.get("verification_status", "UNVERIFIED")):
            yield event
    origins = response.get("requirement_origins", {})
    for gap in response.get("missing_requirements", []):
        yield sse("part", {"id": f"gap:{gap}", "type": "gap", "value": gap, "origin": origins.get(gap)})
    for citation in response.get("citations", []):
        yield sse("part", {"id": f"citation:{citation.get('evidence_id')}", "type": "citation", "citation": citation})
    yield sse("part", {"id": "meta", "type": "meta", **{k: response.get(k) for k in (
        "tool_status", "verification_failures", "searched_scope", "inventory_attested", "review_status",
        "budget", "next_steps", "trace_id", "session_id", "case_id")}})


def describe(event: dict[str, Any]) -> dict[str, Any]:
    """A timeline event as a progress step. Palladion's timeline carries kinds and statuses, not tool names."""
    kind = str(event.get("kind", "EVENT"))
    status = event.get("status")
    labels = {"TOOL_RESULT": "A tool call finished", "USER_REQUEST": "Question received",
              "RUNTIME_REQUEST": "Question received", "REQUEST": "Question received",
              "RELEASED_RESPONSE": "Answer released", "RESPONSE": "Answer released"}
    label = labels.get(kind, kind.replace("_", " ").capitalize())
    detail = str(status) if status else None
    if kind == "RUNTIME_ATTEMPT":  # one model call: started, then received
        label, detail = {"STARTED": ("Asking the model", None), "RECEIVED": ("Model replied", None)}.get(
            str(status), ("Model step", detail))
    if event.get("review_status"):
        detail = f"{detail or ''} · review {event['review_status']}".strip(" ·")
    return {"id": event.get("event_id"), "kind": kind, "label": label, "detail": detail, "at": event.get("at"),
            "main_used": event.get("main_used")}


class Progress:
    """Shows each timeline event once, oldest first, starting after what existed before the request."""

    def __init__(self) -> None:
        self.seen: set[str] = set()

    def prime(self, events: list[dict[str, Any]]) -> None:
        self.seen = {str(e.get("event_id")) for e in events}

    def fresh(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        new = [e for e in events if str(e.get("event_id")) not in self.seen]
        new.sort(key=lambda e: (str(e.get("at")), str(e.get("event_id"))))
        self.seen.update(str(e.get("event_id")) for e in new)
        return [describe(e) for e in new]
