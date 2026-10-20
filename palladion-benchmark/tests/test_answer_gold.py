"""The answer-gold sidecar: closed vocabulary, digests, and that the question file is left alone (B05-T07.01)."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from benchmark.contracts import Claim, ContractError
from benchmark.fixtures import canonical_json, sha256_hex
from benchmark.fixtures.answer_gold import (
    Action,
    AnswerGold,
    AnswerGoldError,
    ClaimKind,
    ForbiddenKind,
    answer_gold_path,
    check_matches_questions,
    derive_all,
    derive_answer_gold,
    read_answer_gold,
    write_answer_gold,
)
from benchmark.fixtures.manifest import Split
from benchmark.fixtures.questions import GoldRecord


def first(questions: tuple[GoldRecord, ...], stratum: str) -> GoldRecord:
    return next(q for q in questions if q.stratum.value == stratum)


def test_every_pilot_question_derives_and_every_claim_lands_in_the_closed_vocabulary(
    s_questions: tuple[GoldRecord, ...],
) -> None:
    golds = derive_all(s_questions)
    assert len(golds) == len(s_questions)
    for gold, record in zip(golds, s_questions, strict=True):
        assert len(gold.units) == len(record.required_claims) and len(gold.forbidden) == len(record.forbidden_claims)
        assert all(isinstance(u.kind, ClaimKind) for u in gold.units)
        assert gold.allowed_actions == (gold.action,)


def test_the_kinds_and_parameters_are_read_from_the_claim_text(s_questions: tuple[GoldRecord, ...]) -> None:
    window = derive_answer_gold(first(s_questions, "Q2"))
    assert [u.kind for u in window.units] == [ClaimKind.WINDOW]
    assert window.units[0].params["hours"].isdigit()
    version = derive_answer_gold(first(s_questions, "Q4"))
    kinds = {u.kind for u in version.units}
    assert ClaimKind.APPLICABLE_VERSION in kinds and ClaimKind.VERSION_BASIS in kinds
    applicable = next(u for u in version.units if u.kind is ClaimKind.APPLICABLE_VERSION)
    assert "@v" in applicable.params["version"] and version.as_of_basis is not None
    conflict = derive_answer_gold(first(s_questions, "Q6"))
    assert conflict.action is Action.REPORT_CONFLICT and conflict.units[0].kind is ClaimKind.CONFLICT
    assert {u.kind for u in conflict.forbidden} == {ForbiddenKind.PICK_ONE_WINDOW}
    unanswerable = derive_answer_gold(first(s_questions, "Q7"))
    assert unanswerable.action is Action.NO_SUPPORT and unanswerable.units == ()
    assert {u.kind for u in unanswerable.forbidden} == {ForbiddenKind.STATE_RULE_FOR_SCOPE}


def test_a_policy_outcome_question_carries_a_closed_outcome_or_asks_for_the_input(
    s_questions: tuple[GoldRecord, ...],
) -> None:
    outcomes = Counter(
        (g.action, g.policy_outcome) for g in derive_all([q for q in s_questions if q.stratum.value == "Q5"])
    )
    assert set(outcomes) <= {
        (Action.ANSWER, "PERMITTED"),
        (Action.ANSWER, "NOT_PERMITTED"),
        (Action.ANSWER, "ESCALATE"),
        (Action.ASK_INPUT, "NEEDS_INPUT"),
    }
    needs = next(g for g in derive_all(s_questions) if g.action is Action.ASK_INPUT)
    assert [u.kind for u in needs.units] == [ClaimKind.INPUT_REQUIRED] and needs.required_inputs


def test_an_unknown_claim_forbidden_claim_or_action_is_refused_not_defaulted(
    s_questions: tuple[GoldRecord, ...],
) -> None:
    base = first(s_questions, "Q2")
    with pytest.raises(AnswerGoldError, match="no claim rule"):
        derive_answer_gold(replace(base, required_claims=("the moon is made of cheese",)))
    with pytest.raises(AnswerGoldError, match="no forbidden-claim rule"):
        derive_answer_gold(replace(base, forbidden_claims=("does something new",)))
    with pytest.raises(AnswerGoldError, match="no action rule"):
        derive_answer_gold(replace(base, preferred_action="improvise"))


def test_a_stated_outcome_without_a_claim_for_it_is_refused(s_questions: tuple[GoldRecord, ...]) -> None:
    base = first(s_questions, "Q2")
    with pytest.raises(AnswerGoldError, match="no claim states it"):
        derive_answer_gold(replace(base, policy_outcome="PERMITTED"))


def test_the_file_round_trips_and_a_changed_byte_fails_the_digest(
    s_questions: tuple[GoldRecord, ...], tmp_path: Path
) -> None:
    golds = derive_all(s_questions)
    path = write_answer_gold(tmp_path, Split.SMOKE, golds)
    assert path == answer_gold_path(tmp_path, Split.SMOKE) and path.parent.name == "annotations_dev"
    digest = sha256_hex(path.read_bytes().decode("utf-8"))
    assert read_answer_gold(path, expected_sha256=digest) == golds
    path.write_bytes(path.read_bytes().replace(b"ANSWER", b"ANSWEX", 1))
    with pytest.raises(AnswerGoldError, match="digest"):
        read_answer_gold(path, expected_sha256=digest)


def test_a_record_with_an_unknown_or_missing_field_or_kind_is_refused(s_questions: tuple[GoldRecord, ...]) -> None:
    data = derive_answer_gold(first(s_questions, "Q2")).to_dict()
    with pytest.raises(AnswerGoldError, match="unknown"):
        AnswerGold.from_dict({**data, "extra": 1})
    with pytest.raises(AnswerGoldError, match="missing"):
        AnswerGold.from_dict({k: v for k, v in data.items() if k != "action"})
    with pytest.raises(AnswerGoldError, match="malformed"):
        AnswerGold.from_dict({**data, "action": "IMPROVISE"})


def test_the_answer_gold_is_bound_to_the_question_it_was_derived_from(s_questions: tuple[GoldRecord, ...]) -> None:
    golds = derive_all(s_questions)
    check_matches_questions(golds, s_questions)
    edited = (replace(s_questions[0], query=s_questions[0].query + " (edited)"), *s_questions[1:])
    with pytest.raises(AnswerGoldError, match="different question"):
        check_matches_questions(golds, edited)
    with pytest.raises(AnswerGoldError, match="same questions"):
        check_matches_questions(golds[1:], s_questions)
    assert golds[0].source_sha256 == sha256_hex(canonical_json(s_questions[0].to_dict()))


def test_writing_the_answer_gold_leaves_the_question_file_byte_for_byte(
    s_root: Path, s_questions: tuple[GoldRecord, ...]
) -> None:
    questions = s_root / "annotations_dev" / "questions_smoke.jsonl"
    before = questions.read_bytes()
    write_answer_gold(s_root, Split.SMOKE, derive_all(s_questions))
    assert questions.read_bytes() == before
    assert sorted(p.name for p in questions.parent.iterdir()) == ["answers_smoke.jsonl", "questions_smoke.jsonl"]


def test_the_structured_fields_on_a_claim_and_a_response_are_optional_and_checked() -> None:
    plain = Claim("c1", "text", ("POL-1@v1#4.1",))
    assert plain.kind is None and dict(plain.params) == {}
    typed = Claim("c1", "the window is 168 hours", (), kind="WINDOW", params={"hours": 168, "version": "POL-1@v1"})
    assert typed.kind == "WINDOW" and typed.params["hours"] == 168
    with pytest.raises(ContractError, match="strings or integers"):
        Claim("c1", "x", (), kind="WINDOW", params={"hours": 1.5})
    with pytest.raises(ContractError, match="strings or integers"):
        Claim("c1", "x", (), kind="WINDOW", params={"hours": True})
    with pytest.raises(ContractError, match="valid identifier"):
        Claim("c1", "x", (), kind="not a kind")


def test_a_response_serialises_its_structured_fields() -> None:
    from benchmark.contracts import CaseResponse, EvidenceStatus

    response = CaseResponse(
        question_id="q-0000000000000001", run_id="run-1", answer_text="ok", evidence_status=EvidenceStatus.SUPPORTED,
        claims=(Claim("c1", "the window is 168 hours", ("POL-1@v1#4.1",), kind="WINDOW", params={"hours": 168}),),
        used_evidence_ids=(), tool_calls=(), critic=None, model_invocations=None, latency_ms=None, cost_usd=None,
        abstention_reason=None, action="ANSWER", policy_outcome="PERMITTED", version_ids=("POL-1@v1",),
    )  # fmt: skip
    data = response.to_dict()
    assert data["action"] == "ANSWER" and data["policy_outcome"] == "PERMITTED" and data["version_ids"] == ["POL-1@v1"]
    assert data["claims"][0]["kind"] == "WINDOW" and data["claims"][0]["params"] == {"hours": 168}
    json.dumps(data)


# answer gold ---------------------------------------------------------------


def test_an_outcome_outside_the_vocabulary_is_refused(s_questions: tuple[GoldRecord, ...]) -> None:
    from dataclasses import replace as dc_replace

    base = next(q for q in s_questions if q.stratum.value == "Q5")
    with pytest.raises(AnswerGoldError, match="no outcome rule"):
        derive_answer_gold(dc_replace(base, policy_outcome="MAYBE"))
