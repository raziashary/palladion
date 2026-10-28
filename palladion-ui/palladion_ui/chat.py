"""One chat turn, as a stream of events for the browser."""
from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from palladion_ui.personas import Directory, Persona
from palladion_ui.settings import Settings
from palladion_ui.stack import Stack
from palladion_ui.store import Store
from palladion_ui.streaming import Progress, reveal, sse
from palladion_ui.upstream import Upstream, UpstreamError


@dataclass
class Context:
    settings: Settings
    directory: Directory
    store: Store
    upstream: Upstream
    stack: Stack


async def _timeline(ctx: Context, token: str, case_id: str) -> list[dict[str, Any]]:
    try:
        events = await ctx.upstream.call("GET", f"/v1/cases/{case_id}/timeline", token, timeout=5)
    except UpstreamError:
        return []  # progress is a courtesy; its absence must never fail the answer
    return events if isinstance(events, list) else []


async def _agent_turn(ctx: Context, persona: Persona, case_id: str, session_id: str, query: str,
                      model: str, started: float) -> AsyncIterator[str]:
    token = ctx.directory.token(persona.id)
    progress = Progress()
    progress.prime(await _timeline(ctx, token, case_id))
    yield sse("progress", {"id": "sent", "kind": "CLIENT", "label": f"Sent to {model}", "detail": None, "at": None})
    call = asyncio.create_task(ctx.upstream.call(
        "POST", f"/v1/cases/{case_id}/messages", token, json={"query": query, "session_id": session_id},
        timeout=ctx.settings.request_timeout + 30))
    try:
        while True:
            finished, _ = await asyncio.wait({call}, timeout=ctx.settings.poll_interval)
            if finished:
                break
            for step in progress.fresh(await _timeline(ctx, token, case_id)):
                yield sse("progress", step)
            yield sse("tick", {"elapsed": round(time.monotonic() - started, 1)})
        response = call.result()  # raises UpstreamError for a refused or failed request
    finally:
        if not call.done():
            call.cancel()
    for step in progress.fresh(await _timeline(ctx, token, case_id)):
        yield sse("progress", step)
    elapsed = round(time.monotonic() - started, 1)
    ctx.store.append_message(persona.id, session_id, {"role": "assistant", "kind": "agent", "response": response,
                                                       "model": model, "elapsed": elapsed})
    async for event in reveal(response, ctx.settings.stream_delay):
        yield event


async def _search_turn(ctx: Context, persona: Persona, case_id: str, session_id: str, query: str,
                       started: float) -> AsyncIterator[str]:
    token = ctx.directory.token(persona.id)
    result = await ctx.upstream.call("POST", "/search", token, timeout=90,
                                     json={"case_id": case_id, "query": query, "mode": "reranked", "limit": 8})
    ctx.store.append_message(persona.id, session_id, {"role": "assistant", "kind": "search", "result": result,
                                                       "elapsed": round(time.monotonic() - started, 1)})
    yield sse("search", result)


async def stream_chat(ctx: Context, persona: Persona, case_id: str, session_id: str,
                      query: str) -> AsyncIterator[str]:
    runtime = await ctx.stack.status()
    model = runtime["model"] if runtime["state"] == "ready" else None
    started = time.monotonic()
    yield sse("start", {"session_id": session_id, "case_id": case_id, "persona": persona.id,
                        "mode": "agent" if model else "search", "model": model})
    ctx.store.append_message(persona.id, session_id, {"role": "user", "text": query})
    try:
        turn = (_agent_turn(ctx, persona, case_id, session_id, query, model, started) if model
                else _search_turn(ctx, persona, case_id, session_id, query, started))
        async for event in turn:
            yield event
    except UpstreamError as error:
        message = error.message
        if error.status == 503 and model:
            message = "The agent is not available right now. Pick a model again from the model menu."
        ctx.store.append_message(persona.id, session_id, {"role": "assistant", "kind": "error",
                                                           "error": {"code": error.code, "message": message}})
        yield sse("error", {"code": error.code, "status": error.status, "message": message})
    yield sse("done", {"elapsed": round(time.monotonic() - started, 1)})
