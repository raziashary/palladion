"""A counting, capping proxy between a third-party comparator and the model provider (BADR-0031, BR36).

A comparator (HippoRAG 2, GraphRAG, LightRAG) builds its own prompts and runs its own LLM client, so a call cap kept in
the benchmark's process cannot see it. The comparator runs in a subprocess whose only route to a model is this proxy on
127.0.0.1. The proxy holds the provider key (the comparator never receives it), refuses any model outside the approved
list, clamps the completion size, spaces the calls, counts every dispatch and every token, and stops dispatching once
the call or token cap is reached. A rate-limited call and a failed call are counted: they used a request.

Embeddings are served locally by an injected function, so no provider call is made for them and the comparator uses the
same pinned embedding model as the benchmark's own arms (protocol 3.1 item 4).

An agent arm (E1, E3, E4) sends tool definitions. They are accepted only when the run states a tool-call cap, every
tool call a reply requests is counted, and a request that offers tools is refused once the cap is reached (a request
without tools, such as a final answer, is still served within the other caps).

Records keep numbers and fixed codes only: never a prompt, a reply or a key. A refusal by the provider is kept as its
facts (limit window, the provider's Limit, Used and Requested figures, wait, error type and code), never its message
(BADR-0048). A run may also set a ceiling on the estimated size of a request; one over it is refused here, unsent
(BADR-0049), and every dispatch row keeps the request's size in characters so the estimate can be calibrated.
"""

from __future__ import annotations

import hmac
import json
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from benchmark.generator import (
    GenerationError,
    GenerationTransientError,
    Transport,
    TransportResponse,
    refusal_facts,
)

CHAT_PATH = "/v1/chat/completions"
EMBEDDINGS_PATH = "/v1/embeddings"
MODELS_PATH = "/v1/models"
MAX_REQUEST_BYTES = 4 * 1024 * 1024
MAX_EMBEDDING_INPUTS = 512
# Chat parameters a comparator may send. Anything else (tools, streaming, several choices) is refused, not dropped.
_ALLOWED_PARAMS = frozenset(
    {"model", "messages", "temperature", "top_p", "response_format", "max_tokens", "max_completion_tokens", "seed",
     "stop", "reasoning_effort", "n"}
)  # fmt: skip
# Accepted only when the run states a tool-call cap (agent arms); they are refused, not dropped, otherwise.
_TOOL_PARAMS = frozenset({"tools", "tool_choice", "parallel_tool_calls"})
_PASS_HEADERS = ("content-type", "retry-after")


class ProxyError(ValueError):
    """The proxy was set up in a way it refuses. The message holds no secret."""


@dataclass(frozen=True)
class ProxyLimits:
    """What a run may spend. Every value is the owner's to state; none has a default that spends."""

    max_calls: int
    max_tokens: int  # prompt plus completion tokens, as the provider reports them
    max_completion_tokens: int
    pace_seconds: float
    models: tuple[str, ...]
    max_tool_calls: int | None = None  # None: a request that carries tools is refused; a number allows them up to it
    max_request_tokens: int | None = None  # a request estimated over this is refused here, unsent (BADR-0049)

    def __post_init__(self) -> None:
        if self.max_calls < 0 or self.max_tokens < 0 or self.max_completion_tokens < 1 or self.pace_seconds < 0:
            raise ProxyError("limits must be non-negative, with a completion cap of at least 1")
        if self.max_tool_calls is not None and self.max_tool_calls < 0:
            raise ProxyError("the tool-call cap must be non-negative")
        if self.max_request_tokens is not None and self.max_request_tokens < 1:
            raise ProxyError("the request ceiling must be at least 1 token")
        if not self.models or any(not m for m in self.models):
            raise ProxyError("a proxy needs at least one approved model")


@dataclass(frozen=True)
class Refusal:
    status: int
    code: str


_DAILY_LIMIT = b"tokens per day"  # the provider's own wording for a per-day token limit (Groq: TPD)
# Refusals that are a limit stopping the run, the provider's day or the owner's cap, and so never an arm's failure.
QUOTA_REFUSALS = frozenset({"DAILY_LIMIT_REACHED", "BUDGET_EXHAUSTED", "TOOL_BUDGET_EXHAUSTED"})


_CHARS_PER_TOKEN = 4  # the request ceiling's estimate: an estimate, calibrated afterwards from the books' request_chars


def _request_chars(payload: Mapping[str, Any]) -> int:
    """The size of what a request sends to be read: its messages and its tool definitions, in characters."""
    return len(json.dumps([payload.get("messages", ""), payload.get("tools", "")], ensure_ascii=False))


def _estimate_tokens(payload: Mapping[str, Any]) -> int:
    """A deliberately high guess of the prompt size (three characters a token), used only to refuse before spending."""
    return len(json.dumps(payload.get("messages", ""), ensure_ascii=False)) // 3 + 1


class CountingProxy:
    """The decision and the books. HTTP is a thin layer over ``chat`` and ``embed`` (see ``ProxyServer``)."""

    def __init__(
        self,
        transport: Transport,
        limits: ProxyLimits,
        *,
        record_path: Path | None = None,
        embedder: Callable[[Sequence[str]], Sequence[Sequence[float]]] | None = None,
        embedding_model: str = "local-embedding",
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._transport = transport
        self.limits = limits
        self._record_path = record_path
        self._embedder = embedder
        self._embedding_model = embedding_model
        self._monotonic = monotonic
        self._sleep = sleep
        self._lock = threading.Lock()
        self._dispatch_lock = threading.Lock()  # one provider call at a time, so the caps are exact
        self._last_dispatch: float | None = None
        self._totals: dict[str, int] = dict.fromkeys(
            ("calls", "rate_limited", "errors", "refused", "quota_refused", "prompt_tokens", "completion_tokens",
             "estimated_tokens", "tool_calls", "embedding_requests", "embedding_inputs"), 0
        )  # fmt: skip
        self._sequence = 0
        self._daily_wall = False  # the provider said the day's tokens are used up, so no call can succeed now

    def __repr__(self) -> str:
        return "CountingProxy(<redacted>)"

    # -- books ---------------------------------------------------------------------------------

    def usage(self) -> dict[str, int]:
        with self._lock:
            return dict(self._totals)

    @property
    def spent_tokens(self) -> int:
        with self._lock:
            return self._totals["prompt_tokens"] + self._totals["completion_tokens"] + self._totals["estimated_tokens"]

    def _record(self, **fields: Any) -> None:
        if self._record_path is None:
            return
        with self._lock:
            self._sequence += 1
            row = {"sequence": self._sequence, "at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), **fields}
        with self._record_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    def _refuse(self, status: int, code: str, **fields: Any) -> Refusal:
        with self._lock:
            self._totals["refused"] += 1
            self._totals["quota_refused"] += code in QUOTA_REFUSALS
        self._record(outcome="REFUSED", code=code, http_status=status, **fields)
        return Refusal(status, code)

    # -- chat ----------------------------------------------------------------------------------

    def chat(self, raw: bytes) -> TransportResponse | Refusal:
        """Check, pace and dispatch one chat call. Returns the provider's answer or the reason for refusing."""
        if len(raw) > MAX_REQUEST_BYTES:
            return self._refuse(413, "REQUEST_TOO_LARGE")
        try:
            payload = json.loads(raw)
        except ValueError:
            return self._refuse(400, "NOT_JSON")
        if not isinstance(payload, dict):
            return self._refuse(400, "NOT_JSON")
        if payload.get("stream"):
            return self._refuse(400, "STREAMING_REFUSED")
        permitted = _ALLOWED_PARAMS if self.limits.max_tool_calls is None else _ALLOWED_PARAMS | _TOOL_PARAMS
        unknown = sorted(set(payload) - permitted - {"stream"})  # a client may say stream=false; it is never forwarded
        if unknown:
            return self._refuse(400, "PARAMETER_REFUSED")
        if payload.get("n", 1) != 1:
            return self._refuse(400, "PARAMETER_REFUSED")
        model = payload.get("model")
        if model not in self.limits.models:
            return self._refuse(403, "MODEL_NOT_APPROVED")
        if not isinstance(payload.get("messages"), list) or not payload["messages"]:
            return self._refuse(400, "NO_MESSAGES")
        ceiling = self.limits.max_request_tokens
        if ceiling is not None:
            chars = _request_chars(payload)
            estimated = chars // _CHARS_PER_TOKEN + 1
            if estimated > ceiling:
                return self._refuse(
                    413, "REQUEST_OVER_CEILING", model=str(model), request_chars=chars,
                    estimated_tokens=estimated, ceiling_tokens=ceiling,
                )  # fmt: skip
        cap = self.limits.max_completion_tokens
        asked = payload.get("max_completion_tokens", payload.get("max_tokens"))
        completion_cap = cap if not isinstance(asked, int) or isinstance(asked, bool) else max(1, min(asked, cap))
        outgoing = {k: v for k, v in payload.items() if k not in ("max_tokens", "n", "stream")}
        outgoing["max_completion_tokens"] = completion_cap
        with self._dispatch_lock:
            return self._dispatch(str(model), outgoing, completion_cap, offers_tools=bool(payload.get("tools")))

    def _dispatch(
        self, model: str, payload: Mapping[str, Any], completion_cap: int, *, offers_tools: bool
    ) -> TransportResponse | Refusal:
        estimate = _estimate_tokens(payload)
        chars = _request_chars(payload)
        with self._lock:
            calls = self._totals["calls"]
            spent = self._totals["prompt_tokens"] + self._totals["completion_tokens"] + self._totals["estimated_tokens"]
            walled = self._daily_wall
            tools_spent = (
                offers_tools
                and self.limits.max_tool_calls is not None
                and self._totals["tool_calls"] >= self.limits.max_tool_calls
            )
            if (
                walled
                or tools_spent
                or calls >= self.limits.max_calls
                or spent + estimate + completion_cap > self.limits.max_tokens
            ):
                over = True
            else:
                over = False
                self._totals["calls"] += 1  # reserved before the call, so nothing can slip past the cap
        if walled:
            return self._refuse(429, "DAILY_LIMIT_REACHED", model=model)
        if over:
            code = "TOOL_BUDGET_EXHAUSTED" if tools_spent else "BUDGET_EXHAUSTED"
            return self._refuse(403, code, model=model)
        if self.limits.pace_seconds and self._last_dispatch is not None:
            wait = self._last_dispatch + self.limits.pace_seconds - self._monotonic()
            if wait > 0:
                self._sleep(wait)
        self._last_dispatch = self._monotonic()
        began = self._monotonic()
        response: TransportResponse | None = None
        failure = ""
        try:
            response = self._transport.post(payload)
        except (GenerationError, GenerationTransientError) as exc:
            failure = exc.code
        except Exception:
            failure = "PROVIDER_UNAVAILABLE"
        latency_ms = (self._monotonic() - began) * 1000.0
        if response is None:
            # Whether the provider processed the prompt is unknown: the worst case is charged, shown as an estimate.
            with self._lock:
                self._totals["errors"] += 1
                self._totals["estimated_tokens"] += estimate + completion_cap
            self._record(
                outcome="ERROR", code=failure, model=model, latency_ms=latency_ms, http_status=None, request_chars=chars
            )
            return Refusal(502, failure)
        prompt, completion = _usage(response)
        requested_tools = _tool_calls(response) if response.status == 200 else 0
        with self._lock:
            if response.status == 429:
                self._totals["rate_limited"] += 1
                if _DAILY_LIMIT in response.body:
                    self._daily_wall = True  # every later call would be refused too and would use a call
            elif response.status != 200:
                self._totals["errors"] += 1
            self._totals["tool_calls"] += requested_tools
            if response.status == 200:
                # A reply that omits its usage is charged at the worst case (the prompt estimate and the full
                # completion cap), shown apart from the provider's own numbers. A refusal (429, other) spent nothing.
                self._totals["prompt_tokens"] += prompt if prompt is not None else 0
                self._totals["completion_tokens"] += completion if completion is not None else 0
                self._totals["estimated_tokens"] += (estimate if prompt is None else 0) + (
                    completion_cap if completion is None else 0
                )
        outcome = "OK" if response.status == 200 else ("RATE_LIMITED" if response.status == 429 else "ERROR")
        facts = {} if response.status == 200 else {"refusal": refusal_facts(response.headers, response.body)}
        self._record(
            outcome=outcome, model=model, http_status=response.status, prompt_tokens=prompt,
            completion_tokens=completion, latency_ms=latency_ms, tool_calls=requested_tools,
            request_chars=chars, **facts,
        )  # fmt: skip
        return response

    # -- embeddings ----------------------------------------------------------------------------

    def embed(self, raw: bytes) -> TransportResponse | Refusal:
        """Answer an embeddings call locally. No provider is called and no key is involved."""
        if self._embedder is None:
            return self._refuse(404, "EMBEDDINGS_NOT_AVAILABLE")
        if len(raw) > MAX_REQUEST_BYTES:
            return self._refuse(413, "REQUEST_TOO_LARGE")
        try:
            payload = json.loads(raw)
            inputs = payload["input"]
        except (ValueError, KeyError, TypeError):
            return self._refuse(400, "NOT_JSON")
        texts = [inputs] if isinstance(inputs, str) else inputs
        if not isinstance(texts, list) or not texts or not all(isinstance(t, str) for t in texts):
            return self._refuse(400, "BAD_INPUT")
        if len(texts) > MAX_EMBEDDING_INPUTS:
            return self._refuse(413, "TOO_MANY_INPUTS")
        vectors = self._embedder(texts)
        if len(vectors) != len(texts):
            return self._refuse(502, "EMBEDDER_MISMATCH")
        words = sum(len(t.split()) for t in texts)
        with self._lock:
            self._totals["embedding_requests"] += 1
            self._totals["embedding_inputs"] += len(texts)
        self._record(outcome="EMBEDDING", inputs=len(texts), http_status=200)
        body = {
            "object": "list",
            "model": self._embedding_model,
            "data": [
                {"object": "embedding", "index": i, "embedding": [float(x) for x in v]} for i, v in enumerate(vectors)
            ],
            "usage": {"prompt_tokens": words, "total_tokens": words},
        }  # fmt: skip
        return TransportResponse(200, {"content-type": "application/json"}, json.dumps(body).encode())


def _tool_calls(response: TransportResponse) -> int:
    """How many tool calls a reply asks for (the single choice); an unreadable reply asks for none."""
    try:
        calls = json.loads(response.body)["choices"][0]["message"].get("tool_calls") or []
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        return 0
    return len(calls) if isinstance(calls, list) else 0


def _usage(response: TransportResponse) -> tuple[int | None, int | None]:
    try:
        usage = json.loads(response.body).get("usage", {})
    except (ValueError, AttributeError, RecursionError):
        return None, None
    prompt, completion = usage.get("prompt_tokens"), usage.get("completion_tokens")
    return (
        prompt if type(prompt) is int and prompt >= 0 else None,
        completion if type(completion) is int and completion >= 0 else None,
    )


# --------------------------------------------------------------------------- the HTTP layer


class ProxyServer:
    """Serve a ``CountingProxy`` on 127.0.0.1 behind a per-run bearer token, so no other process can spend the cap."""

    def __init__(self, proxy: CountingProxy, *, token: str) -> None:
        if len(token) < 16:
            raise ProxyError("the proxy token must be at least 16 characters")
        self._proxy = proxy
        self._token = token
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        if self._server is None:
            raise ProxyError("the proxy is not running")
        return f"http://127.0.0.1:{self._server.server_address[1]}/v1"

    def usage(self) -> dict[str, int]:
        return self._proxy.usage()

    def environment(self, *, llm_model: str, embedding_model: str) -> dict[str, str]:
        """What a comparator's process needs to reach this proxy: an OpenAI-style base URL and the per-run token."""
        if llm_model not in self._proxy.limits.models:
            raise ProxyError("the comparator's model is not on the approved list")
        return {
            "OPENAI_BASE_URL": self.base_url,
            "OPENAI_API_KEY": self._token,
            "COMPARATOR_LLM_MODEL": llm_model,
            "COMPARATOR_EMBED_MODEL": embedding_model,
        }

    def start(self) -> None:
        proxy, token = self._proxy, self._token
        models = list(proxy.limits.models)

        class Handler(BaseHTTPRequestHandler):
            timeout = 600

            def log_message(self, format: str, *args: Any) -> None:
                return None  # nothing the request carried is written anywhere

            def _send(self, status: int, body: bytes, headers: Mapping[str, str] | None = None) -> None:
                self.send_response(status)
                sent = {"content-type": "application/json", "content-length": str(len(body)), **(headers or {})}
                for name, value in sent.items():
                    self.send_header(name, value)
                self.end_headers()
                self.wfile.write(body)

            def _authorized(self) -> bool:
                header = self.headers.get("Authorization", "")
                return hmac.compare_digest(header.encode(), f"Bearer {token}".encode())

            def _fail(self, refusal: Refusal) -> None:
                self._send(
                    refusal.status, json.dumps({"error": {"message": refusal.code, "code": refusal.code}}).encode()
                )

            def do_GET(self) -> None:
                if not self._authorized():
                    return self._fail(Refusal(401, "UNAUTHORIZED"))
                if self.path == MODELS_PATH:
                    data = {"object": "list", "data": [{"id": m, "object": "model"} for m in models]}
                    return self._send(200, json.dumps(data).encode())
                return self._fail(Refusal(404, "NOT_FOUND"))

            def do_POST(self) -> None:
                if not self._authorized():
                    return self._fail(Refusal(401, "UNAUTHORIZED"))
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    length = -1
                if not 0 <= length <= MAX_REQUEST_BYTES:
                    return self._fail(Refusal(413, "REQUEST_TOO_LARGE"))
                raw = self.rfile.read(length)
                if self.path == CHAT_PATH:
                    result = proxy.chat(raw)
                elif self.path == EMBEDDINGS_PATH:
                    result = proxy.embed(raw)
                else:
                    return self._fail(Refusal(404, "NOT_FOUND"))
                if isinstance(result, Refusal):
                    return self._fail(result)
                passed = {k: v for k, v in result.headers.items() if k in _PASS_HEADERS or k.startswith("x-ratelimit-")}
                passed.pop("content-type", None)
                self._send(result.status, result.body, passed)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, name="llm-proxy", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def __enter__(self) -> ProxyServer:
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()
