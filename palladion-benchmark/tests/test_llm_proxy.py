"""The counting LLM proxy: nothing a comparator does can spend past the caps (B06-T00.02, BR36)."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from benchmark.generator import GenerationError, GenerationTransientError, TransportResponse
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


def test_a_missing_usage_is_charged_at_the_estimate_never_as_free(tmp_path: Path) -> None:
    silent = TransportResponse(200, {}, json.dumps({"choices": [{"message": {"content": "x"}}]}).encode())
    proxy = make(Fake(silent), tmp_path)
    assert isinstance(proxy.chat(body()), TransportResponse)
    assert proxy.spent_tokens > 0


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
