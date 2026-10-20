"""R4: HippoRAG 2 as a third-party comparator in an isolated worker (B06-T01.01, BADR-0031).

The worker (``comparators/hipporag2/worker.py``) runs the upstream's own pipeline at the pinned checkout: OpenIE by the
online LLM client, passage, entity and fact embeddings, the graph, and the upstream's ``retrieve`` (fact retrieval,
recognition memory and Personalized PageRank). Nothing here replaces that retrieval with another search.

Model calls: indexing makes two LLM calls per distinct chunk (named entities, then triples) through the counting proxy.
Query time makes one recognition-memory call per query when candidate facts exist (cached upstream by prompt); query
embeddings are local proxy calls. Both are counted by the proxy and reported per query as ``QUERY_LLM_CALLS``.

Unsupported here, declared rather than simulated: ACL filtering (graph outputs carry no document id, so the neutral
filter acts after the upstream ranking) and as-of filtering (the graph input is the published text only).

Native configuration and deviations are recorded by the worker's ``build`` reply and the comparator pin: retrieval only
(no QA step); embeddings through the proxy's OpenAI-compatible endpoint, not the upstream default NV-Embed-v2; upstream
LLM retries disabled; recognition-memory failures raise instead of falling back silently; identical chunk texts indexed
once and expanded at retrieval.
"""

from __future__ import annotations

from pathlib import Path

from benchmark.adapters.common import DEFAULT_CHUNK_WORDS, Condition, PublishedView
from benchmark.adapters.worker import WorkerArm, launch_arm
from benchmark.llm_proxy import ProxyServer
from benchmark.run_manifest import ComparatorPin

WORKER = Path(__file__).resolve().parents[2] / "comparators" / "hipporag2" / "worker.py"
UNSUPPORTED = ("ACL_FILTER", "AS_OF_FILTER")


def build_hipporag2_arm(
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
    query_timeout: float = 100.0,
) -> WorkerArm:
    """Start the HippoRAG 2 worker in its environment, wired to the proxy, and return arm R4."""
    return launch_arm(
        "R4",
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
