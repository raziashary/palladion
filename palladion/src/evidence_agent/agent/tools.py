"""Tool handler: strict schemas and dispatch for exactly four scoped read capabilities.

loop.py passes native function name/JSON arguments here after reserving the tool
budget. This handler injects authenticated identity/case, calls canonical domain
readers and persists success/failure. It returns a structured tool result for the
loop to attach to the matching native tool_call_id; it never grants action authority.
"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field

from evidence_agent.agent.search_worker import MAX_PARALLEL_SEARCHES, SearchWorkers, search
from evidence_agent.core.errors import EvidenceAgentError, PermissionDenied
from evidence_agent.core.models import VersionedModel
from evidence_agent.live.contracts import LookupRequest, Operation
from evidence_agent.live.gateway import LiveGateway
from evidence_agent.memory.store import CaseStore
from evidence_agent.policy.engine import PolicyEngine
from evidence_agent.policy.registry import PolicyRegistry
from evidence_agent.retrieval.evidence import LedgerBound, RequestLedger, model_view

if TYPE_CHECKING:
    from evidence_agent.agent.evaluator_log import EvaluatorLog
    from evidence_agent.memory.vector import VectorMemory


DEFAULT_SEARCH_LIMIT = 8


class KnowledgeArgs(VersionedModel):
    query: str = Field(min_length=1, max_length=2048)
    search_mode: Literal["lexical", "dense", "hybrid", "reranked"] = "reranked"
    limit: int = Field(default=DEFAULT_SEARCH_LIMIT, ge=1, le=12)
    require_graph: bool = False


class PolicyArgs(VersionedModel):
    family_id: str = Field(min_length=1, max_length=100)
    evidence_ids: tuple[str, ...] = Field(default=(), max_length=32)


class LiveArgs(VersionedModel):
    operation: Operation
    operation_version: Literal["1.0"] = "1.0"
    target_id: str = Field(min_length=1, max_length=100)


class MemoryArgs(VersionedModel):
    query: str | None = Field(default=None, max_length=256)
    memory_id: str | None = Field(default=None, min_length=1, max_length=100)
    category: Literal["EPISODIC", "SEMANTIC", "PROCEDURAL"] | None = None
    limit: int = Field(default=8, ge=1, le=20)


ARGUMENTS: dict[str, type[VersionedModel]] = {"search_knowledge": KnowledgeArgs,
    "evaluate_policy": PolicyArgs, "lookup_live_data": LiveArgs, "recall_memory": MemoryArgs}
DESCRIPTIONS = {
    "search_knowledge": "Discover authorized approved original passages. Ranking is not truth; no hits is scoped absence only.",
    "evaluate_policy": "Execute known approved family using current ledger live IDs. No search prerequisite for a known family; no raw facts, as_of or actions.",
    "lookup_live_data": "Read one named authorized case target. Observations are not action permission. Read only.",
    "recall_memory": "Recall this case's attributed events, not verified current facts or company policy."}


def definitions() -> list[dict[str, Any]]:
    def compact(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: compact(v) for k, v in value.items() if k != "title"}  # defaults stay: the model sees them
        if isinstance(value, list):
            return [compact(v) for v in value]
        return value
    return [{"type": "function", "function": {"name": name, "description": DESCRIPTIONS[name],
        "parameters": compact(model.model_json_schema())}} for name, model in ARGUMENTS.items()]


class Tools:
    def __init__(self, ledger: RequestLedger, gateway: LiveGateway, store: CaseStore,
                 log: EvaluatorLog | None = None, workers: SearchWorkers | None = None) -> None:
        self.ledger, self.gateway, self.store = ledger, gateway, store
        self.workers = workers  # long-lived search processes (ADR-0111); None: a process for every search
        self.log = log  # evaluator mode only (ADR-0100); never read by the runtime
        self.memory_enabled = True
        self.search_slots = asyncio.Semaphore(MAX_PARALLEL_SEARCHES)  # this request's searches at once; the pool bounds them for the application
        self.graph_required = False
        self.memory_vector: VectorMemory | None = None

    async def execute(self, name: str, arguments: str) -> dict[str, Any]:
        correlation = self.ledger.trace_id
        try:
            if name not in ARGUMENTS or len(arguments.encode()) > 8192:
                raise ValueError("Invalid tool")
            args = ARGUMENTS[name].model_validate_json(arguments)
            self.store.authorize()
            principal, case = self.ledger.principal, self.ledger.case_id
            data: Any
            recall_incomplete = False
            omitted_passages = 0
            if isinstance(args, KnowledgeArgs):
                applicability = self.ledger.applicability()  # validated here, so a bound error is not "worker down"
                run = self.workers.search if self.workers is not None else search
                async with self.search_slots:
                    result = await run(self.ledger.search, principal.principal_id, case,
                                          args.query, args.search_mode, args.limit,
                                          require_graph=args.require_graph or self.graph_required,
                                          applicability=applicability, named_from=self.ledger.question)
                data = []
                for passage in result.passages:
                    try:
                        data.append(self.ledger.add(passage.citation_id, result.named_versions))
                    except LedgerBound:
                        omitted_passages += 1  # the ledger is full: the model is told, the call does not fail
                if any(w in {"INDEX_UNAVAILABLE", "RERANK_UNAVAILABLE", "GRAPH_REQUIRED_UNAVAILABLE"} for w in result.warnings):
                    self.ledger.failures.append("KNOWLEDGE_UNAVAILABLE")
                self.ledger.tool_status[name] = result.status
            elif isinstance(args, LiveArgs):
                observation = await self.gateway.lookup(principal, LookupRequest(operation=args.operation,
                    operation_version=args.operation_version, case_id=case, target_id=args.target_id))
                data = self.ledger.add(observation.lookup_id)
                self.ledger.tool_status[name] = observation.operation_status.value
                if observation.operation_status.value not in {"OK", "NOT_FOUND"}:
                    self.ledger.failures.append("LIVE_UNAVAILABLE")
            elif isinstance(args, PolicyArgs):
                if any(i not in self.ledger.records or not i.startswith("live_") for i in args.evidence_ids):
                    raise PermissionDenied
                decision = PolicyEngine(PolicyRegistry(self.gateway.registry)).evaluate(
                    principal, case, args.family_id, args.evidence_ids)
                data = self.ledger.add(decision.audit_id)
                self.ledger.tool_status[name] = decision.status.value
            elif isinstance(args, MemoryArgs):
                memory = self.store.memory()
                data = memory.recall(query=args.query, memory_id=args.memory_id,
                    category=args.category, limit=args.limit) if self.memory_enabled else []
                recall_incomplete = memory.last_recall_incomplete
                if self.memory_enabled and self.memory_vector is not None and args.query and not args.memory_id:
                    extra = self.memory_vector.recall(memory,args.query,limit=args.limit)
                    recall_incomplete = recall_incomplete or self.memory_vector.last_truncated
                    combined = {item["memory_id"]:item for item in data}
                    for item in extra:
                        if args.category is None or item["kind"] == args.category:
                            combined.setdefault(item["memory_id"],item)
                    data = list(combined.values())[:args.limit]
                if self.memory_enabled and not args.query and not args.memory_id and not args.category:
                    data = (data + self.store.recent(limit=args.limit))[:args.limit]
                for event in data:
                    self.ledger.add(event["event_id"])
                self.ledger.tool_status[name] = "CONTEXT_ONLY"
            else:
                raise ValueError("Unknown arguments")
            result_payload = {"schema_version": "1.0", "status": "SUCCEEDED", "error_code": None,
                "retryable": False, "correlation_id": correlation, "source_ref": None,
                "data": ([model_view(item) for item in data] if isinstance(args, KnowledgeArgs)
                         else model_view(data) if isinstance(args, PolicyArgs) else data)}
            if isinstance(args, MemoryArgs):
                result_payload["recall_coverage"] = {"candidate_window_incomplete": recall_incomplete,
                    "exhaustive": False, "source_acl_rechecked": True}
            if isinstance(args, KnowledgeArgs):
                result_payload["graph_navigation"] = [p.model_dump(mode="json") for p in result.graph_paths]
                result_payload["retrieval_warnings"] = list(result.warnings)
                result_payload["omitted_passages"] = omitted_passages
            self.store.append("TOOL_RESULT", correlation, {"tool": name, "status": "SUCCEEDED",
                "evidence_ids": list(self.ledger.records),
                "retrieval_trace_id": result.trace_id if isinstance(args, KnowledgeArgs) else None,
                "graph_path_count": len(result.graph_paths) if isinstance(args,KnowledgeArgs) else 0,
                "retrieval_warnings": list(result.warnings) if isinstance(args, KnowledgeArgs) else []})
            return result_payload
        except asyncio.CancelledError:
            self.ledger.failures.append("TOOL_CANCELLED")
            self.ledger.tool_status[name if name in ARGUMENTS else "unknown"] = "CANCELLED"
            self.store.append("TOOL_RESULT", correlation, {"tool": name if name in ARGUMENTS else "unknown",
                "status": "CANCELLED", "error_code": "TOOL_CANCELLED"})
            raise
        except (ValueError, EvidenceAgentError) as exc:
            code = exc.code.value if isinstance(exc, EvidenceAgentError) else "VALIDATION_ERROR"
            self.ledger.failures.append(code)
            self.ledger.tool_status[name if name in ARGUMENTS else "unknown"] = "FAILED"
            self.store.append("TOOL_RESULT", correlation, {"tool": name if name in ARGUMENTS else "unknown",
                                                        "status": "FAILED", "error_code": code})
            return {"schema_version": "1.0", "status": "FAILED", "error_code": code,
                "retryable": False, "correlation_id": correlation, "source_ref": None,
                "user_summary": "Scoped verification could not complete", "data": None}
