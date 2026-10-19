"""Owned cancellable local search; JSON IPC, credential-free environment, no shell."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from evidence_agent.core.errors import DependencyUnavailable
from evidence_agent.retrieval.hybrid import HybridSearch, SearchResult

_ENVIRONMENT = {"SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATH", "PATHEXT", "USERPROFILE",
                "LOCALAPPDATA", "APPDATA", "HOMEDRIVE", "HOMEPATH", "PROCESSOR_ARCHITECTURE",
                "NUMBER_OF_PROCESSORS"}


async def _run(command: tuple[str, ...], payload: bytes) -> bytes:
    if len(payload) > 16384:
        raise ValueError("Search IPC input exceeds bound")
    environment = {k: v for k, v in os.environ.items() if k.upper() in _ENVIRONMENT}
    environment.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", PYTHONUTF8="1")
    pending = asyncio.create_task(asyncio.create_subprocess_exec(*command,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL, env=environment))
    process = None
    try:
        process = await asyncio.shield(pending)
        assert process.stdin is not None and process.stdout is not None
        process.stdin.write(payload)
        await process.stdin.drain()
        process.stdin.close()
        result = bytearray()
        while piece := await process.stdout.read(65536):
            result.extend(piece)
            if len(result) > 512 * 1024:
                raise DependencyUnavailable("Search worker response exceeds bound")
        if await process.wait() != 0:
            raise DependencyUnavailable("Search worker unavailable")
        return bytes(result)
    finally:
        # Cancellation during creation must still obtain and reap the owned child.
        if process is None:
            process = await pending
        async def reap() -> None:
            assert process is not None
            if process.returncode is None:
                process.terminate()
            if process.stdin is not None:
                process.stdin.close()
                try:
                    await process.stdin.wait_closed()
                except (BrokenPipeError, ConnectionResetError):
                    pass
            # Drain/discard residual pipe buffers after termination, without retaining data.
            if process.stdout is not None:
                while await process.stdout.read(65536):
                    pass
            await process.wait()
        cleanup = asyncio.create_task(reap())
        try:
            await asyncio.shield(cleanup)
        except asyncio.CancelledError:
            await cleanup
            raise


async def search(owner: HybridSearch, principal_id: str, case_id: str,
                 query: str, mode: str, limit: int, *, require_graph: bool = False) -> SearchResult:
    from evidence_agent.retrieval.rerank import FastEmbedReranker
    from evidence_agent.storage.qdrant import QdrantIndex
    if not isinstance(owner.index, QdrantIndex) or owner.index.worker_configuration is None:
        raise DependencyUnavailable("Runtime requires reconstructible local search")
    ranker = owner.ranker
    if ranker is not None and not isinstance(ranker, FastEmbedReranker):
        raise DependencyUnavailable("Runtime requires reconstructible reranker")
    payload = {"database": owner.registry.database.path,
        "originals": str(owner.registry.originals.root), "principal_id": principal_id,
        "case_id": case_id, "query": query, "mode": mode, "limit": limit,
        "index": owner.index.worker_configuration,
        "reranker": ranker.worker_configuration if ranker else {"enabled": False},
        "graph": {"backend":owner.graph.backend.worker_configuration,
            "limits":owner.graph.limits.model_dump(mode="json")} if owner.graph else None,
        "require_graph":require_graph}
    try:
        result = await _run((sys.executable, "-X", "utf8", "-m",
            "evidence_agent.agent.search_worker"), json.dumps(payload).encode())
        return SearchResult.model_validate_json(result)
    except (OSError, ValueError) as exc:
        raise DependencyUnavailable("Search worker unavailable") from exc


def main() -> None:
    from evidence_agent.retrieval.rerank import FastEmbedReranker
    from evidence_agent.storage.catalog import Catalog
    from evidence_agent.storage.originals import OriginalStore
    from evidence_agent.storage.qdrant import QdrantIndex
    from evidence_agent.storage.registry import Registry
    from evidence_agent.storage.sqlite import Database
    raw = sys.stdin.buffer.read(16385)
    if len(raw) > 16384:
        raise ValueError("Search IPC input exceeds bound")
    payload: dict[str, Any] = json.loads(raw)
    index = QdrantIndex(**payload["index"])
    graph = None
    try:
        with Database(payload["database"]) as database:
            registry = Registry(database, OriginalStore(Path(payload["originals"])))
            principal = registry.access.authenticate(payload["principal_id"])
            reranker_configuration = payload["reranker"]
            if "cache_dir" in reranker_configuration:
                reranker_configuration["cache_dir"] = Path(reranker_configuration["cache_dir"])
            ranker = FastEmbedReranker(**reranker_configuration)
            if payload.get("graph") is not None:
                from evidence_agent.graph.relations import TraversalLimits
                from evidence_agent.retrieval.graph_expand import GraphExpansion
                from evidence_agent.storage.neo4j import Neo4jIndex
                graph = GraphExpansion(Neo4jIndex(**payload["graph"]["backend"]),
                                      TraversalLimits.model_validate(payload["graph"]["limits"]))
            result = HybridSearch(Catalog(registry), index, ranker, graph).search(principal,
                payload["case_id"], payload["query"], mode=payload["mode"], limit=payload["limit"],
                require_graph=payload.get("require_graph",False))
            sys.stdout.buffer.write(result.model_dump_json().encode())
    finally:
        index.close()
        if graph is not None:
            graph.backend.close()


if __name__ == "__main__":
    main()
