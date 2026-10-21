"""E3 and E4: Palladion as a native system over its message interface (B07-T04.01, BADR-0038, BADR-0039).

Nothing here imports Palladion. The arm sends one question at a time to ``POST /v1/cases/{case}/messages`` of a
running Palladion (the isolated runtime of ``scripts/palladion_runtime.py``) and maps the answer onto the benchmark's
``CaseResponse``. A server started in evaluator mode fixes its control arm for every request: E4 is the full runtime
(the critic runs on every message), E3 is Palladion's own control B5 (the critic removed, the final gate kept). The arm
never chooses; it checks that the server answers as the arm it was built for and refuses a mismatch.

What the arm declares rather than hides:

* **E3 is a distinct treatment.** The gate releases policy results, rule requirements and operational guidance only
  after a review, so without the critic those claims are reported unavailable. E3 is never labelled E4.
* **Counts come from the counting proxy.** Every model call of the server goes through the benchmark's proxy; the
  tokens and tool calls in ``report_usage`` are the proxy's book. Palladion's own counts (and the split of calls by
  role, which only it knows) are kept as self-reported, and a difference is a recorded flag, never reconciled silently.
* **Principals and access.** Palladion cannot express the benchmark's 17 principals; every benchmark principal maps to
  one Palladion reader in one case (``PrincipalMap``). Palladion's answer may use a source the benchmark principal could
  not read; the scorers count that from ``used_evidence_ids``; it is not filtered here.
* **Time.** The server's evaluation time is fixed at launch; a request with another evaluation time is refused as an
  unsupported capability, not answered on the wrong clock.
* **Claims carry no closed kind.** Palladion's claim types are not the benchmark's vocabulary, so ``Claim.kind`` is
  ``None`` and answer scorers do not count them correct or false (BR30). Its own types are in the trace.
* **A deadline cut or a provider fault is a run state.** ``GLOBAL_DEADLINE`` is a timeout; a failed or rejected model
  call is a transient provider fault; neither is returned as a normal abstention.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import Any

import httpx

from benchmark.adapters.palladion import PalladionArm, PrincipalMap, utf8_to_character_offsets
from benchmark.contracts import (
    AbstentionReason,
    ArmUnavailable,
    CapabilityUnsupported,
    CaseRequest,
    CaseResponse,
    Claim,
    ContractError,
    CriticReport,
    EvidenceStatus,
    ModelInvocations,
    ToolCall,
    TransientInfrastructureError,
    UsageReport,
    normalise_timestamp,
)
from benchmark.eval.normalize import clause_spans
from benchmark.eval.tool_use import ToolSchema

ARMS = {"E3": "B5", "E4": "B6"}  # the evaluator control each arm is built for
STATUS_REASON = {
    EvidenceStatus.NOT_ESTABLISHED: AbstentionReason.NO_KNOWN_SUPPORT,
    EvidenceStatus.CONFLICT: AbstentionReason.SOURCE_CONFLICT,
    EvidenceStatus.VERIFICATION_UNAVAILABLE: AbstentionReason.REQUIRED_LIVE_CHECK_UNAVAILABLE,
}
# What a failed or rejected model call, or a server that could not use its model, looks like in Palladion's response.
PROVIDER_FAILURE_PREFIXES = ("PROVIDER_", "MODEL_ENVELOPE", "MODEL_CONTEXT", "MODEL_RESPONSE", "MODEL_DISABLED")
TIMEOUT_SECONDS = 600.0
# The four read tools of Palladion and the arguments each takes (copied from its documented models, not imported).
TOOL_SCHEMAS: Mapping[str, ToolSchema] = {
    "search_knowledge": ToolSchema(
        {"query": "string"}, {"search_mode": "string", "limit": "integer", "require_graph": "boolean"}
    ),
    "evaluate_policy": ToolSchema({"family_id": "string"}, {"evidence_ids": "array"}),
    "lookup_live_data": ToolSchema({"operation": "string", "target_id": "string"}, {"operation_version": "string"}),
    "recall_memory": ToolSchema(
        {}, {"query": "string", "memory_id": "string", "category": "string", "limit": "integer"}
    ),
}


class PalladionSystem:
    """E3 or E4 behind the system-arm interface the Runner dispatches (``answer``, ``reset_case``, usage and trace)."""

    def __init__(
        self,
        arm_id: str,
        connection: PalladionArm,
        usage: Callable[[], Mapping[str, int]],
        *,
        evaluation_time: str | None,
        principals: PrincipalMap | None = None,
    ) -> None:
        if arm_id not in ARMS:
            raise ContractError(f"{arm_id} is not a Palladion system arm (E3 or E4)")
        self.arm_id = arm_id
        self._connection = connection
        self._usage = usage
        self._evaluation_time = normalise_timestamp("evaluation_time", evaluation_time) if evaluation_time else None
        self._principals = principals or connection.principals
        self._session: str | None = None
        self._fresh = True  # the next answer starts a session of its own
        self._started = dict(usage())
        self._calls: list[dict[str, Any]] = []
        self._flags: tuple[str, ...] = ()

    # -- the system-arm interface ----------------------------------------------------------------------------------

    def reset_case(self, case_id: str) -> None:
        """The next answer starts a new private session, without the previous question's conversation."""
        self._fresh = True

    def answer(self, request: CaseRequest) -> CaseResponse:
        if self._evaluation_time is not None and request.evaluation_time != self._evaluation_time:
            raise CapabilityUnsupported(
                f"{self.arm_id}: the server's evaluation time is fixed at launch ({self._evaluation_time})"
            )
        principal, case = self._principals.resolve(request.principal_id)
        if self._fresh:
            self._session, self._fresh = self._start_session(case, principal), False
        body: dict[str, Any] = {"query": request.query, "session_id": self._session}
        before = dict(self._usage())
        started = time.perf_counter()
        response = self._send(case, principal, body)
        latency_ms = (time.perf_counter() - started) * 1000.0
        data = self._parsed(response)
        after = dict(self._usage())
        delta = {key: after.get(key, 0) - before.get(key, 0) for key in after}
        failures = tuple(str(f) for f in data["verification_failures"])
        self._reject_unusable(failures)
        evaluator = data.get("evaluator")
        if not isinstance(evaluator, dict) or evaluator.get("arm") != ARMS[self.arm_id]:
            raise ArmUnavailable(f"{self.arm_id}: the server is not running the evaluator arm {ARMS[self.arm_id]}")
        result, notes = self._response(request, data, evaluator, latency_ms)
        divergence = self._divergence(data, evaluator, delta)
        self._calls.append(
            {
                "question_id": request.question_id,
                "trace_id": data["trace_id"],
                "disposition": data["disposition"],
                "latency_ms": latency_ms,
                "budget": dict(data["budget"]),
                "tool_status": dict(data["tool_status"]),
                "verification_failures": list(failures),
                "palladion_claim_types": {c["claim_id"]: c["type"] for c in evaluator["final_claims"]},
                "proxy_delta": delta,
                "model_calls": list(evaluator["model_calls"]),
                "evaluator": dict(evaluator),  # the critic and tool-use metrics read their inputs from here
                "divergence": divergence,
            }
        )
        flags = [f"PALLADION_ARM={ARMS[self.arm_id]}", *notes]
        flags += [f"PALLADION_FAILURE={f}"[:80] for f in failures]
        if divergence:
            flags.append("USAGE_DIVERGES_FROM_PROXY")
        self._flags = tuple(flags)
        return result

    def report_usage(self) -> UsageReport:
        """Calls and tokens the counting proxy saw since this arm was built, failed answers included.

        The split by role comes from the evaluator report of the answers that completed.
        """
        now = dict(self._usage())
        spent = {key: now.get(key, 0) - self._started.get(key, 0) for key in now}
        roles = [call["role"] for entry in self._calls for call in entry["model_calls"]]
        return UsageReport(
            main_calls=roles.count("main"),
            critic_calls=roles.count("critic"),
            tool_calls=spent.get("tool_calls", 0),
            prompt_tokens=spent.get("prompt_tokens", 0),
            completion_tokens=spent.get("completion_tokens", 0),
            cost_usd=None,
        )

    def report_trace(self) -> list[dict[str, Any]]:
        return [dict(entry) for entry in self._calls]

    def call_flags(self) -> tuple[str, ...]:
        return self._flags

    def describe(self) -> dict[str, Any]:
        return {
            "arm": self.arm_id,
            "evaluator_arm": ARMS[self.arm_id],
            "critic": self.arm_id == "E4",
            "principal_map": {"reader": self._principals.reader, "case": self._principals.case_id},
            "clock": self._evaluation_time or "Palladion wall clock",
            "acl": "one Palladion reader in one case; an answer's use of an unreadable source is scored, not filtered",
            "usage": "the counting proxy's book; Palladion's own counts are kept as self-reported",
            "claims": "no closed kind (BR30); Palladion's own claim types are in the trace",
            "treatment": "the critic is removed and the final gate kept; policy and operational claims need a review "
            "the gate does not get, so they are reported unavailable"
            if self.arm_id == "E3"
            else "the full runtime: the critic runs on every message",
        }

    # -- plumbing --------------------------------------------------------------------------------------------------

    def _start_session(self, case: str, principal: str) -> str:
        response = self._connection.call("POST", f"/v1/cases/{case}/sessions", principal)
        if response.status_code != 201:
            raise TransientInfrastructureError(f"Palladion refused to start a session (HTTP {response.status_code})")
        session = response.json().get("session_id")
        if not isinstance(session, str):
            raise ContractError("Palladion's session answer holds no session id")
        return session

    def _send(self, case: str, principal: str, body: dict[str, Any]) -> httpx.Response:
        try:
            return self._connection.call("POST", f"/v1/cases/{case}/messages", principal, body)
        except httpx.TimeoutException as exc:
            raise TimeoutError("Palladion did not answer in time") from exc

    def _parsed(self, response: httpx.Response) -> dict[str, Any]:
        if response.status_code == 503:
            raise ArmUnavailable("Palladion's agent runtime is disabled")
        if response.status_code >= 500:
            raise TransientInfrastructureError(f"Palladion answered HTTP {response.status_code}")
        if response.status_code != 200:
            raise ContractError(f"Palladion refused the message (HTTP {response.status_code})")
        data = response.json()
        required = ("trace_id", "disposition", "answer", "verified_claims", "citations", "budget", "tool_status",
                    "verification_failures", "review_status")  # fmt: skip
        missing = [key for key in required if key not in data]
        if missing:
            raise ContractError(f"Palladion's answer lacks {', '.join(missing)}")
        return dict(data)

    @staticmethod
    def _reject_unusable(failures: tuple[str, ...]) -> None:
        if "GLOBAL_DEADLINE" in failures:
            raise TimeoutError("Palladion reached its own request deadline and released a safe template")
        provider = sorted(f for f in failures if f.startswith(PROVIDER_FAILURE_PREFIXES))
        if provider:
            raise TransientInfrastructureError(f"Palladion's model call failed: {', '.join(provider)}")

    def _locator(self, citation: Mapping[str, Any]) -> str | None:
        """``doc#clause`` when a document passage lies in one clause, else ``doc``; None for a non-document source."""
        if citation.get("kind") != "DOCUMENT":
            return None
        doc_id = self._connection.document_for(str(citation.get("revision_id")))
        if doc_id is None:
            return None
        text = self._connection.view.document(doc_id).text
        start, end = utf8_to_character_offsets(text, int(citation["start_byte"]), int(citation["end_byte"]))
        for clause, (first, last) in clause_spans(text).items():
            if first <= start and end <= last:
                return f"{doc_id}#{clause}"
        return doc_id

    def _response(
        self, request: CaseRequest, data: Mapping[str, Any], evaluator: Mapping[str, Any], latency_ms: float
    ) -> tuple[CaseResponse, list[str]]:
        locators: dict[str, str] = {}
        foreign = 0
        for citation in data["citations"]:
            locator = self._locator(citation)
            if locator is None:
                foreign += 1
            else:
                locators[str(citation["evidence_id"])] = locator
        claims = tuple(
            Claim(
                str(claim["claim_id"]),
                str(claim["text"]),
                tuple(dict.fromkeys(locators[i] for i in claim["evidence_ids"] if i in locators)),
            )
            for claim in data["verified_claims"]
        )
        status = EvidenceStatus(data["disposition"])
        budget = data["budget"]
        critic_calls = sum(1 for call in evaluator["model_calls"] if call["role"] == "critic")
        enabled = self.arm_id == "E4"
        objections = tuple(
            f"{finding['claim_id']}:{finding['finding']}"
            for review in evaluator["critic_reviews"]
            for finding in review["claim_reviews"]
            if finding["finding"] != "SUPPORTED"
        )
        text = "\n".join([str(data["answer"]), *(claim.text for claim in claims)])
        response = CaseResponse(
            question_id=request.question_id,
            run_id=f"{self.arm_id}-{data['trace_id']}"[:100],
            answer_text=text,
            evidence_status=status,
            claims=claims,
            used_evidence_ids=tuple(dict.fromkeys(locators.values())),
            tool_calls=tuple(ToolCall(name, str(state)) for name, state in sorted(data["tool_status"].items())),
            critic=CriticReport(enabled, critic_calls if enabled else None, objections),
            model_invocations=ModelInvocations(int(budget["main_used"]), int(budget["critic_used"])),
            latency_ms=latency_ms,
            cost_usd=None,
            abstention_reason=STATUS_REASON.get(status),
        )
        notes = [f"CITATIONS_NOT_PUBLISHED={foreign}"] if foreign else []
        return response, notes

    @staticmethod
    def _divergence(data: Mapping[str, Any], evaluator: Mapping[str, Any], delta: Mapping[str, int]) -> bool:
        """Whether Palladion's own count of model calls differs from the proxy's for this answer."""
        logged = len(evaluator["model_calls"])
        return logged != delta.get("calls", 0)
