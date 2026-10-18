"""Real local processes for strict cancellation/IPC; no provider or live data."""
import asyncio
import json
import sys
import time

import pytest

from evidence_agent.agent.search_worker import _run
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
