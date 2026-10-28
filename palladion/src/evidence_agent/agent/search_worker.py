"""Owned cancellable local search; JSON IPC, credential-free environment, no shell.

A search runs in a child process so that it can be killed on a deadline or a cancellation and holds no credential.
`_run` starts a child for one request (scripts and the `per_request` mode). `SearchWorkers` keeps children that serve
many requests, so the embedding model and the reranker are loaded once, not for every search (ADR-0111).
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO

from evidence_agent.core.errors import DependencyUnavailable
from evidence_agent.retrieval.hybrid import HybridSearch, SearchResult
from evidence_agent.storage.applicability import Applicability

if TYPE_CHECKING:
    from evidence_agent.retrieval.rerank import FastEmbedReranker
    from evidence_agent.storage.qdrant import QdrantIndex

MAX_REQUEST_BYTES = 16384
MAX_RESPONSE_BYTES = 512 * 1024
MAX_PARALLEL_SEARCHES = 2  # searches that run at once, each in a process that loads models; also the idle workers kept
WORKER_COMMAND = (sys.executable, "-X", "utf8", "-m", "evidence_agent.agent.search_worker")
SERVE_COMMAND = (*WORKER_COMMAND, "--serve")
_ENVIRONMENT = {"SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATH", "PATHEXT", "USERPROFILE",
                "LOCALAPPDATA", "APPDATA", "HOMEDRIVE", "HOMEPATH", "PROCESSOR_ARCHITECTURE",
                "NUMBER_OF_PROCESSORS"}


def _environment() -> dict[str, str]:
    """What a worker inherits: the system variables it needs and nothing else (no credential, no Python injection)."""
    environment = {k: v for k, v in os.environ.items() if k.upper() in _ENVIRONMENT}
    environment.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", PYTHONUTF8="1")
    return environment


async def _spawn(command: tuple[str, ...]) -> asyncio.subprocess.Process:
    """Start an owned child; if the caller is cancelled while it starts, the child is still obtained and joined."""
    pending = asyncio.create_task(asyncio.create_subprocess_exec(*command,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL, env=_environment(), limit=2 * MAX_RESPONSE_BYTES))
    try:
        return await asyncio.shield(pending)
    except BaseException:
        await _stop(await pending)
        raise


async def _stop(process: asyncio.subprocess.Process, *, drain: bool = True) -> None:
    """Terminate an owned child and join it, even when the caller is cancelled meanwhile. `drain` is false while a request
    is still reading the child's output: that request then ends with the child, and nothing else may read it."""
    async def reap() -> None:
        try:
            if process.returncode is None:
                process.terminate()
            if process.stdin is not None:
                process.stdin.close()
                try:
                    await process.stdin.wait_closed()
                except (BrokenPipeError, ConnectionResetError):
                    pass
            # Drain/discard residual pipe buffers after termination, without retaining data.
            if drain and process.stdout is not None:
                while await process.stdout.read(65536):
                    pass
        finally:
            await process.wait()
    cleanup = asyncio.create_task(reap())
    try:
        await asyncio.shield(cleanup)
    except asyncio.CancelledError:
        await cleanup
        raise


async def _run(command: tuple[str, ...], payload: bytes) -> bytes:
    """One request in a child of its own, read to the end; the child is joined whatever happens."""
    if len(payload) > MAX_REQUEST_BYTES:
        raise ValueError("Search IPC input exceeds bound")
    process = await _spawn(command)
    try:
        assert process.stdin is not None and process.stdout is not None
        process.stdin.write(payload)
        await process.stdin.drain()
        process.stdin.close()
        result = bytearray()
        while piece := await process.stdout.read(65536):
            result.extend(piece)
            if len(result) > MAX_RESPONSE_BYTES:
                raise DependencyUnavailable("Search worker response exceeds bound")
        if await process.wait() != 0:
            raise DependencyUnavailable("Search worker unavailable")
        return bytes(result)
    finally:
        await _stop(process)


def worker_payload(owner: HybridSearch, principal_id: str, case_id: str, query: str, mode: str, limit: int,
                   require_graph: bool, applicability: Applicability, named_from: str | None = None) -> dict[str, Any]:
    """What the search subprocess is told, including the instant the registry's clock gives (ADR-0101)."""
    from evidence_agent.retrieval.rerank import FastEmbedReranker
    from evidence_agent.storage.qdrant import QdrantIndex
    if not isinstance(owner.index, QdrantIndex) or owner.index.worker_configuration is None:
        raise DependencyUnavailable("Runtime requires reconstructible local search")
    ranker = owner.ranker
    if ranker is not None and not isinstance(ranker, FastEmbedReranker):
        raise DependencyUnavailable("Runtime requires reconstructible reranker")
    return {"database": owner.registry.database.path,
        "originals": str(owner.registry.originals.root), "principal_id": principal_id,
        "case_id": case_id, "query": query, "mode": mode, "limit": limit,
        "index": owner.index.worker_configuration,
        "reranker": ranker.worker_configuration if ranker else {"enabled": False},
        "graph": {"backend":owner.graph.backend.worker_configuration,
            "limits":owner.graph.limits.model_dump(mode="json")} if owner.graph else None,
        "require_graph":require_graph, "named_from": named_from, "as_of": applicability.primary.isoformat(),
        "also_at": [instant.isoformat() for instant in applicability.also]}


async def search(owner: HybridSearch, principal_id: str, case_id: str,
                 query: str, mode: str, limit: int, applicability: Applicability, *,
                 require_graph: bool = False, named_from: str | None = None) -> SearchResult:
    """One search in a child process started for it."""
    payload = worker_payload(owner, principal_id, case_id, query, mode, limit, require_graph, applicability, named_from)
    try:
        result = await _run(WORKER_COMMAND, json.dumps(payload).encode())
        return SearchResult.model_validate_json(result)
    except (OSError, ValueError) as exc:
        raise DependencyUnavailable("Search worker unavailable") from exc


# ------------------------------------------------------------------------------------------ the parent's pool


class _Worker:
    """One child that serves requests one at a time: a request line in, a reply line out."""

    def __init__(self, process: asyncio.subprocess.Process) -> None:
        self.process = process
        self.busy = False  # a request is waiting on the child's output
        self.stopping: asyncio.Task[None] | None = None  # set once, by the first caller that stops it

    @property
    def alive(self) -> bool:
        return self.process.returncode is None

    async def request(self, payload: bytes) -> bytes:
        """The reply line to one request; any failure of the pipe or of the line's bound is the worker's failure."""
        stdin, stdout = self.process.stdin, self.process.stdout
        assert stdin is not None and stdout is not None
        self.busy = True
        try:
            stdin.write(payload + b"\n")
            await stdin.drain()
            line = await stdout.readline()
        except (BrokenPipeError, ConnectionResetError, ValueError) as exc:  # a line past the stream's limit is ValueError
            raise DependencyUnavailable("Search worker unavailable") from exc
        finally:
            self.busy = False
        if not line.endswith(b"\n") or len(line) > MAX_RESPONSE_BYTES:
            raise DependencyUnavailable("Search worker unavailable")
        return line


def _decode(line: bytes) -> str | None:
    """The result text of a reply line, None when the worker reported that the search failed; unreadable is an error."""
    try:
        reply = json.loads(line)
    except ValueError as exc:
        raise DependencyUnavailable("Search worker unavailable") from exc
    if not isinstance(reply, dict):
        raise DependencyUnavailable("Search worker unavailable")
    if "error" in reply:
        return None
    result = reply.get("result")
    if not isinstance(result, str):
        raise DependencyUnavailable("Search worker unavailable")
    return result


class SearchWorkers:
    """The application's searches, served by children that stay up between requests (ADR-0111).

    A child is started when a search needs one and no idle child is up, and is kept for the next search. At most `keep`
    searches run at once, whoever asks, so at most `keep` children exist. A child is reused only after a reply that arrived whole; after a cancellation, a
    deadline, an oversized or unreadable reply, or its own exit it is killed and joined and the next search starts a new
    one. An idle child is stopped after `idle_seconds`, so the models' memory
    is held only while searches are being made. The pool belongs to one event loop: used from another loop it abandons
    the children of the first (they are told to end) and starts its own.
    """

    def __init__(self, *, keep: int = MAX_PARALLEL_SEARCHES, idle_seconds: float = 300.0,
                 command: tuple[str, ...] = SERVE_COMMAND) -> None:
        if keep < 1 or idle_seconds <= 0:
            raise ValueError("A pool keeps at least one worker for a positive time")
        self.keep, self.idle_seconds, self.command = keep, idle_seconds, command
        self._workers: set[_Worker] = set()
        self._idle: list[_Worker] = []
        self._timers: dict[_Worker, asyncio.TimerHandle] = {}
        self._stopping: set[asyncio.Task[None]] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._slots: asyncio.Semaphore | None = None
        self._closed = False

    async def search(self, owner: HybridSearch, principal_id: str, case_id: str, query: str, mode: str, limit: int,
                     applicability: Applicability, *, require_graph: bool = False,
                     named_from: str | None = None) -> SearchResult:
        payload = json.dumps(worker_payload(owner, principal_id, case_id, query, mode, limit, require_graph,
                                            applicability, named_from)).encode()
        try:
            result = await self.exchange(payload)
            return SearchResult.model_validate_json(result)
        except (OSError, ValueError) as exc:
            raise DependencyUnavailable("Search worker unavailable") from exc

    async def exchange(self, payload: bytes) -> str:
        """One request line to a worker and its result text; a search the worker reports as failed is unavailable too."""
        if len(payload) > MAX_REQUEST_BYTES:
            raise ValueError("Search IPC input exceeds bound")
        slots = self._attach()
        async with slots:
            worker = await self._acquire()
            try:
                result = _decode(await worker.request(payload))
            except BaseException:
                await self._discard(worker)
                raise
            self._release(worker)
        if result is None:
            raise DependencyUnavailable("Search worker unavailable")
        return result

    def _attach(self) -> asyncio.Semaphore:
        """The slots of the running event loop; children of another loop cannot be used from this one and are let go."""
        loop = asyncio.get_running_loop()
        if self._loop is not loop or self._slots is None:
            self._abandon()
            self._loop, self._slots = loop, asyncio.Semaphore(self.keep)
        return self._slots

    def _abandon(self) -> None:
        for timer in self._timers.values():
            with contextlib.suppress(RuntimeError):  # its loop may be closed already
                timer.cancel()
        for worker in self._workers:
            with contextlib.suppress(ProcessLookupError, RuntimeError, OSError):
                worker.process.terminate()
        self._workers.clear()
        self._idle.clear()
        self._timers.clear()

    async def _acquire(self) -> _Worker:
        if self._closed:
            raise DependencyUnavailable("Search workers are closed")
        while self._idle:
            worker = self._idle.pop()
            self._timers.pop(worker).cancel()
            if worker.alive:
                return worker
            await self._discard(worker)
        worker = _Worker(await _spawn(self.command))
        self._workers.add(worker)
        if self._closed:  # the pool was closed while this child started
            await self._discard(worker)
            raise DependencyUnavailable("Search workers are closed")
        return worker

    def _release(self, worker: _Worker) -> None:
        if self._closed or not worker.alive:
            self._stop_later(worker)
            return
        self._idle.append(worker)
        self._timers[worker] = asyncio.get_running_loop().call_later(self.idle_seconds, self._expire, worker)

    def _expire(self, worker: _Worker) -> None:
        if worker in self._idle:
            self._idle.remove(worker)
            self._timers.pop(worker, None)
            self._stop_later(worker)

    def _stop_later(self, worker: _Worker) -> None:
        task = asyncio.get_running_loop().create_task(self._discard(worker))
        self._stopping.add(task)
        task.add_done_callback(self._stopping.discard)

    async def _discard(self, worker: _Worker) -> None:
        """Stop and join the child once, however many callers ask; each caller returns when it is joined."""
        self._workers.discard(worker)
        if worker.stopping is None:
            worker.stopping = asyncio.get_running_loop().create_task(_stop(worker.process, drain=not worker.busy))
        try:
            await asyncio.shield(worker.stopping)
        except asyncio.CancelledError:
            await worker.stopping
            raise

    def terminate(self) -> None:
        """Refuse further searches and ask every child to end, without waiting for it (a caller with no event loop to
        await on; the children also end by themselves when their input closes)."""
        self._closed = True
        for timer in self._timers.values():
            timer.cancel()
        self._timers.clear()
        self._idle.clear()
        for worker in self._workers:
            if worker.alive:
                worker.process.terminate()

    async def aclose(self) -> None:
        """Stop every child, busy or idle, join it, and refuse further searches."""
        self._attach()  # children of a finished event loop cannot be awaited here: they are let go first
        workers = list(self._workers)
        self.terminate()
        await asyncio.gather(*(self._discard(worker) for worker in workers), *list(self._stopping))


# ------------------------------------------------------------------------------------------------- the child


class _Caches:
    """What a worker keeps between requests: the index client, with the embedding model it loads, and the reranker, each
    by its configuration. The database is not kept: it is opened for each request, so no request reads a stale catalog."""

    MAX_ENTRIES = 4

    def __init__(self) -> None:
        self._indexes: dict[str, QdrantIndex] = {}
        self._rankers: dict[str, FastEmbedReranker] = {}

    def index(self, configuration: dict[str, Any]) -> QdrantIndex:
        from evidence_agent.storage.qdrant import QdrantIndex
        key = json.dumps(configuration, sort_keys=True)
        if key not in self._indexes:
            while len(self._indexes) >= self.MAX_ENTRIES:  # the oldest configuration goes
                self._indexes.pop(next(iter(self._indexes))).close()
            self._indexes[key] = QdrantIndex(**configuration)
        return self._indexes[key]

    def ranker(self, configuration: dict[str, Any]) -> FastEmbedReranker:
        from evidence_agent.retrieval.rerank import FastEmbedReranker
        key = json.dumps(configuration, sort_keys=True)
        if key not in self._rankers:
            while len(self._rankers) >= self.MAX_ENTRIES:
                del self._rankers[next(iter(self._rankers))]
            settings = dict(configuration)
            if "cache_dir" in settings:
                settings["cache_dir"] = Path(settings["cache_dir"])
            self._rankers[key] = FastEmbedReranker(**settings)
        return self._rankers[key]

    def close(self) -> None:
        for index in self._indexes.values():
            index.close()
        self._indexes.clear()
        self._rankers.clear()


def _handle(payload: dict[str, Any], caches: _Caches) -> str:
    """One search, as the JSON of its result."""
    from evidence_agent.storage.catalog import Catalog
    from evidence_agent.storage.originals import OriginalStore
    from evidence_agent.storage.registry import Registry
    from evidence_agent.storage.sqlite import Database
    backend = None
    try:
        with Database(payload["database"]) as database:
            registry = Registry(database, OriginalStore(Path(payload["originals"])))
            principal = registry.access.authenticate(payload["principal_id"])
            graph = None
            if payload.get("graph") is not None:
                from evidence_agent.graph.relations import TraversalLimits
                from evidence_agent.retrieval.graph_expand import GraphExpansion
                from evidence_agent.storage.neo4j import Neo4jIndex
                backend = Neo4jIndex(**payload["graph"]["backend"])
                graph = GraphExpansion(backend, TraversalLimits.model_validate(payload["graph"]["limits"]))
            result = HybridSearch(Catalog(registry), caches.index(payload["index"]),
                caches.ranker(payload["reranker"]), graph).search(principal,
                payload["case_id"], payload["query"], mode=payload["mode"], limit=payload["limit"],
                require_graph=payload.get("require_graph",False), named_from=payload.get("named_from"),
                as_of=datetime.fromisoformat(payload["as_of"]),
                also_at=tuple(datetime.fromisoformat(value) for value in payload["also_at"]))
            return result.model_dump_json()
    finally:
        if backend is not None:
            backend.close()


def serve(requests: BinaryIO, replies: BinaryIO, handler: Callable[[dict[str, Any]], str]) -> None:
    """Answer one request per line until the input closes.

    A search that fails is an error line and the worker serves the next request: its state is per request. A request
    that is not one whole line within the bound has lost the framing, so the worker ends and the parent starts another.
    """
    while raw := requests.readline(MAX_REQUEST_BYTES + 2):
        if len(raw) > MAX_REQUEST_BYTES + 1 or not raw.endswith(b"\n"):
            raise SystemExit(2)
        try:
            reply: dict[str, str] = {"result": handler(json.loads(raw))}
        except Exception as exc:  # noqa: BLE001 - each request is answered or reported, whatever it raised
            reply = {"error": type(exc).__name__}
        replies.write(json.dumps(reply).encode() + b"\n")
        replies.flush()


def main(arguments: list[str] | None = None) -> None:
    arguments = sys.argv[1:] if arguments is None else arguments
    replies = sys.stdout.buffer
    sys.stdout = sys.stderr  # nothing a library prints may break the reply
    caches = _Caches()
    try:
        if "--serve" in arguments:
            serve(sys.stdin.buffer, replies, lambda payload: _handle(payload, caches))
        else:
            raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
            if len(raw) > MAX_REQUEST_BYTES:
                raise ValueError("Search IPC input exceeds bound")
            replies.write(_handle(json.loads(raw), caches).encode())
    finally:
        caches.close()


if __name__ == "__main__":
    main()
