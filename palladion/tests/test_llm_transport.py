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


# --------------------------------------------------------------------------- counted evaluation transport (ADR-0099)


import importlib.util  # noqa: E402
import threading  # noqa: E402
from http.server import BaseHTTPRequestHandler, HTTPServer  # noqa: E402
from pathlib import Path  # noqa: E402


class Provider:
    """A real loopback HTTP server that answers like the provider and remembers what it was sent."""

    def __init__(self) -> None:
        seen = self.seen = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["content-length"]))
                seen.append({"path": self.path, "authorization": self.headers.get("authorization"),
                             "payload": json.loads(body)})
                data = json.dumps({"choices": [{"message": {"content": "{}"}}],
                                   "usage": {"prompt_tokens": 3, "completion_tokens": 2}}).encode()
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.server.server_port}/v1"


def test_a_loopback_base_url_receives_the_call_with_the_configured_cap_and_key():
    with Provider() as provider:
        model = GroqModel("run-token-canary", enabled=True, base_url=provider.base_url, completion_cap=700)
        turn = asyncio.run(model.complete([{"role": "user", "content": "Synthetic request"}], definitions()))
    assert turn.usage == {"prompt_tokens": 3, "completion_tokens": 2}
    [seen] = provider.seen
    assert seen["path"] == "/v1/chat/completions" and seen["authorization"] == "Bearer run-token-canary"
    assert seen["payload"]["max_completion_tokens"] == 700


def test_the_default_address_and_cap_are_unchanged():
    model = GroqModel("synthetic", enabled=True)
    assert model.endpoint == "https://api.groq.com/openai/v1/chat/completions" and model.completion_cap == 768


@pytest.mark.parametrize("url", [
    "https://api.example.com/v1", "http://10.0.0.5:8000/v1", "http://127.0.0.1.evil.example:8000/v1",
    "http://127.0.0.1:8000@evil.example/v1", "http://user:pw@127.0.0.1:8000/v1", "https://127.0.0.1:8000/v1",
    "http://127.0.0.1/v1", "http://127.0.0.1:8000/v1?x=1", "http://127.0.0.1:notaport/v1", "ftp://127.0.0.1:8000/v1",
])
def test_a_base_url_that_is_not_an_http_loopback_address_with_a_port_is_refused(url):
    with pytest.raises(ValueError):
        GroqModel("synthetic", enabled=True, base_url=url)


@pytest.mark.parametrize("cap", [63, 4097, 768.0, True, None])
def test_a_completion_cap_outside_its_range_or_type_is_refused(cap):
    with pytest.raises(ValueError):
        GroqModel("synthetic", enabled=True, completion_cap=cap)


def test_the_key_can_come_from_a_named_variable_and_is_never_echoed(monkeypatch):
    monkeypatch.setenv("BENCH_RUN_KEY", "canary-key-value")
    model = GroqModel.from_environment("BENCH_RUN_KEY", enabled=True)
    assert model.endpoint.startswith("https://api.groq.com/")
    with pytest.raises(PermissionError) as caught:
        GroqModel.from_environment("BENCH_RUN_KEY", enabled=False)
    assert "canary-key-value" not in str(caught.value)
    monkeypatch.setenv("BENCH_RUN_KEY", "has a space")
    with pytest.raises(PermissionError) as caught:
        GroqModel.from_environment("BENCH_RUN_KEY", enabled=True)
    assert "has a space" not in str(caught.value)
    monkeypatch.delenv("BENCH_RUN_KEY")
    with pytest.raises(PermissionError):
        GroqModel.from_environment("BENCH_RUN_KEY", enabled=True)
    with pytest.raises(ValueError):
        GroqModel.from_environment("not a variable; rm -rf", enabled=True)


def load_serve():
    spec = importlib.util.spec_from_file_location("serve_script", Path(__file__).parents[1] / "scripts/serve.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_launcher_defaults_leave_ordinary_serving_unchanged():
    serve = load_serve()
    args, settings = serve.parse_args([])
    assert args.model_base_url is None and args.key_env is None and args.completion_cap == 768
    assert settings.request_timeout_seconds == 60 and args.model_timeout == 25


def test_the_launcher_options_for_a_counted_run_reach_the_model(monkeypatch):
    serve = load_serve()
    monkeypatch.setenv("BENCH_RUN_KEY", "canary-key-value")
    with Provider() as provider:
        args, settings = serve.parse_args(["--enable-live-llm", "--model-base-url", provider.base_url, "--key-env",
                                           "BENCH_RUN_KEY", "--completion-cap", "2000", "--request-timeout", "240",
                                           "--model-timeout", "120", "--model", "openai/gpt-oss-120b"])
        model = serve.build_model(args)
        asyncio.run(model.complete([{"role": "user", "content": "Synthetic request"}], []))
    assert settings.request_timeout_seconds == 240 and model.timeout == 120
    assert provider.seen[0]["payload"]["max_completion_tokens"] == 2000
    assert provider.seen[0]["payload"]["model"] == "openai/gpt-oss-120b"


@pytest.mark.parametrize("argv", [
    ["--model-base-url", "http://127.0.0.1:9/v1"], ["--key-env", "BENCH_RUN_KEY"], ["--request-timeout", "400"],
    ["--enable-live-llm", "--request-timeout", "0"],
])
def test_the_launcher_refuses_counted_run_options_without_enablement_or_outside_their_range(argv):
    serve = load_serve()
    with pytest.raises(SystemExit) as caught:
        serve.parse_args(argv)
    assert caught.value.code == 2


def test_a_named_settings_file_is_used_and_an_unreadable_one_fails_before_serving(tmp_path):
    serve = load_serve()
    chosen = tmp_path / "settings.yaml"
    chosen.write_text("schema_version: '1.0'\nrequest_timeout_seconds: 90\ncontinuity_enabled: false\n", encoding="utf-8")
    args, settings = serve.parse_args(["--settings", str(chosen), "--request-timeout", "90"])
    assert settings.continuity_enabled is False and args.settings == chosen
    with pytest.raises(FileNotFoundError):
        serve.parse_args(["--settings", str(tmp_path / "missing.yaml")])
