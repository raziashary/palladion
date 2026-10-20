"""R5: Microsoft GraphRAG Local as a third-party comparator in an isolated worker (B06-T02.01, BADR-0031).

The worker (``comparators/graphrag/worker.py``) runs the upstream's own standard indexing pipeline at the approved
checkout (release v3.3.0): LLM entity and relationship extraction, leiden communities, and entity and text-unit
embeddings. Retrieval is GraphRAG's own local context builder, which ranks text units by the entities it maps to the
question. Only that builder runs: no answer is generated, and Global and DRIFT search are not built (BADR-0031).

Model calls: indexing makes one extraction call per chunk (no gleaning) through the counting proxy, plus summary calls
where an entity has several descriptions. Query time makes no chat call; the query embedding is a local proxy call.
Both are counted by the proxy and reported per query as ``QUERY_LLM_CALLS``.

Unsupported here, declared rather than simulated: ACL filtering (graph outputs carry no document id, so the neutral
filter acts after the upstream ranking) and as-of filtering (the graph input is the published text only).

Native configuration and deviations are recorded by the worker's ``build`` reply and in the comparator pin: one document
per chunk, no community reports, no gleaning, no answer call, relations without a predicate, and no native hit score.
"""

from __future__ import annotations

from pathlib import Path

from benchmark.adapters.common import DEFAULT_CHUNK_WORDS, Condition, PublishedView
from benchmark.adapters.worker import WorkerArm, launch_arm
from benchmark.llm_proxy import ProxyServer
from benchmark.run_manifest import ComparatorPin

WORKER = Path(__file__).resolve().parents[2] / "comparators" / "graphrag" / "worker.py"
UNSUPPORTED = ("ACL_FILTER", "AS_OF_FILTER")


def build_graphrag_arm(
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
    """Start the GraphRAG Local worker in its environment, wired to the proxy, and return arm R5."""
    return launch_arm(
        "R5",
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
