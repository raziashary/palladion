"""Versioned, strict domain contracts for the evidence-first prototype."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    """Base for persisted/request contracts: reject coercion and unknown fields."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class VersionedModel(StrictModel):
    schema_version: Literal["1.0"] = "1.0"


class EvidenceKind(StrEnum):
    DOCUMENT = "DOCUMENT"
    POLICY_DECISION = "POLICY_DECISION"
    LIVE_OBSERVATION = "LIVE_OBSERVATION"
    CASE_EVENT = "CASE_EVENT"


class EvidenceAuthority(StrEnum):
    CANONICAL_SOURCE = "CANONICAL_SOURCE"
    APPROVED_POLICY = "APPROVED_POLICY"
    OPERATIONAL_OBSERVATION = "OPERATIONAL_OBSERVATION"
    NONE = "NONE"


class VerificationState(StrEnum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    REQUIRES_RECHECK = "REQUIRES_RECHECK"
    REJECTED = "REJECTED"


class EvidenceVerificationState(StrEnum):
    VALID = "VALID"
    STALE = "STALE"
    CONFLICTING = "CONFLICTING"
    INACCESSIBLE = "INACCESSIBLE"
    UNKNOWN = "UNKNOWN"


class SourceKind(StrEnum):
    DOCUMENT_REVISION = "DOCUMENT_REVISION"
    POLICY_DECISION = "POLICY_DECISION"
    LIVE_LOOKUP = "LIVE_LOOKUP"
    CASE_EVENT = "CASE_EVENT"


class SourceRef(VersionedModel):
    source_kind: SourceKind
    tenant_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    revision_id: str | None = None
    chunk_id: str | None = None
    span_start: int | None = Field(default=None, ge=0)
    span_end: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_shape(self) -> SourceRef:
        if self.source_kind is SourceKind.DOCUMENT_REVISION:
            if not self.revision_id or not self.chunk_id:
                raise ValueError("document source references require revision_id and chunk_id")
            if (self.span_start is None) != (self.span_end is None):
                raise ValueError("document source spans require both start and end")
            if self.span_start is not None and self.span_end is not None and self.span_end < self.span_start:
                raise ValueError("span_end must be greater than or equal to span_start")
        elif any(value is not None for value in (self.revision_id, self.chunk_id, self.span_start, self.span_end)):
            raise ValueError("non-document references cannot carry document span fields")
        return self


class Principal(VersionedModel):
    principal_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    roles: tuple[str, ...] = ()
    allowed_case_ids: tuple[str, ...] = ()
    grants: tuple[str, ...] = ()

    @field_validator("roles", "allowed_case_ids", "grants")
    @classmethod
    def require_unique_nonempty_entries(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(not value for value in values) or len(values) != len(set(values)):
            raise ValueError("principal collections must contain unique non-empty values")
        return values


class AccessScope(VersionedModel):
    tenant_id: str = Field(min_length=1)
    allowed_case_ids: tuple[str, ...] = ()
    required_roles: tuple[str, ...] = ()


class EvidenceRecord(VersionedModel):
    evidence_id: str = Field(min_length=1)
    kind: EvidenceKind
    source_identity: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_ref: SourceRef
    provenance: tuple[str, ...] = Field(min_length=1)
    reported_fact_provenance: tuple[str, ...] = ()
    authority: EvidenceAuthority
    authority_record: str | None = None
    occurred_at: datetime
    observed_at: datetime | None = None
    acl: AccessScope
    verification: EvidenceVerificationState
    run_trace_id: str = Field(min_length=1)

    @field_validator("occurred_at", "observed_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("timestamps must include a timezone")
        return value

    @model_validator(mode="after")
    def match_acl_tenant(self) -> EvidenceRecord:
        expected_source_kind = {
            EvidenceKind.DOCUMENT: SourceKind.DOCUMENT_REVISION,
            EvidenceKind.POLICY_DECISION: SourceKind.POLICY_DECISION,
            EvidenceKind.LIVE_OBSERVATION: SourceKind.LIVE_LOOKUP,
            EvidenceKind.CASE_EVENT: SourceKind.CASE_EVENT,
        }[self.kind]
        if self.source_ref.source_kind is not expected_source_kind:
            raise ValueError("evidence kind and source reference kind must match")
        if self.source_ref.tenant_id != self.acl.tenant_id:
            raise ValueError("source and ACL tenant IDs must match")
        if self.kind is EvidenceKind.CASE_EVENT and self.authority is not EvidenceAuthority.NONE:
            raise ValueError("case-event evidence cannot itself establish organization authority")
        if self.authority is EvidenceAuthority.NONE and self.authority_record is not None:
            raise ValueError("authority records require an organization authority kind")
        if self.authority is not EvidenceAuthority.NONE and self.authority_record is None:
            raise ValueError("organization authority requires an authority record")
        if self.reported_fact_provenance and self.authority is not EvidenceAuthority.NONE:
            raise ValueError("reported fact provenance must remain separate from organization authority")
        if self.reported_fact_provenance and self.kind is not EvidenceKind.CASE_EVENT:
            raise ValueError("reported fact provenance must be carried by case-event evidence")
        return self


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    UNAVAILABLE = "UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class OperationStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class GateDisposition(StrEnum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    CONFLICT = "CONFLICT"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"
    VERIFICATION_UNAVAILABLE = "VERIFICATION_UNAVAILABLE"


class TimeBasis(StrEnum):
    TRANSACTION_OCCURRED_AT = "TRANSACTION_OCCURRED_AT"
    CASE_OPENED_AT = "CASE_OPENED_AT"
    EVALUATION_AT = "EVALUATION_AT"
    DOMAIN_EVENT_AT = "DOMAIN_EVENT_AT"


class LiveOperationStatus(StrEnum):
    OK = "OK"
    NOT_FOUND = "NOT_FOUND"
    FORBIDDEN = "FORBIDDEN"
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    STALE_DATA = "STALE_DATA"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
    UNAVAILABLE = "UNAVAILABLE"
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"


class FreshnessState(StrEnum):
    FRESH = "FRESH"
    STALE = "STALE"
    RECHECK_FOR_CURRENT_DECISION = "RECHECK_FOR_CURRENT_DECISION"
    UNKNOWN = "UNKNOWN"


class ErrorEnvelope(VersionedModel):
    error_code: ErrorCode
    retryable: bool
    source_ref: SourceRef | None = None
    correlation_id: str = Field(min_length=1)
    user_summary: str = Field(min_length=1)


class ResultEnvelope(VersionedModel):
    status: OperationStatus
    error: ErrorEnvelope | None = None
    source_ref: SourceRef | None = None
    correlation_id: str = Field(min_length=1)
    data: dict[str, Any] | None = None

    @model_validator(mode="after")
    def status_has_consistent_error(self) -> ResultEnvelope:
        if self.status is OperationStatus.FAILED and self.error is None:
            raise ValueError("failed results require an error envelope")
        if self.status is OperationStatus.SUCCEEDED and self.error is not None:
            raise ValueError("successful results cannot carry an error envelope")
        return self


class ClaimKind(StrEnum):
    VERIFIED = "VERIFIED"
    REPORTED = "REPORTED"
    HYPOTHESIS = "HYPOTHESIS"


class ClaimDraft(VersionedModel):
    claim_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    kind: ClaimKind
    evidence_refs: tuple[str, ...] = ()
    provenance: tuple[str, ...] = ()

    @model_validator(mode="after")
    def require_claim_provenance(self) -> ClaimDraft:
        if self.kind is ClaimKind.VERIFIED and not self.evidence_refs:
            raise ValueError("verified claims require evidence references")
        if self.kind is ClaimKind.REPORTED and not self.provenance:
            raise ValueError("reported claims require provenance")
        return self


class RequirementOrigin(StrEnum):
    POLICY_SCHEMA = "POLICY_SCHEMA"
    TRUSTED_CASE = "TRUSTED_CASE"
    MODEL_SUGGESTION = "MODEL_SUGGESTION"


class InvestigationRequirement(VersionedModel):
    slot: str = Field(min_length=1)
    origin: RequirementOrigin
    required: bool = True


class InvestigationRequirements(VersionedModel):
    factual_slots: tuple[InvestigationRequirement, ...] = ()
    normative_slots: tuple[InvestigationRequirement, ...] = ()
    optional_slots: tuple[InvestigationRequirement, ...] = ()
    question_kind: str = Field(min_length=1)
    risk_tier: str = Field(min_length=1)


class PolicyDecisionStatus(StrEnum):
    DETERMINED = "DETERMINED"
    INCOMPLETE_INPUT = "INCOMPLETE_INPUT"
    UNVERIFIED_INPUT = "UNVERIFIED_INPUT"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NO_APPLICABLE_POLICY = "NO_APPLICABLE_POLICY"
    POLICY_CONFLICT = "POLICY_CONFLICT"
    VERIFICATION_UNAVAILABLE = "VERIFICATION_UNAVAILABLE"


class PolicyDecision(VersionedModel):
    status: PolicyDecisionStatus
    policy_family_id: str = Field(min_length=1)
    version_id: str | None = None
    time_basis: TimeBasis | None = None
    as_of: datetime | None = None
    matched_rules: tuple[str, ...] = ()
    rule_trace: tuple[str, ...] = ()
    input_evidence_refs: tuple[str, ...] = ()
    temporal_input_refs: tuple[str, ...] = Field(default=(), max_length=32)
    source_clauses: tuple[SourceRef, ...] = ()
    missing_fields: tuple[str, ...] = ()
    audit_id: str = Field(min_length=1)
    outcome: str | None = None
    normalized_inputs: dict[str, Any] = Field(default_factory=dict)
    required_fields: tuple[str, ...] = ()
    selection_trace: tuple[str, ...] = ()
    evaluation_mode: Literal["current", "historical_audit"] = "current"
    knowledge_cutoff: datetime | None = None
    evaluated_at: datetime | None = None

    @field_validator("as_of", "knowledge_cutoff", "evaluated_at")
    @classmethod
    def require_aware_as_of(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("as_of must include a timezone")
        return value

    @model_validator(mode="after")
    def determined_has_complete_selection(self) -> PolicyDecision:
        if self.status is PolicyDecisionStatus.DETERMINED and not all(
            (
                self.version_id,
                self.as_of,
                self.time_basis,
                self.rule_trace,
                self.source_clauses,
                self.input_evidence_refs or (self.outcome is not None and
                    not self.normalized_inputs and not self.required_fields),
            )
        ):
            raise ValueError(
                "determined policy decisions require version, as_of, time basis, rule trace, "
                "source clauses and input evidence references"
            )
        return self


class LiveObservation(VersionedModel):
    lookup_id: str = Field(min_length=1)
    operation_id: str = Field(min_length=1)
    operation_status: LiveOperationStatus
    source_system: str = Field(min_length=1)
    data: dict[str, Any]
    observed_at: datetime
    source_event_at: datetime | None = None
    data_as_of: datetime | None = None
    freshness_state: FreshnessState
    scope: AccessScope
    source_ref: SourceRef
    error: ErrorEnvelope | None = None

    @field_validator("observed_at", "source_event_at", "data_as_of")
    @classmethod
    def require_aware_observation_time(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("observation timestamps must include a timezone")
        return value

    @model_validator(mode="after")
    def match_scope_tenant(self) -> LiveObservation:
        if self.scope.tenant_id != self.source_ref.tenant_id:
            raise ValueError("observation and source reference tenant IDs must match")
        return self


class VerifiedObservation(VersionedModel):
    fact_id: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    value: Any
    evidence_id: str = Field(min_length=1)
    observed_at: datetime
    freshness_status: str = Field(min_length=1)

    @field_validator("observed_at")
    @classmethod
    def require_aware_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must include a timezone")
        return value


class ReportedFact(VersionedModel):
    fact_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    source: str = Field(min_length=1)
    verification_status: VerificationState = VerificationState.UNVERIFIED
    validity_policy_id: str = Field(min_length=1)
    provenance: tuple[str, ...] = Field(min_length=1)


class Hypothesis(VersionedModel):
    hypothesis_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    supporting_evidence_refs: tuple[str, ...] = ()
    label: Literal["HYPOTHESIS"] = "HYPOTHESIS"


class ContinuityPacket(VersionedModel):
    case_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    agent_role: str = Field(min_length=1)
    current_goal: str = Field(min_length=1)
    verified_observations: tuple[VerifiedObservation, ...] = ()
    reported_facts: tuple[ReportedFact, ...] = ()
    hypotheses: tuple[Hypothesis, ...] = ()
    open_questions: tuple[str, ...] = ()
    evidence_handles: tuple[SourceRef, ...] = ()
    previous_attempts: tuple[dict[str, Any], ...] = ()
    last_disposition: GateDisposition | None = None
    generated_at: datetime

    @field_validator("generated_at")
    @classmethod
    def require_aware_generated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must include a timezone")
        return value

    @model_validator(mode="after")
    def handles_match_tenant(self) -> ContinuityPacket:
        if any(ref.tenant_id != self.tenant_id for ref in self.evidence_handles):
            raise ValueError("packet evidence handles must match packet tenant")
        return self


class CriticReview(VersionedModel):
    finding_by_claim: dict[str, str] = Field(default_factory=dict)
    missing_slots: tuple[str, ...] = ()
    contrary_evidence_refs: tuple[str, ...] = ()
    suggested_counter_searches: tuple[str, ...] = ()
    proposed_disposition: GateDisposition


class GateDecision(VersionedModel):
    disposition: GateDisposition
    verified_claim_ids: tuple[str, ...] = ()
    blocked_claim_ids: tuple[str, ...] = ()
    cited_evidence_ids: tuple[str, ...] = ()
    missing_requirements: tuple[str, ...] = ()
    safe_template_key: str = Field(min_length=1)
