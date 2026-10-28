"""Bounded investigation, independent advisory review, reserved final turn and gate."""
from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from evidence_agent.agent.critic import EvidenceCritic, ReviewResult
from evidence_agent.agent.draft import DRAFT_INSTRUCTIONS, FINALIZATION_INSTRUCTIONS, Claim, Draft
from evidence_agent.agent.experiments import PLANNER_INSTRUCTIONS, ExperimentControls
from evidence_agent.agent.gate import release
from evidence_agent.agent.llm import LanguageModel, ModelFailure, ModelTurn
from evidence_agent.agent.preflight import preflight
from evidence_agent.agent.tools import Tools, definitions
from evidence_agent.memory.store import CaseStore
from evidence_agent.retrieval.evidence import RequestLedger
from evidence_agent.settings import Settings


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class Budget:
    main_max: int = 5
    tool_max: int = 8
    main_used: int = 0
    tools_used: int = 0
    final_used: bool = False
    critic_used: int = 0
    critic_max: int = 3
    critic_search_max: int = 2
    critic_search_used: int = 0
    prefetch_used: int = 0

    def model(self, *, final: bool = False) -> None:
        # No await between checking and reserving: parallel tasks cannot gain free slots.
        if self.final_used or self.main_used >= self.main_max - (0 if final else 1):
            raise BudgetExceeded
        self.main_used += 1
        self.final_used = final

    def tool(self) -> None:
        if self.tools_used >= self.tool_max:
            raise BudgetExceeded
        self.tools_used += 1

    def critic(self) -> None:
        if self.critic_used >= self.critic_max:
            raise BudgetExceeded
        self.critic_used += 1

    def counter_search(self) -> None:
        # Reserve both resources without yielding; a denied search consumes no tool slot.
        if self.critic_search_used >= self.critic_search_max:
            raise BudgetExceeded
        self.tool()
        self.critic_search_used += 1


def safe_draft(ledger: RequestLedger) -> Draft:
    claims: list[Claim] = []
    for identifier, item in ledger.records.items():
        data = item.get("data")
        if item.get("kind") == "LIVE_OBSERVATION" and item.get("valid") and isinstance(data, dict):
            for field in ("state", "settlement_state", "result"):
                if field in data:
                    claims.append(Claim(id="safe"+str(len(claims)), type="OBSERVED_FACT",
                        text="Observed fact", evidence_ids=(identifier,), field=field, value=data[field]))
    return Draft(claims=tuple(claims[:12]))


class AgentRuntime:
    def __init__(self, model: LanguageModel | None, tools: Tools, store: CaseStore,
                  settings: Settings, *, experiment: ExperimentControls | None = None) -> None:
        self.model, self.tools, self.store, self.settings = model, tools, store, settings
        self.ledger = tools.ledger
        self.tools.memory_enabled = settings.continuity_enabled
        self.budget = Budget(settings.main_max_calls, settings.tool_max_calls,
            critic_max=settings.critic_max_calls, critic_search_max=settings.critic_search_max_calls)
        self.critic = EvidenceCritic(model, tools, self.budget)
        self.review = ReviewResult()
        self.experiment = experiment
        self.planner_used = 0

    async def _plan(self, query: str, hints: dict[str, Any]) -> None:
        if self.experiment is None or not self.experiment.planner:
            return
        if self.planner_used:
            raise BudgetExceeded
        self.planner_used += 1
        self.store.authorize()
        self.store.append("ATTEMPT",self.ledger.trace_id,
            {"attempt":1,"role":"planner","stage":"plan","status":"STARTED"})
        status = "FAILED"
        usage: dict[str,int] = {}
        error_code = None
        def before_send() -> None:
            self.store.authorize()
            if self.ledger.refresh():
                raise ModelFailure("EVIDENCE_CHANGED")
        try:
            if self.model is None:
                raise ModelFailure("MODEL_DISABLED")
            turn = await self.model.complete([
                {"role":"system","content":PLANNER_INSTRUCTIONS},
                {"role":"user","content":json.dumps({"question":query})}],[],
                final=True,before_send=before_send)
            usage = turn.usage
            proposal = json.loads(turn.message.get("content") or "")
            names = proposal.get("suggestions") if isinstance(proposal,dict) else None
            if (turn.message.get("tool_calls") or set(proposal)!={"suggestions"} or
                    not isinstance(names,list) or len(names)>4 or
                    any(name not in {"search_knowledge","evaluate_policy","lookup_live_data",
                                     "recall_memory"} for name in names)):
                raise ValueError("Planner schema")
            hints["suggestions"] = list(dict.fromkeys(hints["suggestions"]+names))
            status = "RECEIVED"
        except (ModelFailure,ValueError,TypeError):
            error_code = "PLANNER_UNAVAILABLE"
            # All four existing tools and grants remain available on planner failure.
        except asyncio.CancelledError:
            status = "CANCELLED"
            raise
        finally:
            self.store.append("ATTEMPT",self.ledger.trace_id,
                {"attempt":1,"role":"planner","stage":"plan","status":status,
                 "usage":usage,"error_code":error_code})

    async def _call(self, messages: list[dict[str, Any]], *, final: bool) -> ModelTurn:
        def before_send() -> None:
            self.store.authorize()
            if self.ledger.refresh():
                raise ModelFailure("EVIDENCE_CHANGED")
        before_send()
        if self.model is None:
            raise ModelFailure("MODEL_DISABLED")
        self.budget.model(final=final)
        number = self.budget.main_used
        self.store.append("ATTEMPT", self.ledger.trace_id,
            {"attempt": number, "role": "main", "stage": "final" if final else "investigate", "status": "STARTED"})
        status = "FAILED"
        error_code: str | None = None
        provider_code: str | None = None
        usage: dict[str, int] = {}
        try:
            turn = await self.model.complete(messages, [] if final else definitions(), final=final,
                                             before_send=before_send)
            usage = turn.usage
            status = "RECEIVED"
            return turn
        except asyncio.CancelledError:
            status = "CANCELLED"
            raise
        except ModelFailure as exc:
            error_code = exc.code
            provider_code = exc.provider_code
            raise
        finally:
            self.store.append("ATTEMPT", self.ledger.trace_id,
                {"attempt": number, "role": "main", "stage": "final" if final else "investigate",
                 "status": status, "usage": usage, "error_code": error_code,
                 "provider_code": provider_code})
            if self.tools.log is not None:
                self.tools.log.model_call("main", "final" if final else "investigate", status, usage, error_code)

    async def _investigate(self, query: str, hints: dict[str, Any]) -> Draft:
        await self._plan(query,hints)
        packet = hints["packet"]
        context = {"verified_observations": packet["verified_observations"],
            "open_questions": packet["open_questions"], "hypotheses": packet["hypotheses"],
            "authorized_targets": hints["authorized_targets"],
            "known_approved_policy_families": hints["known_approved_policy_families"],
            "reported_facts": packet["reported_facts"], "evidence_handles": packet["evidence_handles"],
            "previous_attempts": [{"status": e["payload"].get("status"), "at": e["at"],
                **({"unapproved_experience": e["payload"]["content"], "authority":"NONE"}
                   if e.get("kind")=="UNAPPROVED_PROCEDURAL_EXPERIENCE" else {})}
                                  for e in packet["previous_attempts"]],
            "last_disposition": packet["last_disposition"],
            "conversation_turns": packet["conversation_turns"],
            "conversation_omitted": packet["conversation_omitted"],
            "conversation_truncated": packet["conversation_truncated"]}
        if self.experiment is not None and self.experiment.planner:
            context["nonexclusive_read_suggestions"] = hints["suggestions"]
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": DRAFT_INSTRUCTIONS},
            {"role": "user", "content": json.dumps({"question": query, "untrusted_case_context": context})}]
        draft: Draft | None = None
        while self.budget.main_used < self.budget.main_max-1:
            try:
                turn = await self._call(messages, final=False)
                message = turn.message
                calls = message.get("tool_calls")
                if not calls:
                    draft = Draft.model_validate_json(message.get("content") or "")
                    break
                if not isinstance(calls, list) or not 1 <= len(calls) <= 8:
                    raise ValueError("Tool batch bounds")
                clean_calls = []
                for call in calls:
                    if (not isinstance(call, dict) or set(call) - {"id", "type", "function"} or
                            not isinstance(call.get("id"), str) or not 1 <= len(call["id"]) <= 100 or
                            call.get("type") != "function" or not isinstance(call.get("function"), dict) or
                            set(call["function"]) != {"name", "arguments"} or
                            not isinstance(call["function"]["name"], str) or
                            not 1 <= len(call["function"]["name"]) <= 100 or
                            not isinstance(call["function"]["arguments"], str)):
                        raise ValueError("Tool schema")
                    clean_calls.append(call)
                if len({c["id"] for c in clean_calls}) != len(clean_calls):
                    raise ValueError("Duplicate tool call IDs")
                messages.append({"role": "assistant", "content": None, "tool_calls": clean_calls})

                async def dispatch(call: dict[str, Any]) -> dict[str, Any]:
                    def rejected(code: str) -> dict[str, Any]:
                        if self.tools.log is not None:  # the call passed the schema check above
                            self.tools.log.tool_call("main", call["function"]["name"],
                                                     call["function"]["arguments"], code)
                        self.ledger.failures.append(code)
                        self.store.append("TOOL_RESULT", self.ledger.trace_id, {
                            "tool": "unknown", "status": "FAILED", "error_code": code})
                        return {"schema_version": "1.0", "status": "FAILED", "error_code": code,
                            "retryable": False, "correlation_id": self.ledger.trace_id, "source_ref": None,
                            "user_summary": "Scoped tool request could not be dispatched", "data": None}
                    try:
                        self.budget.tool()
                    except BudgetExceeded:
                        return rejected("TOOL_BUDGET_EXHAUSTED")
                    function = call["function"]
                    if not isinstance(function.get("name"), str) or not isinstance(function.get("arguments"), str):
                        return rejected("TOOL_SCHEMA_INVALID")
                    result = await self.tools.execute(function["name"], function["arguments"])
                    if self.tools.log is not None:
                        self.tools.log.tool_call("main", function["name"], function["arguments"],
                                                 str(result.get("status")))
                    return result

                results = await asyncio.gather(*(dispatch(c) for c in clean_calls))
                for call, result in zip(clean_calls, results, strict=True):
                    messages.append({"role": "tool", "tool_call_id": call["id"],
                                     "name": call["function"]["name"],
                                     "content": json.dumps(result, ensure_ascii=False)})
                if self.budget.tools_used >= self.budget.tool_max:
                    break
            except ModelFailure as exc:
                self.ledger.failures.append(exc.code)
                break  # Provider quota/access failure is not a schema-repair opportunity.
            except (ValidationError, ValueError, TypeError, KeyError):
                self.ledger.failures.append("MODEL_OR_SCHEMA_FAILURE")
                self.store.append("ATTEMPT", self.ledger.trace_id, {"attempt": self.budget.main_used,
                    "role": "main", "stage": "investigate", "status": "SCHEMA_INVALID"})
                # Malformed attempts count. Repair is another bounded exploration turn.
                messages.append({"role": "user", "content": "Previous attempt failed. Return valid draft JSON using current evidence only."})
                if self.model is None:
                    break
        origin = "MODEL" if draft is not None else "SAFE_TEMPLATE"
        draft = draft or safe_draft(self.ledger)
        self.store.append("DIAGNOSTIC", self.ledger.trace_id, {
            "initial_proposed_draft": draft.model_dump(mode="json"), "initial_draft_origin": origin})
        if self.tools.log is not None:
            self.tools.log.initial_draft(draft, origin)
        if self.experiment is None or self.experiment.review_required(query,draft):
            self.review = await self.critic.run(query, packet, draft)
        return await self._finalize(query, draft)

    async def _finalize(self, query: str, draft: Draft) -> Draft:
        """One reserved main turn; also the isolated frozen-draft experiment consumer."""
        messages = [{"role": "system", "content": FINALIZATION_INSTRUCTIONS}, {"role": "user",
            "content": json.dumps({"question": query, "draft": draft.model_dump(mode="json"),
                "review": self.review.finalization_view(),
                "current_ledger": self.ledger.snapshot()})}]
        try:
            turn = await self._call(messages, final=True)
            if turn.message.get("tool_calls"):
                raise ValueError("Finalization cannot explore")
            return Draft.model_validate_json(turn.message.get("content") or "")
        except (ModelFailure, ValidationError, ValueError, BudgetExceeded) as exc:
            self.ledger.failures.append(exc.code if isinstance(exc, ModelFailure) else "FINALIZATION_UNAVAILABLE")
            if not isinstance(exc, ModelFailure):
                self.store.append("ATTEMPT", self.ledger.trace_id, {"attempt": self.budget.main_used,
                    "role": "main", "stage": "final", "status": "SCHEMA_INVALID"})
            return safe_draft(self.ledger)

    async def answer(self, query: str) -> dict[str, Any]:
        self.store.authorize()
        self.ledger.question = query
        # Keep the previous packet separate: current query remains explicitly user-reported.
        hints = preflight(query, self.store, include_memory=self.settings.continuity_enabled,
            packet_max_chars=self.settings.packet_max_chars)
        packet = hints["packet"]
        self.store.append("REQUEST", self.ledger.trace_id, {"query": query,
            "continuity_metrics": {"enabled": self.settings.continuity_enabled,
                "packet_characters": len(json.dumps(packet)),
                "open_question_count": len(packet["open_questions"]),
                "observation_count": len(packet["verified_observations"]),
                "reported_count": len(packet["reported_facts"]),
                "handle_count": len(packet["evidence_handles"]),
                "conversation_turn_count": len(packet["conversation_turns"]),
                "conversation_omitted": packet["conversation_omitted"],
                "conversation_truncated": packet["conversation_truncated"]}})
        try:
            async with asyncio.timeout(self.settings.request_timeout_seconds):
                draft = await self._investigate(query, hints)
        except TimeoutError:
            self.ledger.failures.append("GLOBAL_DEADLINE")
            draft = safe_draft(self.ledger)
        except asyncio.CancelledError:
            self.store.append("CANCELLED", self.ledger.trace_id, {"status": "CANCELLED",
                "main_used": self.budget.main_used, "tools_used": self.budget.tools_used})
            raise
        response = release(draft, self.ledger, review=self.review)
        blocked = response.pop("_blocked_claim_ids")
        self.store.append("DIAGNOSTIC", self.ledger.trace_id, {"blocked_claim_ids": blocked,
            "final_proposed_draft": draft.model_dump(mode="json"), "proposal_sha256": hashlib.sha256(draft.model_dump_json().encode()).hexdigest()})
        response["budget"] = {"main_used": self.budget.main_used, "main_max": self.budget.main_max,
            "tools_used": self.budget.tools_used, "tool_max": self.budget.tool_max,
            "critic_used": self.budget.critic_used, "critic_max": self.settings.critic_max_calls,
            "prefetch_used": self.budget.prefetch_used, "critic_search_used": self.budget.critic_search_used, "adapter_attempt_max_per_lookup": 2}
        response["verification_failures"] = sorted(set(self.ledger.failures))
        if self.experiment is not None:
            response["experiment"] = {"arm":self.experiment.arm,"planner_used":self.planner_used,
                "total_model_calls":self.budget.main_used+self.budget.critic_used+self.planner_used,
                "operational_guidance":False}
        response["session_id"] = self.store.session_id
        self.store.append("RELEASE", self.ledger.trace_id, response)
        if self.tools.log is not None:  # after the stored release: the report is not part of it
            response["evaluator"] = self.tools.log.report(draft, response)
        return response


def new_trace() -> str:
    return "trace_" + uuid.uuid4().hex
