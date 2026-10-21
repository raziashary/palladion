"""E0 worker and the E1 agent loop: LangChain and LangGraph behind the comparator protocol (B07-T01.01, T02.01).

Runs inside the approved framework environment (``artifacts/comparators/env-langchain``: langchain-core,
langchain-openai and langgraph at the exact versions of ``scripts/comparators.py``). Components used:

- ``langchain_core.documents.Document`` for each corpus chunk (the loader step: the published text is already in
  memory);
- ``langchain_openai.OpenAIEmbeddings`` pointed at the counting proxy by ``OPENAI_BASE_URL``, so the embedding model
  is the benchmark's pinned one, served locally by the proxy (``check_embedding_ctx_length=False`` avoids a tokenizer
  download);
- ``langchain_core.vectorstores.InMemoryVectorStore`` and its ``similarity_search_with_score`` (cosine) as the
  retriever;
- for E1, ``langchain_openai.ChatOpenAI`` pointed at the same proxy and a ``langgraph.graph.StateGraph`` with a model
  node, a tool node and a conditional edge: a model that may call the retriever as a tool, then a final answer.

Deviations from a stock LangChain pipeline are returned by ``build`` and recorded on the pin: the splitter step uses the
benchmark's shared 120-word chunks (every arm ranks the same evidence units, protocol 3.1 item 5), and embeddings come
through the proxy rather than a provider's embedding endpoint.

Protocol: ``build``, ``retrieve`` and ``agent``. No prompt, passage or key is written anywhere.
"""

from __future__ import annotations

import importlib.util
import json
import os
import time
from importlib import metadata
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

_PROTOCOL_PATH = os.environ.get("COMPARATOR_PROTOCOL", str(Path(__file__).resolve().parents[1] / "protocol.py"))
_PROTOCOL = importlib.util.spec_from_file_location("comparator_protocol", _PROTOCOL_PATH)
assert _PROTOCOL is not None and _PROTOCOL.loader is not None
_protocol = importlib.util.module_from_spec(_PROTOCOL)
_PROTOCOL.loader.exec_module(_protocol)
serve = _protocol.serve
_protocol.guard_network()  # the proxy is this process's only route to a model or an embedding

EMBEDDING_BATCH = 256  # the proxy refuses more than 512 inputs in one request
PACKAGES = ("langchain-core", "langchain-openai", "langgraph")
PASSAGE_OPEN = '<<passage ids="'  # the shared prompt's passage wrapper (benchmark/track_b.py)
PASSAGE_CLOSE = "<<end>>"
OVERFETCH = 3  # hits asked of the store per hit wanted, because the access filter acts after its ranking


class LangChainFault(RuntimeError):
    """The corpus or a query is outside what the worker accepts. The message is a fixed code, never text."""


class _Index:
    def __init__(self, store: InMemoryVectorStore, passages: dict[str, tuple[str, list[str]]]) -> None:
        self.store = store
        self.passages = passages  # chunk_id -> (doc_id, the clause ids whose lines the chunk holds)


_INDEX: _Index | None = None


def _embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=os.environ["COMPARATOR_EMBED_MODEL"],
        base_url=os.environ["OPENAI_BASE_URL"],
        api_key=os.environ["OPENAI_API_KEY"],  # the proxy's per-run token, never a provider key
        check_embedding_ctx_length=False,
        chunk_size=EMBEDDING_BATCH,
        max_retries=0,
    )


def _read_corpus(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if not all(isinstance(row.get(k), str) for k in ("chunk_id", "doc_id", "text")):
                raise LangChainFault("CORPUS_ROW_INVALID")
            rows.append(row)
    if len({r["chunk_id"] for r in rows}) != len(rows):
        raise LangChainFault("CORPUS_CHUNK_IDS_NOT_UNIQUE")
    return rows


def build(params: dict[str, Any]) -> dict[str, Any]:
    """Index every corpus chunk in an in-memory vector store; the only model use is the proxy's local embeddings."""
    global _INDEX
    rows = _read_corpus(str(params["corpus"]))
    store = InMemoryVectorStore(_embeddings())
    documents = [
        Document(page_content=r["text"], metadata={"chunk_id": r["chunk_id"], "doc_id": r["doc_id"]}) for r in rows
    ]
    store.add_documents(documents, ids=[r["chunk_id"] for r in rows])
    _INDEX = _Index(store, {r["chunk_id"]: (r["doc_id"], [str(c) for c in r.get("clauses", [])]) for r in rows})
    return {
        "framework": {name: metadata.version(name) for name in PACKAGES},
        "vector_store": "InMemoryVectorStore",
        "search": "similarity_search_with_score (cosine)",
        "embedding": "OpenAIEmbeddings through the counting proxy",
        "documents": len(documents),
        "deviations": [
            "the splitter is the benchmark's shared 120-word chunker, not a LangChain text splitter",
            "embeddings come from the benchmark's pinned model served by the counting proxy",
        ],
    }


def retrieve(params: dict[str, Any]) -> dict[str, Any]:
    if _INDEX is None:
        raise LangChainFault("NOT_BUILT")
    query, limit = params["query"], int(params["limit"])
    if not isinstance(query, str) or not query.strip() or limit < 1:
        raise LangChainFault("QUERY_INVALID")
    found = _INDEX.store.similarity_search_with_score(query, k=limit)
    hits = [
        {"chunk_id": str(doc.metadata["chunk_id"]), "score": float(score), "relation": None} for doc, score in found
    ]
    return {"hits": hits}


# --------------------------------------------------------------------------- E1: the bounded agent loop


class _AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    model_calls: int
    tool_calls: int


class _Search:
    """The one retrieval tool, with the neutral access filter and the common evidence budget applied to its results."""

    def __init__(self, index: _Index, params: dict[str, Any]) -> None:
        self.index = index
        self.allowed = set(params["allowed_docs"])
        self.limit = int(params["limit"])
        self.words_left = int(params["max_evidence_words"])
        self.delivered: list[str] = []
        self.trace: list[dict[str, Any]] = []

    def __call__(self, query: str) -> str:
        found = self.index.store.similarity_search_with_score(query, k=min(100, self.limit * OVERFETCH))
        blocks: list[str] = []
        dropped = filtered = 0
        for document, _score in found:
            doc_id, clauses = self.index.passages[str(document.metadata["chunk_id"])]
            if doc_id not in self.allowed:
                filtered += 1
                continue
            words = len(document.page_content.split())
            if len(blocks) >= self.limit or words > self.words_left:
                dropped += 1
                continue
            self.words_left -= words
            ids = [f"{doc_id}#{c}" for c in clauses] or [doc_id]
            self.delivered.extend(ids)
            blocks.append(f'{PASSAGE_OPEN}{", ".join(ids)}">>\n{document.page_content.strip()}\n{PASSAGE_CLOSE}')
        self.trace.append(
            {"step": "tool", "tool": "search", "query": query[:300], "passages": len(blocks),
             "filtered_after_ranking": filtered, "budget_dropped": dropped}
        )  # fmt: skip
        return "\n".join(blocks) if blocks else "(no passages were retrieved)"


def agent(params: dict[str, Any]) -> dict[str, Any]:
    """Run one bounded LangGraph loop: a model that may call the search tool, then a final answer without tools.

    The ceilings are the arm's own, enforced here and, for tools, by the counting proxy as well: at most
    ``max_model_calls`` model calls (the last one is made without tools) and at most ``max_tool_calls`` tool calls; a
    call past the ceiling is refused to the model and counted, never silently executed.
    """
    if _INDEX is None:
        raise LangChainFault("NOT_BUILT")
    max_model, max_tool = int(params["max_model_calls"]), int(params["max_tool_calls"])
    if max_model < 2 or max_tool < 1:
        raise LangChainFault("CEILINGS_INVALID")
    search_state = _Search(_INDEX, params)

    @tool
    def search(query: str) -> str:
        """Search the corpus for evidence passages. Returns passages with the citation ids to cite."""
        return search_state(query)

    llm = ChatOpenAI(
        model=os.environ["COMPARATOR_LLM_MODEL"],
        base_url=os.environ["OPENAI_BASE_URL"],
        api_key=os.environ["OPENAI_API_KEY"],  # the proxy's per-run token, never a provider key
        temperature=0,
        max_retries=0,
        timeout=float(params["call_timeout"]),
    )
    with_tools = llm.bind_tools([search])
    refused = 0
    steps: list[dict[str, Any]] = []

    def call_model(state: _AgentState) -> dict[str, Any]:
        final = state["model_calls"] >= max_model - 1 or state["tool_calls"] >= max_tool
        started = time.perf_counter()
        reply = (llm if final else with_tools).invoke(state["messages"])
        steps.append(
            {"step": "model", "number": state["model_calls"] + 1, "final": final,
             "requested_tools": len(getattr(reply, "tool_calls", []) or []),
             "ms": round((time.perf_counter() - started) * 1000)}
        )  # fmt: skip
        return {"messages": [reply], "model_calls": state["model_calls"] + 1}

    def run_tools(state: _AgentState) -> dict[str, Any]:
        nonlocal refused
        reply = state["messages"][-1]
        assert isinstance(reply, AIMessage)
        results: list[ToolMessage] = []
        used = state["tool_calls"]
        for call in reply.tool_calls:
            if call["name"] != "search" or used >= max_tool:
                refused += 1
                results.append(
                    ToolMessage(content="refused: tool budget exhausted or unknown tool", tool_call_id=call["id"],
                                name=call["name"], status="error")
                )  # fmt: skip
                continue
            used += 1
            output = search.invoke({"query": str(call["args"].get("query", ""))})
            results.append(ToolMessage(content=output, tool_call_id=call["id"], name="search"))
        return {"messages": results, "tool_calls": used}

    def route(state: _AgentState) -> str:
        last = state["messages"][-1]
        wants_tools = isinstance(last, AIMessage) and bool(last.tool_calls)
        return "tools" if wants_tools and state["model_calls"] < max_model else END

    graph = StateGraph(_AgentState)
    graph.add_node("model", call_model)
    graph.add_node("tools", run_tools)
    graph.add_edge(START, "model")
    graph.add_conditional_edges("model", route, ["tools", END])
    graph.add_edge("tools", "model")
    done = graph.compile().invoke(
        {"messages": [SystemMessage(content=params["system"]), HumanMessage(content=params["question"])],
         "model_calls": 0, "tool_calls": 0},
        {"recursion_limit": 2 * max_model + 4},
    )  # fmt: skip
    final = done["messages"][-1]
    text = final.content if isinstance(final, AIMessage) and isinstance(final.content, str) else None
    return {
        "text": text,
        "delivered": sorted(set(search_state.delivered)),
        "model_calls": done["model_calls"],
        "tool_calls": done["tool_calls"],
        "refused_tool_calls": refused,
        "trace": [*steps, *search_state.trace],
    }


if __name__ == "__main__":
    serve({"build": build, "retrieve": retrieve, "agent": agent})
