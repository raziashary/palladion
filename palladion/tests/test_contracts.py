from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from evidence_agent.core.models import (
    AccessScope,
    ClaimDraft,
    ClaimKind,
    ContinuityPacket,
    CriticReview,
    EvidenceAuthority,
    EvidenceKind,
    EvidenceRecord,
    EvidenceVerificationState,
    FreshnessState,
    GateDecision,
    GateDisposition,
    Hypothesis,
    InvestigationRequirement,
    LiveObservation,
    LiveOperationStatus,
    PolicyDecision,
    PolicyDecisionStatus,
    ReportedFact,
    RequirementOrigin,
    SourceKind,
    SourceRef,
    TimeBasis,
    VerifiedObservation,
)

NOW = datetime(2026, 10, 17, 7, 12, tzinfo=UTC)
HASH = "a" * 64


def source_ref() -> SourceRef:
    return SourceRef(
        source_kind=SourceKind.DOCUMENT_REVISION,
        tenant_id="tenant-a",
        source_id="family-1",
        revision_id="rev-1",
        chunk_id="chunk-1",
        span_start=0,
        span_end=10,
    )


def source_ref_for(kind: SourceKind) -> SourceRef:
    fields = {"source_kind": kind, "tenant_id": "tenant-a", "source_id": "source-1"}
    if kind is SourceKind.DOCUMENT_REVISION:
        fields.update(revision_id="rev-1", chunk_id="chunk-1", span_start=0, span_end=10)
    return SourceRef(**fields)


def evidence() -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id="evidence-1",
        kind=EvidenceKind.DOCUMENT,
        source_identity="tenant-a:family-1:rev-1",
        content_hash=HASH,
        source_ref=source_ref(),
        provenance=("registry:approval-1", "originals:sha256"),
        authority=EvidenceAuthority.CANONICAL_SOURCE,
        authority_record="approval-1",
        occurred_at=NOW,
        acl=AccessScope(tenant_id="tenant-a", allowed_case_ids=("case-1",)),
        verification=EvidenceVerificationState.VALID,
        run_trace_id="trace-1",
    )


def test_evidence_json_round_trip_preserves_provenance_and_schema_version() -> None:
    original = evidence()
    restored = EvidenceRecord.model_validate_json(original.model_dump_json())
    assert restored == original
    assert restored.schema_version == "1.0"
    assert restored.provenance == ("registry:approval-1", "originals:sha256")


@pytest.mark.parametrize(
    "change",
    [
        {"kind": "UNKNOWN"},
        {"unexpected": "extra"},
        {"schema_version": "99.0"},
        {"occurred_at": datetime(2026, 10, 17, 7, 12)},
    ],
)
def test_evidence_rejects_unknown_enum_extras_and_naive_timestamps(change: dict) -> None:
    fields = evidence().model_dump()
    fields.update(change)
    with pytest.raises(ValidationError):
        EvidenceRecord.model_validate(fields)


def test_evidence_requires_provenance_and_tenant_consistent_acl() -> None:
    fields = evidence().model_dump()
    fields["provenance"] = ()
    with pytest.raises(ValidationError, match="provenance"):
        EvidenceRecord.model_validate(fields)

    fields = evidence().model_dump()
    fields["acl"] = AccessScope(tenant_id="tenant-b")
    with pytest.raises(ValidationError, match="tenant"):
        EvidenceRecord.model_validate(fields)


def test_case_event_report_provenance_is_separate_from_organization_authority() -> None:
    event_ref = SourceRef(
        source_kind=SourceKind.CASE_EVENT,
        tenant_id="tenant-a",
        source_id="event-1",
    )
    record = EvidenceRecord(
        evidence_id="event-evidence-1",
        kind=EvidenceKind.CASE_EVENT,
        source_identity="case-event:event-1",
        content_hash=HASH,
        source_ref=event_ref,
        provenance=("case-event:event-1",),
        reported_fact_provenance=("reported-by:operator-1",),
        authority=EvidenceAuthority.NONE,
        occurred_at=NOW,
        acl=AccessScope(tenant_id="tenant-a"),
        verification=EvidenceVerificationState.UNKNOWN,
        run_trace_id="trace-1",
    )
    assert record.authority_record is None
    assert record.reported_fact_provenance == ("reported-by:operator-1",)

    fields = record.model_dump()
    fields["authority"] = EvidenceAuthority.CANONICAL_SOURCE
    fields["authority_record"] = "approval-1"
    with pytest.raises(ValidationError, match="case-event evidence"):
        EvidenceRecord.model_validate(fields)


@pytest.mark.parametrize(
    ("evidence_kind", "source_kind"),
    [
        (EvidenceKind.DOCUMENT, SourceKind.DOCUMENT_REVISION),
        (EvidenceKind.POLICY_DECISION, SourceKind.POLICY_DECISION),
        (EvidenceKind.LIVE_OBSERVATION, SourceKind.LIVE_LOOKUP),
        (EvidenceKind.CASE_EVENT, SourceKind.CASE_EVENT),
    ],
)
def test_evidence_kinds_accept_their_matching_source_reference(
    evidence_kind: EvidenceKind, source_kind: SourceKind
) -> None:
    fields = evidence().model_dump()
    fields["kind"] = evidence_kind
    fields["source_ref"] = source_ref_for(source_kind)
    fields["source_identity"] = f"{source_kind.value}:source-1"
    if evidence_kind is EvidenceKind.CASE_EVENT:
        fields["authority"] = EvidenceAuthority.NONE
        fields["authority_record"] = None
        fields["verification"] = EvidenceVerificationState.UNKNOWN
    elif evidence_kind is EvidenceKind.POLICY_DECISION:
        fields["authority"] = EvidenceAuthority.APPROVED_POLICY
        fields["authority_record"] = "decision-trace-1"
    elif evidence_kind is EvidenceKind.LIVE_OBSERVATION:
        fields["authority"] = EvidenceAuthority.OPERATIONAL_OBSERVATION
        fields["authority_record"] = "synthetic-ledger"
    assert EvidenceRecord.model_validate(fields).kind is evidence_kind


@pytest.mark.parametrize(
    ("evidence_kind", "source_kind"),
    [
        (EvidenceKind.DOCUMENT, SourceKind.POLICY_DECISION),
        (EvidenceKind.POLICY_DECISION, SourceKind.LIVE_LOOKUP),
        (EvidenceKind.LIVE_OBSERVATION, SourceKind.CASE_EVENT),
        (EvidenceKind.CASE_EVENT, SourceKind.DOCUMENT_REVISION),
    ],
)
def test_evidence_kind_rejects_a_different_valid_source_reference(
    evidence_kind: EvidenceKind, source_kind: SourceKind
) -> None:
    fields = evidence().model_dump()
    fields["kind"] = evidence_kind
    fields["source_ref"] = source_ref_for(source_kind)
    if evidence_kind is EvidenceKind.CASE_EVENT:
        fields["authority"] = EvidenceAuthority.NONE
        fields["authority_record"] = None
        fields["verification"] = EvidenceVerificationState.UNKNOWN
    with pytest.raises(ValidationError, match="evidence kind and source reference kind"):
        EvidenceRecord.model_validate(fields)


def test_claim_types_keep_reported_and_hypothesis_separate() -> None:
    verified = ClaimDraft(
        claim_id="claim-verified",
        statement="A source states a settlement hold applies.",
        kind=ClaimKind.VERIFIED,
        evidence_refs=("ev-1",),
    )
    reported = ClaimDraft(
        claim_id="claim-reported",
        statement="The operator reports a debit.",
        kind=ClaimKind.REPORTED,
        provenance=("case-event:event-1",),
    )
    hypothesis = ClaimDraft(
        claim_id="claim-hypothesis",
        statement="A delayed callback may explain the discrepancy.",
        kind=ClaimKind.HYPOTHESIS,
    )
    serialized = [item.model_dump_json() for item in (verified, reported, hypothesis)]
    assert [ClaimDraft.model_validate_json(item).kind for item in serialized] == [
        ClaimKind.VERIFIED,
        ClaimKind.REPORTED,
        ClaimKind.HYPOTHESIS,
    ]
    with pytest.raises(ValidationError, match="evidence references"):
        ClaimDraft(claim_id="bad", statement="unsupported", kind=ClaimKind.VERIFIED)
    with pytest.raises(ValidationError, match="provenance"):
        ClaimDraft(claim_id="bad", statement="reported", kind=ClaimKind.REPORTED)


def test_packet_round_trip_preserves_distinct_fact_classes_and_aware_times() -> None:
    packet = ContinuityPacket(
        case_id="case-1",
        tenant_id="tenant-a",
        agent_role="support_investigator",
        current_goal="Establish settlement state",
        verified_observations=(
            VerifiedObservation(
                fact_id="live-1",
                predicate="transaction_state",
                value="PENDING",
                evidence_id="ev-live-1",
                observed_at=NOW,
                freshness_status="RECHECK_FOR_CURRENT_DECISION",
            ),
        ),
        reported_facts=(
            ReportedFact(
                fact_id="report-1",
                statement="Operator reports a debit",
                source="operator",
                validity_policy_id="user-defined",
                provenance=("case-event:event-1",),
            ),
        ),
        hypotheses=(
            Hypothesis(hypothesis_id="hyp-1", statement="Delayed callback"),
        ),
        evidence_handles=(source_ref(),),
        last_disposition=GateDisposition.PARTIALLY_SUPPORTED,
        generated_at=NOW,
    )
    restored = ContinuityPacket.model_validate_json(packet.model_dump_json())
    assert restored == packet
    assert len(restored.verified_observations) == 1
    assert len(restored.reported_facts) == 1
    assert len(restored.hypotheses) == 1
    assert restored.last_disposition is GateDisposition.PARTIALLY_SUPPORTED
    with pytest.raises(ValidationError):
        Hypothesis(hypothesis_id="hyp-2", statement="bad", label="REPORTED")
    packet_fields = packet.model_dump()
    packet_fields["last_disposition"] = "MAYBE"
    with pytest.raises(ValidationError):
        ContinuityPacket.model_validate(packet_fields)


def test_contracts_reject_naive_times_bad_reference_shapes_and_invalid_disposition() -> None:
    with pytest.raises(ValidationError, match="revision_id and chunk_id"):
        SourceRef(
            source_kind=SourceKind.DOCUMENT_REVISION,
            tenant_id="tenant-a",
            source_id="family-1",
        )
    with pytest.raises(ValidationError, match="timezone"):
        PolicyDecision(
            status=PolicyDecisionStatus.DETERMINED,
            policy_family_id="policy-1",
            as_of=datetime(2026, 10, 17),
            audit_id="audit-1",
        )
    with pytest.raises(ValidationError):
        GateDecision(disposition="MAYBE", safe_template_key="safe")


def test_policy_requirements_and_gate_use_typed_enums() -> None:
    requirement = InvestigationRequirement(
        slot="settlement_state", origin=RequirementOrigin.POLICY_SCHEMA
    )
    assert requirement.origin is RequirementOrigin.POLICY_SCHEMA
    gate = GateDecision(
        disposition=GateDisposition.PARTIALLY_SUPPORTED,
        verified_claim_ids=("claim-1",),
        blocked_claim_ids=("claim-2",),
        cited_evidence_ids=("ev-1",),
        missing_requirements=("settlement_state",),
        safe_template_key="partial-investigation",
    )
    assert gate.disposition.value == "PARTIALLY_SUPPORTED"
    with pytest.raises(ValidationError):
        CriticReview(proposed_disposition="MAYBE")


def test_policy_statuses_distinguish_incomplete_from_determined() -> None:
    incomplete = PolicyDecision(
        status=PolicyDecisionStatus.INCOMPLETE_INPUT,
        policy_family_id="policy-1",
        audit_id="audit-incomplete",
        missing_fields=("settlement_state",),
    )
    assert incomplete.version_id is None
    assert incomplete.as_of is None
    unverified = PolicyDecision(
        status=PolicyDecisionStatus.UNVERIFIED_INPUT,
        policy_family_id="policy-1",
        audit_id="audit-unverified",
    )
    assert unverified.status is PolicyDecisionStatus.UNVERIFIED_INPUT

    with pytest.raises(ValidationError, match="determined policy decisions require"):
        PolicyDecision(
            status=PolicyDecisionStatus.DETERMINED,
            policy_family_id="policy-1",
            audit_id="audit-determined",
        )
    decision = PolicyDecision(
        status=PolicyDecisionStatus.DETERMINED,
        policy_family_id="policy-1",
        version_id="version-1",
        time_basis=TimeBasis.TRANSACTION_OCCURRED_AT,
        as_of=NOW,
        matched_rules=("row-investigate",),
        rule_trace=("row-investigate matched transaction_state=FAILED",),
        input_evidence_refs=("ev-live-1",),
        source_clauses=(source_ref(),),
        audit_id="audit-determined",
    )
    assert decision.status is PolicyDecisionStatus.DETERMINED

    with pytest.raises(ValidationError):
        PolicyDecision(
            status="INCOMPLETE",
            policy_family_id="policy-1",
            audit_id="bad-status",
        )
    with pytest.raises(ValidationError):
        PolicyDecision(
            status=PolicyDecisionStatus.INCOMPLETE_INPUT,
            policy_family_id="policy-1",
            time_basis="MADE_UP_TIME",
            audit_id="bad-time-basis",
        )


def test_live_observation_round_trip_keeps_observed_and_source_times_distinct() -> None:
    live_ref = SourceRef(
        source_kind=SourceKind.LIVE_LOOKUP,
        tenant_id="tenant-a",
        source_id="lookup-1",
    )
    observation = LiveObservation(
        lookup_id="lookup-1",
        operation_id="transaction_status",
        operation_status=LiveOperationStatus.OK,
        source_system="synthetic_ledger",
        data={"status": "PENDING"},
        observed_at=NOW,
        source_event_at=NOW.replace(minute=5),
        data_as_of=NOW.replace(minute=10),
        freshness_state=FreshnessState.RECHECK_FOR_CURRENT_DECISION,
        scope=AccessScope(tenant_id="tenant-a", allowed_case_ids=("case-1",)),
        source_ref=live_ref,
    )
    restored = LiveObservation.model_validate_json(observation.model_dump_json())
    assert restored.observed_at != restored.source_event_at
    assert restored.data_as_of != restored.observed_at
    assert restored.data["status"] == "PENDING"
    with pytest.raises(ValidationError):
        LiveObservation.model_validate(
            {**observation.model_dump(), "operation_status": "MAYBE"}
        )
    with pytest.raises(ValidationError):
        LiveObservation.model_validate(
            {**observation.model_dump(), "freshness_state": "MAYBE"}
        )
