"""Generator pool: no hidden fallback, per-call records, bounded waits, key never leaks.

All provider behavior here is injected, so these tests exercise the benchmark's own guards. They do not
establish how Groq behaves; the real-provider proof is separate (B01-T05.02).
"""

from __future__ import annotations

import json
import threading
import traceback
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, ClassVar

import httpx
import pytest

from benchmark import generator
from benchmark.config import GeneratorSettings, load_benchmark_config
from benchmark.contracts import ContractError, TransientInfrastructureError
from benchmark.generator import (
    GenerationError,
    GenerationTransientError,
    GeneratorPool,
    HttpxTransport,
    TransportResponse,
    assign_models,
    prove,
    read_api_key,
)

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = load_benchmark_config(ROOT / "configs" / "benchmark.yaml").generator
QWEN, GPT120, GPT20 = SETTINGS.models
FAKE_KEY = "gsk_" + "Zq7" * 12
Q1, Q2, Q3 = "q-00000001", "q-00000002", "q-00000003"
MESSAGES = [{"role": "system", "content": "be brief"}, {"role": "user", "content": "SENTINEL-PROMPT-TEXT"}]


def ok(model: str, text: str | None = "ready", **headers: str) -> TransportResponse:
    body = {
        "model": model,
        "choices": [{"message": {"content": text}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15, "queue_time": 0.1},
    }
    return TransportResponse(200, {k.replace("_", "-"): v for k, v in headers.items()}, json.dumps(body).encode())


def limited(
    retry_after: str | None = "1", message: str = "Rate limit reached on tokens per minute (TPM)"
) -> TransportResponse:
    headers = {"retry-after": retry_after} if retry_after is not None else {}
    return TransportResponse(429, headers, json.dumps({"error": {"message": message}}).encode())


@dataclass
class FakeTransport:
    script: list[TransportResponse | BaseException]
    payloads: list[dict[str, Any]] = field(default_factory=list)

    def post(self, payload: Any) -> TransportResponse:
        self.payloads.append(dict(payload))
        step = self.script.pop(0)
        if isinstance(step, BaseException):
            raise step
        return step


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        self.now += 0.1
        return self.now


def pool(
    script: Sequence[TransportResponse | BaseException],
    *,
    settings: GeneratorSettings = SETTINGS,
    budget: int = 10,
    assignment: dict[str, str] | None = None,
    enabled: bool = True,
    record_path: Path | None = None,
    sleeps: list[float] | None = None,
) -> tuple[GeneratorPool, FakeTransport]:
    transport = FakeTransport(list(script))
    sleeper = sleeps if sleeps is not None else []
    instance = GeneratorPool(
        settings,
        transport,
        enabled=enabled,
        assignment=assignment or {Q1: QWEN, Q2: GPT120, Q3: GPT20},
        call_budget=budget,
        record_path=record_path,
        sleep=sleeper.append,
        monotonic=Clock(),
        wall_clock=lambda: datetime(2026, 10, 18, 3, 0, tzinfo=UTC),
    )
    return instance, transport


# ----------------------------------------------------------------------------- enabling and credentials


def test_a_disabled_pool_never_calls_the_provider() -> None:
    instance, transport = pool([ok(QWEN)], enabled=False)
    with pytest.raises(GenerationError) as caught:
        instance.complete(Q1, MESSAGES)
    assert caught.value.code == "DISABLED" and transport.payloads == [] and instance.records == ()


def test_live_construction_refuses_before_reading_the_env_file_unless_enabled(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.env"
    with pytest.raises(GenerationError) as caught:
        GeneratorPool.live(SETTINGS, missing, enabled=False, assignment={Q1: QWEN}, call_budget=1)
    assert caught.value.code == "DISABLED"  # not NO_CREDENTIAL: the file was never touched
    with pytest.raises(GenerationError) as caught:
        GeneratorPool.live(SETTINGS, missing, enabled=True, assignment={Q1: QWEN}, call_budget=1)
    assert caught.value.code == "NO_CREDENTIAL"


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        (f"GROQ_API_KEY={FAKE_KEY}", FAKE_KEY),
        (f"GROQ_API_KEY = {FAKE_KEY}", FAKE_KEY),
        (f"export GROQ_API_KEY='{FAKE_KEY}'", FAKE_KEY),
        (f'  GROQ_API_KEY="{FAKE_KEY}"  ', FAKE_KEY),
    ],
)
def test_the_key_is_parsed_as_one_literal(tmp_path: Path, line: str, expected: str) -> None:
    env = tmp_path / ".env"
    env.write_text(f"OTHER=1\n{line}\n", encoding="utf-8")
    assert read_api_key(env, enabled=True) == expected


@pytest.mark.parametrize(
    "content", ["", "GROQ_API_KEY=", "GROQ_API_KEY=two words", "OTHER_KEY=abc", "# GROQ_API_KEY=abc"]
)
def test_a_missing_empty_or_malformed_key_is_refused_with_a_fixed_code(tmp_path: Path, content: str) -> None:
    env = tmp_path / ".env"
    env.write_text(content + "\n", encoding="utf-8")
    with pytest.raises(GenerationError) as caught:
        read_api_key(env, enabled=True)
    assert caught.value.code == "NO_CREDENTIAL"


# ----------------------------------------------------------------------------- records and assignment


def test_each_call_records_requested_and_served_model_tokens_and_parameters() -> None:
    instance, _ = pool(
        [
            ok(
                QWEN,
                x_request_id="req_abc-123",
                x_ratelimit_remaining_tokens="5000",
                x_ratelimit_reset_tokens="1.2s",
                x_ratelimit_limit_requests="oops",
            )
        ]
    )
    result = instance.complete(Q1, MESSAGES, arm_id="R2")
    record = result.record
    assert result.text == "ready"
    assert (record.requested_model, record.served_model, record.model_matches_request) == (QWEN, QWEN, True)
    assert (record.prompt_tokens, record.completion_tokens, record.total_tokens) == (12, 3, 15)
    assert (record.temperature, record.max_completion_tokens, record.reasoning_effort) == (0.0, 256, "none")
    assert record.provider_exposes_revision is False and record.seed is None and record.cached is False
    assert record.request_id == "req_abc-123" and record.arm_id == "R2" and record.attempt == 1
    assert record.rate_limits == {"remaining-tokens": 5000, "reset-tokens": "1.2s"}  # non-numeric header dropped
    assert record.latency_ms == pytest.approx(100.0) and record.started_at_utc == "2026-10-18T03:00:00Z"
    assert "SENTINEL-PROMPT-TEXT" not in json.dumps(record.to_dict())  # a digest, never the prompt
    assert len(record.prompt_sha256) == 64


def test_the_assigned_model_and_its_reasoning_effort_go_into_the_request() -> None:
    instance, transport = pool([ok(QWEN), ok(GPT120), ok(GPT20)])
    for question in (Q1, Q2, Q3):
        instance.complete(question, MESSAGES)
    assert [(p["model"], p["reasoning_effort"]) for p in transport.payloads] == [
        (QWEN, "none"),
        (GPT120, "low"),
        (GPT20, "low"),
    ]
    assert all(p["temperature"] == 0.0 and p["max_completion_tokens"] == 256 for p in transport.payloads)
    assert "response_format" not in transport.payloads[0]


def test_json_output_sets_the_response_format_and_a_smaller_cap_is_allowed() -> None:
    instance, transport = pool([ok(QWEN)])
    instance.complete(Q1, MESSAGES, json_output=True, max_completion_tokens=64)
    assert transport.payloads[0]["response_format"] == {"type": "json_object"}
    assert transport.payloads[0]["max_completion_tokens"] == 64


def test_an_unassigned_question_is_refused_without_a_request() -> None:
    instance, transport = pool([ok(QWEN)])
    with pytest.raises(GenerationError) as caught:
        instance.complete("q-0000dead", MESSAGES)
    assert caught.value.code == "ASSIGNMENT_MISSING" and transport.payloads == []


def test_a_served_model_that_differs_from_the_request_is_recorded_as_a_mismatch() -> None:
    instance, _ = pool([ok(GPT20)])
    record = instance.complete(Q1, MESSAGES).record
    assert (record.requested_model, record.served_model, record.model_matches_request) == (QWEN, GPT20, False)


def test_unapproved_models_cannot_enter_the_pool_or_the_assignment() -> None:
    with pytest.raises(GenerationError) as caught:
        pool([], assignment={Q1: "other/model"})
    assert caught.value.code == "MODEL_NOT_APPROVED"
    with pytest.raises(GenerationError):
        pool([], settings=replace(SETTINGS, models=("other/model",)))


def test_records_are_appended_to_a_jsonl_file_one_line_per_call(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    instance, _ = pool([limited("1"), ok(QWEN)], record_path=path)
    instance.complete(Q1, MESSAGES)
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [(line["attempt"], line["status"]) for line in lines] == [(1, "RATE_LIMITED"), (2, "OK")]


# ----------------------------------------------------------------------------- rate limits and fallback


def test_a_rate_limit_waits_the_advertised_time_and_retries_the_same_model() -> None:
    sleeps: list[float] = []
    instance, transport = pool([limited("2"), ok(QWEN)], sleeps=sleeps)
    result = instance.complete(Q1, MESSAGES)
    assert sleeps == [2.0] and [p["model"] for p in transport.payloads] == [QWEN, QWEN]
    first, second = instance.records
    assert (first.status, first.error_code, first.quota_window, first.retry_after_seconds) == (
        "RATE_LIMITED",
        "RATE_LIMITED",
        "TOKENS_MINUTE",
        2.0,
    )
    assert (second.status, second.attempt, second.failover_from) == ("OK", 2, None) and result.text == "ready"


def test_no_hidden_fallback_ever_occurs_when_failover_is_off() -> None:
    sleeps: list[float] = []
    instance, transport = pool([limited("1")] * 3, sleeps=sleeps)
    with pytest.raises(GenerationError) as caught:
        instance.complete(Q1, MESSAGES)
    assert caught.value.code == "RATE_LIMITED"
    assert {p["model"] for p in transport.payloads} == {QWEN}  # never GPT120 or GPT20
    assert len(transport.payloads) == 3 and sleeps == [1.0, 1.0]  # bounded waits, then a recorded failure
    assert instance.mixed_model_questions == frozenset()


def test_a_wait_longer_than_the_cap_fails_immediately_without_sleeping() -> None:
    sleeps: list[float] = []
    instance, transport = pool([limited("500")], sleeps=sleeps)
    with pytest.raises(GenerationError):
        instance.complete(Q1, MESSAGES)
    assert sleeps == [] and len(transport.payloads) == 1


def test_a_rate_limit_without_any_advertised_wait_fails_immediately() -> None:
    sleeps: list[float] = []
    instance, _ = pool([limited(None, message="something else entirely")], sleeps=sleeps)
    with pytest.raises(GenerationError):
        instance.complete(Q1, MESSAGES)
    assert sleeps == [] and instance.records[0].quota_window == "UNKNOWN"


def test_the_suggested_wait_in_the_error_body_is_used_when_no_header_exists() -> None:
    sleeps: list[float] = []
    message = "Rate limit reached for tokens per day (TPD). Please try again in 1m30.5s."
    instance, _ = pool([limited(None, message=message), ok(QWEN)], sleeps=sleeps)
    instance.complete(Q1, MESSAGES)
    assert sleeps == [90.5] and instance.records[0].quota_window == "TOKENS_DAILY"


def test_explicit_failover_switches_model_records_it_and_marks_the_question_mixed() -> None:
    settings = replace(SETTINGS, allow_automatic_failover=True)
    instance, transport = pool([limited("1")] * 3 + [ok(GPT120)], settings=settings)
    result = instance.complete(Q1, MESSAGES)
    assert [p["model"] for p in transport.payloads] == [QWEN, QWEN, QWEN, GPT120]
    assert result.record.failover_from == QWEN and result.record.requested_model == GPT120
    assert instance.mixed_model_questions == frozenset({Q1})


def test_failover_stops_at_the_last_model() -> None:
    settings = replace(SETTINGS, allow_automatic_failover=True)
    instance, transport = pool([limited("1")] * 3, settings=settings, assignment={Q1: GPT20})
    with pytest.raises(GenerationError):
        instance.complete(Q1, MESSAGES)
    assert {p["model"] for p in transport.payloads} == {GPT20} and instance.mixed_model_questions == frozenset()


# ----------------------------------------------------------------------------- budget and errors


def test_the_call_budget_is_enforced_before_dispatch() -> None:
    instance, transport = pool([ok(QWEN), ok(QWEN), ok(QWEN)], budget=2)
    instance.complete(Q1, MESSAGES)
    instance.complete(Q1, MESSAGES)
    with pytest.raises(GenerationError) as caught:
        instance.complete(Q1, MESSAGES)
    assert caught.value.code == "BUDGET_EXHAUSTED" and len(transport.payloads) == 2
    assert instance.budget_violations == 1


def test_waiting_retries_consume_the_call_budget() -> None:
    instance, transport = pool([limited("1"), limited("1"), ok(QWEN)], budget=2)
    with pytest.raises(GenerationError) as caught:
        instance.complete(Q1, MESSAGES)
    assert caught.value.code == "BUDGET_EXHAUSTED" and len(transport.payloads) == 2


@pytest.mark.parametrize(
    ("response", "error_type", "code"),
    [
        (TransportResponse(500, {}, b"boom"), GenerationTransientError, "PROVIDER_HTTP_500"),
        (TransportResponse(503, {}, b""), GenerationTransientError, "PROVIDER_HTTP_503"),
        (TransportResponse(401, {}, b"{}"), GenerationError, "PROVIDER_HTTP_401"),
        (TransportResponse(400, {}, b"{}"), GenerationError, "PROVIDER_HTTP_400"),
        (TransportResponse(200, {}, b"not json"), GenerationError, "MALFORMED_RESPONSE"),
        (TransportResponse(200, {}, b'{"choices": []}'), GenerationError, "MALFORMED_RESPONSE"),
        (
            TransportResponse(200, {}, b'{"choices": [{"message": {"content": 5}}]}'),
            GenerationError,
            "MALFORMED_RESPONSE",
        ),
    ],
)
def test_failures_have_fixed_codes_and_only_server_faults_are_transient(
    response: TransportResponse, error_type: type[Exception], code: str
) -> None:
    instance, _ = pool([response])
    with pytest.raises(error_type) as caught:
        instance.complete(Q1, MESSAGES)
    assert caught.value.code == code  # type: ignore[attr-defined]
    assert isinstance(caught.value, TransientInfrastructureError) == (error_type is GenerationTransientError)
    assert instance.records[0].error_code == code and instance.records[0].status == "ERROR"


def test_a_null_content_response_is_a_real_response_with_no_text() -> None:
    instance, _ = pool([ok(QWEN, text=None)])
    result = instance.complete(Q1, MESSAGES)
    assert result.text is None and result.record.status == "OK"


@pytest.mark.parametrize(
    "messages",
    [
        [],
        [{"role": "robot", "content": "x"}],
        [{"role": "user"}],
        [{"role": "user", "content": "x", "extra": "y"}],
        [{"role": "user", "content": "  "}],
    ],
)
def test_malformed_messages_are_rejected_before_any_request(messages: list[dict[str, str]]) -> None:
    instance, transport = pool([ok(QWEN)])
    with pytest.raises(ContractError):
        instance.complete(Q1, messages)
    assert transport.payloads == []


def test_cap_above_the_configured_maximum_and_oversized_requests_are_refused() -> None:
    instance, transport = pool([ok(QWEN)])
    with pytest.raises(ContractError, match="cap"):
        instance.complete(Q1, MESSAGES, max_completion_tokens=257)
    big = [{"role": "user", "content": "x" * 16_000}] * 4
    with pytest.raises(GenerationError) as caught:
        instance.complete(Q1, big)
    assert caught.value.code == "REQUEST_TOO_LARGE" and transport.payloads == []


# ----------------------------------------------------------------------------- the key never leaks


def _everything_printable(instance: GeneratorPool, exc: BaseException) -> str:
    parts = [str(exc), repr(exc), "".join(traceback.format_exception(exc))]
    parts += [json.dumps(r.to_dict()) for r in instance.records]
    return "\n".join(parts)


@pytest.mark.parametrize(
    "fault",
    [
        RuntimeError(f"boom {FAKE_KEY}"),
        httpx.ConnectError(f"connect failed with {FAKE_KEY}"),
        OSError(f"os failure {FAKE_KEY}"),
        TransportResponse(500, {}, f'{{"error": {{"message": "bad key {FAKE_KEY}"}}}}'.encode()),
        TransportResponse(429, {}, f'{{"error": {{"message": "tokens per minute {FAKE_KEY}"}}}}'.encode()),
        TransportResponse(401, {}, f"unauthorized {FAKE_KEY}".encode()),
        TransportResponse(200, {}, f"garbage {FAKE_KEY}".encode()),
    ],
)
def test_a_planted_key_forced_through_every_error_path_appears_nowhere(
    fault: BaseException | TransportResponse,
) -> None:
    instance, _ = pool([fault])
    with pytest.raises((GenerationError, GenerationTransientError)) as caught:
        instance.complete(Q1, MESSAGES)
    assert FAKE_KEY not in _everything_printable(instance, caught.value)


def test_the_real_transport_maps_a_connection_failure_to_a_fixed_code_without_leaking_the_key() -> None:
    transport = HttpxTransport(FAKE_KEY, timeout_seconds=2.0, url="http://127.0.0.1:9/never")
    with pytest.raises(GenerationTransientError) as caught:
        transport.post({"model": QWEN})
    assert caught.value.code == "PROVIDER_UNAVAILABLE"
    text = "".join(traceback.format_exception(caught.value)) + repr(transport) + str(transport)
    assert FAKE_KEY not in text and caught.value.__context__ is None


# ----------------------------------------------------------------------------- assignment


def test_without_stated_budgets_every_question_gets_the_primary_model() -> None:
    ids = [f"q-{i:08x}" for i in range(1, 9)]
    plan = assign_models(ids, SETTINGS, seed=3, tokens_per_question=1000)
    assert set(plan.assigned.values()) == {QWEN} and set(plan.assigned) == set(ids) and plan.unassigned == ()


def test_budgets_spill_to_the_next_model_and_the_rest_are_unassigned() -> None:
    settings = replace(SETTINGS, token_budgets={QWEN: 3000, GPT120: 2000, GPT20: None})
    ids = [f"q-{i:08x}" for i in range(1, 11)]
    plan = assign_models(ids, settings, seed=3, tokens_per_question=1000)
    counts = {m: list(plan.assigned.values()).count(m) for m in SETTINGS.models}
    assert counts == {QWEN: 3, GPT120: 2, GPT20: 0}  # an unknown fallback budget means never used
    assert len(plan.unassigned) == 5 and set(plan.assigned) | set(plan.unassigned) == set(ids)
    assert set(plan.assigned).isdisjoint(plan.unassigned)


def test_assignment_is_deterministic_per_seed_and_digest_tracks_content() -> None:
    settings = replace(SETTINGS, token_budgets={QWEN: 3000, GPT120: 3000, GPT20: 3000})
    ids = [f"q-{i:08x}" for i in range(1, 10)]
    first = assign_models(ids, settings, seed=3, tokens_per_question=1000)
    assert first == assign_models(ids, settings, seed=3, tokens_per_question=1000)
    other = assign_models(ids, settings, seed=4, tokens_per_question=1000)
    assert other.assigned != first.assigned and other.digest() != first.digest()
    assert len(first.digest()) == 64


def test_an_unlimited_primary_means_fallbacks_are_never_used() -> None:
    settings = replace(SETTINGS, token_budgets={QWEN: None, GPT120: 99999, GPT20: 99999})
    plan = assign_models([f"q-{i:08x}" for i in range(1, 6)], settings, seed=1, tokens_per_question=10)
    assert set(plan.assigned.values()) == {QWEN}


@pytest.mark.parametrize("bad", [0, -1, True, 1.5])
def test_tokens_per_question_must_be_a_positive_integer(bad: object) -> None:
    with pytest.raises(ContractError):
        assign_models(["q-00000001"], SETTINGS, seed=1, tokens_per_question=bad)  # type: ignore[arg-type]


# ----------------------------------------------------------------------------- the proof entry point


def test_prove_passes_only_when_the_served_model_equals_the_requested_one() -> None:
    ids = {QWEN: Q1, GPT120: Q2, GPT20: Q3}
    instance, _ = pool([ok(QWEN), ok(GPT20), limited("500")])
    rows = prove(instance, [QWEN, GPT120, GPT20], ids, 64)
    assert [r["result"] for r in rows] == ["PASS", "FAIL", "FAIL"]
    assert rows[1]["served_model"] == GPT20  # a mismatch is a failure
    assert rows[2]["code"] == "RATE_LIMITED" and rows[2]["quota_window"] == "TOKENS_MINUTE"
    assert FAKE_KEY not in json.dumps(rows)


def test_the_proof_command_refuses_without_the_enable_flag_and_reads_no_credential(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env = tmp_path / ".env"  # deliberately absent: reaching it would produce NO_CREDENTIAL instead
    assert generator.main(["--prove", "--env-file", str(env)]) == 2
    assert "--enable-live" in capsys.readouterr().err


@pytest.mark.parametrize(
    "extra",
    [["--max-completion-tokens", "999"], ["--max-calls", "7"], ["--models", "other/model"]],
)
def test_the_proof_command_enforces_the_authorised_limits(
    extra: list[str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = generator.main(["--prove", "--enable-live", "--env-file", str(tmp_path / ".env"), *extra])
    assert code == 2 and "REFUSED" in capsys.readouterr().err


def test_the_proof_command_reports_a_missing_credential_with_a_fixed_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = generator.main(["--prove", "--enable-live", "--env-file", str(tmp_path / "absent.env")])
    assert code == 2 and "NO_CREDENTIAL" in capsys.readouterr().err


def test_without_the_prove_flag_the_command_only_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert generator.main([]) == 2 and "--enable-live" in capsys.readouterr().out


# ----------------------------------------------------------------------------- real transport, local server


class _Handler(BaseHTTPRequestHandler):
    seen: ClassVar[list[tuple[str, str | None]]] = []

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers.get("content-length", 0)))
        type(self).seen.append((self.path, self.headers.get("authorization")))
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/target")
            self.end_headers()
            return
        body = b'{"model": "m", "choices": [{"message": {"content": "hi"}}]}'
        self.send_response(200)
        self.send_header("x-request-id", "req-1")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


@pytest.fixture
def local_server() -> Iterator[str]:
    _Handler.seen = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def test_the_real_transport_does_not_follow_redirects_and_so_never_forwards_the_key(local_server: str) -> None:
    transport = HttpxTransport(FAKE_KEY, timeout_seconds=5.0, url=local_server + "/redirect")
    response = transport.post({"model": QWEN})
    assert response.status == 302
    assert [path for path, _ in _Handler.seen] == ["/redirect"]  # /target was never requested


def test_the_real_transport_ignores_proxy_environment_variables(
    local_server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.setenv(name, "http://127.0.0.1:1")
    transport = HttpxTransport(FAKE_KEY, timeout_seconds=5.0, url=local_server + "/ok")
    response = transport.post({"model": QWEN})
    assert response.status == 200 and response.headers["x-request-id"] == "req-1"
    assert _Handler.seen == [("/ok", "Bearer " + FAKE_KEY)]  # the key goes only to the configured URL


def test_a_response_larger_than_the_cap_is_refused(local_server: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(generator, "MAX_RESPONSE_BYTES", 10)
    with pytest.raises(GenerationError) as caught:
        HttpxTransport(FAKE_KEY, timeout_seconds=5.0, url=local_server + "/ok").post({"model": QWEN})
    assert caught.value.code == "MODEL_RESPONSE_TOO_LARGE"


def test_a_pool_with_no_approved_models_cannot_be_built() -> None:
    with pytest.raises(GenerationError) as caught:
        GeneratorPool(
            replace(SETTINGS, models=("other/model",)),
            FakeTransport([]),
            enabled=True,
            assignment={Q1: "other/model"},
            call_budget=1,
        )
    assert caught.value.code == "MODEL_NOT_APPROVED"


def test_invalid_usage_values_are_dropped_to_null_not_trusted_or_zeroed() -> None:
    body = {"model": QWEN, "choices": [{"message": {"content": "x"}}],
            "usage": {"prompt_tokens": -5, "completion_tokens": "7", "total_tokens": True}}  # fmt: skip
    instance, _ = pool([TransportResponse(200, {}, json.dumps(body).encode())])
    record = instance.complete(Q1, MESSAGES).record
    assert (record.prompt_tokens, record.completion_tokens, record.total_tokens) == (None, None, None)


def test_a_response_without_text_is_not_a_pass_even_with_the_right_model() -> None:
    instance, _ = pool([ok(QWEN, text=None)])
    (row,) = prove(instance, [QWEN], {QWEN: Q1}, 64)
    assert row["result"] == "FAIL" and row["text_returned"] is False and row["served_model"] == QWEN


@pytest.mark.parametrize("extra", [["--max-calls", "0"], ["--max-completion-tokens", "0"]])
def test_zero_limits_are_refused_not_crashed(
    extra: list[str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = generator.main(["--prove", "--enable-live", "--env-file", str(tmp_path / ".env"), *extra])
    assert code == 2 and "REFUSED" in capsys.readouterr().err
