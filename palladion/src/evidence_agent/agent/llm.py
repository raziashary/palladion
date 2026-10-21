"""Explicit Groq transport, schemas out and native tool-call messages back.

This layer never executes model-requested functions. AgentRuntime in loop.py owns
attempt budgets/call sequencing; Tools.execute in tools.py validates and dispatches
the four scoped read operations. Tool outputs return through that loop, not here.
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx

from evidence_agent.settings import Settings

PROVIDER_BASE_URL = "https://api.groq.com/openai/v1"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
DEFAULT_COMPLETION_CAP = 768
KEY_VARIABLE = re.compile(r"[A-Z][A-Z0-9_]{0,63}")


def checked_base_url(base_url: str | None) -> str:
    """The provider's address by default; otherwise an http loopback address (a counting proxy), never another host."""
    if base_url is None:
        return PROVIDER_BASE_URL
    try:
        parts = urlsplit(base_url)
        port = parts.port
    except ValueError as exc:
        raise ValueError("Model base URL is not a valid address") from exc
    if (parts.scheme != "http" or parts.hostname not in LOOPBACK_HOSTS or port is None or parts.username
            or parts.password or parts.query or parts.fragment or not parts.path.startswith("/")):
        raise ValueError("Model base URL must be an http loopback address with a port")
    return base_url.rstrip("/")


class ModelFailure(RuntimeError):
    def __init__(self, code: str, provider_code: str | None = None) -> None:
        self.code = code
        self.provider_code = provider_code
        super().__init__(code)


@dataclass(frozen=True)
class ModelTurn:
    message: dict[str, Any]
    usage: dict[str, int]


class LanguageModel(Protocol):
    async def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]],
                       *, final: bool = False,
                       before_send: Callable[[], None] | None = None) -> ModelTurn: ...


class GroqModel:
    """One invocation is one HTTP attempt. The caller owns all attempt accounting."""
    model = "qwen/qwen3.8-27b"
    allowed_models = ("qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b")

    def __init__(self, api_key: str, *, enabled: bool = False, timeout: float = 25,
                 model: str = "qwen/qwen3.8-27b", call_interval_seconds: float = 0,
                 temperature: float = 0, base_url: str | None = None,
                 completion_cap: int = DEFAULT_COMPLETION_CAP) -> None:
        if type(temperature) not in {int,float} or not math.isfinite(temperature) or not 0<=temperature<=1:
            raise ValueError("Temperature must be finite and between zero and one")
        if type(call_interval_seconds) not in {int, float} or not math.isfinite(call_interval_seconds) or not 0 <= call_interval_seconds <= 60:
            raise ValueError("Model call interval must be finite and between 0 and 60 seconds")
        if model not in self.allowed_models:
            raise ValueError("Unapproved Groq model")
        if type(completion_cap) is not int or not 64 <= completion_cap <= 4096:
            raise ValueError("Completion cap must be an integer between 64 and 4096")
        self.endpoint = checked_base_url(base_url) + "/chat/completions"
        self.completion_cap = completion_cap
        Settings(enable_live_llm=enabled).require_live_llm(api_key_present=bool(api_key))
        self.model = model
        self._api_key, self.timeout = api_key, timeout
        self.call_interval_seconds = float(call_interval_seconds)
        self.temperature = float(temperature)
        self._pacing_lock = Lock()
        self._next_dispatch = 0.0
        self.last_failure: dict[str, Any] | None = None
        self.last_rate_limits: dict[str, int | str] = {}

    @classmethod
    def from_environment(cls, variable: str, *, enabled: bool = False,
                         model: str = "qwen/qwen3.8-27b", call_interval_seconds: float = 0,
                         temperature: float = 0, base_url: str | None = None,
                         completion_cap: int = DEFAULT_COMPLETION_CAP, timeout: float = 25) -> GroqModel:
        """Take the key from one named environment variable, so no file copy of it is needed; never echoed."""
        if not enabled:
            raise PermissionError("Explicit model enablement required before reading credentials")
        if not KEY_VARIABLE.fullmatch(variable):
            raise ValueError("Key variable name is not a plain upper-case identifier")
        key = os.environ.get(variable, "")
        if not key or any(c.isspace() for c in key):
            raise PermissionError("Enabled command requires a literal key in the named environment variable")
        return cls(key, enabled=True, model=model, call_interval_seconds=call_interval_seconds,
                   temperature=temperature, base_url=base_url, completion_cap=completion_cap, timeout=timeout)

    @classmethod
    def from_env_file(cls, path: Path, *, enabled: bool = False,
                      model: str = "qwen/qwen3.8-27b", call_interval_seconds: float = 0,
                      temperature: float = 0, base_url: str | None = None,
                      completion_cap: int = DEFAULT_COMPLETION_CAP, timeout: float = 25) -> GroqModel:
        if not enabled:
            raise PermissionError("Explicit model enablement required before reading credentials")
        # Deliberately parse one literal key, without executing shell syntax or exporting it.
        key = ""
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            match = re.fullmatch(r"\s*(?:export\s+)?GROQ_API_KEY\s*=\s*(.*?)\s*", line)
            if match:
                key = match[1].strip().strip("\"'")
        if not key or any(c.isspace() for c in key):
            raise PermissionError("Enabled command requires a literal GROQ_API_KEY")
        return cls(key, enabled=True, model=model, call_interval_seconds=call_interval_seconds,
                   temperature=temperature, base_url=base_url, completion_cap=completion_cap, timeout=timeout)

    async def _pace(self) -> None:
        if not self.call_interval_seconds:
            return
        while True:
            # Reserve only a dispatch that is ready now. Cancelled waiters leave no
            # future queue slots; the lock is never held across an await or HTTP call.
            with self._pacing_lock:
                now = time.monotonic()
                delay = self._next_dispatch - now
                if delay <= 0:
                    self._next_dispatch = now + self.call_interval_seconds
                    return
            await asyncio.sleep(delay)

    async def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]],
                       *, final: bool = False,
                       before_send: Callable[[], None] | None = None) -> ModelTurn:
        self.last_rate_limits = {}
        payload: dict[str, Any] = {"model": self.model, "messages": messages,
            "temperature": self.temperature, "max_completion_tokens": self.completion_cap,
            "reasoning_effort": "none" if self.model == "qwen/qwen3.8-27b" else "low"}
        if final or not tools:
            payload["response_format"] = {"type": "json_object"}
        else:
            payload.update(tools=tools, tool_choice="auto",
                           parallel_tool_calls=self.model == "qwen/qwen3.8-27b")
        if len(json.dumps(payload, ensure_ascii=False).encode()) > 48 * 1024:
            raise ModelFailure("MODEL_CONTEXT_TOO_LARGE")
        await self._pace()
        if before_send is not None:
            before_send()  # Caller rechecks ACL/freshness after waiting, before HTTP.
        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False,
                                         follow_redirects=False) as client:
                async with client.stream("POST", self.endpoint,
                    headers={"Authorization": "Bearer " + self._api_key}, json=payload) as response:
                    # Groq request counters are DAILY; token counters are per MINUTE.
                    # Keep only documented bounded numeric/duration headers, never all headers.
                    for key in ("limit-requests", "remaining-requests", "limit-tokens", "remaining-tokens"):
                        value = response.headers.get("x-ratelimit-" + key, "")
                        if re.fullmatch(r"[0-9]{1,18}", value):
                            self.last_rate_limits[key] = int(value)
                    for key in ("reset-requests", "reset-tokens"):
                        value = response.headers.get("x-ratelimit-" + key, "")
                        if len(value) <= 64 and re.fullmatch(r"(?:[0-9]{1,9}(?:\.[0-9]{1,6})?(?:ms|s|m|h|d))+", value):
                            self.last_rate_limits[key] = value
                    retry = response.headers.get("retry-after", "")
                    if re.fullmatch(r"[0-9]{1,6}(?:\.[0-9]{1,3})?", retry):
                        self.last_rate_limits["retry-after"] = retry
                    if response.status_code != 200:
                        # Read only a bounded error body; never retain or expose provider prose.
                        error_raw = bytearray()
                        async for piece in response.aiter_bytes():
                            error_raw.extend(piece)
                            if len(error_raw) > 32768:
                                break
                        provider_code = None
                        quota_window = "UNKNOWN"
                        suggested_wait: float | None = None
                        quota_counts: dict[str, int] = {}
                        try:
                            error = json.loads(error_raw).get("error", {})
                            label = error.get("code") or error.get("type")
                            if isinstance(label, str) and re.fullmatch(r"[A-Za-z0-9_]{1,80}", label):
                                provider_code = label
                            message = str(error.get("message", "")).lower()
                            for needle, window in (("tokens per day", "TOKENS_DAILY"),
                                ("tokens per minute", "TOKENS_MINUTE"),
                                ("requests per day", "REQUESTS_DAILY"),
                                ("requests per minute", "REQUESTS_MINUTE")):
                                if needle in message:
                                    quota_window = window
                            if quota_window == "TOKENS_MINUTE":
                                if "output" in message:
                                    quota_window = "OUTPUT_TOKENS_MINUTE"
                                elif "input" in message:
                                    quota_window = "INPUT_TOKENS_MINUTE"
                            wait = re.search(r"try again in (?:(\d+)h)?(?:(\d+)m)?(\d+(?:\.\d+)?)s", message)
                            if wait:
                                suggested_wait = int(wait[1] or 0)*3600 + int(wait[2] or 0)*60 + float(wait[3])
                            for name in ("limit", "used", "requested"):
                                count = re.search(r"\b"+name+r"\s*:?\s*(\d+)\b", message)
                                if count:
                                    quota_counts[name] = int(count[1])
                        except (ValueError, AttributeError):
                            pass
                        retry_after = response.headers.get("retry-after", "")
                        self.last_failure = {"http_status": response.status_code,
                            "provider_code": provider_code, "quota_window": quota_window,
                            "quota_counts": quota_counts,
                            "retry_after_seconds": float(retry_after) if re.fullmatch(r"[0-9]{1,6}(?:\.[0-9]{1,3})?", retry_after) else suggested_wait}
                        raise ModelFailure("PROVIDER_HTTP_" + str(response.status_code), provider_code)
                    raw = bytearray()
                    async for piece in response.aiter_bytes():
                        raw.extend(piece)
                        if len(raw) > 256 * 1024:
                            raise ModelFailure("MODEL_RESPONSE_TOO_LARGE")
            data = json.loads(raw)
            message = data["choices"][0]["message"]
            if not isinstance(message, dict):
                raise ValueError
            usage = {key: value for key, value in data.get("usage", {}).items()
                     if key in {"prompt_tokens", "completion_tokens", "total_tokens"} and type(value) is int and value >= 0}
            return ModelTurn(message, usage)
        except (httpx.HTTPError, TimeoutError) as exc:
            raise ModelFailure("PROVIDER_UNAVAILABLE") from exc
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ModelFailure("MODEL_ENVELOPE_INVALID") from exc
