"""E3 and E4 over a real isolated Palladion at the pin, behind the counting proxy (B07-T04.01, B07-T00.01 to T00.04).

A real Palladion server is started in evaluator mode; its only route to a model is the benchmark's counting proxy, which
forwards to a scripted provider. The provider is a fake that answers Palladion's own prompts in Palladion's own formats:
it searches, quotes a source, passes the critic and repeats its draft at finalization. It makes no claim about model
quality; it exercises the system arm, the evaluator report, the counts and the run states.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from test_palladion_runtime import codeless_probe, mini_view, runtime

from benchmark.adapters.common import Condition, PublishedView
from benchmark.adapters.palladion import TABLE_FILE, PalladionArm
from benchmark.adapters.palladion_system import ARMS, TOOL_SCHEMAS, PalladionSystem
from benchmark.contracts import (
    ArmUnavailable,
    CapabilityUnsupported,
    CaseRequest,
    ContractError,
    EvidenceStatus,
    RunStatus,
    TransientInfrastructureError,
    classify_exception,
)
from benchmark.eval.critic import critic_case_from_trace, score_critic
from benchmark.eval.observable import Rate
from benchmark.eval.tool_use import ToolExpectation, check_arguments, reported_calls
from benchmark.generator import TransportResponse
from benchmark.llm_proxy import CountingProxy, ProxyLimits, ProxyServer

MODEL = "qwen/qwen3.8-27b"
TOKEN = "r" * 24
EVALUATION_TIME = "2026-10-18T03:00:00Z"
CRITIC = "You are the independent Evidence Critic"
FINAL = "Backend phase: FINALIZATION"


def completion(message: dict[str, Any], prompt: int = 100, completion_tokens: int = 20) -> TransportResponse:
    body = {
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", **message}}],
        "usage": {"prompt_tokens": prompt, "completion_tokens": completion_tokens, "total_tokens": prompt + 20},
    }
    return TransportResponse(200, {"content-type": "application/json"}, json.dumps(body).encode())


class Provider:
    """Answers Palladion's draft, critic and finalization prompts the way a cooperative model would."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.fail_with: int | None = None
        self.delay = 0.0

    def post(self, payload: Any) -> TransportResponse:
        messages = payload["messages"]
        system = str(messages[0]["content"])
        stage = "critic" if system.startswith(CRITIC) else "final" if FINAL in system else "draft"
        self.calls.append(stage)
        if self.delay:
            time.sleep(self.delay)
        if self.fail_with is not None:
            return TransportResponse(
                self.fail_with, {}, json.dumps({"error": {"code": "rate_limit_exceeded"}}).encode()
            )
        user = json.loads(messages[1]["content"])
        if stage == "critic":
            claims = user["draft"]["claims"] if user.get("draft") else []
            review = {
                "review_id": "r1", "verdict": "PASS", "proposed_disposition": "SUPPORTED",
                "claim_reviews": [
                    {"claim_id": c["id"], "finding": "SUPPORTED", "reason": "quoted from the source",
                     "evidence_ids": c["evidence_ids"]}
                    for c in claims
                ],
            }  # fmt: skip
            return completion({"content": json.dumps(review)})
        if stage == "final":
            return completion({"content": json.dumps(user["draft"])})
        tool = next((m for m in messages if m.get("role") == "tool"), None)
        if tool is None:
            arguments = json.dumps({"query": user["question"], "limit": 3})
            call = {
                "id": "call_1",
                "type": "function",
                "function": {"name": "search_knowledge", "arguments": arguments},
            }
            return completion({"content": None, "tool_calls": [call]})
        found = [d for d in json.loads(tool["content"])["data"] if d.get("kind") == "DOCUMENT"]
        claims = []
        if found:
            claims = [{"id": "C1", "type": "SOURCE_QUOTE", "text": found[0]["text_preview"][:120],
                       "evidence_ids": [found[0]["evidence_id"]]}]  # fmt: skip
        return completion({"content": json.dumps({"answer_kind": "INFORMATIONAL", "claims": claims,
                                                  "required_slots": [], "missing_slots": []})})  # fmt: skip


def case_request(query: str, principal: str, evaluation_time: str = EVALUATION_TIME) -> CaseRequest:
    return CaseRequest("q-0000000000000001", query, principal, "snap", evaluation_time, None, {}, 4000, None, 0)


@pytest.fixture(scope="module")
def prepared(qdrant_server: str) -> Iterator[None]:
    runtime.prepare(reset=True)
    yield


@pytest.fixture(scope="module")
def loaded(prepared: None, s_published: Path, tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """The mini corpus loaded once into the isolated runtime; the table maps its revisions to published documents."""
    view = mini_view(PublishedView.load(s_published))
    table = tmp_path_factory.mktemp("index") / TABLE_FILE
    with runtime.PalladionRuntime() as server:
        arm = PalladionArm(view, server.base_url, runtime.load_tokens(), condition=Condition.C1)
        arm.load_corpus(table)
        arm.close()
    target, probe = codeless_probe(view)
    return {"view": view, "table": table, "target": target, "probe": probe}


class Running:
    """Proxy, evaluator server and the system arm for one test; always stopped."""

    def __init__(self, arm_id: str, loaded: dict[str, Any], tmp_path: Path, provider: Provider, **over: Any) -> None:
        self.arm_id = arm_id
        self.loaded = loaded
        self.over = over
        limits = ProxyLimits(
            max_calls=40, max_tokens=1_000_000, max_completion_tokens=2000, pace_seconds=0.0, models=(MODEL,),
            max_tool_calls=8,
        )  # fmt: skip
        self.proxy = CountingProxy(provider, limits, record_path=tmp_path / f"proxy-{arm_id}.jsonl")
        self.proxy_server = ProxyServer(self.proxy, token=TOKEN)
        self.palladion: Any = None

    def __enter__(self) -> PalladionSystem:
        self.proxy_server.start()
        try:
            settings: dict[str, Any] = {
                "model": MODEL, "proxy_url": self.proxy_server.base_url, "token": TOKEN,
                "evaluation_time": EVALUATION_TIME, "completion_cap": 2000, "model_timeout": 60.0,
                "request_timeout": 60, **self.over,
            }  # fmt: skip
            self.palladion = runtime.evaluator_runtime(self.arm_id, **settings)
            self.palladion.start()
            connection = PalladionArm(
                self.loaded["view"], self.palladion.base_url, runtime.load_tokens(), condition=Condition.C1
            )
            connection.read_table(self.loaded["table"])
            return PalladionSystem(self.arm_id, connection, self.proxy.usage, evaluation_time=EVALUATION_TIME)
        except BaseException:
            self.__exit__()
            raise

    def __exit__(self, *_: object) -> None:
        if self.palladion is not None:
            self.palladion.stop()
        self.proxy_server.stop()


def principal_of(loaded: dict[str, Any]) -> str:
    return str(loaded["view"].identity.principals[0].principal_id)


# --------------------------------------------------------------------------- the real path


def test_e4_runs_the_critic_and_e3_does_not_and_both_report_what_the_proxy_counted(
    loaded: dict[str, Any], tmp_path: Path
) -> None:
    results = {}
    for arm_id in ("E4", "E3"):
        provider = Provider()
        with Running(arm_id, loaded, tmp_path, provider) as system:
            system.reset_case("q-0000000000000001")
            response = system.answer(case_request(loaded["probe"], principal_of(loaded)))
            results[arm_id] = (
                response,
                system.report_usage(),
                system.report_trace(),
                system.call_flags(),
                provider.calls,
            )
    full, full_usage, full_trace, full_flags, full_calls = results["E4"]
    without, no_usage, _, no_flags, no_calls = results["E3"]
    assert full_calls == ["draft", "draft", "critic", "final"] and no_calls == ["draft", "draft", "final"]
    assert full.critic is not None and full.critic.enabled and full.critic.calls == 1
    assert without.critic is not None and not without.critic.enabled and without.critic.calls is None
    assert (full_usage.main_calls, full_usage.critic_calls) == (3, 1) and (
        no_usage.main_calls,
        no_usage.critic_calls,
    ) == (3, 0)
    assert full_usage.prompt_tokens == 400 and full_usage.completion_tokens == 80, (
        "the proxy's book: 4 calls of 100 + 20"
    )
    assert no_usage.prompt_tokens == 300 and no_usage.tool_calls == 1
    assert "PALLADION_ARM=B6" in full_flags and "PALLADION_ARM=B5" in no_flags
    assert "USAGE_DIVERGES_FROM_PROXY" not in full_flags + no_flags
    assert full_trace[0]["proxy_delta"]["calls"] == 4 and full_trace[0]["divergence"] is False
    for response in (full, without):
        assert response.evidence_status is EvidenceStatus.SUPPORTED and response.claims
        assert response.model_invocations is not None and response.latency_ms is not None
    documents = {r.doc_id for r in loaded["view"].records}
    assert full.used_evidence_ids and all(c.split("#", 1)[0] in documents for c in full.used_evidence_ids), (
        "the quote maps to a published document"
    )
    assert all(c.kind is None for c in full.claims), "Palladion's own claim types are not the benchmark's vocabulary"
    assert full_trace[0]["palladion_claim_types"] == {"C1": "SOURCE_QUOTE"}

    # the metrics modules read what the adapter wrote: the critic score and the tool-use arguments, from the real trace
    case = critic_case_from_trace(full_trace[0], "c1", "label-1")
    score = score_critic([case], critic_enabled=True)
    assert score.cases == 1 and score.objection_recall == Rate(0, 0), "a clean draft has no defect to recall"
    calls = reported_calls(full_trace[0]["evaluator"])
    expectation = ToolExpectation(frozenset({"search_knowledge"}), TOOL_SCHEMAS)
    assert [c.name for c in calls] == ["search_knowledge"]
    assert all(check_arguments(c, expectation) is None for c in calls), "Palladion's own arguments validate"


def test_every_model_call_went_through_the_proxy_and_no_key_reached_the_server_log(
    loaded: dict[str, Any], tmp_path: Path
) -> None:
    provider = Provider()
    with Running("E4", loaded, tmp_path, provider) as system:
        system.reset_case("q-0000000000000001")
        system.answer(case_request(loaded["probe"], principal_of(loaded)))
        book = [json.loads(line) for line in (tmp_path / "proxy-E4.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["outcome"] for r in book] == ["OK"] * 4 and all(r["model"] == MODEL for r in book)
    log = (runtime.RUNTIME_ROOT.parent / "palladion-serve.log").read_text(encoding="utf-8", errors="replace")
    assert TOKEN not in log


def test_a_request_with_another_evaluation_time_is_unsupported_not_answered_on_the_wrong_clock(
    loaded: dict[str, Any], tmp_path: Path
) -> None:
    provider = Provider()
    with Running("E4", loaded, tmp_path, provider) as system:
        with pytest.raises(CapabilityUnsupported) as caught:
            system.answer(case_request(loaded["probe"], principal_of(loaded), "2026-10-19T03:00:00Z"))
        assert classify_exception(caught.value)[0] is RunStatus.FEATURE_NOT_SUPPORTED
    assert provider.calls == []


def test_a_server_running_another_arm_is_refused(loaded: dict[str, Any], tmp_path: Path) -> None:
    with Running("E3", loaded, tmp_path, Provider()) as system:
        mislabelled = PalladionSystem(
            "E4", system._connection, system._usage, evaluation_time=EVALUATION_TIME
        )  # fmt: skip
        mislabelled.reset_case("q-0000000000000001")
        with pytest.raises(ArmUnavailable, match="evaluator arm B6"):
            mislabelled.answer(case_request(loaded["probe"], principal_of(loaded)))


def test_a_provider_fault_is_a_transient_run_state_not_an_abstention(loaded: dict[str, Any], tmp_path: Path) -> None:
    provider = Provider()
    provider.fail_with = 429
    with Running("E4", loaded, tmp_path, provider) as system:
        system.reset_case("q-0000000000000001")
        with pytest.raises(TransientInfrastructureError, match="PROVIDER_HTTP_429"):
            system.answer(case_request(loaded["probe"], principal_of(loaded)))
        usage = system.report_usage()
    assert usage.prompt_tokens == 0, "a rejected call spent no tokens, and the failed answer is still in the usage"


def test_a_deadline_cut_is_a_timeout(loaded: dict[str, Any], tmp_path: Path) -> None:
    provider = Provider()
    provider.delay = 3.0
    with Running("E3", loaded, tmp_path, provider, request_timeout=1) as system:
        system.reset_case("q-0000000000000001")
        with pytest.raises(TimeoutError):
            system.answer(case_request(loaded["probe"], principal_of(loaded)))


def test_a_new_session_keeps_one_question_from_seeing_the_previous(loaded: dict[str, Any], tmp_path: Path) -> None:
    provider = Provider()
    with Running("E3", loaded, tmp_path, provider) as system:
        system.reset_case("q-0000000000000001")
        system.answer(case_request(loaded["probe"], principal_of(loaded)))
        first = system._session
        system.answer(case_request(loaded["probe"], principal_of(loaded)))
        assert system._session == first, "no reset: the same private session, as inside an episode"
        system.reset_case("q-0000000000000002")
        system.answer(case_request(loaded["probe"], principal_of(loaded)))
        assert system._session != first


# --------------------------------------------------------------------------- contract guards (no server)


def test_only_e3_and_e4_are_palladion_system_arms(loaded: dict[str, Any]) -> None:
    assert set(ARMS) == {"E3", "E4"}
    with pytest.raises(ContractError, match="not a Palladion system arm"):
        PalladionSystem("E0", None, dict, evaluation_time=None)  # type: ignore[arg-type]


def test_the_unreachable_server_is_not_run(loaded: dict[str, Any]) -> None:
    connection = PalladionArm(loaded["view"], "http://127.0.0.1:9", runtime.load_tokens(), condition=Condition.C1)
    system = PalladionSystem("E4", connection, dict, evaluation_time=None)
    system.reset_case("q-0000000000000001")
    with pytest.raises((ArmUnavailable, httpx.HTTPError)):
        system.answer(case_request(loaded["probe"], principal_of(loaded)))
    connection.close()
