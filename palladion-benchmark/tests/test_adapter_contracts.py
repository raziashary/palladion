"""Contracts: invalid input is rejected, valid input round-trips, null stays null."""

from __future__ import annotations

import dataclasses
import json
import math
from pathlib import Path
from typing import Any

import pytest

from benchmark.config import load_comparators_config
from benchmark.contracts import (
    ALLOWED_FILTER_KEYS,
    AbstentionReason,
    ArmUnavailable,
    CapabilityUnsupported,
    CaseRequest,
    CaseResponse,
    Claim,
    ContractError,
    CriticReport,
    ErrorOrigin,
    EvidenceCandidate,
    EvidenceStatus,
    ModelInvocations,
    RetrievalRequest,
    RetrieverAdapter,
    RunStatus,
    SystemAdapter,
    ToolCall,
    Track,
    TransientInfrastructureError,
    UsageReport,
    classify_exception,
    screen_arm_visible,
)
from benchmark.registry import (
    ArmRegistry,
    ArmSpec,
    Capability,
    CapabilityNotVerified,
    Declaration,
    Support,
    default_registry,
)

QID = "q-3f9a1c2b"


def make_request(**overrides: Any) -> RetrievalRequest:
    values: dict[str, Any] = {
        "question_id": QID,
        "query": "Can the reversal be done today?",
        "principal_id": "support_tenant_alpha_l2",
        "corpus_snapshot_id": "snapshot_2026_10_18",
        "evaluation_time": "2026-10-18T03:00:00Z",
        "event_time": "2026-10-17T04:20:00+00:00",
        "filters": {"tenant_id": "alpha", "language": "id-en"},
        "limit": 10,
        "max_evidence_tokens": 4000,
    }
    values.update(overrides)
    return RetrievalRequest(**values)


def make_candidate(**overrides: Any) -> EvidenceCandidate:
    values: dict[str, Any] = {
        "source_version_id": "SOP-7@v3",
        "locator": "4.2",
        "content": "Reversal needs a verified settlement state.",
        "rank": 1,
        "native_score": 0.42,
        "retrieval_channel": "dense",
        "evidence_path": ("SOP-7@v3",),
        "native_citation_supported": True,
        "additional_metadata": {"chunk": 7},
    }
    values.update(overrides)
    return EvidenceCandidate(**values)


def make_response(**overrides: Any) -> CaseResponse:
    values: dict[str, Any] = {
        "question_id": QID,
        "run_id": "run-e4-test-007",
        "answer_text": "The accessible evidence is incomplete.",
        "evidence_status": EvidenceStatus.PARTIALLY_SUPPORTED,
        "claims": (Claim("c1", "The SOP has a settlement prerequisite.", ("SOP-7@v3#4.2",)),),
        "used_evidence_ids": ("SOP-7@v3#4.2",),
        "tool_calls": (ToolCall("search_knowledge", "OK"),),
        "critic": CriticReport(True, 1, ("settlement unverified",)),
        "model_invocations": ModelInvocations(2, 1),
        "latency_ms": None,
        "cost_usd": None,
        "abstention_reason": AbstentionReason.MISSING_CASE_INPUT,
    }
    values.update(overrides)
    return CaseResponse(**values)


# ----------------------------------------------------------------------------- RetrievalRequest


def test_valid_request_round_trips_through_json() -> None:
    request = make_request()
    again = RetrievalRequest.from_dict(json.loads(json.dumps(request.to_dict())))
    assert again == request
    assert request.event_time == "2026-10-17T04:20:00Z"  # offset normalised to UTC


@pytest.mark.parametrize("bad", ["2026-10-18T03:00:00", "2026-10-18", "yesterday", 20261018, None])
def test_naive_or_malformed_evaluation_time_is_rejected(bad: object) -> None:
    with pytest.raises(ContractError):
        make_request(evaluation_time=bad)


def test_offset_timestamps_are_normalised_to_utc_for_comparison() -> None:
    a = make_request(evaluation_time="2026-10-18T10:00:00+07:00")
    b = make_request(evaluation_time="2026-10-18T03:00:00Z")
    assert a.evaluation_time == b.evaluation_time


@pytest.mark.parametrize("bad", [0, -1, True, 5.0, "5", 101, None])
def test_limit_must_be_a_bounded_real_integer(bad: object) -> None:
    with pytest.raises(ContractError):
        make_request(limit=bad)


@pytest.mark.parametrize("bad", [0, True, 4000.0, math.inf])
def test_token_budget_must_be_a_positive_integer(bad: object) -> None:
    with pytest.raises(ContractError):
        make_request(max_evidence_tokens=bad)


@pytest.mark.parametrize(
    "bad",
    [
        "Q4-LOCK-017",
        "q-xyz",
        "northwave-reversal",
        "q-3F9A1C2B",
        "",
        17,
        "test-0a1b2c3d",
        "lock-0a1b2c3d",
        "q4-0a1b2c3d",
        "ep-0a1b2c3d",
    ],
)
def test_question_ids_must_be_pseudonymous(bad: object) -> None:
    with pytest.raises(ContractError):
        make_request(question_id=bad)


def test_unknown_field_is_rejected_when_loading() -> None:
    data = make_request().to_dict()
    data["gold_slots"] = ["x"]
    with pytest.raises(ContractError, match="unknown field"):
        RetrievalRequest.from_dict(data)


def test_unknown_constructor_field_is_a_type_error() -> None:
    with pytest.raises(TypeError):
        RetrievalRequest(**{**make_request().to_dict(), "answerability": "ANSWERABLE"})


def test_filter_keys_outside_the_allowlist_are_rejected() -> None:
    with pytest.raises(ContractError, match="allowlist"):
        make_request(filters={"split": "test"})
    assert "metadata_condition" in ALLOWED_FILTER_KEYS


def test_gold_like_value_in_a_benign_field_is_rejected_and_a_benign_value_passes() -> None:
    with pytest.raises(ContractError, match="gold-like marker"):
        make_request(filters={"language": "expected answer: reversal allowed"})
    with pytest.raises(ContractError, match="gold-like marker"):
        make_request(filters={"source_types": ["sop", "gold evidence"]})
    with pytest.raises(ContractError, match="gold-like marker"):
        make_request(filters={"language": "gold_answer"})  # underscores do not hide the marker
    assert make_request(filters={"language": "id-en", "source_types": ["sop", "runbook"]})


def test_screen_rejects_gold_like_keys_at_any_depth() -> None:
    with pytest.raises(ContractError, match="gold-like key"):
        screen_arm_visible("x", {"outer": [{"Required-Evidence": 1}]})
    with pytest.raises(ContractError, match="gold-like key"):
        screen_arm_visible("x", {"expected_answer": "n/a"})
    screen_arm_visible("x", {"outer": [{"chunk": 1}], "note": "ordinary text"})


def test_request_is_immutable_and_isolated_from_the_source_dict() -> None:
    source: dict[str, Any] = {"tenant_id": "alpha", "source_types": ["sop"]}
    request = make_request(filters=source)
    source["tenant_id"] = "beta"
    source["source_types"].append("runbook")
    assert request.filters["tenant_id"] == "alpha"
    assert request.filters["source_types"] == ("sop",)
    with pytest.raises(TypeError):
        request.filters["tenant_id"] = "beta"  # type: ignore[index]
    with pytest.raises(dataclasses.FrozenInstanceError):
        request.limit = 5  # type: ignore[misc]


def test_non_json_filter_values_are_rejected() -> None:
    with pytest.raises(ContractError):
        make_request(filters={"language": object()})
    with pytest.raises(ContractError):
        make_request(filters={"language": float("nan")})


# ----------------------------------------------------------------------------- EvidenceCandidate


def test_candidate_round_trip_and_defaults() -> None:
    candidate = make_candidate()
    assert EvidenceCandidate.from_dict(json.loads(json.dumps(candidate.to_dict()))) == candidate
    minimal = EvidenceCandidate.from_dict(
        {
            "source_version_id": None,
            "locator": None,
            "content": "x",
            "rank": 1,
            "native_score": None,
            "retrieval_channel": "bm25",
            "native_citation_supported": False,
        }
    )
    assert minimal.evidence_path == () and dict(minimal.additional_metadata) == {}


def test_native_citation_flag_is_required_and_has_no_default() -> None:
    with pytest.raises(ContractError, match="missing field"):
        EvidenceCandidate.from_dict(
            {
                "source_version_id": "S@v1",
                "locator": None,
                "content": "x",
                "rank": 1,
                "native_score": None,
                "retrieval_channel": "bm25",
            }
        )


def test_native_citation_claim_without_a_source_version_is_a_phantom_citation() -> None:
    with pytest.raises(ContractError, match="phantom"):
        make_candidate(source_version_id=None, native_citation_supported=True)
    assert make_candidate(source_version_id=None, locator=None, native_citation_supported=False)


@pytest.mark.parametrize("bad", [0, -3, True, 1.0, "1"])
def test_rank_must_be_a_positive_integer(bad: object) -> None:
    with pytest.raises(ContractError):
        make_candidate(rank=bad)


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, True, "0.4"])
def test_native_score_must_be_finite_number_or_null(bad: object) -> None:
    with pytest.raises(ContractError):
        make_candidate(native_score=bad)
    assert make_candidate(native_score=None).native_score is None


def test_candidate_unknown_field_and_non_boolean_flag() -> None:
    data = make_candidate().to_dict()
    data["surprise"] = 1
    with pytest.raises(ContractError, match="unknown field"):
        EvidenceCandidate.from_dict(data)
    with pytest.raises(ContractError):
        make_candidate(native_citation_supported="yes")


def test_candidate_evidence_path_is_a_tuple_of_strings() -> None:
    assert make_candidate(evidence_path=["a", "b"]).evidence_path == ("a", "b")
    with pytest.raises(ContractError):
        make_candidate(evidence_path=[1])


# ----------------------------------------------------------------------------- adapter protocols


class _Retriever:
    def build_index(self, source_manifest_uri: str, index_namespace: str) -> None: ...

    def retrieve(self, request: RetrievalRequest) -> list[EvidenceCandidate]:
        return []

    def index_stats(self) -> dict[str, Any]:
        return {}


class _NotARetriever:
    def retrieve(self, request: RetrievalRequest) -> list[EvidenceCandidate]:
        return []


def test_retriever_protocol_accepts_a_conforming_class_and_rejects_a_partial_one() -> None:
    assert isinstance(_Retriever(), RetrieverAdapter)
    assert not isinstance(_NotARetriever(), RetrieverAdapter)
    assert not isinstance(_Retriever(), SystemAdapter)


# ----------------------------------------------------------------------------- CaseRequest / CaseResponse


def test_case_request_applies_the_same_barrier() -> None:
    base: dict[str, Any] = {
        "question_id": QID,
        "query": "q",
        "principal_id": "p1",
        "corpus_snapshot_id": "s1",
        "evaluation_time": "2026-10-18T03:00:00Z",
        "event_time": None,
        "filters": {},
        "max_evidence_tokens": 4000,
        "episode_id": "ep-0a1b2c3d",
        "turn_index": 0,
    }
    assert CaseRequest(**base).turn_index == 0
    with pytest.raises(ContractError):
        CaseRequest(**{**base, "filters": {"gold": "x"}})
    with pytest.raises(ContractError):
        CaseRequest(**{**base, "turn_index": -1})
    with pytest.raises(ContractError):
        CaseRequest(**{**base, "episode_id": "lock-family-7"})
    with pytest.raises(ContractError):
        CaseRequest(**{**base, "episode_id": "q-0a1b2c3d"})  # an episode id is not a question id


def test_null_latency_and_cost_are_preserved_not_coerced_to_zero() -> None:
    response = make_response()
    assert response.latency_ms is None and response.cost_usd is None
    encoded = json.loads(json.dumps(response.to_dict()))
    assert encoded["latency_ms"] is None and encoded["cost_usd"] is None
    assert encoded["evidence_status"] == "PARTIALLY_SUPPORTED"
    assert encoded["model_invocations"] == {"main": 2, "critic": 1}


def test_observed_zero_is_distinct_from_not_observed() -> None:
    assert make_response(latency_ms=0).latency_ms == 0.0
    assert make_response(model_invocations=ModelInvocations(None, None)).model_invocations == ModelInvocations(
        None, None
    )


@pytest.mark.parametrize("field", ["latency_ms", "cost_usd"])
@pytest.mark.parametrize("bad", [-1.0, math.nan, math.inf, True, "3"])
def test_latency_and_cost_reject_invalid_numbers(field: str, bad: object) -> None:
    with pytest.raises(ContractError):
        make_response(**{field: bad})


def test_unknown_evidence_status_is_rejected() -> None:
    with pytest.raises(ContractError):
        make_response(evidence_status="MOSTLY_TRUE")
    assert make_response(evidence_status="CONFLICT").evidence_status is EvidenceStatus.CONFLICT


def test_there_are_exactly_five_evidence_statuses_and_six_run_states() -> None:
    assert {s.value for s in EvidenceStatus} == {
        "SUPPORTED",
        "PARTIALLY_SUPPORTED",
        "CONFLICT",
        "NOT_ESTABLISHED",
        "VERIFICATION_UNAVAILABLE",
    }
    assert {s.value for s in RunStatus} == {
        "OK",
        "NOT_RUN",
        "UNSUPPORTED",
        "FEATURE_NOT_SUPPORTED",
        "INVALID_RUN",
        "TIMEOUT",
    }


def test_supported_answer_cannot_carry_an_abstention_reason() -> None:
    with pytest.raises(ContractError, match="abstention"):
        make_response(evidence_status=EvidenceStatus.SUPPORTED)
    assert make_response(evidence_status=EvidenceStatus.SUPPORTED, abstention_reason=None)


def test_disabled_critic_cannot_report_calls() -> None:
    with pytest.raises(ContractError):
        CriticReport(False, 2, ())
    assert CriticReport(False, None, ()).calls is None


def test_usage_report_keeps_unobserved_values_null() -> None:
    usage = UsageReport(None, None, 3, None, None, None)
    assert usage.main_calls is None and usage.tool_calls == 3
    with pytest.raises(ContractError):
        UsageReport(-1, None, None, None, None, None)


# ----------------------------------------------------------------------------- failure classification


@pytest.mark.parametrize(
    ("exc", "status", "origin", "expected_code"),
    [
        (ArmUnavailable("down"), RunStatus.NOT_RUN, ErrorOrigin.ARM, "ARM_UNAVAILABLE"),
        (CapabilityUnsupported("no acl"), RunStatus.FEATURE_NOT_SUPPORTED, ErrorOrigin.ARM, "CAPABILITY_UNSUPPORTED"),
        (TimeoutError(), RunStatus.TIMEOUT, ErrorOrigin.ARM, "DEADLINE_EXCEEDED"),
        (
            TransientInfrastructureError("503"),
            RunStatus.INVALID_RUN,
            ErrorOrigin.PROVIDER,
            "TRANSIENT_FAULT_RETRIES_EXHAUSTED",
        ),
        (ContractError("bad"), RunStatus.INVALID_RUN, ErrorOrigin.ARM, "CONTRACT_VIOLATION"),
        (ZeroDivisionError("boom"), RunStatus.INVALID_RUN, ErrorOrigin.ARM, "UNHANDLED_ZeroDivisionError"),
    ],
)
def test_each_exception_maps_to_one_state_and_origin(
    exc: BaseException, status: RunStatus, origin: ErrorOrigin, expected_code: str
) -> None:
    assert classify_exception(exc) == (status, origin, expected_code)  # fixed labels, never exception prose


def test_classification_code_never_contains_exception_text() -> None:
    secret = "gsk_" + "x" * 30
    _, _, code = classify_exception(RuntimeError(secret))
    assert secret not in code


# ----------------------------------------------------------------------------- arm registry

COMPARATORS = Path(__file__).resolve().parents[1] / "configs" / "comparators.yaml"


def make_spec(arm_id: str = "X1", **support: Support) -> ArmSpec:
    capabilities: dict[Capability, Declaration] = {
        c: Declaration(support.get(c.value, Support.SUPPORTED), "test declaration") for c in Capability
    }
    return ArmSpec(arm_id, "Test arm", (Track.RETRIEVAL_ONLY,), capabilities)


def test_default_registry_has_all_fifteen_arms_and_matches_the_config() -> None:
    registry = default_registry()
    assert registry.ids() == [
        "R0",
        "R1",
        "R2",
        "R3",
        "R4",
        "R5",
        "R6",
        "R7",
        "R7a",
        "R7b",
        "E0",
        "E1",
        "E2",
        "E3",
        "E4",
    ]
    registry.check_against_config(load_comparators_config(COMPARATORS))
    for arm_id in registry.ids():
        assert set(registry.get(arm_id).capabilities) == set(Capability)


def test_registry_and_config_drift_is_detected() -> None:
    registry = ArmRegistry()
    registry.register(make_spec("R0"))
    with pytest.raises(ContractError, match="differ"):
        registry.check_against_config(load_comparators_config(COMPARATORS))


def test_arm_with_a_missing_declaration_is_rejected() -> None:
    partial: dict[Capability, Declaration] = {
        c: Declaration(Support.SUPPORTED, "x") for c in Capability if c is not Capability.GRAPH
    }
    with pytest.raises(ContractError, match="undeclared capabilities: graph"):
        ArmSpec("X1", "Partial", (Track.RETRIEVAL_ONLY,), partial)


def test_declaration_needs_a_source_note_and_a_real_support_value() -> None:
    with pytest.raises(ContractError):
        Declaration(Support.SUPPORTED, "  ")
    with pytest.raises(ContractError):
        Declaration("supported", "note")  # type: ignore[arg-type]


def test_duplicate_registration_and_unknown_arm_are_rejected() -> None:
    registry = ArmRegistry()
    registry.register(make_spec("X1"))
    with pytest.raises(ContractError, match="already registered"):
        registry.register(make_spec("X1"))
    with pytest.raises(ContractError, match="unknown arm"):
        registry.get("X9")


def test_capabilities_are_read_only() -> None:
    spec = make_spec()
    with pytest.raises(TypeError):
        spec.capabilities[Capability.GRAPH] = Declaration(Support.SUPPORTED, "x")  # type: ignore[index]


def test_matrix_prints_a_word_in_every_cell_never_blank() -> None:
    matrix = default_registry().render_matrix()
    rows = [line for line in matrix.splitlines() if line.startswith("| ")]
    assert len(rows) == 1 + 15
    for row in rows:
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        assert all(cells), f"blank cell in {row}"
    assert "unsupported" in matrix and "UNVERIFIED" in matrix and "supported" in matrix


def test_matrix_for_a_subset_and_unknown_arm() -> None:
    registry = default_registry()
    subset = registry.render_matrix(["R0", "R7b"])
    assert subset.count("\n") == 3 and "FEATURE_NOT_SUPPORTED" in subset
    with pytest.raises(ContractError):
        registry.render_matrix(["R99"])


def test_unverified_capability_blocks_the_run_and_is_recorded_as_not_run() -> None:
    registry = default_registry()
    with pytest.raises(CapabilityNotVerified) as caught:
        registry.require_runnable("R7", [Capability.ACL_FILTER])  # the aggregate R7 row stays unverified
    assert classify_exception(caught.value)[0] is RunStatus.NOT_RUN


def test_unsupported_capability_is_recorded_as_feature_not_supported() -> None:
    registry = default_registry()
    with pytest.raises(CapabilityUnsupported) as caught:
        registry.require_runnable("R0", [Capability.GRAPH])
    assert classify_exception(caught.value)[0] is RunStatus.FEATURE_NOT_SUPPORTED


def test_verified_support_passes_and_no_requirement_returns_the_spec() -> None:
    registry = ArmRegistry()
    registry.register(make_spec("X1", graph=Support.UNSUPPORTED))
    assert registry.require_runnable("X1", [Capability.ACL_FILTER]).arm_id == "X1"
    assert registry.require_runnable("X1").arm_id == "X1"


def test_the_palladion_system_arms_are_runnable_with_every_capability_declared() -> None:
    registry = default_registry()
    for arm_id in ("E3", "E4"):
        spec = registry.require_runnable(arm_id, [Capability.NATIVE_CITATION])
        assert spec.forced_status is None
        assert all(d.support is not Support.UNVERIFIED for d in spec.capabilities.values())
        with pytest.raises(CapabilityUnsupported):
            registry.require_runnable(arm_id, [Capability.ACL_FILTER])
        with pytest.raises(CapabilityUnsupported):
            registry.require_runnable(arm_id, [Capability.TEMPORAL_FILTER])


def test_forced_status_needs_a_reason_and_a_legal_value() -> None:
    capabilities = {c: Declaration(Support.SUPPORTED, "x") for c in Capability}
    with pytest.raises(ContractError):
        ArmSpec("X1", "n", (Track.RETRIEVAL_ONLY,), capabilities, forced_status=RunStatus.NOT_RUN)
    with pytest.raises(ContractError):
        ArmSpec("X1", "n", (Track.RETRIEVAL_ONLY,), capabilities, RunStatus.OK, "because")


@pytest.mark.parametrize("value", ["gold", "Gold answer", "gold_answer", "gold-slots", "the gold set"])
def test_the_gold_marker_is_caught_as_a_word_in_any_spelling(value: str) -> None:
    with pytest.raises(ContractError, match="gold-like marker"):
        make_request(filters={"language": value})


@pytest.mark.parametrize("value", ["Goldman", "goldstar", "marigold", "id-en"])
def test_words_that_merely_contain_gold_are_not_refused(value: str) -> None:
    assert make_request(filters={"language": value}).filters["language"] == value
