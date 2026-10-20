from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from evidence_agent.core.evaluation import macro_average, score_ranked_references


def test_p08_rates_distinguish_absence_zero_and_refusal_utility():
    from evidence_agent.core.evaluation import measured_rate, score_study_rows
    assert measured_rate(0, 3)["value"] == 0
    assert measured_rate(0, 0)["status"] == "NOT_APPLICABLE"
    with pytest.raises(ValueError):
        measured_rate(2, 1)
    with pytest.raises(ValueError):
        measured_rate(None, None)
    rows = [{"case_id":"case", "arm":"B0", "repetition":0, "status":"RECEIVED",
        "response":{"disposition":"NOT_ESTABLISHED"}, "elapsed_seconds":1,
        "calls":1,"usage":{},"citation_readback":False,
        "expected_disposition":"SUPPORTED","slices":["answerable","en"]}]
    report = score_study_rows(rows)["B0"]
    assert report["disposition_accuracy_all_attempts"]["value"] == 0
    assert report["semantic_support_precision"]["value"] is None
    assert report["human_usefulness"]["status"] == "UNKNOWN"
    assert report["usage_missing_runs"] == 1 and report["billing"]["value"] is None
    partial=score_study_rows([{**rows[0],"calls":2,"attempt_usage":[{"total_tokens":73},None]}])["B0"]
    assert partial["known_received_tokens"]==73 and partial["usage_missing_attempts"]==1
    assert partial["usage_missing_runs"]==1 and partial["billing"]["value"] is None
    with pytest.raises(ValueError, match="Duplicate"):
        score_study_rows(rows + rows)
    with pytest.raises(ValueError, match="Missing actual"):
        score_study_rows([{}])


def test_p08_split_rejects_family_and_near_duplicate_leakage():
    from evidence_agent.core.evaluation import validate_study_split
    dev={"case_id":"d","family_id":"f1","split":"development",
         "document":"apples pears oranges lemons fruit orchard"}
    evaluation={"case_id":"e","family_id":"f2","split":"evaluation",
                "document":"wheels doors engines tyres vehicle highway"}
    assert validate_study_split([dev,evaluation]) == {"development":["d"],"evaluation":["e"]}
    with pytest.raises(ValueError, match="family crosses"):
        validate_study_split([dev,{**evaluation,"family_id":"f1"}])
    with pytest.raises(ValueError, match="Near-duplicate"):
        validate_study_split([dev,{**evaluation,"document":dev["document"]+" new"}])
    with pytest.raises(ValueError):
        validate_study_split([dev,dev,evaluation])


def test_p08_case_clustered_intervals_do_not_count_repetitions_as_cases():
    from evidence_agent.core.evaluation import clustered_difference, latency_summary
    rows=[{"case_id":"a","control":0,"treatment":1}]*4+[
        {"case_id":"b","control":1,"treatment":0},
        {"case_id":"c","control":None,"treatment":0}]
    report=clustered_difference(rows)
    assert report["case_clusters"] == 2 and report["difference"] == 0
    assert report["missing_pairs"] == 1 and report["generalization_claim"] is False
    assert clustered_difference([])["interval95"] is None
    assert latency_summary([])["p95"] is None
    assert latency_summary([1,3])["p50"] == 2
    with pytest.raises(ValueError):
        latency_summary([float("nan")])


def _p08_manifest():
    names=("dirty_patch_sha256 corpus_sha256 gold_sha256 split_sha256 protocol_sha256 "
           "prompt_sha256 dependency_lock_sha256 scope_sha256").split()
    manifest={name:"a"*64 for name in names}
    manifest.update(schema_version="p08.1",study_id="pilot",phase="development",
        annotation_status="PILOT_NOT_HUMAN_ADJUDICATED",revision="revision",
        model="openai/gpt-oss-20b",representations={},generations=[],hardware={},
        cache="cold",randomness={"repetitions":2},budgets={"calls":100},
        treatments=["B0","B1"],created_at="2026-10-19T00:00:00Z")
    return manifest


def test_p08_manifest_requires_complete_frozen_inputs_and_finite_json():
    from evidence_agent.core.evaluation import canonical_digest, validate_run_manifest
    manifest=_p08_manifest()
    validate_run_manifest(manifest)
    changed=dict(manifest)
    changed.pop("gold_sha256")
    with pytest.raises(ValueError):
        validate_run_manifest(changed)
    with pytest.raises(ValueError):
        canonical_digest({"measurement":float("nan")})
    with pytest.raises(ValueError,match="Independent annotation"):
        validate_run_manifest({**manifest,"annotation_status":"ADJUDICATED"})


def test_p08_replay_binds_actual_plan_outputs_calls_and_source_snapshot(tmp_path):
    import hashlib
    import json

    from evidence_agent.core.evaluation import canonical_digest
    from evidence_agent.evaluation.study import replay_study
    manifest=_p08_manifest()
    files={"manifest.json":manifest,"inputs.json":{"config":{"limitations":["unit guard only"]},
        "order":[["case","B0",0]]},"source_snapshot.json":{"module":"source"}}
    for name,value in files.items():
        (tmp_path/name).write_text(json.dumps(value),encoding="utf-8")
    row={"case_id":"case","arm":"B0","repetition":0,"status":"RECEIVED","calls":1,
        "call_numbers":[1],"usage":{},"elapsed_seconds":1,"citation_readback":False,
        "response":{"disposition":"NOT_ESTABLISHED"},"expected_disposition":"SUPPORTED","slices":["en"]}
    (tmp_path/"rows.jsonl").write_text(json.dumps(row)+"\n",encoding="utf-8")
    (tmp_path/"calls.jsonl").write_text(json.dumps({"number":1,"event":"STARTED"})+"\n"+
        json.dumps({"number":1,"event":"FINISHED"})+"\n",encoding="utf-8")
    completion={"manifest_sha256":canonical_digest(manifest),"actual_rows":1,"expected_rows":1}
    for name,filename in (("rows","rows.jsonl"),("calls","calls.jsonl"),("inputs","inputs.json"),
                          ("source_snapshot","source_snapshot.json")):
        completion[name+"_sha256"]=hashlib.sha256((tmp_path/filename).read_bytes()).hexdigest()
    (tmp_path/"completion.json").write_text(json.dumps(completion),encoding="utf-8")
    replay = replay_study(tmp_path)
    assert replay["rows"]==1
    assert replay["configuration_binding"]["adapters_yaml_bound"] is False
    assert replay["retrieval_measurement_limits"]["candidate_stage_metrics"] is None
    assert replay["retrieval_measurement_limits"]["legacy_cutoffs_withdrawn"] == [5, 10, 20]
    (tmp_path/"source_snapshot.json").write_text('{}',encoding="utf-8")
    with pytest.raises(ValueError,match="digest mismatch"):
        replay_study(tmp_path)


def test_p08_document_only_prompt_matches_one_call_no_tool_capability():
    from evidence_agent.evaluation.study import BASELINE_INSTRUCTIONS
    assert "No functions, tools" in BASELINE_INSTRUCTIONS
    assert "Do not" in BASELINE_INSTRUCTIONS
    assert "Investigate with the four read tools" not in BASELINE_INSTRUCTIONS
    assert "SOURCE_QUOTE" in BASELINE_INSTRUCTIONS and "text_preview" in BASELINE_INSTRUCTIONS


def test_p08_top_four_packet_cannot_measure_unobserved_rank_five_or_ten():
    from evidence_agent.core.evaluation import score_observed_packet
    ranking = [f"item-{i}" for i in range(1, 11)]
    assert score_ranked_references(["item-5"], ranking, cutoffs=(4, 5))["recall_at_4"] == 0
    assert score_ranked_references(["item-5"], ranking)["recall_at_5"] == 1
    assert score_ranked_references(["item-10"], ranking)["recall_at_5"] == 0
    assert score_ranked_references(["item-10"], ranking)["recall_at_10"] == 1
    for gold in ("item-5", "item-10"):
        packet = score_observed_packet([gold], ranking[:4], limit=4)
        assert packet["recall_at_4"] == 0 and packet["packet_mrr"] == 0
        assert packet["unobserved_cutoffs"] == {"5": None, "10": None, "20": None}
        assert packet["candidate_mrr"] is None
    with pytest.raises(ValueError, match="exceeds"):
        score_observed_packet(["item-5"], ranking[:5], limit=4)


def test_p08_actual_observation_keeps_model_evidence_packet_at_four(tmp_path):
    import asyncio
    import json

    from evidence_agent.agent.llm import ModelFailure
    from evidence_agent.core.retrieval import Candidate
    from evidence_agent.evaluation.study import _observe
    from evidence_agent.ingest.pipeline import IngestPipeline
    from evidence_agent.retrieval.rerank import FastEmbedReranker

    from .test_pipeline import MemoryIndex, _setup

    database, registry, catalog, uploader, _, _ = _setup(tmp_path)
    class RankedIndex(MemoryIndex):
        def query(self, *args, **kwargs):
            return tuple(Candidate(chunk_id=identifier, generation=generation, score=1, channel="guard")
                         for (_, generation), chunks in self.points.items() for identifier in chunks)
    class CaptureFailure:
        def __init__(self):
            self.records = []
            self.packet = None
        async def complete(self, messages, *args, **kwargs):
            self.packet = json.loads(messages[1]["content"])["current_ledger"]["evidence"]
            self.records.append({"number": 1, "usage": None})
            raise ModelFailure("BOUNDARY_GUARD_NO_PROVIDER")
    try:
        reader = registry.bootstrap_principal(uploader.model_copy(update={
            "principal_id": "reader-a", "grants": ("source:read", "case:read")}))
        reader = registry.bootstrap_membership(reader, "case-1")
        content = "# Packet\n\n" + "\n\n".join(
            f"## Section {i}\n\n" + (f"Observed chapter {i} evidence. " * 200) for i in range(8))
        revision = registry.register_source(uploader, tenant_id="tenant-a", case_id="case-1",
            family_id="packet", content=content.encode(), source_path="packet.md", owner_id="uploader")
        registry.approve_source(registry.access.authenticate("approver"), revision)
        index = RankedIndex()
        index.fingerprint = "a" * 64
        IngestPipeline(catalog, index).index(uploader, revision)
        assert len(catalog.chunks_for_revision(reader, revision)) > 4
        model = CaptureFailure()
        case = {"case_id": "case-1", "family_id": "packet", "question": "Read the observed chapters",
                "expected_quote": "Observed chapter 0 evidence.", "expected_disposition": "SUPPORTED", "slices": ["en"]}
        row = asyncio.run(_observe(case, "B1", 0, tmp_path, index, registry, model,
                                   FastEmbedReranker(enabled=False), None))
        assert row["failure"] == "BOUNDARY_GUARD_NO_PROVIDER"
        assert model.packet is not None and len(model.packet) == 4
        assert row["retrieval"]["observed_limit"] == 4
        assert row["retrieval"]["unobserved_cutoffs"]["5"] is None
    finally:
        database.close()


def test_p08_cli_passes_application_assets_and_refuses_ignored_model_override(monkeypatch):
    from evidence_agent.evaluation import study
    spec=importlib.util.spec_from_file_location("p08_cli_guard",Path(__file__).parents[1]/"scripts/evaluate.py")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    seen=[]
    def observe(url,**kwargs):
        seen.append(kwargs)
        return {"guard_only":True}
    monkeypatch.setattr(study,"run_study",observe)
    assert module.main(["--study","development","--run","--enable-live-llm"])==0
    assert seen[0]["app"]==Path(__file__).parents[1]
    assert (seen[0]["app"]/"data/demo/p08_study.json").exists()
    with pytest.raises(SystemExit):
        module.main(["--study","development","--run","--enable-live-llm","--model","openai/gpt-oss-120b"])
    assert len(seen)==1


def test_p08_observation_clones_preserve_originals_without_cross_arm_history(tmp_path):
    import sqlite3

    from evidence_agent.evaluation.study import _clone_inputs
    source=tmp_path/"source"
    (source/"originals").mkdir(parents=True)
    (source/"originals/clause").write_bytes(b"immutable original")
    with sqlite3.connect(source/"registry.sqlite") as db:
        db.execute("CREATE TABLE events(value TEXT)")
        db.execute("INSERT INTO events VALUES('source-only')")
    for name in ("B5","B6"):
        _clone_inputs(source,tmp_path/name)
    with sqlite3.connect(tmp_path/"B5/registry.sqlite") as db:
        db.execute("INSERT INTO events VALUES('generated B5 answer')")
    for root in (source,tmp_path/"B6"):
        with sqlite3.connect(root/"registry.sqlite") as db:
            assert db.execute("SELECT * FROM events").fetchall()==[("source-only",)]
        assert (root/"originals/clause").read_bytes()==b"immutable original"
    with pytest.raises(FileExistsError):
        _clone_inputs(source,tmp_path/"B6")


def test_p08_integrity_reader_never_turns_missing_or_skipped_checks_green(tmp_path):
    from evidence_agent.core.evaluation import reconcile_integrity_tests
    controls={f"T{i:02d}":["test_example.test_guard"] for i in range(1,25)}
    report=tmp_path/"checks.xml"
    report.write_text('<testsuite><testcase classname="tests.test_example" name="test_guard">'
        '<skipped message="explicit live service disabled"/></testcase></testsuite>',encoding="utf-8")
    assert reconcile_integrity_tests([report],controls)["cases"]["T01"]["state"]=="PARTIAL"
    report.write_text('<testsuite><testcase classname="tests.test_example" name="test_guard"/></testsuite>',encoding="utf-8")
    assert reconcile_integrity_tests([report],controls)["all_declared_checks_pass"]
    report.write_text('<testsuite><testcase classname="tests.test_example" name="test_guard">'
        '<failure message="guard failed"/></testcase></testsuite>',encoding="utf-8")
    assert reconcile_integrity_tests([report],controls)["cases"]["T01"]["state"]=="FAIL"
    controls["T02"]=["test_example.test_missing"]
    assert reconcile_integrity_tests([report],controls)["cases"]["T02"]["state"]=="PARTIAL"


def test_p08_fixed_fusion_changes_method_without_changing_candidates_or_double_fusion():
    from evidence_agent.core.evaluation import fuse_fixed_rankings
    dense=[{"chunk_id":"a","score":100},{"chunk_id":"b","score":99},
           {"chunk_id":"c","score":0}]
    sparse=[{"chunk_id":"b","score":100},{"chunk_id":"a","score":0},
            {"chunk_id":"c","score":0}]
    assert fuse_fixed_rankings(dense,sparse,method="rrf")[0]=="a"
    assert fuse_fixed_rankings(dense,sparse,method="minmax_combsum")[0]=="b"
    assert fuse_fixed_rankings(dense,sparse,method="minmax_combsum")!=fuse_fixed_rankings(dense,sparse)
    with pytest.raises(ValueError):
        fuse_fixed_rankings(dense+dense,sparse)


def test_continuation_scorer_detects_critical_omission_stale_claim_and_missing_measurements():
    from evidence_agent.core.evaluation import score_continuation
    packet = {"open_questions": ["settlement_state"]}
    output = {"disposition": "PARTIALLY_SUPPORTED", "verification_failures": [],
        "missing_requirements": ["settlement_state"],
        "verified_claims": [{"text": "Last observed mock state: PENDING at now."}]}
    def score(out=output, context=packet):
        return score_continuation(out, context, required_gaps=["settlement_state"],
                                  current_value="PENDING", stale_value="FAILED")
    assert score()["completion"]
    assert score(context={"open_questions": []})["packet_omitted_gaps"] == ["settlement_state"]
    assert not score({**output, "missing_requirements": []})["completion"]
    stale = {**output, "verified_claims": [{"text": "Last observed mock state: FAILED at yesterday."}]}
    assert score(stale)["stale_claim_count"] == 1 and not score(stale)["completion"]
    assert not score({**output, "verification_failures": ["PROVIDER_HTTP_429"]})["completion"]
    with pytest.raises(ValueError):
        score({})
    assert score_continuation(output, packet, required_gaps=[], current_value="PENDING",
                              stale_value="FAILED")["packet_gap_recall"] is None


def test_duplicate_predictions_do_not_inflate_recall_or_shift_repeat_rank() -> None:
    scores = score_ranked_references(
        ("clause-a", "clause-b", "clause-a"),
        ("other", "clause-a", "clause-a", "clause-b"),
    )

    assert scores["recall_at_5"] == 1.0
    assert scores["mrr"] == 0.5
    assert scores["ndcg_at_5"] == pytest.approx(
        (1 / 1.584962500721156 + 1 / 2) / (1 + 1 / 1.584962500721156)
    )


def test_empty_gold_denominator_is_null_and_omitted_from_macro_average() -> None:
    empty = score_ranked_references((), ("candidate",))
    observed = score_ranked_references(("gold",), ("gold",))

    assert all(value is None for value in empty.values())
    assert macro_average((empty, observed))["mrr"] == 1.0
    assert macro_average((empty,))["mrr"] is None


def test_wrong_expected_clause_receives_no_retrieval_credit() -> None:
    scores = score_ranked_references(("wrong-clause",), ("actual-clause",))

    assert scores["recall_at_5"] == 0.0
    assert scores["mrr"] == 0.0
    assert scores["ndcg_at_5"] == 0.0


def test_relevance_grades_are_validated() -> None:
    with pytest.raises(ValueError, match="finite and non-negative"):
        score_ranked_references(("clause",), ("clause",), relevance={"clause": -1})


def test_stage_error_cannot_be_reported_as_a_completed_pilot(monkeypatch) -> None:
    spec = importlib.util.spec_from_file_location("p02_evaluator_test", Path(__file__).parents[1] / "scripts/evaluate.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "_safe_run_profile", lambda *args: {
        "bm25_profile": "english", "cases": [{"stages": {"lexical": {"status": "ERROR"}},
                                               "exact_identifier_result": None}]})
    assert module.run("http://127.0.0.1:1")["status"] == "INCOMPLETE_FAILURE_RECORDED"


def test_critic_pair_scorer_preserves_unknown_semantics_and_falsifies_inputs():
    from evidence_agent.core.evaluation import score_critic_output
    output = {"verified_claims": [{"text":"Last observed state: FAILED", "evidence_ids":["live-known"]},
        {"text":"Approved source states: exact exception", "evidence_ids":["exception"]}],
        "citations":[{"evidence_id":"exception"}],"inventory_attested":False,"verification_failures":[]}
    kwargs = dict(frozen_hash="a"*64,consumed_hash="a"*64,expected_quote="exact exception",known_fact_id="live-known",
                  initial_ids=["live-known"],final_ids=["live-known","exception"],initial_fact_retained=True)
    score = score_critic_output(output, **kwargs)
    assert score["mechanical_exception_quote_corrected"] is True and score["known_fact_retained"] is True
    assert score["changed_evidence_ids"] == ["exception"] and score["unadjudicated_semantic_correction"] is None
    output["verified_claims"] = []
    score = score_critic_output(output, **kwargs)
    assert score["mechanical_exception_quote_corrected"] is False and score["known_fact_retention_loss_vs_off"] is True
    assert score["mechanical_false_veto_vs_off"] is None
    output["verification_failures"] = ["PROVIDER_HTTP_429"]
    failed_score = score_critic_output(output, **kwargs)
    assert failed_score["known_fact_retention_loss_vs_off"] is True
    assert failed_score["mechanical_false_veto_vs_off"] is None
    assert failed_score["verification_failure_count"] == 1
    import pytest
    with pytest.raises(ValueError, match="inputs differ"):
        score_critic_output(output, **{**kwargs,"consumed_hash":"b"*64})
    with pytest.raises(ValueError, match="Actual gate output"):
        score_critic_output({}, **kwargs)



def test_critic_discovery_smoke_rejects_presupplied_and_unreviewed_sources():
    spec = importlib.util.spec_from_file_location("p06_smoke_predicate", Path(__file__).parents[1]/"scripts/validate_agent.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = {"evidence_id":"approved-chunk", "revision_id":"appendix-revision"}
    assert module.critic_discovered_revision([[],[source]],"appendix-revision")
    assert not module.critic_discovered_revision([[source],[source]],"appendix-revision")
    assert not module.critic_discovered_revision([[]],"appendix-revision")
    assert not module.critic_discovered_revision([],"appendix-revision")


def _blocking_study_worker(pipe, arguments):
    import json
    import subprocess
    import sys
    import time
    from pathlib import Path
    root = Path(arguments["root"])
    child = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(120)"])
    (root/"child_pid").write_text(str(child.pid))
    (root/"calls.jsonl").write_text(json.dumps({"number":1,"event":"STARTED","usage":None})+"\n")
    if arguments.get("partial"):
        with (root/"calls.jsonl").open("ab") as stream:
            stream.write(b'\xff{"unfinished')
    time.sleep(120)


def _finished_study_worker(pipe, arguments):
    pipe.send({"result":{"completed":True}})
    pipe.close()


@pytest.mark.parametrize("partial", [False, True])
def test_whole_study_deadline_joins_tree_and_retains_unknown_attempt(tmp_path, partial):
    import ctypes
    import json
    import os
    import time

    from evidence_agent.evaluation.study import _bounded_study, replay_study
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        _bounded_study({"root":str(tmp_path), "partial":partial}, tmp_path, 8, _blocking_study_worker)
    assert time.monotonic()-started < 15
    report = json.loads((tmp_path/"termination.json").read_text())
    assert report["worker_joined"] is True and report["unfinished_attempt_numbers"] == [1]
    assert report["unfinished_usage"] is None and report["completed"] is False
    assert report["invalid_partial_lines"] == int(partial)
    assert report["attempt_accounting_complete"] is not partial
    pid = int((tmp_path/"child_pid").read_text())
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x00100000, False, pid)
        if handle:
            try:
                assert kernel.WaitForSingleObject(handle, 5000) == 0
            finally:
                kernel.CloseHandle(handle)
    with pytest.raises(ValueError, match="Terminated"):
        replay_study(tmp_path)


def test_whole_study_valid_worker_completes_without_termination(tmp_path):
    from evidence_agent.evaluation.study import _bounded_study
    assert _bounded_study({}, tmp_path, 15, _finished_study_worker) == {"completed":True}
    assert not (tmp_path/"termination.json").exists()


def test_bound_study_configuration_is_consumed_byte_for_byte(tmp_path):
    import hashlib
    import json
    from pathlib import Path

    from evidence_agent.core.evaluation import canonical_digest
    from evidence_agent.core.fixtures import load_fixtures
    from evidence_agent.evaluation.study import _bind_study_inputs
    from evidence_agent.live.gateway import load_config
    app = Path(__file__).resolve().parents[1]
    config = json.loads((app/"data/demo/p08_study.json").read_text(encoding="utf-8"))
    snapshot, bound, hashes = _bind_study_inputs(app,tmp_path,canonical_digest(config))
    assert load_fixtures(bound).summary() == load_fixtures(app).summary()
    assert load_config(bound/"config/adapters.yaml") == load_config(app/"config/adapters.yaml")
    for name in ("config/adapters.yaml", "config/policies/demo_reversal_v2.json", "data/demo/goldens.jsonl"):
        assert (bound/name).read_bytes() == (app/name).read_bytes() == snapshot[name].encode("utf-8")
        assert hashes[name] == hashlib.sha256((bound/name).read_bytes()).hexdigest()
    assert not any(".env" in name for name in snapshot)
    assert not (bound/".env").exists()


def test_evaluator_capability_cli_is_read_only_and_boundaries_remain_mandatory():
    import json
    import subprocess
    import sys
    from pathlib import Path

    from evidence_agent.agent.experiments import evaluator_capabilities
    app = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable,str(app/"scripts/evaluate.py"),"--capabilities"],
        capture_output=True,text=True,check=True)
    actual = json.loads(result.stdout)
    assert actual == evaluator_capabilities()
    assert actual["serving_bypass_supported"] is False
    assert len(actual["arms"]) == 11
    assert "final gate retained" in actual["arms"]["B5"]
    assert set(actual["unsupported_controls"].values()) == {"FEATURE_NOT_SUPPORTED"}
