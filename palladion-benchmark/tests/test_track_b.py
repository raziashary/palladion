"""Track B: one prompt, one generator and one gate for every retriever, run through the real Runner (B05-T05.01)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from support import cited, make_candidate, oracle

from benchmark.adapters.common import Condition, PublishedView
from benchmark.config import GeneratorSettings, load_benchmark_config
from benchmark.contracts import (
    CaseRequest,
    CaseResponse,
    ContractError,
    EvidenceCandidate,
    EvidenceStatus,
    RetrievalRequest,
    RunStatus,
)
from benchmark.eval.normalize import PublishedCorpus
from benchmark.fixtures.manifest import Split
from benchmark.fixtures.questions import GoldRecord
from benchmark.generator import GeneratorPool
from benchmark.run_manifest import read_verified
from benchmark.runner import RunLedger
from benchmark.track_a import TrackAError, build_local_arms
from benchmark.track_b import (
    PROMPT_DIGEST,
    STUB_MODEL,
    ExtractiveStubTransport,
    TrackBSpec,
    build_messages,
    execute_track_b,
    gate_flags,
    make_pool_paths,
    mixed_model_questions,
    parse_answer,
    plan_assignment,
)

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = load_benchmark_config(ROOT / "configs" / "benchmark.yaml").generator


class GoldRetriever:
    """A test-only retriever that returns the gold passages of each question (a perfect retriever)."""

    def __init__(
        self, arm_id: str, corpus: PublishedCorpus, records: tuple[GoldRecord, ...], *, empty: bool = False
    ) -> None:
        self.arm_id = arm_id
        self.corpus, self.empty = corpus, empty
        self.by_id = {r.question_id: r for r in records}

    def build_index(self, source_manifest_uri: str, index_namespace: str) -> None: ...

    def retrieve(self, request: RetrievalRequest) -> list[EvidenceCandidate]:
        if self.empty:
            return []
        return oracle(self.corpus, self.by_id[request.question_id])[: request.limit]

    def index_stats(self) -> dict[str, Any]:
        return {"arm": self.arm_id}

    def describe(self) -> dict[str, Any]:
        return {"arm": self.arm_id, "kind": "test-only gold retriever"}


def case(record: GoldRecord) -> CaseRequest:
    return CaseRequest(record.question_id, record.query, record.principal_id, record.corpus_snapshot_id,
                       record.evaluation_time, record.event_time, {}, 4000, None, 0)  # fmt: skip


def make_pool(
    out: Path, plan_assigned: dict[str, str], transport: Any, settings: GeneratorSettings = GENERATOR
) -> GeneratorPool:
    records, prompts = make_pool_paths(out)
    return GeneratorPool(
        settings, transport, enabled=True, assignment=plan_assigned, call_budget=10_000,
        record_path=records, prompt_path=prompts, wall_clock=lambda: datetime(2026, 10, 18, 3, 0, tzinfo=UTC),
    )  # fmt: skip


def run(
    s_root: Path,
    tmp: Path,
    corpus: PublishedCorpus,
    records: tuple[GoldRecord, ...],
    arms: Mapping[str, GoldRetriever],
    *,
    settings: GeneratorSettings = GENERATOR,
    withdrawn: dict[str, str] | None = None,
    split: str = "smoke",
    run_id: str = "run-b-0001",
) -> tuple[Path, Any]:
    out = tmp / run_id
    spec = TrackBSpec(run_id, split, 10, 4000, s_root, out, withdrawn=withdrawn)
    from benchmark.track_b import eligible_records

    plan = plan_assignment(eligible_records(records, withdrawn), settings, spec, 7)
    pool = make_pool(out, dict(plan.assigned), ExtractiveStubTransport(), settings)
    outcome = execute_track_b(spec, arms, pool, plan, corpus, settings, pool_label="offline-stub")
    return out, outcome


def good_json(**over: object) -> str:
    base: dict[str, object] = {
        "evidence_status": "SUPPORTED", "abstention_reason": None, "action": "ANSWER", "policy_outcome": None,
        "version_ids": ["POL-1@v1"], "answer_text": "ok",
        "claims": [{"kind": "WINDOW", "params": {"hours": 24}, "text": "w", "citations": ["POL-1@v1#4.1"]}],
    }  # fmt: skip
    return json.dumps({**base, **over})


# --------------------------------------------------------------------------- the shared prompt


def test_the_prompt_is_the_same_for_every_arm_and_differs_only_in_the_evidence(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus
) -> None:
    record = next(q for q in s_questions if q.stratum.value == "Q2")
    shown = oracle(s_published_corpus, record)
    first, ids_first = build_messages(case(record), shown, s_published_corpus)
    second, ids_second = build_messages(case(record), list(shown), s_published_corpus)
    assert first == second and ids_first == ids_second and first[0]["content"].strip()
    empty, ids_empty = build_messages(case(record), [], s_published_corpus)
    assert empty[0] == first[0] and ids_empty == [] and "no passages were retrieved" in empty[1]["content"]
    assert all(i in first[1]["content"] for i in ids_first) and ids_first


def test_the_prompt_never_carries_a_gold_marker_or_the_gold_answer(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus, s_golds: tuple[Any, ...]
) -> None:
    from benchmark.contracts import screen_arm_visible

    for record, gold in zip(s_questions, s_golds, strict=True):
        messages, _ = build_messages(case(record), oracle(s_published_corpus, record), s_published_corpus)
        for message in messages:
            screen_arm_visible("prompt", message["content"])
        assert gold.source_sha256 not in messages[1]["content"]


def test_the_prompt_digest_is_the_digest_of_the_system_prompt() -> None:
    from benchmark.fixtures import sha256_hex
    from benchmark.track_b import SYSTEM_PROMPT

    assert sha256_hex(SYSTEM_PROMPT) == PROMPT_DIGEST


# --------------------------------------------------------------------------- reading the answer


def request_for(record: GoldRecord) -> CaseRequest:
    return case(record)


def test_a_valid_answer_becomes_a_case_response_with_the_delivered_ids(s_questions: tuple[GoldRecord, ...]) -> None:
    record = s_questions[0]
    response = parse_answer(good_json(), request_for(record), "run-1", ["POL-1@v1#4.1", "POL-1@v1"])
    assert isinstance(response, CaseResponse) and response.evidence_status is EvidenceStatus.SUPPORTED
    assert response.action == "ANSWER" and response.version_ids == ("POL-1@v1",)
    assert response.used_evidence_ids == ("POL-1@v1#4.1", "POL-1@v1")
    assert response.claims[0].kind == "WINDOW" and dict(response.claims[0].params) == {"hours": 24}


@pytest.mark.parametrize(
    "text",
    [
        "", "not json", "[]", good_json(extra=1), good_json(action="IMPROVISE"), good_json(evidence_status="MAYBE"),
        good_json(policy_outcome="DUNNO"), good_json(version_ids="POL-1"), good_json(claims="x"),
        good_json(claims=[1]), good_json(abstention_reason="BECAUSE"),
    ],
)  # fmt: skip
def test_an_answer_outside_the_schema_is_an_invalid_answer(text: str, s_questions: tuple[GoldRecord, ...]) -> None:
    with pytest.raises(ContractError):
        parse_answer(text, request_for(s_questions[0]), "run-1", [])


def test_an_unknown_claim_kind_is_kept_as_unclassified_not_dropped(s_questions: tuple[GoldRecord, ...]) -> None:
    claims = [{"kind": "SOMETHING_NEW", "params": {}, "text": "t", "citations": []}]
    response = parse_answer(good_json(claims=claims), request_for(s_questions[0]), "run-1", [])
    assert response.claims[0].kind is None and response.claims[0].text == "t"


def test_the_gate_records_a_citation_outside_the_bundle_and_leaves_the_answer_alone(
    s_questions: tuple[GoldRecord, ...],
) -> None:
    record = s_questions[0]
    outside = parse_answer(good_json(), request_for(record), "run-1", ["POL-2@v1#4.1"])
    assert gate_flags(outside) == ("CITATION_OUTSIDE_BUNDLE=1",) and outside.claims[0].citations == ("POL-1@v1#4.1",)
    inside = parse_answer(good_json(), request_for(record), "run-1", ["POL-1@v1#4.1"])
    assert gate_flags(inside) == ()
    document_level = parse_answer(
        good_json(claims=[{"kind": "WINDOW", "params": {"hours": 1}, "text": "t", "citations": ["POL-1@v1"]}]),
        request_for(record), "run-1", ["POL-1@v1#4.1"],
    )  # fmt: skip
    assert gate_flags(document_level) == ()


# --------------------------------------------------------------------------- through the Runner


def test_every_arm_answers_every_eligible_question_through_the_runner(
    s_root: Path, s_published_corpus: PublishedCorpus, s_questions: tuple[GoldRecord, ...], tmp_path: Path
) -> None:
    arms = {
        "R2": GoldRetriever("R2", s_published_corpus, s_questions),
        "R3": GoldRetriever("R3", s_published_corpus, s_questions, empty=True),
    }
    out, outcome = run(s_root, tmp_path, s_published_corpus, s_questions, arms)
    eligible = [q for q in s_questions if "controlled_qa" in q.track_eligibility]
    assert outcome.questions == len(eligible) < len(s_questions) and outcome.arms == ("R2", "R3")
    finals = [r for r in RunLedger(out / "ledger.jsonl").records if r.is_final]
    assert len(finals) == 2 * len(eligible) and {r.status for r in finals} == {RunStatus.OK}
    assert all(any(f.startswith("GENERATOR_MODEL=") for f in r.flags) for r in finals if r.flags)
    manifest = read_verified(out / "manifest-R2.json")
    assert manifest.track.value == "controlled_qa" and manifest.prompt_digest == PROMPT_DIGEST
    assert manifest.generator_assignment_sha256 and manifest.retrieval_config["generator"]["single_model"] is True
    assert manifest.retrieval_config["generator"]["live"] is False


def test_the_prompt_and_generation_records_are_kept_for_every_call(
    s_root: Path, s_published_corpus: PublishedCorpus, s_questions: tuple[GoldRecord, ...], tmp_path: Path
) -> None:
    arms = {"R2": GoldRetriever("R2", s_published_corpus, s_questions)}
    out, outcome = run(s_root, tmp_path, s_published_corpus, s_questions, arms)
    prompts = [json.loads(line) for line in (out / "prompts.jsonl").read_text(encoding="utf-8").splitlines()]
    records = [json.loads(line) for line in (out / "generation_records.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(prompts) == len(records) == outcome.questions
    assert {p["arm_id"] for p in prompts} == {"R2"} and {r["served_model"] for r in records} == {STUB_MODEL}
    by_hash = {p["prompt_sha256"] for p in prompts}
    assert {r["prompt_sha256"] for r in records} == by_hash


def test_arms_see_the_same_system_prompt_and_only_the_evidence_differs(
    s_root: Path, s_published_corpus: PublishedCorpus, s_questions: tuple[GoldRecord, ...], tmp_path: Path
) -> None:
    arms = {
        "R2": GoldRetriever("R2", s_published_corpus, s_questions),
        "R3": GoldRetriever("R3", s_published_corpus, s_questions, empty=True),
    }
    out, _ = run(s_root, tmp_path, s_published_corpus, s_questions, arms)
    prompts = [json.loads(line) for line in (out / "prompts.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {p["messages"][0]["content"] for p in prompts} == {p["messages"][0]["content"] for p in prompts[:1]}
    by_question: dict[str, dict[str, str]] = {}
    for p in prompts:
        by_question.setdefault(p["question_id"], {})[p["arm_id"]] = p["messages"][1]["content"]
    for texts in by_question.values():
        assert texts["R2"].split("\n\nEvidence passages:")[0] == texts["R3"].split("\n\nEvidence passages:")[0]


def test_withdrawn_questions_and_native_only_questions_are_not_asked(
    s_root: Path, s_published_corpus: PublishedCorpus, s_questions: tuple[GoldRecord, ...], tmp_path: Path
) -> None:
    gone = next(q for q in s_questions if "controlled_qa" in q.track_eligibility)
    arms = {"R2": GoldRetriever("R2", s_published_corpus, s_questions)}
    out, _ = run(s_root, tmp_path, s_published_corpus, s_questions, arms, withdrawn={gone.question_id: "defect"})
    asked = {r.question_id for r in RunLedger(out / "ledger.jsonl").records}
    native_only = {q.question_id for q in s_questions if "controlled_qa" not in q.track_eligibility}
    assert gone.question_id not in asked and not (asked & native_only)
    assert json.loads((out / "run_config.json").read_text(encoding="utf-8"))["withdrawn"] == [gone.question_id]


def test_questions_no_budget_covers_are_not_run_for_every_arm(
    s_root: Path, s_published_corpus: PublishedCorpus, s_questions: tuple[GoldRecord, ...], tmp_path: Path
) -> None:
    primary = GENERATOR.models[0]
    settings = replace(GENERATOR, token_budgets={**GENERATOR.token_budgets, primary: 6000 * 5})
    arms = {
        "R2": GoldRetriever("R2", s_published_corpus, s_questions),
        "R3": GoldRetriever("R3", s_published_corpus, s_questions, empty=True),
    }
    out, outcome = run(s_root, tmp_path, s_published_corpus, s_questions, arms, settings=settings)
    finals = [r for r in RunLedger(out / "ledger.jsonl").records if r.is_final]
    unassigned = set(outcome.unassigned)
    assert len(unassigned) > 0 and len(outcome.unassigned) == outcome.questions - 5
    for r in finals:
        if r.question_id in unassigned:
            assert (r.status, r.code, r.origin.value if r.origin else None) == (
                RunStatus.NOT_RUN, "ASSIGNMENT_MISSING", "HARNESS",
            )  # fmt: skip
        else:
            assert r.status is RunStatus.OK
    assert {r.arm for r in finals if r.question_id in unassigned} == {"R2", "R3"}


def test_a_gold_marked_passage_is_refused_before_any_generator_call(
    s_root: Path, s_published_corpus: PublishedCorpus, s_questions: tuple[GoldRecord, ...], tmp_path: Path
) -> None:
    class Leaky(GoldRetriever):
        def retrieve(self, request: RetrievalRequest) -> list[EvidenceCandidate]:
            return [make_candidate("the expected answer is 168 hours", 1)]

    arms = {"R2": Leaky("R2", s_published_corpus, s_questions)}
    out, _ = run(s_root, tmp_path, s_published_corpus, s_questions, arms)
    finals = [r for r in RunLedger(out / "ledger.jsonl").records if r.is_final]
    assert {r.status for r in finals} == {RunStatus.INVALID_RUN} and {r.code for r in finals} == {"CONTRACT_VIOLATION"}
    assert not (out / "generation_records.jsonl").exists(), "no generator call was made"


def test_a_provider_deadline_is_a_timeout_from_the_provider_not_an_arm_fault(
    s_root: Path, s_published_corpus: PublishedCorpus, s_questions: tuple[GoldRecord, ...], tmp_path: Path
) -> None:
    import benchmark.track_b as track_b

    original = track_b.DEADLINE_MARGIN_SECONDS
    track_b.DEADLINE_MARGIN_SECONDS = 1e9  # the call cannot finish before its deadline
    try:
        arms = {"R2": GoldRetriever("R2", s_published_corpus, s_questions)}
        out, _ = run(s_root, tmp_path, s_published_corpus, s_questions, arms)
    finally:
        track_b.DEADLINE_MARGIN_SECONDS = original
    finals = [r for r in RunLedger(out / "ledger.jsonl").records if r.is_final]
    assert {r.status for r in finals} == {RunStatus.TIMEOUT} and {r.code for r in finals} == {"GENERATION_DEADLINE"}
    assert {r.origin.value for r in finals if r.origin} == {"PROVIDER"}


def test_the_locked_test_split_is_refused(
    s_root: Path, s_published_corpus: PublishedCorpus, s_questions: tuple[GoldRecord, ...], tmp_path: Path
) -> None:
    arms = {"R2": GoldRetriever("R2", s_published_corpus, s_questions)}
    with pytest.raises(TrackAError, match="locked test split"):
        run(s_root, tmp_path, s_published_corpus, s_questions, arms, split=Split.TEST.value)


def test_a_run_over_a_real_local_arm_completes(
    s_root: Path, s_published_corpus: PublishedCorpus, s_questions: tuple[GoldRecord, ...], tmp_path: Path
) -> None:
    view = PublishedView.load(s_root / "published")
    local, _ = build_local_arms(view, ["R0"], condition=Condition.C2, index_dir=tmp_path / "index")
    out = tmp_path / "real"
    spec = TrackBSpec("run-b-0002", "smoke", 10, 4000, s_root, out)
    from benchmark.track_b import eligible_records

    plan = plan_assignment(eligible_records(s_questions, None), GENERATOR, spec, 7)
    pool = make_pool(out, dict(plan.assigned), ExtractiveStubTransport())
    outcome = execute_track_b(spec, local, pool, plan, s_published_corpus, GENERATOR, pool_label="offline-stub")
    assert outcome.summary.status_counts == {"OK": outcome.questions}


# --------------------------------------------------------------------------- pairing across models


def test_a_pair_whose_arms_ran_on_different_generator_models_is_flagged(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    rows = [
        {"question_id": "q-1", "arm_id": "R2", "status": "OK", "served_model": "m-a", "requested_model": "m-a"},
        {"question_id": "q-1", "arm_id": "R3", "status": "OK", "served_model": "m-b", "requested_model": "m-b"},
        {"question_id": "q-2", "arm_id": "R2", "status": "OK", "served_model": "m-a", "requested_model": "m-a"},
        {"question_id": "q-2", "arm_id": "R3", "status": "OK", "served_model": "m-a", "requested_model": "m-a"},
        {
            "question_id": "q-3",
            "arm_id": "R2",
            "status": "RATE_LIMITED",
            "served_model": None,
            "requested_model": "m-z",
        },
        {"question_id": "q-3", "arm_id": "R2", "status": "OK", "served_model": "m-a", "requested_model": "m-a"},
        {"question_id": "q-3", "arm_id": "R3", "status": "OK", "served_model": "m-a", "requested_model": "m-a"},
    ]
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    assert mixed_model_questions(path) == ["q-1"]
    assert mixed_model_questions(tmp_path / "missing.jsonl") == []


def test_the_stand_in_transport_answers_from_the_delivered_passages_only(s_published_corpus: PublishedCorpus) -> None:
    doc = next(d for d in s_published_corpus.docs.values() if d.clauses and "hours" in d.text)
    clause = next(c for c, (s, e) in doc.clauses.items() if "hours" in doc.text[s:e])
    candidate = cited(s_published_corpus, __import__("benchmark.fixtures.questions", fromlist=["Citation"]).Citation(
        doc.record.doc_id, clause, 0, 1, "x"), 1)  # fmt: skip
    request = CaseRequest("q-00000001", "how long?", "P-1", "snap", "2026-10-18T03:00:00Z", None, {}, 4000, None, 0)
    messages, ids = build_messages(request, [candidate], s_published_corpus)
    transport = ExtractiveStubTransport()
    body = json.loads(transport.post({"messages": messages}).body)
    answer = json.loads(body["choices"][0]["message"]["content"])
    assert answer["action"] == "ANSWER" and answer["claims"][0]["citations"][0] in ids
    none = json.loads(
        json.loads(transport.post({"messages": build_messages(request, [], s_published_corpus)[0]}).body)["choices"][0][
            "message"
        ]["content"]
    )
    assert none["action"] == "NO_SUPPORT" and none["claims"] == [] and transport.calls == 2


# --------------------------------------------------------------------------- the command line


def run_script(*args: str) -> Any:
    import subprocess
    import sys

    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_track_b.py"), *args],
        capture_output=True, text=True, check=False, timeout=900,
    )  # fmt: skip


def test_the_command_line_runs_the_offline_stand_in_end_to_end(s_root: Path, tmp_path: Path) -> None:
    out = tmp_path / "cli"
    done = run_script("--root", str(s_root), "--split", "smoke", "--out", str(out), "--run-id", "run-b-0003",
                      "--arms", "R0", "--generator", "stub")  # fmt: skip
    assert done.returncode == 0, done.stderr
    summary = json.loads(done.stdout)
    assert summary["generator"] == "offline-stub" and summary["unassigned"] == 0
    assert summary["status_counts"] == {"OK": summary["questions"]}
    assert (out / "prompts.jsonl").exists() and (out / "manifest-R0.json").exists()


def test_a_live_run_is_refused_without_the_flag_and_without_a_call_budget_and_reads_no_credential(
    s_root: Path, tmp_path: Path
) -> None:
    probe = tmp_path / "must-not-be-read.env"  # absent on purpose: a read would fail differently
    base = ["--root", str(s_root), "--split", "smoke", "--out", str(tmp_path / "x"), "--run-id", "run-b-0004",
            "--arms", "R0", "--env-file", str(probe)]  # fmt: skip
    no_flag = run_script(*base, "--generator", "live", "--call-budget", "5")
    assert no_flag.returncode == 2 and "--enable-live" in no_flag.stderr
    no_budget = run_script(*base, "--generator", "live", "--enable-live")
    assert no_budget.returncode == 2 and "--call-budget" in no_budget.stderr
    wrong = run_script(*base, "--generator", "stub", "--enable-live")
    assert wrong.returncode == 2 and "--generator live" in wrong.stderr
    assert not (tmp_path / "x").exists(), "nothing was started"


def test_the_command_line_refuses_the_locked_test_split(s_root: Path, tmp_path: Path) -> None:
    done = run_script("--root", str(s_root), "--split", "test", "--out", str(tmp_path / "y"), "--run-id", "run-b-0005",
                      "--arms", "R0")  # fmt: skip
    assert done.returncode == 2 and "locked test split" in done.stderr


# --------------------------------------------------------------------------- audit fixes (aud-1, 6, 9)


def test_every_final_record_carries_the_generator_model_and_the_gate_notes_in_the_ledger(
    s_root: Path, s_published_corpus: PublishedCorpus, s_questions: tuple[GoldRecord, ...], tmp_path: Path
) -> None:
    arms = {"R2": GoldRetriever("R2", s_published_corpus, s_questions)}
    out, _ = run(s_root, tmp_path, s_published_corpus, s_questions, arms)
    finals = [r for r in RunLedger(out / "ledger.jsonl").records if r.is_final]
    assert finals and all(f"GENERATOR_MODEL={STUB_MODEL}" in r.flags for r in finals)


def test_a_passage_with_a_blank_line_is_read_back_whole(s_published_corpus: PublishedCorpus) -> None:
    from benchmark.track_b import prompt_ids, prompt_passages

    doc = next(d for d in s_published_corpus.docs.values() if d.clauses)
    clause = next(iter(doc.clauses))
    start, end = doc.clauses[clause]
    body = doc.text[start:end] + "\n\nsecond paragraph of the same passage"
    candidate = make_candidate(body, 1, source_document_id=doc.record.doc_id, locator=f"clause:{clause}")
    request = CaseRequest("q-00000001", "q", "P-1", "snap", "2026-10-18T03:00:00Z", None, {}, 4000, None, 0)
    messages, ids = build_messages(request, [candidate], s_published_corpus)
    passages = prompt_passages(messages[1]["content"])
    assert len(passages) == 1 and passages[0][1] == body.strip() and passages[0][0] == ids
    assert prompt_ids(messages[1]["content"]) == ids


def test_the_ids_the_generator_was_shown_are_read_back_from_the_kept_prompts(
    s_root: Path, s_published_corpus: PublishedCorpus, s_questions: tuple[GoldRecord, ...], tmp_path: Path
) -> None:
    from benchmark.track_b import read_prompt_ids

    arms = {"R2": GoldRetriever("R2", s_published_corpus, s_questions)}
    out, _ = run(s_root, tmp_path, s_published_corpus, s_questions, arms)
    shown = read_prompt_ids(out / "prompts.jsonl")
    answers = [r for r in RunLedger(out / "ledger.jsonl").records if r.is_final and r.payload]
    assert shown and all(shown[(r.question_id, "R2")] == r.payload["used_evidence_ids"] for r in answers)
    assert read_prompt_ids(tmp_path / "missing.jsonl") == {}


def test_the_reported_usage_counts_every_generator_call_including_a_rate_limit_retry(
    s_published_corpus: PublishedCorpus, s_questions: tuple[GoldRecord, ...]
) -> None:
    from benchmark.generator import TransportResponse
    from benchmark.track_b import ControlledQaSystem

    record = next(q for q in s_questions if "controlled_qa" in q.track_eligibility)
    limited = TransportResponse(
        429, {"retry-after": "1"}, json.dumps({"error": {"message": "tokens per minute"}}).encode()
    )
    stub = ExtractiveStubTransport()

    class RateLimitedOnce:
        calls = 0

        def post(self, payload: Any) -> TransportResponse:
            self.calls += 1
            return limited if self.calls == 1 else stub.post(payload)

    pool = GeneratorPool(
        GENERATOR, RateLimitedOnce(), enabled=True, assignment={record.question_id: GENERATOR.models[0]},
        call_budget=10, sleep=lambda _s: None, wall_clock=lambda: datetime(2026, 10, 18, 3, 0, tzinfo=UTC),
    )  # fmt: skip
    system = ControlledQaSystem(
        "R2", GoldRetriever("R2", s_published_corpus, s_questions), pool, s_published_corpus,
        k=10, run_id="run-usage", case_deadline_seconds=120.0,
    )  # fmt: skip
    system.answer(case(record))
    usage = system.report_usage()
    assert usage.main_calls == 2 and usage.prompt_tokens is not None
    assert system.report_trace()[0]["step"] == "retrieve"
