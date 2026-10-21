"""An offline scripted provider for smokes of the end-to-end arms (B07-T08.01).

It answers in the OpenAI chat format to the three prompts the Track C systems send, with no network and no model:

* E0 (retrieve then answer): the shared generator prompt with passages in the user message. It reads the passages and
  answers from the first window it finds (``ExtractiveStubTransport``).
* E1 (agent): the same system prompt with a ``search`` tool. It searches once with the question, then answers from the
  passages the tool returned.
* E3 and E4 (Palladion): Palladion's own draft, critic and finalization prompts. It searches with the question,
  quotes the first source it was shown, passes the critic and repeats its draft at finalization.

It makes no claim about model quality and every answer it gives is a function of the passages it was shown. Nothing it
produces is a result about any model, and a run that used it says so in its manifest.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from benchmark.generator import TransportResponse
from benchmark.track_b import SYSTEM_PROMPT, ExtractiveStubTransport

CRITIC_PREFIX = "You are the independent Evidence Critic"
FINAL_MARKER = "Backend phase: FINALIZATION"
_PASSAGE = re.compile(r'<<passage ids="(?P<ids>[^"]*)">>')
MODEL = "scripted-offline"


def completion(message: Mapping[str, Any], prompt: int = 100, completion_tokens: int = 20) -> TransportResponse:
    body = {
        "model": MODEL,
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", **message}}],
        "usage": {
            "prompt_tokens": prompt,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt + completion_tokens,
        },
    }
    return TransportResponse(200, {"content-type": "application/json"}, json.dumps(body).encode())


class ScriptedProvider:
    """One object that plays the model for whichever system is calling."""

    def __init__(self) -> None:
        self.stages: list[str] = []
        self.estimated_prompt_tokens = 0  # four characters a token: what a live run's prompts would roughly cost
        self._extractive = ExtractiveStubTransport()

    def post(self, payload: Mapping[str, Any]) -> TransportResponse:
        messages = payload["messages"]
        self.estimated_prompt_tokens += len(json.dumps(messages, ensure_ascii=False)) // 4
        system = str(messages[0]["content"])
        if system.startswith(CRITIC_PREFIX):
            return self._critic(messages)
        if FINAL_MARKER in system:
            self.stages.append("palladion_final")
            draft = json.loads(messages[1]["content"])["draft"]
            return completion({"content": json.dumps(draft)})
        if system.startswith(SYSTEM_PROMPT.splitlines()[0]):
            return self._agent(payload) if payload.get("tools") else self._plain(payload)
        return self._palladion_draft(messages)

    def _plain(self, payload: Mapping[str, Any]) -> TransportResponse:
        self.stages.append("e0_answer")
        return self._extractive.post(payload)

    def _agent(self, payload: Mapping[str, Any]) -> TransportResponse:
        messages = payload["messages"]
        tool_results = [m for m in messages if m["role"] == "tool"]
        if not tool_results:
            self.stages.append("e1_search")
            question = next(m["content"] for m in messages if m["role"] == "user")
            call = {
                "id": "call_1",
                "type": "function",
                "function": {"name": "search", "arguments": json.dumps({"query": str(question).splitlines()[0][:200]})},
            }
            return completion({"content": None, "tool_calls": [call]})
        self.stages.append("e1_answer")
        text = "\n".join(str(m["content"]) for m in tool_results)
        seen = _PASSAGE.search(text)
        cite = seen.group("ids").split(", ") if seen else []
        answer = {
            "evidence_status": "SUPPORTED" if cite else "NOT_ESTABLISHED",
            "abstention_reason": None if cite else "NO_KNOWN_SUPPORT",
            "action": "ANSWER" if cite else "NO_SUPPORT",
            "policy_outcome": None,
            "version_ids": [],
            "answer_text": "see the cited passage" if cite else "nothing in the evidence answers this",
            "claims": [{"kind": "WINDOW", "params": {"hours": 24}, "text": "a window", "citations": cite}]
            if cite
            else [],
        }
        return completion({"content": json.dumps(answer)})

    def _critic(self, messages: list[Mapping[str, Any]]) -> TransportResponse:
        self.stages.append("palladion_critic")
        user = json.loads(messages[1]["content"])
        claims = user["draft"]["claims"] if user.get("draft") else []
        review = {
            "review_id": "r1",
            "verdict": "PASS",
            "proposed_disposition": "SUPPORTED",
            "claim_reviews": [
                {"claim_id": c["id"], "finding": "SUPPORTED", "reason": "quoted from the source",
                 "evidence_ids": c["evidence_ids"]}
                for c in claims
            ],
        }  # fmt: skip
        return completion({"content": json.dumps(review)})

    def _palladion_draft(self, messages: list[Mapping[str, Any]]) -> TransportResponse:
        user = json.loads(messages[1]["content"])
        tool = next((m for m in messages if m.get("role") == "tool"), None)
        if tool is None:
            self.stages.append("palladion_search")
            arguments = json.dumps({"query": user["question"], "limit": 3})
            call = {
                "id": "call_1",
                "type": "function",
                "function": {"name": "search_knowledge", "arguments": arguments},
            }
            return completion({"content": None, "tool_calls": [call]})
        self.stages.append("palladion_draft")
        found = [d for d in json.loads(tool["content"])["data"] if d.get("kind") == "DOCUMENT"]
        claims = []
        if found:
            claims = [{"id": "C1", "type": "SOURCE_QUOTE", "text": found[0]["text_preview"][:120],
                       "evidence_ids": [found[0]["evidence_id"]]}]  # fmt: skip
        draft = {"answer_kind": "INFORMATIONAL", "claims": claims, "required_slots": [], "missing_slots": []}
        return completion({"content": json.dumps(draft)})
