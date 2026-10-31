"""The counting LLM proxy: nothing a comparator does can spend past the caps (B06-T00.02, BR36)."""

from __future__ import annotations

import json
import re
import threading
import urllib.error
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from benchmark.generator import (
    GenerationError,
    GenerationTransientError,
    TransportResponse,
    _quota_window,
    refusal_facts,
)
from benchmark.llm_proxy import (
    CHAT_PATH,
    EMBEDDINGS_PATH,
    CountingProxy,
    ProxyError,
    ProxyLimits,
    ProxyServer,
    Refusal,
)

MODEL = "qwen/qwen3.8-27b"
OTHER = "openai/gpt-oss-120b"
TOKEN = "t" * 24
KEY = "gsk_" + "k" * 30


def reply(
    prompt: int = 100, completion: int = 20, *, status: int = 200, headers: Mapping[str, str] | None = None
) -> Any:
    usage = {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": prompt + completion}
    body = {"model": MODEL, "choices": [{"message": {"content": "ok"}}], "usage": usage}
    return TransportResponse(status, dict(headers or {}), json.dumps(body).encode())


class Fake:
    """A transport that answers from a script and remembers every payload it was given."""

    def __init__(self, *responses: Any) -> None:
        self.script = list(responses) or [reply()]
        self.payloads: list[Mapping[str, Any]] = []

    def post(self, payload: Mapping[str, Any]) -> TransportResponse:
        self.payloads.append(payload)
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, Exception):
            raise item
        return item  # type: ignore[no-any-return]


def limits(**over: Any) -> ProxyLimits:
    base: dict[str, Any] = {"max_calls": 3, "max_tokens": 10_000, "max_completion_tokens": 700, "pace_seconds": 0.0,
                            "models": (MODEL, OTHER)}  # fmt: skip
    return ProxyLimits(**{**base, **over})


def body(**over: Any) -> bytes:
    base: dict[str, Any] = {"model": MODEL, "messages": [{"role": "user", "content": "hello"}]}
    return json.dumps({**base, **over}).encode()


def make(transport: Fake, tmp_path: Path, **over: Any) -> CountingProxy:
    sleeps = over.pop("sleeps", [])
    return CountingProxy(transport, limits(**over), record_path=tmp_path / "proxy.jsonl", sleep=sleeps.append)


# --------------------------------------------------------------------------- the caps


def test_calls_stop_at_the_cap_and_a_refused_call_never_reaches_the_provider(tmp_path: Path) -> None:
    transport = Fake()
    proxy = make(transport, tmp_path, max_calls=2)
    results = [proxy.chat(body()) for _ in range(5)]
    assert [isinstance(r, TransportResponse) for r in results] == [True, True, False, False, False]
    assert [r.code for r in results[2:] if isinstance(r, Refusal)] == ["BUDGET_EXHAUSTED"] * 3
    assert len(transport.payloads) == 2 and proxy.usage()["calls"] == 2 and proxy.usage()["refused"] == 3


def test_a_rate_limited_and_a_failed_call_each_use_a_call(tmp_path: Path) -> None:
    transport = Fake(reply(status=429, headers={"retry-after": "7"}), GenerationTransientError("PROVIDER_UNAVAILABLE"),
                     GenerationError("MALFORMED_RESPONSE"), reply())  # fmt: skip
    proxy = make(transport, tmp_path, max_calls=3)
    first, second, third = proxy.chat(body()), proxy.chat(body()), proxy.chat(body())
    assert isinstance(first, TransportResponse) and first.status == 429
    assert isinstance(second, Refusal) and second.code == "PROVIDER_UNAVAILABLE"
    assert isinstance(third, Refusal) and third.code == "MALFORMED_RESPONSE"
    assert isinstance(proxy.chat(body()), Refusal), "three attempts already used the whole cap"
    assert proxy.usage()["calls"] == 3 and proxy.usage()["rate_limited"] == 1 and proxy.usage()["errors"] == 2
    assert len(transport.payloads) == 3


def test_tokens_stop_at_the_cap_using_what_the_provider_reported(tmp_path: Path) -> None:
    transport = Fake(reply(4000, 500))
    proxy = make(transport, tmp_path, max_calls=50, max_tokens=9000)
    assert isinstance(proxy.chat(body()), TransportResponse)
    assert proxy.spent_tokens == 4500
    assert isinstance(proxy.chat(body()), TransportResponse), "4500 spent, and this call can still fit under 9000"
    assert proxy.spent_tokens == 9000
    assert isinstance(proxy.chat(body()), Refusal), "the next call could not fit and is refused"
    assert len(transport.payloads) == 2


def test_a_call_that_could_overrun_the_token_cap_is_refused_before_it_is_made(tmp_path: Path) -> None:
    transport = Fake()
    proxy = make(transport, tmp_path, max_tokens=500)  # a 700-token completion alone does not fit
    result = proxy.chat(body())
    assert isinstance(result, Refusal) and result.code == "BUDGET_EXHAUSTED" and transport.payloads == []
    assert proxy.usage()["calls"] == 0, "a refused call does not use a call"


def test_a_missing_usage_is_charged_at_the_worst_case_never_as_free(tmp_path: Path) -> None:
    silent = TransportResponse(200, {}, json.dumps({"choices": [{"message": {"content": "x"}}]}).encode())
    proxy = make(Fake(silent), tmp_path)
    assert isinstance(proxy.chat(body()), TransportResponse)
    usage = proxy.usage()
    assert usage["prompt_tokens"] == 0 and usage["completion_tokens"] == 0, "the provider reported nothing"
    assert usage["estimated_tokens"] >= 700, "the full completion cap is charged, and shown apart from reported tokens"
    assert proxy.spent_tokens == usage["estimated_tokens"]


def test_a_provider_refusal_spends_no_tokens_and_a_lost_connection_is_charged_at_the_worst_case(tmp_path: Path) -> None:
    limited = TransportResponse(429, {}, json.dumps({"error": {"message": "slow down"}}).encode())
    proxy = make(Fake(limited), tmp_path)
    assert isinstance(proxy.chat(body()), TransportResponse)
    assert proxy.usage()["rate_limited"] == 1 and proxy.spent_tokens == 0

    lost = make(Fake(ConnectionError("down")), tmp_path)
    assert isinstance(lost.chat(body()), Refusal)
    assert lost.usage()["errors"] == 1 and lost.spent_tokens >= 700


def test_every_row_of_the_book_carries_the_time_of_the_call(tmp_path: Path) -> None:
    proxy = make(Fake(), tmp_path)
    proxy.chat(body())
    rows = [json.loads(line) for line in (tmp_path / "proxy.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows and all(re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", r["at"]) for r in rows)


def test_concurrent_callers_cannot_slip_past_the_call_cap(tmp_path: Path) -> None:
    transport = Fake()
    proxy = make(transport, tmp_path, max_calls=5)
    results: list[Any] = []
    lock = threading.Lock()

    def worker() -> None:
        outcome = proxy.chat(body())
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(isinstance(r, TransportResponse) for r in results) == 5 and len(transport.payloads) == 5


# --------------------------------------------------------------------------- what may be asked


def test_a_model_outside_the_approved_list_is_refused(tmp_path: Path) -> None:
    transport = Fake()
    proxy = make(transport, tmp_path)
    for model in ("gpt-4o", "", None, "openai/gpt-oss-20b"):
        result = proxy.chat(body(model=model))
        assert isinstance(result, Refusal) and result.code == "MODEL_NOT_APPROVED" and result.status == 403
    assert transport.payloads == [] and isinstance(proxy.chat(body(model=OTHER)), TransportResponse)


@pytest.mark.parametrize(
    ("extra", "code"),
    [({"stream": True}, "STREAMING_REFUSED"), ({"tools": [{}]}, "PARAMETER_REFUSED"), ({"n": 2}, "PARAMETER_REFUSED"),
     ({"logprobs": True}, "PARAMETER_REFUSED"), ({"messages": []}, "NO_MESSAGES")],
)  # fmt: skip
def test_streaming_tools_and_extra_choices_are_refused_not_ignored(
    tmp_path: Path, extra: dict[str, Any], code: str
) -> None:
    transport = Fake()
    result = make(transport, tmp_path).chat(body(**extra))
    assert isinstance(result, Refusal) and result.code == code and transport.payloads == []


@pytest.mark.parametrize("raw", [b"not json", b"[]", b'"x"'])
def test_a_body_that_is_not_a_json_object_is_refused(tmp_path: Path, raw: bytes) -> None:
    result = make(Fake(), tmp_path).chat(raw)
    assert isinstance(result, Refusal) and result.code == "NOT_JSON"


def test_an_oversized_request_is_refused(tmp_path: Path) -> None:
    result = make(Fake(), tmp_path).chat(b" " * (5 * 1024 * 1024))
    assert isinstance(result, Refusal) and result.code == "REQUEST_TOO_LARGE"


@pytest.mark.parametrize(
    ("asked", "sent"),
    [({}, 700), ({"max_tokens": 5000}, 700), ({"max_completion_tokens": 5000}, 700), ({"max_tokens": 50}, 50),
     ({"max_completion_tokens": 0}, 1), ({"max_tokens": True}, 700)],
)  # fmt: skip
def test_the_completion_size_is_clamped_and_sent_in_one_field(tmp_path: Path, asked: dict[str, Any], sent: int) -> None:
    transport = Fake()
    assert isinstance(make(transport, tmp_path).chat(body(**asked)), TransportResponse)
    (payload,) = transport.payloads
    assert payload["max_completion_tokens"] == sent and "max_tokens" not in payload


# --------------------------------------------------------------------------- pace


def test_calls_are_spaced_by_the_pace_and_the_first_does_not_wait(tmp_path: Path) -> None:
    sleeps: list[float] = []
    clock = iter(float(i) for i in range(0, 1000, 1))
    proxy = CountingProxy(
        Fake(), limits(pace_seconds=25.0), record_path=None, monotonic=lambda: next(clock), sleep=sleeps.append
    )
    for _ in range(3):
        proxy.chat(body())
    assert len(sleeps) == 2 and all(0 < s <= 25.0 for s in sleeps)


# --------------------------------------------------------------------------- what is written


def test_records_hold_numbers_and_codes_and_never_a_prompt_a_reply_or_a_key(tmp_path: Path) -> None:
    secret_prompt = "SECRET-PROMPT-CANARY"
    transport = Fake(reply())
    proxy = CountingProxy(transport, limits(), record_path=tmp_path / "proxy.jsonl")
    proxy.chat(body(messages=[{"role": "user", "content": secret_prompt}]))
    proxy.chat(body(model="nope"))
    text = (tmp_path / "proxy.jsonl").read_text(encoding="utf-8")
    assert secret_prompt not in text and KEY not in text and '"ok"' not in text
    rows = [json.loads(line) for line in text.splitlines()]
    assert [r["outcome"] for r in rows] == ["OK", "REFUSED"] and [r["sequence"] for r in rows] == [1, 2]
    assert rows[0]["prompt_tokens"] == 100 and rows[1]["code"] == "MODEL_NOT_APPROVED"


def test_the_proxy_does_not_show_its_internals_when_printed() -> None:
    assert "redacted" in repr(CountingProxy(Fake(), limits()))


def test_limits_that_cannot_spend_sensibly_are_refused() -> None:
    for bad in (
        {"max_calls": -1},
        {"max_tokens": -1},
        {"max_completion_tokens": 0},
        {"pace_seconds": -1.0},
        {"models": ()},
    ):
        with pytest.raises(ProxyError):
            limits(**bad)


# --------------------------------------------------------------------------- embeddings


def embedder(texts: Any) -> list[list[float]]:
    return [[float(len(t)), 1.0] for t in texts]


def test_embeddings_are_served_locally_and_use_no_provider_call(tmp_path: Path) -> None:
    transport = Fake()
    proxy = CountingProxy(transport, limits(max_calls=0), embedder=embedder)
    result = proxy.embed(json.dumps({"input": ["ab", "abcd"], "model": "x"}).encode())
    assert isinstance(result, TransportResponse) and result.status == 200
    data = json.loads(result.body)["data"]
    assert [d["index"] for d in data] == [0, 1] and data[1]["embedding"] == [4.0, 1.0]
    assert transport.payloads == [] and proxy.usage()["embedding_inputs"] == 2 and proxy.usage()["calls"] == 0


@pytest.mark.parametrize("raw", [b"x", b"{}", b'{"input": []}', b'{"input": [1]}', b'{"input": 5}'])
def test_a_bad_embeddings_request_is_refused(raw: bytes) -> None:
    result = CountingProxy(Fake(), limits(), embedder=embedder).embed(raw)
    assert isinstance(result, Refusal) and result.status == 400


def test_embeddings_without_an_embedder_and_with_too_many_inputs_are_refused() -> None:
    assert isinstance(CountingProxy(Fake(), limits()).embed(b'{"input": "a"}'), Refusal)
    many = json.dumps({"input": ["a"] * 513}).encode()
    result = CountingProxy(Fake(), limits(), embedder=embedder).embed(many)
    assert isinstance(result, Refusal) and result.code == "TOO_MANY_INPUTS"


# --------------------------------------------------------------------------- over real HTTP


def call(url: str, path: str, data: bytes | None, token: str | None) -> tuple[int, dict[str, Any], dict[str, str]]:
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        url + path, data=data, headers=headers, method="POST" if data is not None else "GET"
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read()), {k.lower(): v for k, v in response.headers.items()}
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read()), {k.lower(): v for k, v in exc.headers.items()}


def test_over_http_the_token_is_required_and_the_caps_hold(tmp_path: Path) -> None:
    transport = Fake(reply(headers={"x-ratelimit-remaining-tokens": "5000", "set-cookie": "no", "retry-after": "3"}))
    proxy = make(transport, tmp_path, max_calls=1)
    with ProxyServer(proxy, token=TOKEN) as server:
        url = server.base_url
        assert call(url, "/chat/completions", body(), None)[0] == 401
        assert call(url, "/chat/completions", body(), "wrong" * 5)[0] == 401
        assert transport.payloads == []
        status, answer, headers = call(url, "/chat/completions", body(), TOKEN)
        assert status == 200 and answer["usage"]["prompt_tokens"] == 100
        assert headers["x-ratelimit-remaining-tokens"] == "5000" and "set-cookie" not in headers
        status, refused, _ = call(url, "/chat/completions", body(), TOKEN)
        assert status == 403 and refused["error"]["code"] == "BUDGET_EXHAUSTED"
        listed = call(url, "/models", None, TOKEN)
        assert listed[0] == 200 and [m["id"] for m in listed[1]["data"]] == [MODEL, OTHER]
        assert call(url, "/nowhere", b"{}", TOKEN)[0] == 404
    assert len(transport.payloads) == 1


def test_over_http_a_rate_limit_is_passed_on_so_the_caller_sees_it_and_it_is_counted(tmp_path: Path) -> None:
    proxy = make(Fake(reply(status=429, headers={"retry-after": "9"})), tmp_path, max_calls=2)
    with ProxyServer(proxy, token=TOKEN) as server:
        status, _, headers = call(server.base_url, "/chat/completions", body(), TOKEN)
        assert status == 429 and headers["retry-after"] == "9"
    assert proxy.usage()["rate_limited"] == 1 and proxy.usage()["calls"] == 1


def test_over_http_embeddings_work_and_the_server_stops_cleanly(tmp_path: Path) -> None:
    proxy = CountingProxy(Fake(), limits(), embedder=embedder)
    server = ProxyServer(proxy, token=TOKEN)
    with pytest.raises(ProxyError):
        _ = server.base_url
    server.start()
    status, answer, _ = call(server.base_url, "/embeddings", json.dumps({"input": "abc"}).encode(), TOKEN)
    assert status == 200 and answer["data"][0]["embedding"] == [3.0, 1.0]
    server.stop()
    with pytest.raises(ProxyError):
        _ = server.base_url


def test_a_short_token_is_refused() -> None:
    with pytest.raises(ProxyError):
        ProxyServer(CountingProxy(Fake(), limits()), token="short")


def test_the_paths_a_comparator_uses_are_the_openai_ones() -> None:
    assert (CHAT_PATH, EMBEDDINGS_PATH) == ("/v1/chat/completions", "/v1/embeddings")


def test_a_daily_token_limit_stops_the_run_instead_of_spending_calls_on_refusals(tmp_path: Path) -> None:
    daily = TransportResponse(
        429,
        {},
        json.dumps({"error": {"message": "Rate limit reached ... on tokens per day (TPD): Limit 200000"}}).encode(),
    )
    minute = TransportResponse(429, {}, json.dumps({"error": {"message": "on tokens per minute (TPM)"}}).encode())
    transport = Fake(minute, daily, reply())
    proxy = make(transport, tmp_path, max_calls=10)
    assert isinstance(proxy.chat(body()), TransportResponse), "a per-minute limit is passed on and the run goes on"
    assert proxy.usage()["calls"] == 1
    assert isinstance(proxy.chat(body()), TransportResponse)  # the daily limit is passed on once
    refused = proxy.chat(body())
    assert isinstance(refused, Refusal) and refused.code == "DAILY_LIMIT_REACHED"
    assert proxy.usage()["calls"] == 2 and len(transport.payloads) == 2, "no further call is made or counted"


# --------------------------------------------------------------------------- tools for agent arms


def tool_reply(calls: int) -> TransportResponse:
    message: dict[str, Any] = {"role": "assistant", "content": None}
    message["tool_calls"] = [
        {"id": f"c{i}", "type": "function", "function": {"name": "search", "arguments": "{}"}} for i in range(calls)
    ]
    body = {"choices": [{"message": message}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}}
    return TransportResponse(200, {}, json.dumps(body).encode())


TOOLS = [{"type": "function", "function": {"name": "search", "parameters": {"type": "object", "properties": {}}}}]


def body_with_tools(**extra: Any) -> bytes:
    payload = json.loads(body())
    payload.update(tools=TOOLS, tool_choice="auto", **extra)
    return json.dumps(payload).encode()


def test_a_request_with_tools_is_refused_unless_the_run_states_a_tool_cap(tmp_path: Path) -> None:
    transport = Fake(tool_reply(1))
    refused = make(transport, tmp_path).chat(body_with_tools())
    assert isinstance(refused, Refusal) and refused.code == "PARAMETER_REFUSED" and transport.payloads == []
    allowed = make(Fake(tool_reply(1)), tmp_path, max_tool_calls=2).chat(body_with_tools(parallel_tool_calls=False))
    assert isinstance(allowed, TransportResponse)


def test_every_tool_call_a_reply_requests_is_counted_and_the_cap_stops_the_next_offer(tmp_path: Path) -> None:
    transport = Fake(tool_reply(2), tool_reply(1), reply())
    proxy = make(transport, tmp_path, max_calls=10, max_tool_calls=3)
    assert isinstance(proxy.chat(body_with_tools()), TransportResponse)
    assert proxy.usage()["tool_calls"] == 2
    assert isinstance(proxy.chat(body_with_tools()), TransportResponse)
    assert proxy.usage()["tool_calls"] == 3
    stopped = proxy.chat(body_with_tools())
    assert isinstance(stopped, Refusal) and stopped.code == "TOOL_BUDGET_EXHAUSTED"
    assert proxy.usage()["calls"] == 2 and len(transport.payloads) == 2, "a refused offer is neither sent nor counted"
    final = proxy.chat(body())  # the final answer carries no tools and is still served
    assert isinstance(final, TransportResponse) and proxy.usage()["calls"] == 3


def test_an_unknown_parameter_is_still_refused_when_tools_are_allowed(tmp_path: Path) -> None:
    proxy = make(Fake(), tmp_path, max_tool_calls=2)
    payload = json.loads(body_with_tools())
    payload["logit_bias"] = {}
    refused = proxy.chat(json.dumps(payload).encode())
    assert isinstance(refused, Refusal) and refused.code == "PARAMETER_REFUSED"


def test_a_negative_tool_cap_is_refused() -> None:
    with pytest.raises(ProxyError):
        limits(max_tool_calls=-1)


def test_a_client_that_says_stream_false_is_served_and_the_key_is_not_forwarded(tmp_path: Path) -> None:
    transport = Fake()
    proxy = make(transport, tmp_path)
    payload = json.loads(body())
    assert isinstance(proxy.chat(json.dumps({**payload, "stream": False}).encode()), TransportResponse)
    assert "stream" not in transport.payloads[0], "nothing about streaming reaches the provider"
    refused = proxy.chat(json.dumps({**payload, "stream": True}).encode())
    assert isinstance(refused, Refusal) and refused.code == "STREAMING_REFUSED"


def test_a_cap_or_a_daily_limit_is_counted_as_a_quota_refusal_and_a_parameter_refusal_is_not(tmp_path: Path) -> None:
    capped = make(Fake(), tmp_path, max_calls=1)
    capped.chat(body())
    assert isinstance(capped.chat(body()), Refusal)
    assert capped.usage()["quota_refused"] == 1 and capped.usage()["refused"] == 1
    daily = TransportResponse(429, {}, b'{"error": {"message": "Rate limit on tokens per day (TPD)"}}')
    walled = make(Fake(daily), tmp_path)
    walled.chat(body())
    assert isinstance(walled.chat(body()), Refusal) and walled.usage()["quota_refused"] == 1
    other = make(Fake(), tmp_path)
    assert isinstance(other.chat(body(stream=True)), Refusal)
    assert other.usage()["refused"] == 1 and other.usage()["quota_refused"] == 0, "a malformed request is not a limit"


# --------------------------------------------------------------------------- the provider's refusal facts (BADR-0048)

ORG = "org_01abcdefghijklmnop"
TOO_LARGE = (
    "Request too large for model `qwen/qwen3.8-27b` in organization `" + ORG + "` service tier `on_demand` on tokens "
    "per minute (TPM): Limit 6000, Requested 9034, please reduce your message size and try again."
)
THROTTLED = (
    "Rate limit reached for model `qwen/qwen3.8-27b` in organization `" + ORG + "` service tier `on_demand` on tokens "
    "per minute (TPM): Limit 6000, Used 5100, Requested 1900. Please try again in 1m2.5s."
)


def refused(
    message: str, *, status: int, code: str = "rate_limit_exceeded", headers: Mapping[str, str] | None = None
) -> Any:
    error = {"message": message, "type": "tokens", "code": code}
    return TransportResponse(status, dict(headers or {}), json.dumps({"error": error}).encode())


def book(tmp_path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in (tmp_path / "proxy.jsonl").read_text(encoding="utf-8").splitlines()]


def test_a_413_is_kept_as_its_window_and_figures_and_not_as_its_message(tmp_path: Path) -> None:
    proxy = make(Fake(refused(TOO_LARGE, status=413, code="request_too_large")), tmp_path)
    assert isinstance(proxy.chat(body()), TransportResponse)
    row = book(tmp_path)[0]
    assert row["http_status"] == 413 and row["outcome"] == "ERROR"
    assert row["refusal"] == {
        "window": "TOKENS_MINUTE", "limit": 6000, "requested": 9034, "error_type": "tokens",
        "error_code": "request_too_large",
    }  # fmt: skip
    assert ORG not in json.dumps(row) and "reduce your message" not in json.dumps(row)


def test_a_429_keeps_the_used_figure_the_wait_and_the_bounded_headers(tmp_path: Path) -> None:
    headers = {
        "x-ratelimit-limit-tokens": "6000",
        "x-ratelimit-remaining-tokens": "0",
        "x-ratelimit-reset-tokens": "1m2s",
    }
    proxy = make(Fake(refused(THROTTLED, status=429, headers=headers)), tmp_path)
    proxy.chat(body())
    row = book(tmp_path)[0]
    assert row["outcome"] == "RATE_LIMITED"
    assert row["refusal"] == {
        "window": "TOKENS_MINUTE", "limit": 6000, "used": 5100, "requested": 1900, "retry_after_seconds": 62.5,
        "error_type": "tokens", "error_code": "rate_limit_exceeded",
        "rate_limits": {"limit-tokens": 6000, "remaining-tokens": 0, "reset-tokens": "1m2s"},
    }  # fmt: skip
    assert ORG not in json.dumps(row)


def test_an_unreadable_or_hostile_refusal_adds_no_text_it_says(tmp_path: Path) -> None:
    hostile = {"message": "secret prompt text " + KEY, "type": KEY, "code": ORG}
    proxy = make(
        Fake(
            TransportResponse(502, {}, b"<html>gateway</html>"),
            TransportResponse(500, {}, json.dumps({"error": hostile}).encode()),
            TransportResponse(500, {}, json.dumps({"error": [KEY]}).encode()),
            TransportResponse(500, {}, json.dumps({"error": KEY}).encode()),
            TransportResponse(500, {}, json.dumps([KEY]).encode()),
        ),
        tmp_path,
        max_calls=5,
    )
    for _ in range(5):
        proxy.chat(body())
    rows = book(tmp_path)
    assert [r["refusal"] for r in rows] == [
        {"window": "UNKNOWN"},
        {"window": "UNKNOWN", "error_type": "OTHER", "error_code": "OTHER"},
        {"window": "UNKNOWN"},
        {"window": "UNKNOWN"},
        {"window": "UNKNOWN"},
    ]
    assert KEY not in json.dumps(rows) and ORG not in json.dumps(rows) and "secret prompt" not in json.dumps(rows)


def test_absurd_numbers_and_nesting_in_a_refusal_never_stop_the_book_from_being_written(tmp_path: Path) -> None:
    huge = "Limit " + "9" * 5000 + ", Requested 13. Please try again in " + "9" * 5000 + "h1s."
    nested = b'{"error":' * 60000 + b"1" + b"}" * 60000
    proxy = make(
        Fake(
            refused(huge, status=429),
            TransportResponse(500, {}, nested),
            refused(THROTTLED, status=429, headers={"retry-after": "soon"}),
        ),
        tmp_path,
    )
    for _ in range(3):
        assert isinstance(proxy.chat(body()), TransportResponse)
    rows = book(tmp_path)
    assert len(rows) == 3 and proxy.usage()["calls"] == 3
    assert rows[0]["refusal"].get("requested") == 13 and "limit" not in rows[0]["refusal"]
    assert rows[1]["refusal"] == {"window": "UNKNOWN"}
    assert rows[2]["refusal"]["retry_after_seconds"] == 62.5  # a non-numeric header falls back to the body's wait


def test_figures_are_read_with_a_colon_or_extra_spaces_and_an_unknown_code_is_kept_as_other() -> None:
    facts = refusal_facts(
        {},
        refused(
            "on tokens per day (TPD): Limit:  500000,  Used 499990, Requested 20", status=429, code="brand_new"
        ).body,
    )
    assert facts == {"window": "TOKENS_DAILY", "limit": 500000, "used": 499990, "requested": 20,
                     "error_type": "tokens", "error_code": "OTHER"}  # fmt: skip


def test_a_successful_call_carries_no_refusal_field(tmp_path: Path) -> None:
    proxy = make(Fake(), tmp_path)
    proxy.chat(body())
    assert "refusal" not in book(tmp_path)[0]


def test_the_facts_read_the_same_window_and_wait_as_the_pool_does() -> None:
    body_ = refused(THROTTLED, status=429).body
    facts = refusal_facts({}, body_)
    assert (facts["window"], facts["retry_after_seconds"]) == _quota_window(body_)
    assert refusal_facts({"retry-after": "9"}, body_)["retry_after_seconds"] == 9.0


# --------------------------------------------------------------------------- the request ceiling (BADR-0049)

TOOL = {"type": "function", "function": {"name": "search", "description": "x" * 400, "parameters": {"type": "object"}}}


def test_a_request_over_the_ceiling_is_refused_unsent_and_uses_no_call(tmp_path: Path) -> None:
    transport = Fake()
    proxy = make(transport, tmp_path, max_request_tokens=100)
    messages = [{"role": "user", "content": "w" * 800}]  # about 200 tokens at four characters each
    result = proxy.chat(body(messages=messages))
    assert result == Refusal(413, "REQUEST_OVER_CEILING")
    assert transport.payloads == [] and proxy.usage()["calls"] == 0 and proxy.usage()["refused"] == 1
    row = book(tmp_path)[0]
    assert row["outcome"] == "REFUSED" and row["code"] == "REQUEST_OVER_CEILING" and row["ceiling_tokens"] == 100
    assert row["estimated_tokens"] > 100 and row["request_chars"] > 800 and "w" * 20 not in json.dumps(row)


def test_the_tool_definitions_count_toward_the_ceiling(tmp_path: Path) -> None:
    transport = Fake()
    proxy = make(transport, tmp_path, max_request_tokens=100, max_tool_calls=5)
    assert proxy.chat(body()).__class__ is TransportResponse  # the short message alone is under the ceiling
    assert proxy.chat(body(tools=[TOOL])) == Refusal(413, "REQUEST_OVER_CEILING")
    assert len(transport.payloads) == 1


def test_a_request_exactly_at_the_ceiling_is_sent_and_one_token_over_is_not(tmp_path: Path) -> None:
    transport = Fake()
    proxy = make(transport, tmp_path, max_request_tokens=50, max_calls=5)
    probe = json.dumps([[{"role": "user", "content": ""}], ""])  # the fixed part of the size
    room = 50 * 4 - len(probe)  # characters of content that bring the estimate to 50 + 1 - 1
    exactly = [{"role": "user", "content": "a" * (room - 4 + 3)}]
    assert isinstance(proxy.chat(body(messages=exactly)), TransportResponse)
    over = [{"role": "user", "content": "a" * (room - 4 + 4)}]
    assert proxy.chat(body(messages=over)) == Refusal(413, "REQUEST_OVER_CEILING")


def test_with_no_ceiling_a_large_request_is_sent_and_every_dispatch_row_keeps_its_size(tmp_path: Path) -> None:
    transport = Fake(reply(), refused(TOO_LARGE, status=413))
    proxy = make(transport, tmp_path, max_calls=5, max_tokens=100_000)
    assert isinstance(proxy.chat(body(messages=[{"role": "user", "content": "w" * 40_000}])), TransportResponse)
    proxy.chat(body())
    rows = book(tmp_path)
    assert [r["outcome"] for r in rows] == ["OK", "ERROR"]
    assert rows[0]["request_chars"] > 40_000 and 0 < rows[1]["request_chars"] < 400


def test_a_ceiling_below_one_token_is_refused_at_set_up() -> None:
    with pytest.raises(ProxyError):
        limits(max_request_tokens=0)


def test_over_http_a_request_over_the_ceiling_comes_back_as_a_413_with_the_code(tmp_path: Path) -> None:
    proxy = make(Fake(), tmp_path, max_request_tokens=10)
    with ProxyServer(proxy, token=TOKEN) as server:
        status, answer, _ = call(
            server.base_url, "/chat/completions", body(messages=[{"role": "user", "content": "w" * 400}]), TOKEN
        )
    assert status == 413 and "REQUEST_OVER_CEILING" in json.dumps(answer)


def test_a_transport_failure_row_keeps_the_request_size_too(tmp_path: Path) -> None:
    proxy = make(Fake(GenerationTransientError("PROVIDER_UNAVAILABLE")), tmp_path)
    assert proxy.chat(body()) == Refusal(502, "PROVIDER_UNAVAILABLE")
    assert 0 < book(tmp_path)[0]["request_chars"] < 400
