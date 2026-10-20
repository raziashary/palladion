"""R6: LightRAG in hybrid mode as a third-party comparator in an isolated worker (B06-T03.01, BADR-0031).

The worker (``comparators/lightrag/worker.py``) runs the upstream's own pipeline at the approved commit 28ff1b05
(v1.5.7): its fixed-token chunker, entity and relation extraction with gleaning, description merging, and the
upstream's hybrid ``aquery_data`` (local entity retrieval plus global relation retrieval over the knowledge graph).
Nothing here replaces that retrieval with another search. Each corpus chunk is one LightRAG document whose id and
file path are the corpus ``chunk_id``, so native chunks map back to corpus chunks.

Model calls: indexing calls the LLM for entity and relation extraction (with gleaning) and occasionally for description
summaries, through the counting proxy; embeddings are local proxy calls. Query time makes one keyword-extraction LLM
call per distinct query (hybrid mode asks the LLM for high- and low-level keywords; upstream caches it by prompt). This
call is NOT disabled: it is the upstream's retrieval step. No answer is generated. Both are counted by the proxy and
reported per query as ``QUERY_LLM_CALLS``.

Unsupported here, declared rather than simulated: ACL filtering (graph outputs carry no document id, so the neutral
filter acts after the upstream ranking) and as-of filtering (the graph input is the published text only).

Native configuration and deviations are recorded by the worker's ``build`` reply and the comparator pin: retrieval only
(no answer step); embeddings through the proxy's OpenAI-compatible endpoint with the benchmark's pinned MiniLM model
(384 dimensions), not the upstream example's embedding; the default tokenizer (tiktoken ``gpt-4o-mini``, ``o200k_base``)
loaded from the owner-approved cache in ``artifacts/comparators/tiktoken-cache``; hybrid mode without a rerank model;
exact-duplicate chunk texts indexed once and expanded at retrieval; a document the upstream does not index is a build
failure, not a partial index.
"""

from __future__ import annotations

from pathlib import Path

from benchmark.adapters.common import DEFAULT_CHUNK_WORDS, Condition, PublishedView
from benchmark.adapters.worker import WorkerArm, launch_arm
from benchmark.llm_proxy import ProxyServer
from benchmark.run_manifest import ComparatorPin

WORKER = Path(__file__).resolve().parents[2] / "comparators" / "lightrag" / "worker.py"
UNSUPPORTED = ("ACL_FILTER", "AS_OF_FILTER")


def build_lightrag_arm(
    *,
    interpreter: Path,
    server: ProxyServer,
    pin: ComparatorPin,
    view: PublishedView,
    work_dir: Path,
    llm_model: str,
    embedding_model: str,
    condition: Condition = Condition.C2,
    chunk_words: int = DEFAULT_CHUNK_WORDS,
    build_timeout: float = 3600.0,
    query_timeout: float = 120.0,
) -> WorkerArm:
    """Start the LightRAG worker in its environment, wired to the proxy, and return arm R6."""
    return launch_arm(
        "R6",
        script=WORKER,
        interpreter=interpreter,
        server=server,
        pin=pin,
        view=view,
        work_dir=work_dir,
        llm_model=llm_model,
        embedding_model=embedding_model,
        unsupported=UNSUPPORTED,
        condition=condition,
        chunk_words=chunk_words,
        build_timeout=build_timeout,
        query_timeout=query_timeout,
    )
