"""Transport fault injection only; E-P04-001 separately records actual Groq requests."""
import asyncio
import json

import httpx
import pytest

from evidence_agent.agent.llm import GroqModel, ModelFailure
from evidence_agent.agent.tools import definitions


def transport_model(monkeypatch, handler):
    original = httpx.AsyncClient
    calls = []
    def record(request):
        calls.append(request)
        return handler(request)
    def client(**kwargs):
        return original(transport=httpx.MockTransport(record), **kwargs)
    monkeypatch.setattr("evidence_agent.agent.llm.httpx.AsyncClient", client)
    return GroqModel("synthetic-test-credential", enabled=True), calls


def test_native_tools_and_json_final_use_distinct_validated_requests(monkeypatch):
    def handler(request):
        body = json.loads(request.content)
        assert body["model"] == "qwen/qwen3.8-27b"
        assert 0 < body["max_completion_tokens"] < 1000
        if "tools" in body:
            assert len(body["tools"]) == 4 and "response_format" not in body
        else:
            assert body["response_format"] == {"type": "json_object"}
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok":true}'}}],
                                        "usage": {"total_tokens": 12}})
    model, calls = transport_model(monkeypatch, handler)
    async def run():
        first = await model.complete([{"role": "user", "content": "Synthetic request"}], definitions())
        final = await model.complete([{"role": "user", "content": "JSON final"}], [], final=True)
        assert first.usage == final.usage == {"total_tokens": 12}
    asyncio.run(run())
    assert len(calls) == 2


def test_provider_error_redacts_prose_and_never_retries(monkeypatch):
    model, calls = transport_model(monkeypatch, lambda request: httpx.Response(429, json={
        "error": {"code": "rate_limit_exceeded", "message": "PROTECTED_ERROR_CANARY"}}))
    with pytest.raises(ModelFailure) as caught:
        asyncio.run(model.complete([], []))
    assert caught.value.code == "PROVIDER_HTTP_429"
    assert caught.value.provider_code == "rate_limit_exceeded"
    assert "PROTECTED_ERROR_CANARY" not in str(caught.value)
    assert len(calls) == 1


@pytest.mark.parametrize("response,code", [
    ({"choices": []}, "MODEL_ENVELOPE_INVALID"),
    ({"choices": [{"message": None}]}, "MODEL_ENVELOPE_INVALID"),
])
def test_malformed_envelope_is_failure_not_success(monkeypatch, response, code):
    model, calls = transport_model(monkeypatch, lambda request: httpx.Response(200, json=response))
    with pytest.raises(ModelFailure, match=code):
        asyncio.run(model.complete([], []))
    assert len(calls) == 1


def test_response_and_context_bounds_do_not_create_free_requests(monkeypatch):
    model, calls = transport_model(monkeypatch, lambda request: httpx.Response(200, content=b"x" * (256*1024+1)))
    with pytest.raises(ModelFailure, match="MODEL_RESPONSE_TOO_LARGE"):
        asyncio.run(model.complete([], []))
    assert len(calls) == 1
    with pytest.raises(ModelFailure, match="MODEL_CONTEXT_TOO_LARGE"):
        asyncio.run(model.complete([{"role": "user", "content": "x"*50000}], []))
    assert len(calls) == 1


def test_quota_diagnostics_keep_only_window_counts_and_wait(monkeypatch):
    model, calls = transport_model(monkeypatch, lambda request: httpx.Response(429, json={"error":{
        "code":"rate_limit_exceeded", "message":"tokens per minute (TPM): Limit 1000, Used 0, Requested 1142. Please try again in 1m2.5s. PROTECTED_ERROR_CANARY"}}))
    with pytest.raises(ModelFailure):
        asyncio.run(model.complete([], []))
    assert model.last_failure["quota_window"] == "TOKENS_MINUTE"
    assert model.last_failure["quota_counts"] == {"limit":1000,"used":0,"requested":1142}
    assert model.last_failure["retry_after_seconds"] == 62.5
    assert "PROTECTED_ERROR_CANARY" not in str(model.last_failure)
    assert len(calls) == 1


@pytest.mark.parametrize("direction,window", [
    ("output", "OUTPUT_TOKENS_MINUTE"), ("input", "INPUT_TOKENS_MINUTE"),
])
def test_split_quota_failure_is_counted_without_retry(monkeypatch, direction, window):
    model, calls = transport_model(monkeypatch, lambda request: httpx.Response(429, json={
        "error": {"code": "rate_limit_exceeded", "message":
            f"{direction} tokens per minute: Limit 1000, Requested 1151. PROTECTED_ERROR_CANARY"}}))
    with pytest.raises(ModelFailure, match="PROVIDER_HTTP_429"):
        asyncio.run(model.complete([], []))
    assert model.last_failure["quota_window"] == window
    assert model.last_failure["quota_counts"] == {"limit": 1000, "requested": 1151}
    assert "PROTECTED_ERROR_CANARY" not in str(model.last_failure)
    assert len(calls) == 1


@pytest.mark.parametrize("status", [200, 429])
def test_documented_quota_headers_are_bounded_on_success_and_failure(monkeypatch, status):
    model, calls = transport_model(monkeypatch, lambda request: httpx.Response(status,
        headers={"x-ratelimit-limit-requests": "1000", "x-ratelimit-remaining-requests": "999",
            "x-ratelimit-limit-tokens": "8000", "x-ratelimit-remaining-tokens": "7914",
            "x-ratelimit-reset-requests": "2m59.56s", "x-ratelimit-reset-tokens": "644ms",
            "retry-after": "2", "authorization": "PROTECTED_HEADER_CANARY",
            "x-other-provider-data": "PROTECTED_HEADER_CANARY"},
        json={"choices": [{"message": {"content": '{"ok":true}'}}]} if status == 200 else
            {"error": {"code": "rate_limit_exceeded"}}))
    if status == 200:
        asyncio.run(model.complete([], []))
    else:
        with pytest.raises(ModelFailure):
            asyncio.run(model.complete([], []))
    assert model.last_rate_limits == {"limit-requests": 1000, "remaining-requests": 999,
        "limit-tokens": 8000, "remaining-tokens": 7914, "reset-requests": "2m59.56s",
        "reset-tokens": "644ms", "retry-after": "2"}
    assert "PROTECTED_HEADER_CANARY" not in str(model.last_rate_limits)
    assert len(calls) == 1


def test_invalid_or_absent_headers_do_not_become_zero_or_stale_quota(monkeypatch):
    model, calls = transport_model(monkeypatch, lambda request: httpx.Response(200,
        headers={"x-ratelimit-limit-tokens": "9" * 30,
                 "x-ratelimit-reset-tokens": "PROTECTED_HEADER_CANARY"},
        json={"choices": [{"message": {"content": '{"ok":true}'}}]}))
    model.last_rate_limits = {"limit-tokens": 8000}
    asyncio.run(model.complete([], []))
    assert model.last_rate_limits == {}
    assert len(calls) == 1


@pytest.mark.parametrize("name", GroqModel.allowed_models)
def test_explicit_model_selection_preserves_provider_capabilities(monkeypatch, name):
    def handler(request):
        body = json.loads(request.content)
        assert body["model"] == name
        qwen = name == "qwen/qwen3.8-27b"
        assert body["reasoning_effort"] == ("none" if qwen else "low")
        assert body["parallel_tool_calls"] is qwen
        return httpx.Response(200, json={"choices": [{"message": {"tool_calls": []}}]})
    model, calls = transport_model(monkeypatch, handler)
    model = GroqModel("synthetic-test-credential", enabled=True, model=name)
    asyncio.run(model.complete([], definitions()))
    assert len(calls) == 1


def test_unapproved_model_is_rejected_before_dispatch():
    with pytest.raises(ValueError, match="Unapproved"):
        GroqModel("synthetic-test-credential", enabled=True, model="unapproved-model")


@pytest.mark.parametrize("value", [-1, 61, float("nan"), float("inf"), True, "10"])
def test_call_pacing_rejects_invalid_config_before_http(value):
    with pytest.raises(ValueError, match="interval"):
        GroqModel("synthetic", enabled=True, call_interval_seconds=value)


def test_shared_model_paces_main_critic_and_final_without_retry(monkeypatch):
    import time
    times = []
    def handler(request):
        times.append(time.monotonic())
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})
    _, calls = transport_model(monkeypatch, handler)
    model = GroqModel("synthetic", enabled=True, call_interval_seconds=0.03)
    async def run():
        await asyncio.gather(model.complete([], definitions()), model.complete([], []),
                             model.complete([], [], final=True))
    asyncio.run(run())
    assert len(calls) == 3
    assert all(b-a >= 0.024 for a,b in zip(times,times[1:]))


def test_pacing_wait_cancels_without_http_or_abandoned_future_slots(monkeypatch):
    _, calls = transport_model(monkeypatch, lambda request: httpx.Response(200,
        json={"choices": [{"message": {"content": "{}"}}]}))
    model = GroqModel("synthetic", enabled=True, call_interval_seconds=0.04)
    async def run():
        await model.complete([], [])
        next_dispatch = model._next_dispatch
        with pytest.raises(TimeoutError):
            async with asyncio.timeout(0.005):
                await model.complete([], [])
        assert len(calls) == 1 and model._next_dispatch == next_dispatch
        await asyncio.sleep(0.05)
        await model.complete([], [])
    asyncio.run(run())
    assert len(calls) == 2


def test_after_pacing_caller_revalidates_before_any_http(monkeypatch):
    _, calls = transport_model(monkeypatch, lambda request: httpx.Response(200,
        json={"choices": [{"message": {"content": "{}"}}]}))
    model = GroqModel("synthetic", enabled=True, call_interval_seconds=0.04)
    checked = []
    def revalidate():
        checked.append(True)
        raise PermissionError("Revoked during wait")
    async def run():
        await model.complete([], [])
        task = asyncio.create_task(model.complete([], [], before_send=revalidate))
        await asyncio.sleep(0.005)
        assert checked == [] and len(calls) == 1
        with pytest.raises(PermissionError):
            await task
    asyncio.run(run())
    assert checked == [True] and len(calls) == 1


def test_same_model_pacing_supports_separate_event_loops(monkeypatch):
    import time
    from concurrent.futures import ThreadPoolExecutor
    times = []
    def handler(request):
        times.append(time.monotonic())
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})
    _, calls = transport_model(monkeypatch, handler)
    model = GroqModel("synthetic", enabled=True, call_interval_seconds=0.03)
    def run():
        return asyncio.run(model.complete([], []))
    with ThreadPoolExecutor(max_workers=2) as pool:
        tasks = [pool.submit(run), pool.submit(run)]
        for task in tasks:
            task.result()
    assert len(calls) == 2 and times[1]-times[0] >= 0.024
