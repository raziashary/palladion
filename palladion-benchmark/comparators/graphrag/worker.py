"""R5 Microsoft GraphRAG Local, served to the benchmark as a worker (B06-T02.01, BADR-0031).

Runs inside ``artifacts/comparators/env-graphrag`` (Python 3.12, graphrag 3.3.0 from the approved checkout). The index
is built by GraphRAG's own standard pipeline over one input document per corpus chunk (title = chunk_id): entity,
relationship and description extraction, community detection and embeddings all come from upstream. Retrieval runs
GraphRAG's own local context builder and stops there: no answer is generated, so no chat call is made at query time.

Upstream entry points (artifacts/comparators/graphrag/packages/graphrag/graphrag):
- api/index.py:29 ``build_index`` with ``input_documents``, method Standard
- config/models/graph_rag_config.py ``GraphRagConfig``, built in code below (its api_key is the per-run proxy token)
- data_model/data_reader.py ``DataReader`` for the output tables
- query/indexer_adapters.py ``read_indexer_*``, the loaders the CLI query uses
- utils/api.py:15 ``get_embedding_store``
- query/factory.py:37 ``get_local_search_engine`` (constructs the engine; its answer path is never called)
- query/structured_search/local_search/mixed_context.py:91 ``LocalSearchMixedContext.build_context``

Deviations from upstream defaults are listed in ``NATIVE_DEVIATIONS`` and returned with the build.

Network: the process is kept loopback-only. A non-loopback name lookup or connection raises ``NetworkRefused`` and
writes the host name to the worker's stderr log, so a fetch the upstream attempts is reported, never performed.
Models are reached only through the counting proxy in ``OPENAI_BASE_URL``.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
import urllib.request
from importlib import metadata
from pathlib import Path
from typing import Any

for _name, _value in (
    ("LITELLM_LOCAL_MODEL_COST_MAP", "True"),
    ("ANONYMIZED_TELEMETRY", "False"),
    ("DO_NOT_TRACK", "1"),
    ("HF_HUB_OFFLINE", "1"),
    ("TRANSFORMERS_OFFLINE", "1"),
):
    os.environ.setdefault(_name, _value)
if "TIKTOKEN_CACHE_DIR" in os.environ:
    # litellm points TIKTOKEN_CACHE_DIR at its own bundled tokenizers on import; its CUSTOM_ setting keeps the approved
    # cache (the one the coordinator verified by hash) as the only place tiktoken reads encodings from.
    os.environ.setdefault("CUSTOM_TIKTOKEN_CACHE_DIR", os.environ["TIKTOKEN_CACHE_DIR"])


def _load_protocol() -> Any:
    """The benchmark's protocol module, loaded by the path the launcher gives in COMPARATOR_PROTOCOL (no sys.path)."""
    spec = importlib.util.spec_from_file_location("comparator_protocol", os.environ["COMPARATOR_PROTOCOL"])
    if spec is None or spec.loader is None:
        raise RuntimeError("COMPARATOR_PROTOCOL does not name a Python file")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_protocol = _load_protocol()
serve = _protocol.serve
NetworkRefused = _protocol.NetworkRefused
guard_network = _protocol.guard_network

# Worker-side switches. Build params carry only corpus, workdir and namespace, so these are fixed here and recorded.
COMMUNITY_REPORTS = False  # one LLM call per community: too costly for the test corpus
MAX_GLEANINGS = 0  # native default is 1 (one more extraction call per chunk); 0 keeps the call count predictable
CONCURRENT_REQUESTS = 4
CHUNK_TOKENS = 1200  # native defaults for the tokens chunker
CHUNK_OVERLAP = 100
ENCODING = "o200k_base"  # native default; loaded from TIKTOKEN_CACHE_DIR, never downloaded
LOCAL_LEVEL = 2  # the CLI's default community level for local search
CREATION_DATE = "2026-10-18T00:00:00Z"  # fixed, so the same corpus always produces the same input rows
WORKFLOWS = [
    "load_input_documents",
    "create_base_text_units",
    "create_final_documents",
    "extract_graph",
    "finalize_graph",
    "create_communities",
    "create_final_text_units",
    "generate_text_embeddings",
]
EMBED_NAMES = ["entity_description", "text_unit_text"]  # community_full_content needs reports, which are off
NATIVE_DEVIATIONS = (
    "input is one document per corpus chunk (title = chunk_id), so each 120-word chunk is one text unit",
    "community reports are not generated (COMMUNITY_REPORTS=False); local search has no community section",
    f"max_gleanings={MAX_GLEANINGS} (native default 1)",
    "no answer LLM call: the local context builder only, so ranked evidence is returned, not a generated answer",
    "GraphRAG relationships carry no predicate; a relation gets the predicate 'related_to'",
    "hit score is None: local search ranks text units by entity order and has no per-unit score",
    "vector_size is probed from the embedding model through the proxy at build time (its native dimension)",
)


class IndexingFailed(RuntimeError):
    """A GraphRAG workflow finished with an error. The workflow names go to stderr, not the protocol."""


class NotBuilt(RuntimeError):
    """Retrieval was asked before a successful build, or the environment lacks the proxy settings."""


guard_network()

import litellm  # noqa: E402  (after the environment and the guard are in place)
import pandas as pd  # noqa: E402

litellm.telemetry = False

from graphrag.api import build_index  # noqa: E402
from graphrag.config.embeddings import entity_description_embedding  # noqa: E402
from graphrag.config.enums import IndexingMethod  # noqa: E402
from graphrag.config.models.graph_rag_config import GraphRagConfig  # noqa: E402
from graphrag.data_model.data_reader import DataReader  # noqa: E402
from graphrag.query.factory import get_local_search_engine  # noqa: E402
from graphrag.query.indexer_adapters import (  # noqa: E402
    read_indexer_entities,
    read_indexer_relationships,
    read_indexer_text_units,
)
from graphrag.utils.api import get_embedding_store  # noqa: E402
from graphrag_storage import create_storage  # noqa: E402
from graphrag_storage.tables.table_provider_factory import create_table_provider  # noqa: E402

_STATE: dict[str, Any] = {}


def _proxy_environment() -> tuple[str, str, str, str]:
    """The proxy address, the run token, and the two approved model names. The token is never logged or returned."""
    try:
        return (
            os.environ["OPENAI_BASE_URL"],
            os.environ["OPENAI_API_KEY"],
            os.environ["COMPARATOR_LLM_MODEL"],
            os.environ["COMPARATOR_EMBED_MODEL"],
        )
    except KeyError as exc:
        raise NotBuilt(f"missing environment variable {exc.args[0]}") from None


def _probe_dimension(base: str, token: str, embed: str) -> int:
    """One embedding through the proxy, to learn the model's native dimension for the vector table."""
    body = json.dumps({"model": embed, "input": ["dimension probe"]}).encode("utf-8")
    request = urllib.request.Request(
        f"{base}/embeddings",
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:  # loopback proxy only
        vector = json.loads(response.read())["data"][0]["embedding"]
    return len(vector)


def _read_corpus(path: Path) -> list[dict[str, str]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows:
        if not all(isinstance(row.get(key), str) for key in ("chunk_id", "doc_id", "text")):
            raise ValueError("a corpus row lacks chunk_id, doc_id or text")
    return rows


def _settings(work: Path, base: str, token: str, llm: str, embed: str, vector_size: int) -> GraphRagConfig:
    """The native configuration, in code. ``api_key`` is the per-run proxy token, never a provider key."""
    return GraphRagConfig.model_validate(
        {
            "completion_models": {
                "default_completion_model": {
                    "model_provider": "openai",
                    "model": llm,
                    "api_base": base,
                    "api_key": token,
                    "call_args": {"temperature": 0.0},
                }
            },
            "embedding_models": {
                "default_embedding_model": {
                    "model_provider": "openai",
                    "model": embed,
                    "api_base": base,
                    "api_key": token,
                }
            },
            "concurrent_requests": CONCURRENT_REQUESTS,
            "input_storage": {"type": "file", "base_dir": str(work / "input")},
            "output_storage": {"type": "file", "base_dir": str(work / "output")},
            "update_output_storage": {"type": "file", "base_dir": str(work / "update_output")},
            "cache": {"type": "json", "storage": {"type": "file", "base_dir": str(work / "cache")}},
            "reporting": {"type": "file", "base_dir": str(work / "logs")},
            "vector_store": {
                "type": "lancedb",
                "db_uri": str(work / "output" / "lancedb"),
                "vector_size": vector_size,
            },
            "chunking": {"type": "tokens", "size": CHUNK_TOKENS, "overlap": CHUNK_OVERLAP, "encoding_model": ENCODING},
            "embed_text": {"embedding_model_id": "default_embedding_model", "names": EMBED_NAMES},
            "extract_graph": {"max_gleanings": MAX_GLEANINGS},
            "workflows": WORKFLOWS,
        }
    )


def build(params: dict[str, Any]) -> dict[str, Any]:
    """Index the corpus with GraphRAG's standard pipeline and keep what local search needs in memory."""
    rows = _read_corpus(Path(params["corpus"]))
    work = Path(params["workdir"])
    work.mkdir(parents=True, exist_ok=True)
    base, token, llm, embed = _proxy_environment()
    vector_size = _probe_dimension(base, token, embed)
    config = _settings(work, base, token, llm, embed, vector_size)
    documents = pd.DataFrame(
        [
            {
                "id": f"doc-{index}",
                "human_readable_id": index,
                "title": row["chunk_id"],
                "text": row["text"],
                "creation_date": CREATION_DATE,
                "raw_data": None,
            }
            for index, row in enumerate(rows)
        ]
    )
    outputs = asyncio.run(build_index(config=config, method=IndexingMethod.Standard, input_documents=documents))
    failed = [output.workflow for output in outputs if output.error is not None]
    if failed:
        print(f"WORKFLOWS_FAILED {failed}", file=sys.stderr, flush=True)
        raise IndexingFailed("IndexingFailed")
    provider = create_table_provider(config.table_provider, storage=create_storage(config.output_storage))
    reader = DataReader(provider)
    tables = {
        name: asyncio.run(getattr(reader, name)())
        for name in ("documents", "text_units", "entities", "relationships", "communities")
    }
    _STATE.clear()
    _STATE.update(
        config=config,
        corpus={row["chunk_id"]: row["text"] for row in rows},
        tables=tables,
        store=get_embedding_store(config.vector_store, embedding_name=entity_description_embedding),
        units=read_indexer_text_units(tables["text_units"]),
        entities=read_indexer_entities(tables["entities"], tables["communities"], LOCAL_LEVEL),
        relationships=read_indexer_relationships(tables["relationships"]),
    )
    return {
        "method": "graphrag standard indexing (LLM extraction, leiden communities, embeddings)",
        "package": {"graphrag": metadata.version("graphrag"), "litellm": metadata.version("litellm")},
        "search": "local context builder only (no answer LLM call)",
        "community_reports": COMMUNITY_REPORTS,
        "workflows": WORKFLOWS,
        "chunking": {"type": "tokens", "size": CHUNK_TOKENS, "overlap": CHUNK_OVERLAP, "encoding": ENCODING},
        "models": {"llm": llm, "embeddings": embed},
        "vector_size": vector_size,
        "documents": len(rows),
        "text_units": len(tables["text_units"]),
        "entities": len(tables["entities"]),
        "relationships": len(tables["relationships"]),
        "deviations": list(NATIVE_DEVIATIONS),
    }


def _named(name: str, text: str) -> bool:
    return bool(name) and name.casefold() in text.casefold()


def _relation(chunk_id: str, unit_id: str, edges: list[tuple[str, str, set[str]]], text: str) -> dict[str, Any] | None:
    """The first returned relationship that this chunk's text unit carries and whose two names its text contains."""
    for source, target, unit_ids in edges:
        if unit_id in unit_ids and _named(source, text) and _named(target, text):
            return {"subject": source, "predicate": "related_to", "object": target, "supporting_ids": [chunk_id]}
    return None


def retrieve(params: dict[str, Any]) -> dict[str, Any]:
    """Run GraphRAG's local context builder and map its ranked text units to corpus chunk ids, best first."""
    if not _STATE:
        raise NotBuilt("NotBuilt")
    query = str(params["query"])
    limit = int(params["limit"])
    tables = _STATE["tables"]
    title_of = dict(zip(tables["documents"]["id"], tables["documents"]["title"], strict=True))
    text_units = tables["text_units"]
    chunk_of_unit = {
        uid: title_of[doc_id] for uid, doc_id in zip(text_units["id"], text_units["document_id"], strict=True)
    }
    unit_by_short = {
        str(short): uid for short, uid in zip(text_units["human_readable_id"], text_units["id"], strict=True)
    }
    rels = tables["relationships"]
    edges_by_short = {
        str(short): (src, dst, set(unit_ids))
        for short, src, dst, unit_ids in zip(
            rels["human_readable_id"], rels["source"], rels["target"], rels["text_unit_ids"], strict=True
        )
    }
    engine = get_local_search_engine(
        config=_STATE["config"],
        reports=[],
        text_units=_STATE["units"],
        entities=_STATE["entities"],
        relationships=_STATE["relationships"],
        covariates={"claims": []},
        description_embedding_store=_STATE["store"],
        response_type="Multiple Paragraphs",
        system_prompt=None,
    )
    context = engine.context_builder.build_context(
        query=query, conversation_history=None, **engine.context_builder_params
    )
    records = context.context_records
    returned_edges = [
        edges_by_short[str(short)]
        for short in records.get("relationships", pd.DataFrame()).get("id", pd.Series(dtype=str))
        if str(short) in edges_by_short
    ]
    hits: list[dict[str, Any]] = []
    seen: set[str] = set()
    for short in records.get("sources", pd.DataFrame()).get("id", pd.Series(dtype=str)):
        unit_id = unit_by_short[str(short)]
        chunk_id = chunk_of_unit[unit_id]
        if chunk_id in seen:
            continue
        seen.add(chunk_id)
        relation = _relation(chunk_id, unit_id, returned_edges, _STATE["corpus"][chunk_id])
        hits.append({"chunk_id": chunk_id, "score": None, "relation": relation})
        if len(hits) == limit:
            break
    return {"hits": hits}


if __name__ == "__main__":
    serve({"build": build, "retrieve": retrieve})
