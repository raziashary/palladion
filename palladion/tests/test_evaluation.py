from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from evidence_agent.core.evaluation import macro_average, score_ranked_references


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
