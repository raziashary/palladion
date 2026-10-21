"""E0: a plain LangChain two-step as a retriever in an isolated worker (B07-T01.01, BADR-0039, BADR-0040).

The worker (``comparators/langchain/worker.py``) indexes the shared 120-word chunks in LangChain's
``InMemoryVectorStore`` with ``OpenAIEmbeddings`` pointed at the counting proxy (the benchmark's pinned embedding model,
served locally) and answers with ``similarity_search_with_score``. The benchmark's shared generator, prompt and answer
gate then answer from the retrieved passages (the Track B pattern), so E0 differs from R3 and R7a in its retrieval
stack only.

Declared, not hidden: E0 is a reference implementation of ordinary retrieve-then-answer RAG built from LangChain
components, not one algorithm (protocol 2.2); the splitter step is the shared chunker so every arm ranks the same
evidence units; the access filter acts after the ranking (the store has no principal filter); there is no as-of
selection; and the index cost is the proxy's embedding count, since no model extraction happens.
"""

from __future__ import annotations

from pathlib import Path

from benchmark.adapters.common import DEFAULT_CHUNK_WORDS, Condition, PublishedView
from benchmark.adapters.worker import WorkerArm, launch_arm
from benchmark.llm_proxy import ProxyServer
from benchmark.run_manifest import ComparatorPin

WORKER = Path(__file__).resolve().parents[2] / "comparators" / "langchain" / "worker.py"
UNSUPPORTED = ("ACL_FILTER", "AS_OF_FILTER")


def build_langchain_arm(
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
    """Start the LangChain worker in its environment, wired to the proxy, and return the retriever of arm E0."""
    return launch_arm(
        "E0",
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
