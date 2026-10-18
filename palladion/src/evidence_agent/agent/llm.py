"""Explicit Groq transport, schemas out and native tool-call messages back.

This layer never executes model-requested functions. AgentRuntime in loop.py owns
attempt budgets/call sequencing; Tools.execute in tools.py validates and dispatches
the four scoped read operations. Tool outputs return through that loop, not here.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import httpx

from evidence_agent.settings import Settings


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
                       *, final: bool = False) -> ModelTurn: ...


class GroqModel:
    """One invocation is one HTTP attempt. The caller owns all attempt accounting."""
    model = "qwen/qwen3.8-27b"
    allowed_models = ("qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b")

    def __init__(self, api_key: str, *, enabled: bool = False, timeout: float = 25,
                 model: str = "qwen/qwen3.8-27b") -> None:
        if model not in self.allowed_models:
            raise ValueError("Unapproved Groq model")
        Settings(enable_live_llm=enabled).require_live_llm(api_key_present=bool(api_key))
        self.model = model
        self._api_key, self.timeout = api_key, timeout
        self.last_failure: dict[str, Any] | None = None
        self.last_rate_limits: dict[str, int | str] = {}

    @classmethod
    def from_env_file(cls, path: Path, *, enabled: bool = False,
                      model: str = "qwen/qwen3.8-27b") -> GroqModel:
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
        return cls(key, enabled=True, model=model)

    async def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]],
                       *, final: bool = False) -> ModelTurn:
        self.last_rate_limits = {}
        payload: dict[str, Any] = {"model": self.model, "messages": messages,
            "temperature": 0, "max_completion_tokens": 768,
            "reasoning_effort": "none" if self.model == "qwen/qwen3.8-27b" else "low"}
        if final or not tools:
            payload["response_format"] = {"type": "json_object"}
        else:
            payload.update(tools=tools, tool_choice="auto",
                           parallel_tool_calls=self.model == "qwen/qwen3.8-27b")
        if len(json.dumps(payload, ensure_ascii=False).encode()) > 48 * 1024:
            raise ModelFailure("MODEL_CONTEXT_TOO_LARGE")
        try:
            async with httpx.AsyncClient(timeout=self.timeout, trust_env=False,
                                         follow_redirects=False) as client:
                async with client.stream("POST", "https://api.groq.com/openai/v1/chat/completions",
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
