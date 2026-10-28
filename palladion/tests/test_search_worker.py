"""Real local processes for strict cancellation/IPC; no provider or live data."""
import asyncio
import io
import json
import os
import sys
import time
from pathlib import Path

import pytest

from evidence_agent.agent.search_worker import (
    MAX_REQUEST_BYTES,
    SearchWorkers,
    _Caches,
    _run,
    serve,
)
from evidence_agent.core.errors import DependencyUnavailable


@pytest.mark.parametrize("stop", ["cancel", "deadline"])
def test_blocked_child_is_terminated_and_joined_on_stop(monkeypatch, stop):
    captured = []
    original = asyncio.create_subprocess_exec
    async def run():
        created = asyncio.Event()
        async def capture(*args, **kwargs):
            process = await original(*args, **kwargs)
            captured.append(process)
            created.set()
            return process
        monkeypatch.setattr(asyncio, "create_subprocess_exec", capture)
        command = (sys.executable, "-c", "import time; time.sleep(60)")
        if stop == "cancel":
            task = asyncio.create_task(_run(command, b"{}"))
            await created.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            with pytest.raises(TimeoutError):
                async with asyncio.timeout(0.4):
                    await _run(command, b"{}")
        assert len(captured) == 1
        assert captured[0].returncode is not None
    start = time.monotonic()
    asyncio.run(run())
    assert time.monotonic() - start < 5


def test_worker_does_not_inherit_credentials_or_python_injection(monkeypatch):
    for key in ("GROQ_API_KEY", "DATABASE_URL", "PROTECTED_SECRET", "PYTHONSTARTUP", "PYTHONPATH"):
        monkeypatch.setenv(key, "SYNTHETIC_CREDENTIAL_CANARY")
    code = ("import os,json,sys; sys.stdin.buffer.read(); "
        "print(json.dumps({k:k in os.environ for k in "
        "['GROQ_API_KEY','DATABASE_URL','PROTECTED_SECRET','PYTHONSTARTUP','PYTHONPATH']}))")
    result = asyncio.run(_run((sys.executable, "-c", code), b"{}"))
    assert not any(json.loads(result).values())


def test_oversized_output_terminates_child_without_unbounded_capture():
    code = "import sys,time; sys.stdout.buffer.write(b'x'*600000); sys.stdout.flush(); time.sleep(60)"
    with pytest.raises(DependencyUnavailable):
        asyncio.run(_run((sys.executable, "-c", code), b"{}"))


def test_failed_child_is_not_a_successful_search():
    with pytest.raises(DependencyUnavailable, match="unavailable"):
        asyncio.run(_run((sys.executable, "-c", "raise SystemExit(2)"), b"{}"))


# ------------------------------------------------------------------------------ long-lived workers (ADR-0111)

# A stand-in child that speaks the workers' protocol: one request line in, one reply line out, whatever `op` asks for.
FAKE = (
    "import json, os, sys, time\n"
    "for line in sys.stdin.buffer:\n"
    "    request = json.loads(line)\n"
    "    op = request['op']\n"
    "    if op == 'pid':\n"
    "        reply = {'result': str(os.getpid())}\n"
    "    elif op == 'slow':\n"
    "        time.sleep(request.get('seconds', 0.4)); reply = {'result': str(os.getpid())}\n"
    "    elif op == 'block':\n"
    "        time.sleep(60); reply = {'result': 'never'}\n"
    "    elif op == 'exit':\n"
    "        os._exit(3)\n"
    "    elif op == 'error':\n"
    "        reply = {'error': 'Boom'}\n"
    "    elif op == 'big':\n"
    "        sys.stdout.buffer.write(b'x' * 700000 + b'\\n'); sys.stdout.flush(); continue\n"
    "    elif op == 'huge':\n"
    "        reply = {'result': 'y' * 600000}\n"
    "    elif op == 'list':\n"
    "        reply = [1, 2]\n"
    "    elif op == 'garbage':\n"
    "        sys.stdout.buffer.write(b'not json\\n'); sys.stdout.flush(); continue\n"
    "    elif op == 'env':\n"
    "        keys = ['GROQ_API_KEY', 'DATABASE_URL', 'PYTHONSTARTUP', 'PYTHONPATH']\n"
    "        reply = {'result': json.dumps({k: k in os.environ for k in keys})}\n"
    "    sys.stdout.buffer.write(json.dumps(reply).encode() + b'\\n'); sys.stdout.flush()\n"
)
COMMAND = (sys.executable, "-c", FAKE)


def ask(pool: SearchWorkers, op: str, **more):  # type: ignore[no-untyped-def]
    return pool.exchange(json.dumps({"op": op, **more}).encode())


def pools(**options):  # type: ignore[no-untyped-def]
    return SearchWorkers(command=COMMAND, **options)


def test_a_worker_serves_one_request_after_another_as_the_same_process() -> None:
    async def run() -> None:
        pool = pools()
        first, second = await ask(pool, "pid"), await ask(pool, "pid")
        assert first == second and int(first) != os.getpid()
        await pool.aclose()
    asyncio.run(run())


def test_searches_at_once_use_one_worker_each_up_to_the_bound_and_wait_beyond_it() -> None:
    async def run() -> None:
        pool = pools(keep=2)
        began = time.monotonic()
        pids = await asyncio.gather(*(ask(pool, "slow", seconds=0.5) for _ in range(3)))
        elapsed = time.monotonic() - began
        assert len(set(pids)) == 2, "two workers, a worker serves one request at a time"
        assert elapsed >= 0.95, "the third search waited for a free slot, whoever asked"
        assert len(pool._idle) == 2
        await pool.aclose()
    asyncio.run(run())


def test_a_closed_pool_starts_no_worker_for_a_search() -> None:
    async def run() -> None:
        pool = pools()
        await pool.aclose()
        with pytest.raises(DependencyUnavailable):
            await ask(pool, "pid")
        assert not pool._workers
    asyncio.run(run())


@pytest.mark.parametrize("stop", ["cancel", "deadline"])
def test_a_cancelled_or_late_search_kills_its_worker_and_the_next_search_starts_another(stop) -> None:
    async def run() -> None:
        pool = pools()
        known = int(await ask(pool, "pid"))
        victim = next(iter(pool._workers)).process
        if stop == "cancel":
            task = asyncio.create_task(ask(pool, "block"))
            await asyncio.sleep(0.5)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            with pytest.raises(TimeoutError):
                async with asyncio.timeout(0.5):
                    await ask(pool, "block")
        assert victim.returncode is not None, "the worker that was searching is killed and joined"
        assert not pool._idle and not pool._workers
        assert int(await ask(pool, "pid")) != known
        await pool.aclose()
    start = time.monotonic()
    asyncio.run(run())
    assert time.monotonic() - start < 20


def test_a_worker_that_died_while_idle_is_not_handed_to_the_next_search() -> None:
    async def run() -> None:
        pool = pools()
        known = int(await ask(pool, "pid"))
        idle = pool._idle[0].process
        idle.kill()
        await idle.wait()
        assert int(await ask(pool, "pid")) != known
        await pool.aclose()
    asyncio.run(run())


def test_a_worker_that_exits_during_a_request_is_a_failure_and_is_not_reused() -> None:
    async def run() -> None:
        pool = pools()
        known = int(await ask(pool, "pid"))
        with pytest.raises(DependencyUnavailable):
            await ask(pool, "exit")
        assert not pool._idle and not pool._workers
        assert int(await ask(pool, "pid")) != known
        await pool.aclose()
    asyncio.run(run())


@pytest.mark.parametrize("op", ["big", "huge", "garbage", "list"])
def test_a_reply_that_is_too_large_or_unreadable_kills_the_worker(op) -> None:
    async def run() -> None:
        pool = pools()
        known = int(await ask(pool, "pid"))
        with pytest.raises(DependencyUnavailable):
            await ask(pool, op)
        assert not pool._idle and not pool._workers, "the framing is no longer trusted"
        assert int(await ask(pool, "pid")) != known
        await pool.aclose()
    asyncio.run(run())


def test_a_search_the_worker_reports_as_failed_is_unavailable_but_the_worker_stays() -> None:
    async def run() -> None:
        pool = pools()
        known = int(await ask(pool, "pid"))
        with pytest.raises(DependencyUnavailable, match="unavailable"):
            await ask(pool, "error")
        assert len(pool._idle) == 1
        assert int(await ask(pool, "pid")) == known
        await pool.aclose()
    asyncio.run(run())


def test_an_idle_worker_is_stopped_after_its_time_and_the_next_search_starts_another() -> None:
    async def run() -> None:
        pool = pools(idle_seconds=0.3)
        known = int(await ask(pool, "pid"))
        worker = next(iter(pool._workers)).process
        await asyncio.sleep(1.0)
        assert not pool._idle and worker.returncode is not None
        assert int(await ask(pool, "pid")) != known
        await pool.aclose()
    asyncio.run(run())


def test_closing_the_pool_stops_busy_and_idle_workers_and_refuses_more_searches() -> None:
    async def run() -> None:
        pool = pools()
        await ask(pool, "pid")
        busy = asyncio.create_task(ask(pool, "block"))
        await asyncio.sleep(0.5)
        processes = [worker.process for worker in pool._workers]
        assert len(processes) == 1, "the busy request took the idle worker"
        await pool.aclose()
        assert all(process.returncode is not None for process in processes)
        with pytest.raises(DependencyUnavailable):
            await busy
        with pytest.raises(DependencyUnavailable):
            await ask(pool, "pid")
        assert pool._closed and not pool._workers, "refused without starting a worker"
    asyncio.run(run())


def test_terminate_ends_the_workers_without_waiting_for_them_and_closes_the_pool() -> None:
    async def start() -> SearchWorkers:
        pool = pools()
        await ask(pool, "pid")
        return pool
    loop = asyncio.new_event_loop()
    try:
        pool = loop.run_until_complete(start())
        processes = [worker.process for worker in pool._workers]
        pool.terminate()

        async def joined() -> None:
            await asyncio.gather(*(process.wait() for process in processes))
        loop.run_until_complete(joined())
        assert all(process.returncode is not None for process in processes)
        with pytest.raises(DependencyUnavailable):
            loop.run_until_complete(ask(pool, "pid"))
        assert pool._closed
    finally:
        loop.close()


def test_a_long_lived_worker_does_not_inherit_credentials_or_python_injection(monkeypatch) -> None:
    for key in ("GROQ_API_KEY", "DATABASE_URL", "PYTHONSTARTUP", "PYTHONPATH"):
        monkeypatch.setenv(key, "SYNTHETIC_CREDENTIAL_CANARY")

    async def run() -> dict:
        pool = pools()
        try:
            return json.loads(await ask(pool, "env"))
        finally:
            await pool.aclose()
    assert not any(asyncio.run(run()).values())


def test_a_request_past_the_bound_is_refused_before_any_worker_starts() -> None:
    async def run() -> None:
        pool = pools()
        with pytest.raises(ValueError, match="exceeds bound"):
            await pool.exchange(b"x" * (MAX_REQUEST_BYTES + 1))
        assert not pool._workers
    asyncio.run(run())


def test_a_pool_needs_a_positive_keep_and_time() -> None:
    for options in ({"keep": 0}, {"idle_seconds": 0}):
        with pytest.raises(ValueError):
            SearchWorkers(command=COMMAND, **options)


# ---------------------------------------------------------------------------------- the child's serving loop


def test_the_serving_loop_answers_each_line_and_reports_a_failed_search_without_ending() -> None:
    def handler(payload: dict) -> str:
        if payload.get("fail"):
            raise RuntimeError("boom")
        return "ok " + payload["n"]
    requests = io.BytesIO(b'{"n": "1"}\n{"fail": true}\n{"n": "3"}\n')
    replies = io.BytesIO()
    serve(requests, replies, handler)
    assert [json.loads(line) for line in replies.getvalue().splitlines()] == [
        {"result": "ok 1"}, {"error": "RuntimeError"}, {"result": "ok 3"}]


@pytest.mark.parametrize("line", [b"x" * (MAX_REQUEST_BYTES + 5) + b"\n", b'{"n": "1"}'])
def test_the_serving_loop_ends_when_a_request_is_not_one_whole_line_within_the_bound(line) -> None:
    replies = io.BytesIO()
    with pytest.raises(SystemExit):
        serve(io.BytesIO(line), replies, lambda payload: "never")
    assert replies.getvalue() == b""


def test_the_worker_keeps_its_index_and_reranker_by_configuration_and_closes_them(monkeypatch) -> None:
    from evidence_agent.retrieval import rerank
    from evidence_agent.storage import qdrant

    closed: list[object] = []

    class Index:
        def __init__(self, **configuration) -> None:  # type: ignore[no-untyped-def]
            self.configuration = configuration

        def close(self) -> None:
            closed.append(self)

    class Ranker:
        def __init__(self, **configuration) -> None:  # type: ignore[no-untyped-def]
            self.configuration = configuration

    monkeypatch.setattr(qdrant, "QdrantIndex", Index)
    monkeypatch.setattr(rerank, "FastEmbedReranker", Ranker)
    caches = _Caches()
    one = caches.index({"url": "http://127.0.0.1:1", "collection_name": "a"})
    assert caches.index({"collection_name": "a", "url": "http://127.0.0.1:1"}) is one, "the same configuration"
    other = caches.index({"url": "http://127.0.0.1:1", "collection_name": "b"})
    assert other is not one
    ranker = caches.ranker({"enabled": True, "cache_dir": "x", "max_candidates": 20})
    assert caches.ranker({"enabled": True, "cache_dir": "x", "max_candidates": 20}) is ranker
    assert ranker.configuration["cache_dir"] == Path("x")  # type: ignore[attr-defined]
    caches.close()
    assert set(map(id, closed)) == {id(one), id(other)}
    assert caches.index({"url": "http://127.0.0.1:1", "collection_name": "a"}) is not one, "closed means gone"


def test_the_agent_tool_uses_the_pool_when_it_has_one_and_a_process_per_search_otherwise(monkeypatch) -> None:
    from types import SimpleNamespace

    from evidence_agent.agent import tools as agent_tools
    from evidence_agent.agent.tools import Tools

    calls: list[str] = []

    async def one_shot(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append("one-shot")
        raise DependencyUnavailable("stop here")

    class Pool:
        async def search(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            calls.append("pool")
            raise DependencyUnavailable("stop here")

    monkeypatch.setattr(agent_tools, "search", one_shot)
    ledger = SimpleNamespace(trace_id="t", principal=SimpleNamespace(principal_id="p"), case_id="c", question="",
                             search=object(), applicability=lambda: None, failures=[], tool_status={}, records={})
    store = SimpleNamespace(authorize=lambda: None, append=lambda *args, **kwargs: None)
    for workers, expected in ((Pool(), "pool"), (None, "one-shot")):
        calls.clear()
        tools = Tools(ledger, None, store, workers=workers)  # type: ignore[arg-type]
        asyncio.run(tools.execute("search_knowledge", json.dumps({"query": "reversal"})))
        assert calls == [expected]


def test_the_services_own_a_pool_in_the_persistent_mode_and_close_it() -> None:
    from evidence_agent.agent.services import AgentServices
    from evidence_agent.settings import Settings

    persistent = AgentServices(Path("."), None, None, None, None, Settings())  # type: ignore[arg-type]
    per_request = AgentServices(Path("."), None, None, None, None,  # type: ignore[arg-type]
                                Settings(search_worker_mode="per_request"))
    assert isinstance(persistent.workers, SearchWorkers) and per_request.workers is None
    assert persistent.workers.idle_seconds == Settings().search_worker_idle_seconds
    asyncio.run(persistent.aclose())
    assert persistent.workers._closed


def test_the_real_worker_answers_an_unusable_request_as_an_error_and_serves_the_next_one() -> None:
    from evidence_agent.agent.search_worker import SERVE_COMMAND

    async def run() -> None:
        pool = SearchWorkers(command=SERVE_COMMAND)
        try:
            for _ in range(2):  # no database in the request: the search fails, the worker stays and answers again
                with pytest.raises(DependencyUnavailable, match="unavailable"):
                    await pool.exchange(b"{}")
                assert len(pool._idle) == 1
            assert next(iter(pool._workers)).alive
        finally:
            await pool.aclose()
    asyncio.run(run())


def test_a_pool_closed_while_a_worker_starts_does_not_serve_the_search(monkeypatch) -> None:
    from evidence_agent.agent import search_worker

    original = search_worker._spawn
    started = asyncio.Event()

    async def slow_spawn(command):  # type: ignore[no-untyped-def]
        started.set()
        await asyncio.sleep(0.3)
        return await original(command)

    monkeypatch.setattr(search_worker, "_spawn", slow_spawn)

    async def run() -> None:
        pool = pools()
        search_task = asyncio.create_task(ask(pool, "pid"))
        await started.wait()
        await pool.aclose()
        with pytest.raises(DependencyUnavailable):
            await search_task
        assert not pool._workers and not pool._idle
    asyncio.run(run())


def test_stopping_a_worker_twice_at_once_joins_it_once_without_error() -> None:
    async def run() -> None:
        pool = pools()
        await ask(pool, "pid")
        worker = pool._idle[0]
        await asyncio.gather(pool._discard(worker), pool._discard(worker), pool._discard(worker))
        assert worker.process.returncode is not None
        await pool.aclose()
    asyncio.run(run())


@pytest.mark.filterwarnings("ignore::ResourceWarning", "ignore::pytest.PytestUnraisableExceptionWarning")  # let-go children
def test_a_pool_used_from_another_event_loop_starts_its_own_workers() -> None:
    pool = pools()
    first = int(asyncio.run(ask(pool, "pid")))
    second = int(asyncio.run(ask(pool, "pid")))
    assert first != second, "a worker of a finished loop is not handed to the next one"
    asyncio.run(pool.aclose())


def test_the_worker_forgets_the_oldest_configuration_past_its_bound(monkeypatch) -> None:
    from evidence_agent.retrieval import rerank
    from evidence_agent.storage import qdrant

    closed: list[str] = []

    class Index:
        def __init__(self, **configuration) -> None:  # type: ignore[no-untyped-def]
            self.name = configuration["collection_name"]

        def close(self) -> None:
            closed.append(self.name)

    class Ranker:
        def __init__(self, **configuration) -> None:  # type: ignore[no-untyped-def]
            self.configuration = configuration

    monkeypatch.setattr(qdrant, "QdrantIndex", Index)
    monkeypatch.setattr(rerank, "FastEmbedReranker", Ranker)
    caches = _Caches()
    ranker = caches.ranker({"enabled": True})
    for number in range(_Caches.MAX_ENTRIES + 1):
        caches.index({"collection_name": f"c{number}"})
    assert closed == ["c0"], "only the oldest index went"
    assert caches.ranker({"enabled": True}) is ranker, "a new index configuration does not reload the reranker"


def test_the_services_release_what_they_hold_even_when_the_workers_fail_to_stop() -> None:
    from evidence_agent.agent.services import AgentServices
    from evidence_agent.settings import Settings

    class Broken:
        terminated = False

        async def aclose(self) -> None:
            raise RuntimeError("could not stop")

        def terminate(self) -> None:
            Broken.terminated = True

    services = AgentServices(Path("."), None, None, None, None, Settings())  # type: ignore[arg-type]
    services.workers = Broken()  # type: ignore[assignment]
    with pytest.raises(RuntimeError, match="could not stop"):
        asyncio.run(services.aclose())
    assert Broken.terminated, "the services still closed, and asked the workers to end"
