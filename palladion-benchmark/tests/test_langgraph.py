"""E1: a bounded LangGraph agent in the real framework environment, behind the counting proxy (B07-T02.01).

The model is a scripted provider that answers in the OpenAI chat format: it asks for the search tool, reads the passages
the tool returned and cites their ids. It says nothing about any real model; it exercises the loop, the ceilings, the
proxy's counts, the neutral access filter and the shared answer parsing. Embeddings come from the local stand-in.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from support import HashingEncoder

from benchmark.adapters.common import AccessFilter, Condition, PublishedView, build_chunks
from benchmark.adapters.langgraph import (
    AGENT_PROMPT,
    MAX_MODEL_CALLS,
    MAX_TOOL_CALLS,
    LangGraphSystem,
    build_langgraph_system,
)
from benchmark.contracts import CaseRequest, ContractError, EvidenceStatus, TransientInfrastructureError
from benchmark.generator import TransportResponse
from benchmark.llm_proxy import CountingProxy, ProxyLimits, ProxyServer
from benchmark.run_manifest import ComparatorPin
from benchmark.track_b import AnswerRejected

ROOT = Path(__file__).resolve().parents[1]
INTERPRETER = ROOT / "artifacts" / "comparators" / "env-langchain" / "Scripts" / "python.exe"
MODEL = "qwen/qwen3.8-27b"
EMBED = "paraphrase-multilingual-MiniLM-L12-v2"
TOKEN = "t" * 24
PIN = ComparatorPin.from_dict(
    {
        "repository": "https://pypi.org/project/langchain-core/",
        "commit": "",
        "lock_sha256": "d" * 64,
        "interpreter": "3.12.15",
        "native_config": {},
        "deviations": [],
        "packages": {"langchain-core": "1.6.7", "langgraph": "1.2.14"},
    }
)

pytestmark = pytest.mark.skipif(not INTERPRETER.is_file(), reason="the framework environment is not installed")

PASSAGE = re.compile(r'<<passage ids="(?P<ids>[^"]*)">>')


def completion(message: dict[str, Any], status: int = 200) -> TransportResponse:
    body: dict[str, Any] = {
        "id": "x", "object": "chat.completion", "created": 0, "model": MODEL,
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", **message}}],
        "usage": {"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60},
    }  # fmt: skip
    return TransportResponse(status, {"content-type": "application/json"}, json.dumps(body).encode())


def answer_json(cite: list[str]) -> str:
    return json.dumps(
        {
            "evidence_status": "SUPPORTED", "abstention_reason": None, "action": "ANSWER", "policy_outcome": None,
            "version_ids": [], "answer_text": "see the cited passage",
            "claims": [{"kind": "WINDOW", "params": {"hours": 24}, "text": "a window", "citations": cite}],
        }
    )  # fmt: skip


class Agent:
    """A scripted model. ``parallel`` tool calls per turn; ``mode`` picks the behaviour on a final turn."""

    def __init__(self, parallel: int = 1, always_search: bool = False, final: str | None = None) -> None:
        self.parallel = parallel
        self.always_search = always_search
        self.final = final
        self.payloads: list[dict[str, Any]] = []
        self.fail_with: int | None = None

    def post(self, payload: Any) -> TransportResponse:
        self.payloads.append(dict(payload))
        if self.fail_with is not None:
            return TransportResponse(self.fail_with, {}, json.dumps({"error": {"message": "slow down"}}).encode())
        messages = payload["messages"]
        question = next(m["content"] for m in messages if m["role"] == "user")
        offered = bool(payload.get("tools"))
        searched = any(m["role"] == "tool" for m in messages)
        if offered and (self.always_search or not searched):
            calls = [
                {"id": f"call_{len(self.payloads)}_{i}", "type": "function",
                 "function": {"name": "search", "arguments": json.dumps({"query": question.splitlines()[0][:200]})}}
                for i in range(self.parallel)
            ]  # fmt: skip
            return completion({"content": None, "tool_calls": calls})
        if self.final is not None:
            return completion({"content": self.final})
        seen = [m for m in PASSAGE.finditer("\n".join(str(m["content"]) for m in messages if m["role"] == "tool"))]
        cite = seen[0].group("ids").split(", ") if seen else []
        return completion({"content": answer_json(cite)})


@pytest.fixture
def server_for(tmp_path: Path) -> Iterator[Any]:
    started: list[ProxyServer] = []

    def make(agent: Agent, **over: Any) -> ProxyServer:
        settings: dict[str, Any] = {
            "max_calls": 60, "max_tokens": 1_000_000, "max_completion_tokens": 700, "pace_seconds": 0.0,
            "models": (MODEL,), "max_tool_calls": 40, **over,
        }  # fmt: skip
        limits = ProxyLimits(**settings)
        proxy = CountingProxy(
            agent,
            limits,
            record_path=tmp_path / f"proxy-{len(started)}.jsonl",
            embedder=HashingEncoder().embed_documents,
            embedding_model=EMBED,
        )
        server = ProxyServer(proxy, token=TOKEN)
        server.start()
        started.append(server)
        return server

    yield make
    for server in started:
        server.stop()


def small_view(s_root: Path, documents: int = 3) -> PublishedView:
    full = PublishedView.load(s_root / "published")
    records = list(full.records[:documents])
    return PublishedView(full.root, records, full.identity, {r.doc_id: full.document(r.doc_id).text for r in records})


def case(view: PublishedView, query: str, principal: str | None = None, budget: int = 4000) -> CaseRequest:
    who = principal or view.identity.principals[0].principal_id
    return CaseRequest("q-0123456789abcdef", query, who, "snap-1", "2026-10-18T03:00:00Z", None, {}, budget, None, 0)


def system_over(tmp_path: Path, server: ProxyServer, view: PublishedView, **kwargs: Any) -> LangGraphSystem:
    system = build_langgraph_system(
        interpreter=INTERPRETER,
        server=server,
        pin=PIN,
        view=view,
        work_dir=tmp_path / "work",
        llm_model=MODEL,
        embedding_model=EMBED,
        run_id="run-e1-0001",
        build_timeout=300.0,
        agent_timeout=300.0,
        **kwargs,
    )
    system.build_index(str(view.root), "track_c")
    return system


def first_chunk_text(view: PublishedView) -> str:
    return build_chunks(view)[0].text


def test_the_agent_searches_then_answers_in_the_shared_schema_and_the_proxy_counts_everything(
    tmp_path: Path, s_root: Path, server_for: Any
) -> None:
    agent = Agent()
    server = server_for(agent)
    view = small_view(s_root)
    system = system_over(tmp_path, server, view)
    system.reset_case("q-0123456789abcdef")
    response = system.answer(case(view, first_chunk_text(view)))
    usage, trace, flags = system.report_usage(), system.report_trace(), system.call_flags()
    system.close()
    assert [bool(p.get("tools")) for p in agent.payloads] == [True, True], "a search turn, then a turn that answers"
    assert response.evidence_status is EvidenceStatus.SUPPORTED and response.claims and response.claims[0].citations
    assert response.model_invocations is not None and (
        response.model_invocations.main,
        response.model_invocations.critic,
    ) == (2, 0)
    assert (
        [t.name for t in response.tool_calls] == ["search"]
        and response.critic is not None
        and not response.critic.enabled
    )
    assert (usage.main_calls, usage.tool_calls, usage.prompt_tokens, usage.completion_tokens) == (2, 1, 100, 20)
    assert "AGENT_MODEL_CALLS=2" in flags and "AGENT_TOOL_CALLS=1" in flags and not [f for f in flags if "OUTSIDE" in f]
    assert [s["step"] for s in trace[0]["steps"]].count("tool") == 1 and trace[0]["proxy_delta"]["calls"] == 2
    assert AGENT_PROMPT in {m["content"] for m in agent.payloads[0]["messages"]}, (
        "the shared prompt plus the tool paragraph"
    )


def test_a_model_that_keeps_searching_is_stopped_by_the_ceilings_and_the_last_call_has_no_tools(
    tmp_path: Path, s_root: Path, server_for: Any
) -> None:
    agent = Agent(parallel=3, always_search=True)
    server = server_for(agent)
    view = small_view(s_root)
    system = system_over(tmp_path, server, view)
    system.reset_case("q-0123456789abcdef")
    response = system.answer(case(view, first_chunk_text(view)))
    flags = system.call_flags()
    system.close()
    offered = [bool(p.get("tools")) for p in agent.payloads]
    assert offered == [True, True, True, False], "three tool turns of three calls, then a final turn without tools"
    assert response.model_invocations is not None and response.model_invocations.main == 4
    assert [t.status for t in response.tool_calls].count("OK") == MAX_TOOL_CALLS
    assert [t.status for t in response.tool_calls].count("REFUSED") == 1, "the ninth call is refused, not run"
    assert "AGENT_TOOL_CALLS_REFUSED=1" in flags


def test_the_model_call_ceiling_makes_the_fifth_call_the_final_answer(
    tmp_path: Path, s_root: Path, server_for: Any
) -> None:
    agent = Agent(parallel=1, always_search=True)
    server = server_for(agent)
    view = small_view(s_root)
    system = system_over(tmp_path, server, view)
    system.reset_case("q-0123456789abcdef")
    system.answer(case(view, first_chunk_text(view)))
    system.close()
    assert [bool(p.get("tools")) for p in agent.payloads] == [True] * (MAX_MODEL_CALLS - 1) + [False]


def test_a_reply_outside_the_schema_is_rejected_for_the_same_named_rule_as_every_arm(
    tmp_path: Path, s_root: Path, server_for: Any
) -> None:
    server = server_for(Agent(final="this is not JSON"))
    view = small_view(s_root)
    system = system_over(tmp_path, server, view)
    system.reset_case("q-0123456789abcdef")
    with pytest.raises(AnswerRejected) as caught:
        system.answer(case(view, first_chunk_text(view)))
    system.close()
    assert caught.value.rule == "NOT_JSON" and caught.value.ledger_flags == ("ANSWER_REJECTED=NOT_JSON",)


def test_a_citation_the_tool_never_returned_is_flagged_outside_the_bundle(
    tmp_path: Path, s_root: Path, server_for: Any
) -> None:
    server = server_for(Agent(final=answer_json(["NO-SUCH-DOC#1.1"])))
    view = small_view(s_root)
    system = system_over(tmp_path, server, view)
    system.reset_case("q-0123456789abcdef")
    response = system.answer(case(view, first_chunk_text(view)))
    flags = system.call_flags()
    system.close()
    assert response.claims[0].citations == ("NO-SUCH-DOC#1.1",) and "CITATION_OUTSIDE_BUNDLE=1" in flags


def test_a_provider_fault_is_a_transient_run_state(tmp_path: Path, s_root: Path, server_for: Any) -> None:
    agent = Agent()
    agent.fail_with = 429
    server = server_for(agent)
    view = small_view(s_root)
    system = system_over(tmp_path, server, view)
    system.reset_case("q-0123456789abcdef")
    with pytest.raises(TransientInfrastructureError):
        system.answer(case(view, first_chunk_text(view)))
    usage = system.report_usage()
    system.close()
    assert usage.main_calls == 1, "the rejected call used one of the proxy's calls and is counted"


def restricted(s_root: Path) -> tuple[PublishedView, str, str]:
    full = PublishedView.load(s_root / "published")
    access = AccessFilter(full, Condition.C2)
    hidden = next(
        r for r in full.records if any(not access.allows(p.principal_id, r.doc_id) for p in full.identity.principals)
    )
    records = [hidden, *[r for r in full.records if r.doc_id != hidden.doc_id][:2]]
    view = PublishedView(full.root, records, full.identity, {r.doc_id: full.document(r.doc_id).text for r in records})
    local = AccessFilter(view, Condition.C2)
    denied = next(p.principal_id for p in view.identity.principals if not local.allows(p.principal_id, hidden.doc_id))
    return view, hidden.doc_id, denied


def test_the_tool_never_shows_the_model_a_document_the_principal_may_not_read(
    tmp_path: Path, s_root: Path, server_for: Any
) -> None:
    view, hidden, denied = restricted(s_root)
    agent = Agent()
    server = server_for(agent)
    system = system_over(tmp_path, server, view)
    probe = next(c.text for c in build_chunks(view) if c.doc_id == hidden)
    system.reset_case("q-0123456789abcdef")
    system.answer(case(view, probe, principal=denied))
    trace = system.report_trace()
    system.close()
    shown = "\n".join(str(m["content"]) for p in agent.payloads for m in p["messages"] if m["role"] == "tool")
    assert f'{hidden}"' not in shown and f"{hidden}#" not in shown, (
        "no passage of the hidden document reached the model"
    )
    assert any(s.get("filtered_after_ranking", 0) >= 1 for s in trace[0]["steps"] if s["step"] == "tool")


def test_the_evidence_budget_is_a_running_total_across_the_tool_results(
    tmp_path: Path, s_root: Path, server_for: Any
) -> None:
    agent = Agent()
    server = server_for(agent)
    view = small_view(s_root)
    system = system_over(tmp_path, server, view)
    system.reset_case("q-0123456789abcdef")
    system.answer(case(view, first_chunk_text(view), budget=150))
    trace = system.report_trace()
    system.close()
    tool = next(s for s in trace[0]["steps"] if s["step"] == "tool")
    assert tool["budget_dropped"] >= 1 and 1 <= tool["passages"] < 5
    shown = [m["content"] for m in agent.payloads[-1]["messages"] if m["role"] == "tool"]
    words = sum(
        len(block.split("\n", 1)[1].rsplit("<<end>>", 1)[0].split()) for block in shown[0].split("<<passage ids=")[1:]
    )
    assert words <= 150


class Replying:
    def __init__(self, reply: Any) -> None:
        self.reply = reply


@pytest.mark.parametrize(
    "reply",
    [
        {
            "text": "x",
            "delivered": [],
            "model_calls": MAX_MODEL_CALLS + 1,
            "tool_calls": 0,
            "refused_tool_calls": 0,
            "trace": [],
        },
        {
            "text": "x",
            "delivered": [],
            "model_calls": 2,
            "tool_calls": MAX_TOOL_CALLS + 1,
            "refused_tool_calls": 0,
            "trace": [],
        },
        {"text": "x", "delivered": [], "model_calls": True, "tool_calls": 0, "refused_tool_calls": 0, "trace": []},
        {"text": "x", "delivered": "a", "model_calls": 2, "tool_calls": 0, "refused_tool_calls": 0, "trace": []},
        {"text": "x"},
        "not a mapping",
    ],
)
def test_a_reply_that_breaks_a_ceiling_or_the_protocol_is_an_invalid_run(reply: Any) -> None:
    with pytest.raises(ContractError):
        LangGraphSystem._checked(reply)
