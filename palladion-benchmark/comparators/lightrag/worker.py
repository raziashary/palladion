"""R6 LightRAG worker: the upstream's own hybrid retrieval over the corpus, behind the comparator protocol (B06-T03.01).

Runs inside the approved LightRAG environment (``artifacts/comparators/env-LightRAG``, HKUDS/LightRAG at
28ff1b05f2ac3f3e6fa14dd2cd33656579bd0c9c, release v1.5.7). Upstream entry points used:

- ``lightrag.LightRAG`` (``lightrag/lightrag.py:391``) with its default storages (JSON KV, NanoVectorDB, NetworkX,
  JSON doc status), its default fixed-token chunker and its default tokenizer (``TiktokenTokenizer``,
  ``lightrag.py:1343``).
- ``LightRAG.ainsert(texts, ids=..., file_paths=...)`` (``lightrag/lightrag.py:1794``): the upstream's own chunking,
  entity and relation extraction, gleaning and description merging. Every document is one corpus row; its document id
  and ``file_path`` are the corpus ``chunk_id``, so each native chunk names its corpus chunk.
- ``LightRAG.aquery_data`` (``lightrag/lightrag.py:3998``) with ``QueryParam(mode="hybrid")``: the structured,
  data-returning query (no answer generation). Hybrid is the upstream's local (entity) plus global (relation) retrieval
  over the knowledge graph (``lightrag/operate.py:kg_query``).
- ``openai_complete_if_cache`` (``lightrag/llm/openai.py:305``) and ``openai_embed`` (``lightrag/llm/openai.py:1054``),
  both pointed at the counting proxy by ``OPENAI_BASE_URL``. The proxy serves the embeddings locally.

Query-time model calls: hybrid mode first asks the LLM for high- and low-level keywords of the query
(``operate.py:get_keywords_from_query``), unless keywords are supplied. That call is NOT disabled; it is counted by the
proxy and reported per query. No answer is generated.

Deviations from the upstream defaults are listed in ``build``'s return value and in the adapter's docstring.

Protocol: ``build`` and ``retrieve`` as in ``comparators/protocol.py``. A library's stdout is redirected to stderr by
``serve``; no prompt, passage or key is written anywhere except the worker's own ``workdir``.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import re
from collections.abc import Coroutine
from dataclasses import asdict
from functools import partial
from importlib import metadata
from pathlib import Path
from typing import Any

import pipmaster as _pipmaster

# The upstream's OpenAI binding calls pipmaster at import time to install a missing package from the network. This
# environment installs packages only through the owner, so a missing module is reported by name and never installed.
_INSTALLERS = (
    "install", "install_if_missing", "install_multiple", "install_multiple_if_not_installed", "install_version",
    "install_or_update", "install_requirements", "install_edit", "ensure_packages", "ensure_requirements",
)  # fmt: skip


def _refuse_install(*args: Any, **kwargs: Any) -> None:
    raise ImportError(f"package not installed in this environment; runtime installs are refused: {args!r}")


for _name in _INSTALLERS:
    setattr(_pipmaster, _name, _refuse_install)

from lightrag import LightRAG, QueryParam  # noqa: E402
from lightrag.base import DocStatus  # noqa: E402
from lightrag.constants import GRAPH_FIELD_SEP  # noqa: E402
from lightrag.llm.openai import openai_complete_if_cache, openai_embed  # noqa: E402
from lightrag.utils import EmbeddingFunc  # noqa: E402

# The benchmark's launcher names protocol.py by path (COMPARATOR_PROTOCOL), never through PYTHONPATH.
_PROTOCOL_PATH = os.environ.get("COMPARATOR_PROTOCOL", str(Path(__file__).resolve().parents[1] / "protocol.py"))
_PROTOCOL = importlib.util.spec_from_file_location("comparator_protocol", _PROTOCOL_PATH)
assert _PROTOCOL is not None and _PROTOCOL.loader is not None
_protocol = importlib.util.module_from_spec(_PROTOCOL)
_PROTOCOL.loader.exec_module(_protocol)
serve = _protocol.serve
_protocol.guard_network()  # the proxy is this process's only route to a model

# The benchmark's pinned embedding model, paraphrase-multilingual-MiniLM-L12-v2 (configs/comparators.yaml).
EMBEDDING_DIM = 384
UNKNOWN_SOURCE = "unknown_source"


class LightRagFault(RuntimeError):
    """The upstream did not index a document, or did not answer a query. The message is a fixed code."""


class _Index:
    """The live LightRAG instance, its event loop and the mapping from native results to corpus chunk ids."""

    def __init__(
        self, rag: LightRAG, loop: asyncio.AbstractEventLoop, texts: dict[str, str], siblings: dict[str, list[str]]
    ) -> None:
        self.rag = rag
        self.loop = loop
        self.texts = texts  # corpus chunk_id -> text
        self.siblings = siblings  # representative chunk_id -> every corpus chunk_id with the same exact text


_INDEX: _Index | None = None


def _run(index: _Index, coroutine: Coroutine[Any, Any, Any]) -> Any:
    return index.loop.run_until_complete(coroutine)


def _endpoint() -> tuple[str, str]:
    """The proxy's address and per-run token, as launch_arm sets them. Never printed or written."""
    return os.environ["OPENAI_BASE_URL"], os.environ["OPENAI_API_KEY"]


async def _complete(
    model: str, prompt: str, system_prompt: str | None = None, history_messages: Any = None, **kwargs: Any
) -> str:
    base_url, api_key = _endpoint()
    return await openai_complete_if_cache(  # type: ignore[no-any-return]
        model, prompt, system_prompt=system_prompt, history_messages=history_messages or [],
        base_url=base_url, api_key=api_key, **kwargs,
    )  # fmt: skip


def _read_corpus(path: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if not all(isinstance(row.get(k), str) for k in ("chunk_id", "doc_id", "text")):
                raise LightRagFault("CORPUS_ROW_INVALID")
            rows.append(row)
    if len({r["chunk_id"] for r in rows}) != len(rows):
        raise LightRagFault("CORPUS_CHUNK_IDS_NOT_UNIQUE")
    return rows


async def _resume_unfinished(rag: LightRAG, ids: set[str]) -> None:
    """Finish what an earlier attempt in this working directory left half done.

    Inserting a text whose id is already stored only records a failed duplicate and processes nothing, and the
    pipeline's own scan skips failed documents (retrying them is a manual action of the upstream's server). So the
    duplicate records are dropped (they would be processed as new documents and pay twice), the failed documents of
    this corpus are marked pending again, and the pipeline runs over them and over any interrupted ones."""
    failed = await rag.doc_status.get_docs_by_statuses([DocStatus.FAILED])
    junk = [k for k, v in failed.items() if k not in ids and "File name already exists" in (v.error_msg or "")]
    if junk:
        await rag.doc_status.delete(junk)
    again = {
        k: asdict(v) | {"status": DocStatus.PENDING.value, "error_msg": None} for k, v in failed.items() if k in ids
    }
    if again:
        await rag.doc_status.upsert(again)
    if await rag.doc_status.get_docs_by_statuses([DocStatus.PENDING, DocStatus.PROCESSING]):
        await rag.apipeline_process_enqueue_documents()


def build(params: dict[str, Any]) -> dict[str, Any]:
    """Index the corpus with the upstream pipeline. Exact-duplicate texts are inserted once (see the adapter)."""
    global _INDEX
    rows = _read_corpus(str(params["corpus"]))
    workdir = Path(params["workdir"])
    workdir.mkdir(parents=True, exist_ok=True)
    model = os.environ["COMPARATOR_LLM_MODEL"]
    embed_model = os.environ["COMPARATOR_EMBED_MODEL"]
    base_url, api_key = _endpoint()

    first_of: dict[str, str] = {}
    siblings: dict[str, list[str]] = {}
    for row in rows:
        representative = first_of.setdefault(row["text"], row["chunk_id"])
        siblings.setdefault(representative, []).append(row["chunk_id"])
    inserted = [row for row in rows if first_of[row["text"]] == row["chunk_id"]]

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    rag = LightRAG(
        working_dir=str(workdir),
        llm_model_func=partial(_complete, model),
        llm_model_name=model,
        llm_model_max_async=1,  # the proxy dispatches one call at a time; parallel writers also race on Windows
        max_parallel_insert=1,
        embedding_func=EmbeddingFunc(
            embedding_dim=EMBEDDING_DIM,
            func=partial(openai_embed.func, model=embed_model, base_url=base_url, api_key=api_key),
        ),
    )
    index = _Index(rag, loop, {r["chunk_id"]: r["text"] for r in rows}, siblings)
    _run(index, rag.initialize_storages())
    ids = [row["chunk_id"] for row in inserted]
    _run(index, _resume_unfinished(rag, set(ids)))
    stored = _run(index, rag.aget_docs_by_ids(ids))
    new = [row for row in inserted if row["chunk_id"] not in stored]  # a stored id is never inserted again
    if new:
        new_ids = [row["chunk_id"] for row in new]
        _run(index, rag.ainsert([row["text"] for row in new], ids=new_ids, file_paths=new_ids))
    statuses = _run(index, rag.aget_docs_by_ids(ids))
    # The doc-status storage returns each record as a plain mapping; its status is the DocStatus value.
    not_processed = [i for i in ids if i not in statuses or statuses[i].get("status") != DocStatus.PROCESSED.value]
    if not_processed:
        raise LightRagFault("DOCUMENT_NOT_INDEXED")
    _INDEX = index
    query = QueryParam()
    return {
        "upstream": {
            "package": "lightrag-hku",
            "version": metadata.version("lightrag-hku"),
            "repository": "https://github.com/HKUDS/LightRAG",
            "commit": "28ff1b05f2ac3f3e6fa14dd2cd33656579bd0c9c",
        },
        "mode": "hybrid",
        "llm_model": model,
        "embedding_model": embed_model,
        "embedding_dim": EMBEDDING_DIM,
        "tokenizer": type(rag.tokenizer).__name__ + f"({rag.tiktoken_model_name})",
        "chunk_strategy": "fixed-token (LightRAG ainsert default)",
        "chunk_token_size": rag.chunk_token_size,
        "chunk_overlap_token_size": rag.chunk_overlap_token_size,
        "entity_extract_max_gleaning": rag.entity_extract_max_gleaning,
        "storage": {
            "kv": rag.kv_storage,
            "vector": rag.vector_storage,
            "graph": rag.graph_storage,
            "doc_status": rag.doc_status_storage,
        },
        "query": {"top_k": query.top_k, "chunk_top_k": query.chunk_top_k, "rerank": "no rerank model configured"},
        "documents": len(rows),
        "documents_inserted": len(inserted),
        "chunk_ids_sharing_text": len(rows) - len(inserted),
    }


def _supported(name: str, text: str) -> bool:
    return bool(name) and re.search(re.escape(name.casefold()), text.casefold()) is not None


def retrieve(params: dict[str, Any]) -> dict[str, Any]:
    """Return the upstream's hybrid context as corpus chunk ids, in the upstream's chunk order.

    A hit carries the first upstream relation (in the context's relationship order) that cites its chunk, when both of
    the relation's entity names appear in that chunk's text; otherwise its relation is null. Chunks the context cites
    only through a relation are appended after the upstream's chunk list.
    """
    if _INDEX is None:
        raise LightRagFault("NOT_BUILT")
    index = _INDEX
    limit = int(params["limit"])
    data = _run(index, index.rag.aquery_data(str(params["query"]), QueryParam(mode="hybrid")))
    if data.get("status") != "success":
        if (data.get("metadata") or {}).get("failure_reason") == "no_results":
            return {"hits": []}
        raise LightRagFault("QUERY_FAILED")
    section = data.get("data") or {}
    known = set(index.texts)

    relation_of: dict[str, dict[str, Any]] = {}
    for rel in section.get("relationships", []):
        subject, obj = str(rel.get("src_id", "")), str(rel.get("tgt_id", ""))
        for source in str(rel.get("file_path", "")).split(GRAPH_FIELD_SEP):
            text = index.texts.get(source)
            if text is None or source in relation_of or not (_supported(subject, text) and _supported(obj, text)):
                continue
            relation_of[source] = {
                "subject": subject,
                "predicate": str(rel.get("keywords", "")),
                "object": obj,
                "supporting_ids": [source],
            }

    order: list[str] = []
    for chunk in section.get("chunks", []):
        source = str(chunk.get("file_path", UNKNOWN_SOURCE))
        if source in known:
            order.append(source)
    for rel in section.get("relationships", []):
        order.extend(s for s in str(rel.get("file_path", "")).split(GRAPH_FIELD_SEP) if s in known)

    hits: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in order:
        for sibling in index.siblings.get(source, [source]):
            if sibling in seen:
                continue
            seen.add(sibling)
            edge = relation_of.get(source)
            relation = None if edge is None else {**edge, "supporting_ids": [sibling]}
            hits.append({"chunk_id": sibling, "score": None, "relation": relation})
    return {"hits": hits[:limit]}


if __name__ == "__main__":
    serve({"build": build, "retrieve": retrieve})
