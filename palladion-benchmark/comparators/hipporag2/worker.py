"""R4 worker: HippoRAG 2 (OSU-NLP-Group/HippoRAG, version 2.0.0a5) behind the comparator protocol (B06-T01.01).

Runs inside the isolated HippoRAG environment (Python 3.12, ``hipporag`` installed from the approved checkout), never in
the benchmark's own environment. The upstream's own pipeline does all indexing and retrieval:

- ``build``: ``HippoRAG.index`` over the corpus passages. The upstream runs OpenIE (named entities, then triples) with
  its online LLM client, embeds passages, entities and facts, and builds the graph. Entity and fact embeddings use the
  upstream's OpenAI-compatible embedding client pointed at the counting proxy (``embedding_provider="openai"``).
- ``retrieve``: ``HippoRAG.retrieve`` with ``num_to_retrieve`` set to the requested limit. The upstream runs fact
  retrieval, recognition memory (one LLM call per query when candidate facts exist) and Personalized PageRank over the
  graph, and returns passage texts with PPR scores.

Mapping native outputs to chunk ids: the upstream keys passages by the MD5 of their text, so two corpus chunks with
identical text collapse into one passage. The worker indexes each distinct text once, keeps an order-preserving table
from text to every chunk id that carries it, and returns all of those chunk ids with the passage's score, in corpus
order, trimmed to the limit. A relation is attached to a hit only when a retrieved fact's subject and object both
appear (normalized with the upstream's ``text_processing``) in that hit's text; ``supporting_ids`` are the chunks whose
OpenIE output the upstream recorded for that fact and whose text also holds both names.

Query-time model calls: recognition memory only (one call per query with candidate facts, served from the upstream's
SQLite LLM cache when the same prompt was seen). Query embeddings are local proxy calls. Upstream silently falls back
to dense passage retrieval when recognition memory raises an error; this worker turns that error into a failed
request instead (see ``RecognitionMemoryError``). Question answering (``qa``, ``rag_qa``) is not run.

The ``namespace`` parameter of ``build`` is accepted and not used: the index lives in ``workdir``.
"""

from __future__ import annotations

import importlib.util
import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path
from typing import Any

from hipporag import HippoRAG
from hipporag.utils.config_utils import BaseConfig
from hipporag.utils.misc_utils import text_processing

# The protocol is loaded by file path (launch_arm sets COMPARATOR_PROTOCOL): a directory named like a package must not
# shadow the installed one on sys.path.
_protocol_spec = importlib.util.spec_from_file_location("comparator_protocol", os.environ["COMPARATOR_PROTOCOL"])
assert _protocol_spec is not None and _protocol_spec.loader is not None
_protocol = importlib.util.module_from_spec(_protocol_spec)
_protocol_spec.loader.exec_module(_protocol)
serve = _protocol.serve


class RecognitionMemoryError(RuntimeError):
    """The recognition-memory step failed inside the upstream; its message is never kept (it may hold a prompt)."""


@dataclass
class _Index:
    rag: HippoRAG
    text_to_ids: dict[str, list[str]]  # distinct passage text -> chunk ids carrying it, in corpus order
    hash_to_text: dict[str, str]  # the upstream's chunk key -> passage text
    failures: list[str] = field(default_factory=list)  # exception type names raised inside recognition memory


_INDEX: _Index | None = None


def _require_index() -> _Index:
    if _INDEX is None:
        raise RuntimeError("build must run before retrieve")
    return _INDEX


def _read_corpus(path: str) -> list[dict[str, str]]:
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _watched(infer: Callable[..., Any], index: _Index) -> Callable[..., Any]:
    """Record, then re-raise, any failure of the recognition-memory LLM call (the upstream would swallow it)."""

    def call(*args: Any, **kwargs: Any) -> Any:
        try:
            return infer(*args, **kwargs)
        except Exception as exc:
            index.failures.append(type(exc).__name__)
            raise

    return call


def build(params: dict[str, Any]) -> dict[str, Any]:
    global _INDEX
    rows = _read_corpus(str(params["corpus"]))
    workdir = Path(params["workdir"])
    workdir.mkdir(parents=True, exist_ok=True)
    text_to_ids: dict[str, list[str]] = {}
    for row in rows:
        text_to_ids.setdefault(row["text"], []).append(row["chunk_id"])
    distinct = list(text_to_ids)
    config = BaseConfig(
        save_dir=str(workdir),
        llm_name=os.environ["COMPARATOR_LLM_MODEL"],
        llm_base_url=os.environ["OPENAI_BASE_URL"],
        embedding_model_name=os.environ["COMPARATOR_EMBED_MODEL"],
        embedding_base_url=os.environ["OPENAI_BASE_URL"],
        embedding_provider="openai",
        openie_mode="online",
        max_retry_attempts=0,  # a retry is another proxy call: the proxy counts and caps it, the SDK must not add more
    )
    rag = HippoRAG(global_config=config)
    rag.index(docs=distinct)
    index = _Index(
        rag=rag,
        text_to_ids=text_to_ids,
        hash_to_text={rag.chunk_embedding_store.get_hash_id(text): text for text in distinct},
    )
    if rag.rerank_filter is None:  # online mode always builds the recognition-memory filter
        raise RuntimeError("the upstream built no recognition-memory filter")
    rag.rerank_filter.llm_infer_fn = _watched(rag.extraction_llm.infer, index)
    original_rerank = rag.rerank_facts

    def checked_rerank(query: str, query_fact_scores: Any) -> Any:
        indices, facts, log = original_rerank(query, query_fact_scores)
        if "error" in log:
            raise RecognitionMemoryError("fact reranking failed inside the upstream")
        return indices, facts, log

    rag.rerank_facts = checked_rerank  # an instance attribute: HippoRAG.retrieve calls self.rerank_facts
    _INDEX = index
    graph = rag.graph
    return {
        "hipporag_version": metadata.version("hipporag"),
        "mode": "official HippoRAG 2 index and retrieve; QA not run",
        "llm": {"model": config.llm_name, "route": "counting proxy", "max_retry_attempts": config.max_retry_attempts},
        "embedding": {"provider": "openai", "model": config.embedding_model_name, "route": "counting proxy"},
        "openie_mode": config.openie_mode,
        "retrieval": {
            "retrieval_top_k_default": config.retrieval_top_k,
            "linking_top_k": config.linking_top_k,
            "damping": config.damping,
            "passage_node_weight": config.passage_node_weight,
            "graph_type": config.graph_type,
            "synonymy_edge_sim_threshold": config.synonymy_edge_sim_threshold,
            "synonymy_edge_topk": config.synonymy_edge_topk,
            "rerank_prompt": "upstream built-in",
        },
        "corpus_chunks": len(rows),
        "distinct_passages": len(distinct),
        "graph": {"nodes": graph.vcount(), "edges": graph.ecount()},
    }


def _relation(index: _Index, passage: str, facts: list[Any]) -> dict[str, Any] | None:
    """The first retrieved fact whose names both occur in this passage, with the chunks that extracted it."""
    padded = f" {text_processing(passage)} "
    for fact in facts:
        if len(fact) != 3:
            continue
        subject, predicate, obj = (str(part) for part in fact)
        if not subject or not obj or f" {subject} " not in padded or f" {obj} " not in padded:
            continue
        keys = index.rag.proc_triples_to_docs.get(str(tuple(text_processing(list(fact)))), set())
        supporting: set[str] = set()
        for key in keys:
            text = index.hash_to_text.get(key)
            if text is None:
                continue
            padded_source = f" {text_processing(text)} "
            if f" {subject} " in padded_source and f" {obj} " in padded_source:
                supporting.update(index.text_to_ids[text])
        if supporting:
            return {"subject": subject, "predicate": predicate, "object": obj, "supporting_ids": sorted(supporting)}
    return None


def retrieve(params: dict[str, Any]) -> dict[str, Any]:
    index = _require_index()
    query = str(params["query"])
    limit = int(params["limit"])
    index.failures.clear()
    solution = index.rag.retrieve(queries=[query], num_to_retrieve=limit)[0]
    if index.failures:
        raise RecognitionMemoryError(index.failures[0])
    graph_seeds = list(solution.graph_seeds or [])
    hits: list[dict[str, Any]] = []
    for text, score in zip(solution.docs, solution.doc_scores, strict=True):
        relation = _relation(index, text, graph_seeds)
        for chunk_id in index.text_to_ids[text]:
            hits.append({"chunk_id": chunk_id, "score": float(score), "relation": relation})
    return {"hits": hits[:limit]}


if __name__ == "__main__":
    serve({"build": build, "retrieve": retrieve})
