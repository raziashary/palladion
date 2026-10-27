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
    ErrorOrigin,
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
    ("text", "rule"),
    [
        ("", "NO_TEXT"), ("not json", "NOT_JSON"), ("[]", "NOT_IN_SCHEMA"), (good_json(extra=1), "NOT_IN_SCHEMA"),
        (good_json(action="IMPROVISE"), "VOCABULARY"), (good_json(evidence_status="MAYBE"), "VOCABULARY"),
        (good_json(policy_outcome="DUNNO"), "OUTCOME_VOCABULARY"), (good_json(policy_outcome=7), "FIELD_NOT_STRING"),
        (good_json(version_ids="POL-1"), "VERSION_IDS"), (good_json(claims="x"), "CLAIMS_NOT_LIST"),
        (good_json(claims=[1]), "CLAIM_NOT_OBJECT"), (good_json(abstention_reason="BECAUSE"), "VOCABULARY"),
        (good_json(claims=[{"kind": "WINDOW", "citations": "POL-1@v1#4.1"}]), "CLAIM_FIELD_TYPE"),
        pytest.param(
            good_json(claims=[{"kind": "WINDOW", "text": "x" * 100_000, "citations": []}]),
            "FIELD_INVALID",
            id="too-long",
        ),
    ],
)  # fmt: skip
def test_an_answer_outside_the_schema_is_rejected_with_the_rule_it_broke(
    text: str, rule: str, s_questions: tuple[GoldRecord, ...]
) -> None:
    from benchmark.track_b import ANSWER_RULES, AnswerRejected

    with pytest.raises(AnswerRejected) as caught:
        parse_answer(text, request_for(s_questions[0]), "run-1", [])
    assert caught.value.rule == rule and rule in ANSWER_RULES
    assert caught.value.ledger_flags == (f"ANSWER_REJECTED={rule}",)
    assert isinstance(caught.value, ContractError), "the Runner still classes it as a contract violation"


def test_an_unknown_answer_rule_cannot_be_made() -> None:
    from benchmark.track_b import AnswerRejected

    with pytest.raises(ValueError, match="unknown answer rule"):
        AnswerRejected("MADE_UP", "x")


def test_a_rejected_live_answer_leaves_its_rule_in_the_ledger_and_the_reply_nowhere(
    s_root: Path, s_published_corpus: PublishedCorpus, s_questions: tuple[GoldRecord, ...], tmp_path: Path
) -> None:
    from benchmark.generator import TransportResponse
    from benchmark.track_b import eligible_records

    class Rambling:
        def post(self, payload: Any) -> TransportResponse:
            reply = json.dumps({"evidence_status": "MAYBE", "answer_text": "SECRET-REPLY-CANARY"})
            body = {"model": STUB_MODEL, "choices": [{"message": {"content": reply}}],
                    "usage": {"prompt_tokens": 9, "completion_tokens": 9, "total_tokens": 18}}  # fmt: skip
            return TransportResponse(200, {}, json.dumps(body).encode())

    out = tmp_path / "rejected"
    spec = TrackBSpec("run-b-0008", "smoke", 10, 4000, s_root, out)
    plan = plan_assignment(eligible_records(s_questions, None), GENERATOR, spec, 7)
    pool = make_pool(out, dict(plan.assigned), Rambling())
    arms = {"R2": GoldRetriever("R2", s_published_corpus, s_questions)}
    execute_track_b(spec, arms, pool, plan, s_published_corpus, GENERATOR, pool_label="offline-stub")
    finals = [r for r in RunLedger(out / "ledger.jsonl").records if r.is_final]
    assert (
        finals
        and {r.status for r in finals} == {RunStatus.INVALID_RUN}
        and {r.code for r in finals} == {"CONTRACT_VIOLATION"}
    )
    assert {r.flags for r in finals} == {("ANSWER_REJECTED=VOCABULARY",)}
    assert "SECRET-REPLY-CANARY" not in "".join(f.read_text(encoding="utf-8") for f in out.glob("*.jsonl"))


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


# --------------------------------------------------------------------- the first live pass: subset, pace, failover


def test_a_subset_is_seeded_stratum_balanced_and_the_right_size(s_questions: tuple[GoldRecord, ...]) -> None:
    from benchmark.track_b import pick_subset

    eligible = [q for q in s_questions if "controlled_qa" in q.track_eligibility]
    chosen = pick_subset(eligible, 8, seed=7)
    assert len(chosen) == 8 == len(set(chosen)) and chosen == sorted(chosen)
    strata = [next(q.stratum.value for q in eligible if q.question_id == i) for i in chosen]
    assert len(set(strata)) == 8, "eight strata, one question each, before any stratum repeats"
    assert pick_subset(eligible, 8, seed=7) == chosen and pick_subset(eligible, 8, seed=8) != chosen
    assert len(pick_subset(eligible, 1000, seed=7)) == len(eligible)
    with pytest.raises(TrackAError, match="at least one"):
        pick_subset(eligible, 0, seed=7)


def test_a_question_recorded_as_asked_must_be_eligible(s_questions: tuple[GoldRecord, ...]) -> None:
    from benchmark.track_b import asked_records

    native_only = next(q for q in s_questions if "controlled_qa" not in q.track_eligibility)
    with pytest.raises(TrackAError, match="not eligible"):
        asked_records(s_questions, None, [native_only.question_id])
    assert asked_records(s_questions, None, None) == [q for q in s_questions if "controlled_qa" in q.track_eligibility]


def test_a_subset_run_asks_only_those_questions_and_is_scored_and_validated(
    s_root: Path, s_published_corpus: PublishedCorpus, s_questions: tuple[GoldRecord, ...], tmp_path: Path
) -> None:
    from benchmark.eval.score_answers import score_answer_run
    from benchmark.results_check import validate_run
    from benchmark.track_b import asked_records, pick_subset

    eligible = [q for q in s_questions if "controlled_qa" in q.track_eligibility]
    ids = tuple(pick_subset(eligible, 6, seed=7))
    out = tmp_path / "subset"
    spec = TrackBSpec("run-b-0006", "smoke", 10, 4000, s_root, out, question_ids=ids, case_deadline_seconds=300.0)
    plan = plan_assignment(asked_records(s_questions, None, ids), GENERATOR, spec, 7)
    pool = make_pool(out, dict(plan.assigned), ExtractiveStubTransport())
    arms = {"R2": GoldRetriever("R2", s_published_corpus, s_questions)}
    outcome = execute_track_b(spec, arms, pool, plan, s_published_corpus, GENERATOR, pool_label="offline-stub")
    assert outcome.questions == 6 and {r.question_id for r in RunLedger(out / "ledger.jsonl").records} == set(ids)
    config = json.loads((out / "run_config.json").read_text(encoding="utf-8"))
    assert config["asked"] == sorted(ids) and config["case_deadline_seconds"] == 300.0
    assert score_answer_run(run_dir=out, root=s_root).arms == ["R2"]
    assert validate_run(out, root=s_root) == []


def test_a_daily_limit_pauses_the_run_and_a_second_invocation_of_the_directory_completes_it(
    s_root: Path, s_published_corpus: PublishedCorpus, s_questions: tuple[GoldRecord, ...], tmp_path: Path
) -> None:
    from benchmark.eval.score_answers import score_answer_run
    from benchmark.generator import TransportResponse
    from benchmark.results_check import validate_run
    from benchmark.track_b import asked_records, pick_subset

    eligible = [q for q in s_questions if "controlled_qa" in q.track_eligibility]
    ids = tuple(pick_subset(eligible, 3, seed=7))
    message = "Rate limit reached for tokens per day (TPD). Please try again in 5h3m."
    refusal = TransportResponse(429, {}, json.dumps({"error": {"message": message}}).encode())

    class Refusing:
        def post(self, payload: Any) -> TransportResponse:
            return refusal

    out = tmp_path / "paused"
    spec = TrackBSpec("run-b-0007", "smoke", 10, 4000, s_root, out, question_ids=ids)
    plan = plan_assignment(asked_records(s_questions, None, ids), GENERATOR, spec, 7)
    arms = {"R2": GoldRetriever("R2", s_published_corpus, s_questions)}
    first = execute_track_b(
        spec, arms, make_pool(out, dict(plan.assigned), Refusing()), plan, s_published_corpus, GENERATOR,
        pool_label="offline-stub",
    )  # fmt: skip
    assert first.summary.quota_blocked_pairs == 3 and first.summary.status_counts == {}
    assert any("the run is paused" in f.render() for f in validate_run(out, root=s_root))

    second = execute_track_b(
        spec, arms, make_pool(out, dict(plan.assigned), ExtractiveStubTransport()), plan, s_published_corpus,
        GENERATOR, pool_label="offline-stub",
    )  # fmt: skip
    assert second.summary.quota_blocked_pairs == 0 and second.summary.status_counts == {"OK": 3}
    rows = [json.loads(line) for line in (out / "ledger.jsonl").read_text(encoding="utf-8").splitlines()]
    assert sorted((r["question_id"], r["attempt"], r["is_final"], r["code"]) for r in rows) == sorted(
        [(q, 1, False, "QUOTA_BLOCKED") for q in ids] + [(q, 2, True, None) for q in ids]
    )
    assert score_answer_run(run_dir=out, root=s_root).arms == ["R2"]
    assert validate_run(out, root=s_root) == []


def test_closing_a_paused_run_makes_it_complete_with_not_run_quota_blocked_pairs(
    s_root: Path, s_published_corpus: PublishedCorpus, s_questions: tuple[GoldRecord, ...], tmp_path: Path
) -> None:
    from benchmark.generator import TransportResponse
    from benchmark.results_check import validate_run
    from benchmark.track_b import asked_records, pick_subset

    eligible = [q for q in s_questions if "controlled_qa" in q.track_eligibility]
    ids = tuple(pick_subset(eligible, 2, seed=7))
    message = "Rate limit reached for tokens per day (TPD). Please try again in 5h3m."
    refusal = TransportResponse(429, {}, json.dumps({"error": {"message": message}}).encode())

    class Refusing:
        def post(self, payload: Any) -> TransportResponse:
            return refusal

    out = tmp_path / "closed"
    spec = TrackBSpec("run-b-0008", "smoke", 10, 4000, s_root, out, question_ids=ids, close_quota_blocked=True)
    plan = plan_assignment(asked_records(s_questions, None, ids), GENERATOR, spec, 7)
    arms = {"R2": GoldRetriever("R2", s_published_corpus, s_questions)}
    outcome = execute_track_b(
        spec, arms, make_pool(out, dict(plan.assigned), Refusing()), plan, s_published_corpus, GENERATOR,
        pool_label="offline-stub",
    )  # fmt: skip
    assert outcome.summary.quota_blocked_pairs == 2
    finals = [r for r in RunLedger(out / "ledger.jsonl").records if r.is_final]
    assert [(r.status, r.origin, r.code) for r in finals] == [
        (RunStatus.NOT_RUN, ErrorOrigin.HARNESS, "QUOTA_BLOCKED")
    ] * 2
    assert json.loads((out / "run_config.json").read_text(encoding="utf-8"))["quota_blocked_closed"] == 2
    assert validate_run(out, root=s_root) == []


def test_the_command_line_takes_a_subset_and_records_failover(s_root: Path, tmp_path: Path) -> None:
    out = tmp_path / "limit"
    done = run_script("--root", str(s_root), "--split", "smoke", "--out", str(out), "--run-id", "run-b-0007",
                      "--arms", "R0", "--limit-questions", "5", "--allow-failover", "--pace-seconds", "0",
                      "--case-deadline-seconds", "300")  # fmt: skip
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["questions"] == 5
    config = json.loads((out / "run_config.json").read_text(encoding="utf-8"))
    assert config["failover"] is True and len(config["asked"]) == 5
    manifest = read_verified(out / "manifest-R0.json")
    assert manifest.retrieval_config["generator"]["failover"] is True


# ------------------------------------------------------------------ paired endpoints and the daily limit (B08-T08.10)


def stats_settings() -> Any:
    from benchmark.config import load_evaluation_config

    return load_evaluation_config(ROOT / "configs" / "evaluation.yaml").statistics


def loss_matrix() -> Any:
    from benchmark.config import load_evaluation_config

    return load_evaluation_config(ROOT / "configs" / "evaluation.yaml").loss_matrix


def test_the_co_primary_endpoints_are_paired_with_the_reference_on_the_same_questions(
    s_root: Path, s_published_corpus: PublishedCorpus, s_questions: tuple[GoldRecord, ...], tmp_path: Path
) -> None:
    from benchmark.analysis.tables import answer_effects, render_answer_scorecard
    from benchmark.eval.abstention import loss_sweep
    from benchmark.eval.score_answers import score_answer_run, summarize_arm
    from benchmark.eval.statistics import StatisticsError

    arms = {
        "R2": GoldRetriever("R2", s_published_corpus, s_questions),
        "R3": GoldRetriever("R3", s_published_corpus, s_questions, empty=True),
        "R4": GoldRetriever("R4", s_published_corpus, s_questions, empty=True),
    }
    out, _ = run(s_root, tmp_path, s_published_corpus, s_questions, arms)
    score = score_answer_run(run_dir=out, root=s_root)
    settings = stats_settings()
    effects = answer_effects(score, reference="R3", primary="R2", stats=settings)
    coverage = next(e for e in effects if e.arm == "R2" and e.metric == "correct_answer")
    assert coverage.primary and coverage.only_arm is not None and coverage.only_reference is not None
    assert coverage.only_arm > coverage.only_reference == 0, (
        "the arm with the evidence answers what the empty one cannot"
    )
    assert coverage.difference.estimate > 0 and coverage.p_value is not None and coverage.adjusted_p is None
    twin = next(e for e in effects if e.arm == "R4" and e.metric == "correct_answer")
    assert twin.difference.estimate == 0 and twin.only_arm == twin.only_reference == 0 and twin.adjusted_p is not None
    with pytest.raises(StatisticsError, match="primary arm"):
        answer_effects(score, reference="R3", primary="R3", stats=settings)
    with pytest.raises(StatisticsError, match="reference arm"):
        answer_effects(score, reference="R9", primary=None, stats=settings)
    summaries = [summarize_arm(score, arm, loss_matrix()) for arm in score.arms]
    text = render_answer_scorecard(score, summaries, loss_sweep({}, {}, ()), effects)
    assert "paired with the reference" in text and "primary (unadjusted)" in text


def test_a_pair_a_daily_limit_stopped_is_in_no_rate_and_is_counted_apart(
    s_root: Path, s_published_corpus: PublishedCorpus, s_questions: tuple[GoldRecord, ...], tmp_path: Path
) -> None:
    from benchmark.analysis.tables import answer_effects
    from benchmark.eval.score_answers import score_answer_run, summarize_arm
    from benchmark.generator import TransportResponse
    from benchmark.track_b import asked_records, pick_subset

    eligible = [q for q in s_questions if "controlled_qa" in q.track_eligibility]
    ids = tuple(pick_subset(eligible, 4, seed=7))
    refusal = TransportResponse(
        429,
        {},
        json.dumps(
            {"error": {"message": "Rate limit reached for tokens per day (TPD). Please try again in 5h."}}
        ).encode(),
    )

    class Refusing:
        def post(self, payload: Any) -> TransportResponse:
            return refusal

    out = tmp_path / "blocked"
    spec = TrackBSpec("run-b-0009", "smoke", 10, 4000, s_root, out, question_ids=ids, close_quota_blocked=True)
    plan = plan_assignment(asked_records(s_questions, None, ids), GENERATOR, spec, 7)
    arms = {
        "R2": GoldRetriever("R2", s_published_corpus, s_questions),
        "R3": GoldRetriever("R3", s_published_corpus, s_questions, empty=True),
    }
    execute_track_b(
        spec, arms, make_pool(out, dict(plan.assigned), Refusing()), plan, s_published_corpus, GENERATOR,
        pool_label="offline-stub",
    )  # fmt: skip
    score = score_answer_run(run_dir=out, root=s_root)
    summary = summarize_arm(score, "R2", loss_matrix())
    assert summary.pairs == 4 and summary.quota_blocked == 4 and summary.states == {"QUOTA_BLOCKED": 4}
    endpoints = summary.endpoints
    assert endpoints.pairs == 0 and endpoints.coverage_itt is None and endpoints.directive_rate_worst_case is None
    assert answer_effects(score, reference="R3", primary="R2", stats=stats_settings()) == []


def test_the_daily_token_cap_stops_a_model_for_the_day_and_a_later_invocation_finishes_the_run(
    s_root: Path, tmp_path: Path
) -> None:
    out, books = tmp_path / "capped", tmp_path / "books"
    books.mkdir()
    base = ["--root", str(s_root), "--split", "smoke", "--out", str(out), "--run-id", "run-b-0200", "--arms", "R0",
            "--limit-questions", "5", "--ledger-root", str(books)]  # fmt: skip
    first = run_script(*base, "--daily-token-cap", "100")
    assert first.returncode == 0, first.stderr
    report = json.loads(first.stdout)
    assert report["status_counts"] == {"OK": 1} and report["quota_blocked_pairs"] == 4
    later = run_script(*base, "--daily-token-cap", "100000000")  # a new day: the cap is not reached
    assert later.returncode == 0, later.stderr
    assert json.loads(later.stdout)["quota_blocked_pairs"] == 0 and json.loads(later.stdout)["status_counts"] == {
        "OK": 4
    }
    rows = [json.loads(line) for line in (out / "ledger.jsonl").read_text(encoding="utf-8").splitlines()]
    assert sum(r["is_final"] for r in rows) == 5 and sum(r["code"] == "QUOTA_BLOCKED" for r in rows) == 4
