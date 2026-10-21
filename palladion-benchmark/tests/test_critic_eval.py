"""Critic evaluation (B07-T06.01): injected-error pairs and clean drafts are both scored; the critic stays blind."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from benchmark.eval.critic import (
    CriticCase,
    CriticEvalError,
    ErrorType,
    InjectedError,
    blind_violations,
    critic_case_from_trace,
    score_critic,
)
from benchmark.eval.observable import NotObservable, Rate


def claim(claim_id: str, text: str, evidence: tuple[str, ...] = ("ev-1",)) -> dict[str, Any]:
    return {"claim_id": claim_id, "type": "FACT", "field": None, "evidence_ids": list(evidence), "text": text}


def finding(claim_id: str, verdict: str, evidence: tuple[str, ...] = ()) -> dict[str, Any]:
    return {"claim_id": claim_id, "finding": verdict, "evidence_ids": list(evidence), "missing_slots": []}


def block(
    claims: list[dict[str, Any]],
    reviews: list[dict[str, Any]],
    released: list[str],
    *,
    queries: tuple[str, ...] = (),
    critic_tokens: tuple[int | None, int | None] = (100, 20),
) -> dict[str, Any]:
    return {
        "arm": "B6",
        "model_calls": [
            {
                "role": "main",
                "stage": "draft",
                "status": "ok",
                "prompt_tokens": 500,
                "completion_tokens": 80,
                "error_code": None,
            },
            {
                "role": "critic",
                "stage": "review",
                "status": "ok",
                "prompt_tokens": critic_tokens[0],
                "completion_tokens": critic_tokens[1],
                "error_code": None,
            },
        ],
        "tool_calls": [],
        "initial_draft": {"origin": "model", "sha256": "0" * 64, "answer_kind": "ANSWER", "claims": claims},
        "critic_reviews": [
            {
                "verdict": "REVISE",
                "proposed_disposition": None,
                "claim_reviews": reviews,
                "missing_slots": [],
                "contradiction_count": 0,
                "counter_search_queries": list(queries),
            }
        ],
        "final_claims": [c for c in claims if c["claim_id"] in released],
        "released_claim_ids": released,
    }


def injected(
    case_id: str, kind: ErrorType, *, objects: bool, repairs: bool = True, independent: bool = True
) -> CriticCase:
    claims = [claim("c1", "The window is 14 days."), claim("c2", "The cap is 5 million.")]
    reviews = [finding("c1", "UNSUPPORTED", ("ev-9",) if independent else ("ev-1",))] if objects else []
    released = ["c2"] if objects and repairs else ["c1", "c2"]
    return CriticCase(
        case_id, f"lab-{case_id}", (InjectedError("c1", kind),), block(claims, reviews, released, queries=("window",))
    )


def clean(case_id: str, *, objects: bool = False) -> CriticCase:
    claims = [claim("c1", "The window is 30 days.")]
    reviews = [finding("c1", "UNSUPPORTED")] if objects else []
    return CriticCase(case_id, f"lab-{case_id}", (), block(claims, reviews, [] if objects else ["c1"]))


def test_a_critic_that_catches_every_injected_error_and_leaves_clean_drafts_alone() -> None:
    cases = [injected(f"a{i}", kind, objects=True) for i, kind in enumerate(ErrorType)] + [clean("z1"), clean("z2")]
    score = score_critic(cases, critic_enabled=True)
    assert score.objection_precision == Rate(4, 4) and score.objection_recall == Rate(4, 4)
    assert score.escape_rate == Rate(0, 4) and score.repair_rate == Rate(4, 4) and score.regression_rate == Rate(0, 6)
    assert {name: rate for name, rate in score.recall_by_type.items()} == {t.value: Rate(1, 1) for t in ErrorType}
    assert score.clean_cases == 2 and score.additional_retrievals == 4


def test_a_critic_that_misses_everything_has_zero_recall_and_every_error_escapes() -> None:
    cases = [injected(f"a{i}", kind, objects=False) for i, kind in enumerate(ErrorType)]
    score = score_critic(cases, critic_enabled=True)
    assert score.objection_recall == Rate(0, 4) and score.escape_rate == Rate(4, 4)
    assert isinstance(score.objection_precision, Rate) and score.objection_precision.value is None, (
        "no objection at all has no precision, which is not zero"
    )
    assert (
        isinstance(score.cost_per_net_prevented, NotObservable) and "undefined" in score.cost_per_net_prevented.reason
    )


def test_a_critic_that_objects_to_everything_is_penalised_on_clean_drafts_not_rewarded() -> None:
    cases = [injected("a1", ErrorType.WRONG_AS_OF, objects=True), clean("z1", objects=True), clean("z2", objects=True)]
    score = score_critic(cases, critic_enabled=True)
    assert score.objection_recall == Rate(1, 1) and score.objection_precision == Rate(1, 3)
    assert score.regression_rate == Rate(2, 3), "two correct claims were objected to and lost"


def test_net_prevented_subtracts_regressions_from_repairs_and_prices_critic_tokens() -> None:
    cases = [
        injected("a1", ErrorType.WRONG_AS_OF, objects=True),
        injected("a2", ErrorType.STALE_LIVE_STATE, objects=True),
        clean("z1", objects=True),
    ]
    score = score_critic(cases, critic_enabled=True)
    assert score.repair_rate == Rate(2, 2) and score.regression_rate == Rate(1, 3)
    assert score.cost_per_net_prevented == pytest.approx(3 * 120 / (2 - 1))


def test_missing_critic_tokens_make_the_cost_not_observable_rather_than_free() -> None:
    case = injected("a1", ErrorType.WRONG_AS_OF, objects=True)
    case.evaluator["model_calls"][1]["prompt_tokens"] = None
    score = score_critic([case], critic_enabled=True)
    assert isinstance(score.cost_per_net_prevented, NotObservable) and "token" in score.cost_per_net_prevented.reason


def test_an_objection_with_the_drafters_own_evidence_is_not_independent() -> None:
    own = score_critic([injected("a1", ErrorType.WRONG_AS_OF, objects=True, independent=False)], critic_enabled=True)
    other = score_critic([injected("a1", ErrorType.WRONG_AS_OF, objects=True, independent=True)], critic_enabled=True)
    assert own.independent_evidence == Rate(0, 1) and other.independent_evidence == Rate(1, 1)


def test_an_objection_the_drafter_ignored_is_a_repair_failure_and_an_escape() -> None:
    case = injected("a1", ErrorType.FABRICATED_CITATION, objects=True, repairs=False)
    score = score_critic([case], critic_enabled=True)
    assert score.repair_rate == Rate(0, 1) and score.escape_rate == Rate(1, 1) and score.objection_recall == Rate(1, 1)


def test_an_arm_without_a_critic_is_not_observable_everywhere_and_never_zero() -> None:
    score = score_critic([injected("a1", ErrorType.WRONG_AS_OF, objects=False)], critic_enabled=False)
    values = list(score.measures().values())
    assert values and all(isinstance(v, NotObservable) for v in values)
    assert all("no critic" in v.reason for v in values if isinstance(v, NotObservable))


def test_agreement_is_not_among_the_measures() -> None:
    names = set(score_critic([clean("z1")], critic_enabled=True).measures())
    assert not any("agree" in name for name in names)


def test_a_planted_label_in_what_the_critic_saw_is_caught_and_clean_input_passes() -> None:
    cases = [injected("a1", ErrorType.WRONG_AS_OF, objects=True)]
    assert blind_violations(["Review these claims against the evidence.", "c1: The window is 14 days."], cases) == []
    assert blind_violations(["note: this draft has a wrong_as_of_date error"], cases) == [
        "error type: wrong_as_of_date"
    ]
    assert blind_violations(["case LAB-A1 is injected"], cases) == ["a1: lab-a1"]


def test_a_malformed_block_or_an_error_on_an_unknown_claim_is_refused() -> None:
    good = injected("a1", ErrorType.WRONG_AS_OF, objects=True)
    with pytest.raises(CriticEvalError, match="no initial draft"):
        score_critic([CriticCase("a1", "lab-a1", (), {"arm": "B6"})], critic_enabled=True)
    with pytest.raises(CriticEvalError, match="lacks released_claim_ids"):
        score_critic(
            [
                CriticCase(
                    "a1", "lab-a1", good.errors, {k: v for k, v in good.evaluator.items() if k != "released_claim_ids"}
                )
            ],
            critic_enabled=True,
        )
    with pytest.raises(CriticEvalError, match="does not hold"):
        score_critic(
            [CriticCase("a1", "lab-a1", (InjectedError("c9", ErrorType.WRONG_AS_OF),), good.evaluator)],
            critic_enabled=True,
        )


def test_a_case_is_read_from_a_trace_entry_and_a_trace_without_the_block_is_refused() -> None:
    evaluator = injected("a1", ErrorType.WRONG_AS_OF, objects=True).evaluator
    case = critic_case_from_trace(
        {"evaluator": evaluator}, "a1", "lab-a1", [InjectedError("c1", ErrorType.WRONG_AS_OF)]
    )
    assert case.evaluator is evaluator and score_critic([case], critic_enabled=True).objection_recall == Rate(1, 1)
    with pytest.raises(CriticEvalError, match="no evaluator block"):
        critic_case_from_trace({"model_calls": []}, "a1", "lab-a1")


def test_a_counter_search_logged_as_a_query_and_as_a_tool_call_is_counted_once() -> None:
    case = injected("a1", ErrorType.WRONG_AS_OF, objects=True)
    call = {"role": "critic", "name": "search_knowledge", "arguments": "{}", "status": "SUCCEEDED"}
    both = replace(case, evaluator={**case.evaluator, "tool_calls": [call]})
    proposals_only = replace(case, evaluator={**case.evaluator, "tool_calls": []})
    assert score_critic([both], critic_enabled=True).additional_retrievals == 1, (
        "one proposed, one executed: one search"
    )
    assert score_critic([proposals_only], critic_enabled=True).additional_retrievals == 1, (
        "proposals count when none ran"
    )
