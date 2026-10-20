"""Strict loader and integrity checks for the synthetic Slice 0 corpus."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from evidence_agent.core.models import Principal

_TIME_SOURCES = {
    "TRANSACTION_OCCURRED_AT": "verified_live.transaction_occurred_at",
    "EVALUATION_AT": "server_clock.evaluation_time",
}

class FixtureValidationError(ValueError):
    """Raised when a synthetic fixture is malformed or internally inconsistent."""


class StrictFixture(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class CaseFixture(StrictFixture):
    case_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    product: str = Field(min_length=1)
    transaction_class: str = Field(min_length=1)
    transaction_id: str = Field(min_length=1)
    opened_at: datetime
    allowed_principal_ids: tuple[str, ...]

    @field_validator("opened_at")
    @classmethod
    def aware_opened_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("case opened_at must include a timezone")
        return value


class SourceMetadata(StrictFixture):
    source_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    family_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    approval_state: Literal["APPROVED", "DRAFT", "REVIEW", "REVOKED"]
    approval_record_id: str | None
    approved_by: str | None
    approved_at: datetime | None
    valid_from: datetime | None
    valid_to: datetime | None
    case_ids: tuple[str, ...]
    allowed_principal_ids: tuple[str, ...] = ()
    supersedes: tuple[str, ...]
    visibility: Literal["tenant", "case"]

    @field_validator("approved_at", "valid_from", "valid_to")
    @classmethod
    def aware_optional_times(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("source timestamps must include a timezone")
        return value

    @model_validator(mode="after")
    def approval_metadata_matches_state(self) -> SourceMetadata:
        if self.approval_state == "APPROVED":
            if not all((self.approval_record_id, self.approved_by, self.approved_at, self.valid_from)):
                raise ValueError("approved source requires trusted approval and validity metadata")
            if self.valid_to is not None and self.valid_from is not None and self.valid_to <= self.valid_from:
                raise ValueError("source valid_to must be after valid_from")
        elif any(value is not None for value in (self.approval_record_id, self.approved_by, self.approved_at)):
            raise ValueError("unapproved source cannot carry approval metadata")
        return self


class ClauseSpan(StrictFixture):
    clause_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    span_start: int = Field(ge=0)
    span_end: int = Field(ge=0)
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SourceFixture(SourceMetadata):
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_length: int = Field(ge=0)
    clauses: dict[str, ClauseSpan]


class ClauseReference(StrictFixture):
    source_id: str = Field(min_length=1)
    clause_id: str = Field(min_length=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    span_start: int = Field(ge=0)
    span_end: int = Field(ge=0)
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reference_use: Literal["expected_denial_only"] | None = None


class PrincipalScope(StrictFixture):
    tenant_id: str
    principal_id: str
    role: str


class GoldenCase(StrictFixture):
    query_id: str
    case_id: str
    principal_scope: PrincipalScope
    user_question: str = Field(min_length=1)
    setup: dict[str, Any]
    source_clause_refs: tuple[ClauseReference, ...]
    source_reference_not_applicable_reason: str | None = None
    required_fact_slots: tuple[str, ...]
    time_basis: Literal[
        "TRANSACTION_OCCURRED_AT",
        "CASE_OPENED_AT",
        "EVALUATION_AT",
        "DOMAIN_EVENT_AT",
        "MIXED_TRANSACTION_OCCURRED_AT_AND_EVALUATION_AT",
    ] | None
    policy_family_id: str | None
    accepted_policy_version_id: str | None
    expected_policy_decision: str = Field(min_length=1)
    expected_disposition: Literal[
        "SUPPORTED", "PARTIALLY_SUPPORTED", "CONFLICT", "NOT_ESTABLISHED", "VERIFICATION_UNAVAILABLE"
    ]
    allowed_hypotheses: tuple[str, ...]
    forbidden_actions: tuple[str, ...] = Field(min_length=1)
    evaluator_notes: str = Field(min_length=1)

    @model_validator(mode="after")
    def source_reference_contract(self) -> GoldenCase:
        if self.source_clause_refs and self.source_reference_not_applicable_reason is not None:
            raise ValueError("source references and a not-applicable reason cannot both be supplied")
        if not self.source_clause_refs and not (self.source_reference_not_applicable_reason or "").strip():
            raise ValueError("golden without a document reference must explain why no clause applies")
        if len({(ref.source_id, ref.clause_id) for ref in self.source_clause_refs}) != len(self.source_clause_refs):
            raise ValueError("golden source clause references must be unique")
        return self


class ObservationFixture(StrictFixture):
    observation_id: str
    case_id: str
    tenant_id: str
    operation: Literal["get_transaction_status", "get_settlement_status", "get_merchant_summary", "user_report"]
    status: Literal["OK", "TIMEOUT", "REPORTED"]
    source_system: str
    data: dict[str, Any]
    source_event_at: datetime | None
    observed_at: datetime
    data_as_of: datetime | None
    trusted_fields: tuple[str, ...]
    sequence: int = Field(ge=0)

    @field_validator("source_event_at", "observed_at", "data_as_of")
    @classmethod
    def aware_observation_times(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("observation timestamps must include a timezone")
        return value


class SnapshotVersion(StrictFixture):
    snapshot_id: str
    transaction: str | None = None
    settlement: str | None = None
    bi: str | None = None
    recorded_at: datetime

    @field_validator("recorded_at")
    @classmethod
    def aware_recorded_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("snapshot recorded_at must include a timezone")
        return value


class MockSnapshotHistory(StrictFixture):
    versions: tuple[SnapshotVersion, ...]
    changing: bool


class FixtureCatalog(StrictFixture):
    schema_version: Literal[1]
    annotation_status: Literal["PILOT"]
    annotation_note: str = Field(min_length=1)
    principals: tuple[Principal, ...]
    cases: tuple[CaseFixture, ...]
    sources: tuple[SourceMetadata, ...]
    observations: tuple[ObservationFixture, ...]
    mock_snapshots: dict[str, MockSnapshotHistory]


class PolicyFixture(StrictFixture):
    schema_version: Literal[1]
    policy_family_id: str
    description: str
    allowed_time_bases: tuple[str, ...]
    allowed_timestamp_sources: tuple[str, ...]
    allowed_fact_sources: tuple[str, ...]
    versions: tuple[dict[str, Any], ...]
    evaluation_policy: dict[str, Any]
    conflict_fixture: dict[str, Any]


class FixtureSummary(StrictFixture):
    source_count: int
    approved_source_count: int
    case_count: int
    principal_count: int
    observation_count: int
    golden_count: int
    golden_ids: tuple[str, ...]
    policy_version_ids: tuple[str, ...]
    annotation_status: Literal["PILOT"]


class FixtureBundle(StrictFixture):
    root: Path
    principals: tuple[Principal, ...]
    cases: tuple[CaseFixture, ...]
    sources: tuple[SourceFixture, ...]
    observations: tuple[ObservationFixture, ...]
    mock_snapshots: dict[str, Any]
    policy: PolicyFixture
    goldens: tuple[GoldenCase, ...]
    annotation_status: Literal["PILOT"]

    def principal_map(self) -> dict[str, Principal]:
        return {principal.principal_id: principal for principal in self.principals}

    def case_map(self) -> dict[str, CaseFixture]:
        return {case.case_id: case for case in self.cases}

    def source_map(self) -> dict[str, SourceFixture]:
        return {source.source_id: source for source in self.sources}

    def golden_map(self) -> dict[str, GoldenCase]:
        return {golden.query_id: golden for golden in self.goldens}

    def summary(self) -> FixtureSummary:
        versions = [item["policy_version_id"] for item in self.policy.versions]
        versions.append(self.policy.evaluation_policy["policy_version_id"])
        versions.extend(candidate["policy_version_id"] for candidate in self.policy.conflict_fixture["candidates"])
        return FixtureSummary(
            source_count=len(self.sources),
            approved_source_count=sum(source.approval_state == "APPROVED" for source in self.sources),
            case_count=len(self.cases),
            principal_count=len(self.principals),
            observation_count=len(self.observations),
            golden_count=len(self.goldens),
            golden_ids=tuple(golden.query_id for golden in self.goldens),
            policy_version_ids=tuple(versions),
            annotation_status=self.annotation_status,
        )


def _application_root(root: Path) -> Path:
    root = root.resolve()
    if (root / "data" / "demo").is_dir():
        return root
    app_root = root / "palladion"
    if (app_root / "data" / "demo").is_dir():
        return app_root
    raise FixtureValidationError(f"cannot find palladion/data/demo under {root}")


def _unique(items: tuple[Any, ...], attribute: str, label: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in items:
        key = getattr(item, attribute)
        if key in result:
            raise FixtureValidationError(f"duplicate {label}: {key}")
        result[key] = item
    return result


def _parse_json(path: Path, model: type[BaseModel]) -> Any:
    try:
        return model.model_validate_json(path.read_bytes())
    except (ValidationError, OSError) as exc:
        raise FixtureValidationError(f"invalid {path.name}: {exc}") from exc


def _extract_clause_spans(raw: bytes, source_id: str) -> dict[str, ClauseSpan]:
    spans: dict[str, ClauseSpan] = {}
    offset = 0
    lines = raw.splitlines(keepends=True)
    for index, line in enumerate(lines):
        marker = line.rstrip(b"\r\n")
        if marker.startswith(b"[CLAUSE: ") and marker.endswith(b"]"):
            clause_id = marker[len(b"[CLAUSE: ") : -1].decode("ascii")
            if index + 1 >= len(lines):
                raise FixtureValidationError(f"{source_id}#{clause_id} has no clause text")
            body_start = offset + len(line)
            body = lines[index + 1].rstrip(b"\r\n")
            if not body or body.startswith(b"["):
                raise FixtureValidationError(f"{source_id}#{clause_id} has no exact clause body")
            if clause_id in spans:
                raise FixtureValidationError(f"duplicate clause marker: {source_id}#{clause_id}")
            spans[clause_id] = ClauseSpan(
                clause_id=clause_id,
                text=body.decode("utf-8"),
                span_start=body_start,
                span_end=body_start + len(body),
                text_sha256=hashlib.sha256(body).hexdigest(),
            )
        offset += len(line)
    return spans


def _verify_reference(reference: ClauseReference, sources: dict[str, SourceFixture]) -> None:
    source = sources.get(reference.source_id)
    if source is None:
        raise FixtureValidationError(f"unknown source reference: {reference.source_id}")
    clause = source.clauses.get(reference.clause_id)
    if clause is None:
        raise FixtureValidationError(f"unknown clause reference: {reference.source_id}#{reference.clause_id}")
    if (
        reference.source_sha256 != source.sha256
        or reference.span_start != clause.span_start
        or reference.span_end != clause.span_end
        or reference.text_sha256 != clause.text_sha256
    ):
        raise FixtureValidationError(f"source hash/span mismatch: {reference.source_id}#{reference.clause_id}")


def _validate_policy(
    policy: PolicyFixture,
    sources: dict[str, SourceFixture],
    principals: dict[str, Principal],
) -> tuple[str, ...]:
    supported_time_bases = {"TRANSACTION_OCCURRED_AT", "CASE_OPENED_AT", "EVALUATION_AT", "DOMAIN_EVENT_AT"}
    if not policy.allowed_time_bases or set(policy.allowed_time_bases) - supported_time_bases or not policy.allowed_timestamp_sources:
        raise FixtureValidationError("policy must declare allowed time bases and timestamp sources")
    if any(source not in {"verified_live.transaction_occurred_at", "server_clock.evaluation_time"} for source in policy.allowed_timestamp_sources):
        raise FixtureValidationError("policy uses an unknown timestamp source")
    if any(source not in {"verified_live.state", "verified_live.settlement_state"} for source in policy.allowed_fact_sources):
        raise FixtureValidationError("policy uses an unknown fact source")
    version_ids: list[str] = []
    versions = list(policy.versions) + [policy.evaluation_policy]
    for version in versions:
        expected_version_fields = {
            "policy_version_id", "state", "source_clauses", "applicability", "required_facts", "rule_rows", "default_outcome"
        }
        if set(version) != expected_version_fields:
            raise FixtureValidationError("policy version has missing or unknown fields")
        if version.get("state") != "APPROVED":
            raise FixtureValidationError("policy versions used in fixtures must be approved by trusted fixture metadata")
        version_id = version.get("policy_version_id")
        if not isinstance(version_id, str) or not version_id:
            raise FixtureValidationError("policy version is missing policy_version_id")
        if version_id in version_ids:
            raise FixtureValidationError(f"duplicate policy version: {version_id}")
        version_ids.append(version_id)
        applicability = version.get("applicability")
        if not isinstance(applicability, dict) or set(applicability) != {
            "tenant_id", "product", "transaction_class", "time_basis", "timestamp_source", "valid_from", "valid_to", "supersedes"
        }:
            raise FixtureValidationError(f"{version_id} is missing applicability")
        basis = applicability.get("time_basis")
        timestamp_source = applicability.get("timestamp_source")
        if basis not in policy.allowed_time_bases:
            raise FixtureValidationError(f"{version_id} has unknown time basis: {basis}")
        if timestamp_source not in policy.allowed_timestamp_sources:
            raise FixtureValidationError(f"{version_id} has unknown time source: {timestamp_source}")
        if basis in _TIME_SOURCES and timestamp_source != _TIME_SOURCES[basis]:
            raise FixtureValidationError(f"{version_id} timestamp source does not match its declared time basis")
        for time_field in ("valid_from", "valid_to"):
            value = applicability.get(time_field)
            if value is not None:
                try:
                    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except (AttributeError, ValueError) as exc:
                    raise FixtureValidationError(f"{version_id} has invalid {time_field}") from exc
                if parsed.tzinfo is None or parsed.utcoffset() is None:
                    raise FixtureValidationError(f"{version_id} {time_field} must include a timezone")
        start_value = applicability.get("valid_from")
        end_value = applicability.get("valid_to")
        if start_value is not None and end_value is not None:
            start = datetime.fromisoformat(start_value.replace("Z", "+00:00"))
            end = datetime.fromisoformat(end_value.replace("Z", "+00:00"))
            if end <= start:
                raise FixtureValidationError(f"{version_id} has an empty or reversed validity interval")
        required_facts = version.get("required_facts", [])
        if not isinstance(required_facts, list):
            raise FixtureValidationError(f"{version_id} required_facts must be an array")
        for fact in required_facts:
            if (
                not isinstance(fact, dict)
                or set(fact) != {"name", "type", "source", "allowed_values", "max_age_seconds"}
                or fact.get("name") not in {"transaction_state", "settlement_state"}
                or fact.get("type") != "enum"
                or fact.get("source") not in policy.allowed_fact_sources
                or type(fact.get("max_age_seconds")) is not int
                or fact["max_age_seconds"] <= 0
            ):
                raise FixtureValidationError(f"{version_id} has unknown fact source")
        if not isinstance(version.get("rule_rows"), list):
            raise FixtureValidationError(f"{version_id} rule_rows must be an array")
        clause_refs = list(version.get("source_clauses", []))
        for row in version.get("rule_rows", []):
            if not isinstance(row, dict) or set(row) - {"id", "all", "any", "outcome", "source_clause"} or not {"id", "source_clause", "outcome"}.issubset(row):
                raise FixtureValidationError(f"{version_id} rule row is missing source_clause")
            conditions = row.get("all", row.get("any", []))
            if not isinstance(conditions, list) or ("all" in row and "any" in row):
                raise FixtureValidationError(f"{version_id} rule row has invalid conditions")
            for condition in conditions:
                if (
                    not isinstance(condition, dict)
                    or set(condition) != {"field", "operator", "value"}
                    or condition.get("field") not in {"transaction_state", "settlement_state"}
                    or condition.get("operator") not in {"eq", "in", "lt", "lte", "gt", "gte"}
                ):
                    raise FixtureValidationError(f"{version_id} rule row has unknown field or operator")
            clause_refs.append(row["source_clause"])
        for ref_data in clause_refs:
            try:
                ref = ClauseReference.model_validate(ref_data)
            except ValidationError as exc:
                raise FixtureValidationError(f"{version_id} has malformed source clause: {exc}") from exc
            _verify_reference(ref, sources)
            if sources[ref.source_id].approval_state != "APPROVED":
                raise FixtureValidationError(f"policy cites unapproved source: {ref.source_id}")
            if sources[ref.source_id].tenant_id != applicability["tenant_id"]:
                raise FixtureValidationError(f"policy {version_id} cites a source from another tenant")
    conflict = policy.conflict_fixture
    if set(conflict) != {"description", "candidates", "expected_outcome"} or conflict.get("expected_outcome") != "POLICY_CONFLICT":
        raise FixtureValidationError("conflict fixture must declare candidates and expect POLICY_CONFLICT")
    candidates = conflict.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 2:
        raise FixtureValidationError("conflict fixture must declare exactly two policy candidates")
    candidate_ids: list[str] = []
    candidate_windows: list[tuple[datetime, datetime | None]] = []
    shared_scope: tuple[str, str, str, str, str] | None = None
    for candidate in candidates:
        candidate_fields = {
            "policy_version_id", "state", "approval_record_id", "approved_by", "approved_at", "registered_at",
            "source_clauses", "applicability",
        }
        if not isinstance(candidate, dict) or set(candidate) != candidate_fields or candidate.get("state") != "APPROVED":
            raise FixtureValidationError("conflict candidate must be a complete approved policy record")
        candidate_id = candidate.get("policy_version_id")
        if not isinstance(candidate_id, str) or not candidate_id or candidate_id in version_ids or candidate_id in candidate_ids:
            raise FixtureValidationError("conflict fixture has an unknown or duplicate policy version ID")
        candidate_ids.append(candidate_id)
        applicability = candidate.get("applicability")
        applicability_fields = {
            "tenant_id", "product", "transaction_class", "time_basis", "timestamp_source", "valid_from", "valid_to",
            "supersedes", "precedence",
        }
        if not isinstance(applicability, dict) or set(applicability) != applicability_fields:
            raise FixtureValidationError(f"conflict candidate {candidate_id} has incomplete applicability")
        approver = principals.get(candidate.get("approved_by", ""))
        if (
            approver is None
            or approver.tenant_id != applicability["tenant_id"]
            or "admin" not in approver.roles
            or "document:approve" not in approver.grants
            or not candidate.get("approval_record_id")
        ):
            raise FixtureValidationError(f"conflict candidate {candidate_id} lacks trusted admin approval metadata")
        scope_values = tuple(
            applicability.get(field)
            for field in ("tenant_id", "product", "transaction_class", "time_basis", "timestamp_source")
        )
        if any(not isinstance(value, str) or not value for value in scope_values):
            raise FixtureValidationError(f"conflict candidate {candidate_id} has incomplete scope")
        scope = cast(tuple[str, str, str, str, str], scope_values)
        if shared_scope is None:
            shared_scope = scope
        elif scope != shared_scope:
            raise FixtureValidationError("conflict candidates must share tenant, product, transaction class, time basis, and timestamp source")
        if applicability["time_basis"] not in policy.allowed_time_bases or applicability["timestamp_source"] not in policy.allowed_timestamp_sources:
            raise FixtureValidationError(f"conflict candidate {candidate_id} has an unknown time basis or source")
        if applicability["time_basis"] in _TIME_SOURCES and applicability["timestamp_source"] != _TIME_SOURCES[applicability["time_basis"]]:
            raise FixtureValidationError(f"conflict candidate {candidate_id} has a mismatched timestamp source")
        if applicability["supersedes"] or applicability["precedence"] is not None:
            raise FixtureValidationError("conflict candidates cannot have a supersession or precedence relationship")
        parsed_times: dict[str, datetime | None] = {}
        for field in ("valid_from", "valid_to"):
            value = applicability[field]
            if value is not None and not isinstance(value, str):
                raise FixtureValidationError(f"conflict candidate {candidate_id} has invalid {field}")
            try:
                parsed_candidate_time = (
                    datetime.fromisoformat(value.replace("Z", "+00:00")) if value is not None else None
                )
            except (AttributeError, ValueError) as exc:
                raise FixtureValidationError(f"conflict candidate {candidate_id} has invalid {field}") from exc
            if parsed_candidate_time is not None and (
                parsed_candidate_time.tzinfo is None or parsed_candidate_time.utcoffset() is None
            ):
                raise FixtureValidationError(f"conflict candidate {candidate_id} {field} must include a timezone")
            parsed_times[field] = parsed_candidate_time
        candidate_start = parsed_times["valid_from"]
        candidate_end = parsed_times["valid_to"]
        if candidate_start is None or (candidate_end is not None and candidate_end <= candidate_start):
            raise FixtureValidationError(f"conflict candidate {candidate_id} has an empty or invalid half-open interval")
        candidate_windows.append((candidate_start, candidate_end))
        approved_at = candidate.get("approved_at")
        registered_at = candidate.get("registered_at")
        if not isinstance(approved_at, str) or not isinstance(registered_at, str):
            raise FixtureValidationError(f"conflict candidate {candidate_id} has invalid approval or record time")
        try:
            approved_time = datetime.fromisoformat(approved_at.replace("Z", "+00:00"))
            registered_time = datetime.fromisoformat(registered_at.replace("Z", "+00:00"))
        except (AttributeError, ValueError) as exc:
            raise FixtureValidationError(f"conflict candidate {candidate_id} has invalid approval or record time") from exc
        if (
            approved_time.tzinfo is None
            or approved_time.utcoffset() is None
            or registered_time.tzinfo is None
            or registered_time.utcoffset() is None
            or registered_time < approved_time
        ):
            raise FixtureValidationError(f"conflict candidate {candidate_id} has invalid approval/record ordering")
        candidate_clauses = candidate.get("source_clauses")
        if not isinstance(candidate_clauses, list) or not candidate_clauses:
            raise FixtureValidationError(f"conflict candidate {candidate_id} requires approved source clauses")
        for ref_data in candidate_clauses:
            try:
                ref = ClauseReference.model_validate(ref_data)
            except ValidationError as exc:
                raise FixtureValidationError(f"conflict candidate {candidate_id} has malformed source clause") from exc
            _verify_reference(ref, sources)
            source = sources[ref.source_id]
            if source.approval_state != "APPROVED" or source.tenant_id != applicability["tenant_id"]:
                raise FixtureValidationError(f"conflict candidate {candidate_id} cites an unapproved or cross-tenant source")
            if source.valid_from is None or source.valid_from > candidate_start:
                raise FixtureValidationError(f"conflict candidate {candidate_id} begins before its source is valid")
            if source.valid_to is not None and (candidate_end is None or candidate_end > source.valid_to):
                raise FixtureValidationError(f"conflict candidate {candidate_id} extends beyond its source validity")
    (first_start, first_end), (second_start, second_end) = candidate_windows
    overlap_start = max(first_start, second_start)
    overlap_end = min((end or datetime.max.replace(tzinfo=overlap_start.tzinfo) for _, end in candidate_windows))
    if overlap_start >= overlap_end:
        raise FixtureValidationError("conflict candidate half-open validity intervals do not overlap")
    version_ids.extend(candidate_ids)
    return tuple(version_ids)


def _validate_case_inventory(
    catalog: FixtureCatalog,
    principals: dict[str, Principal],
    cases: dict[str, CaseFixture],
    sources: dict[str, SourceFixture],
    observations: dict[str, ObservationFixture],
    goldens: tuple[GoldenCase, ...],
    policy_version_ids: tuple[str, ...],
    policy: PolicyFixture,
) -> None:
    if {case.tenant_id for case in catalog.cases} != {"tenant-a", "tenant-b"}:
        raise FixtureValidationError("fixture catalog must cover exactly tenant-a and tenant-b")
    if not {"admin", "uploader", "reader"}.issubset({role for principal in catalog.principals for role in principal.roles}):
        raise FixtureValidationError("fixture catalog must include admin, uploader, and reader roles")
    for tenant_id in ("tenant-a", "tenant-b"):
        tenant_principals = [principal for principal in catalog.principals if principal.tenant_id == tenant_id]
        if not any("admin" in principal.roles and "document:approve" in principal.grants for principal in tenant_principals):
            raise FixtureValidationError(f"{tenant_id} requires a separate admin approval principal")
        if not any("uploader" in principal.roles and "document:upload" in principal.grants and "document:approve" not in principal.grants for principal in tenant_principals):
            raise FixtureValidationError(f"{tenant_id} requires a separate uploader without approval grant")
        if not any("reader" in principal.roles and "source:read" in principal.grants for principal in tenant_principals):
            raise FixtureValidationError(f"{tenant_id} requires a source reader")
    for principal in catalog.principals:
        if any(case_id not in cases for case_id in principal.allowed_case_ids):
            raise FixtureValidationError(f"{principal.principal_id} names an unknown case")
        for case_id in principal.allowed_case_ids:
            case = cases[case_id]
            if principal.tenant_id != case.tenant_id or principal.principal_id not in case.allowed_principal_ids:
                raise FixtureValidationError(f"principal/case tenant or membership mismatch: {principal.principal_id}/{case_id}")
    for case in catalog.cases:
        if any(principal_id not in principals for principal_id in case.allowed_principal_ids):
            raise FixtureValidationError(f"{case.case_id} names an unknown principal")
    for source in catalog.sources:
        if source.tenant_id not in {case.tenant_id for case in catalog.cases}:
            raise FixtureValidationError(f"source uses unknown tenant: {source.tenant_id}")
        if any(case_id not in cases or cases[case_id].tenant_id != source.tenant_id for case_id in source.case_ids):
            raise FixtureValidationError(f"source {source.source_id} has invalid case scope")
        if source.approval_state == "APPROVED":
            approver = principals.get(source.approved_by or "")
            if approver is None or approver.tenant_id != source.tenant_id or "admin" not in approver.roles or "document:approve" not in approver.grants:
                raise FixtureValidationError(f"source {source.source_id} approval is not backed by an in-tenant admin grant")
        if any(pid not in principals or principals[pid].tenant_id != source.tenant_id for pid in source.allowed_principal_ids):
            raise FixtureValidationError(f"source {source.source_id} has an invalid principal restriction")
        if any(parent not in sources or sources[parent].family_id != source.family_id for parent in source.supersedes):
            raise FixtureValidationError(f"source {source.source_id} supersedes unknown or different-family source")
    for observation in catalog.observations:
        observation_case = cases.get(observation.case_id)
        if observation_case is None or observation_case.tenant_id != observation.tenant_id:
            raise FixtureValidationError(f"observation has invalid case scope: {observation.observation_id}")
        allowed_fields = {"transaction_id", "state", "transaction_occurred_at", "settlement_state", "result"}
        if set(observation.data) - allowed_fields:
            raise FixtureValidationError(f"observation {observation.observation_id} has an unknown data field")
        trusted_envelope_fields = {"data_as_of"} if observation.data_as_of is not None else set()
        if set(observation.trusted_fields) - (set(observation.data) | trusted_envelope_fields):
            raise FixtureValidationError(f"observation {observation.observation_id} trusts a field it does not contain")
        if observation.status == "TIMEOUT" and observation.data:
            raise FixtureValidationError(f"timed out observation {observation.observation_id} cannot assert returned facts")
    if len(goldens) != 24 or {golden.query_id for golden in goldens} != {f"T{i:02d}" for i in range(1, 25)}:
        raise FixtureValidationError("golden inventory must contain T01 through T24 exactly once")
    for golden in goldens:
        golden_case = cases.get(golden.case_id)
        golden_principal = principals.get(golden.principal_scope.principal_id)
        if golden_case is None or golden_principal is None:
            raise FixtureValidationError(f"{golden.query_id} references an unknown case or principal")
        if (golden_case.tenant_id, golden_principal.tenant_id) != (golden.principal_scope.tenant_id, golden.principal_scope.tenant_id):
            raise FixtureValidationError(f"{golden.query_id} principal/case tenant mismatch")
        if golden.principal_scope.role not in golden_principal.roles:
            raise FixtureValidationError(f"{golden.query_id} principal role does not match the principal catalog")
        if golden.case_id not in golden_principal.allowed_case_ids:
            raise FixtureValidationError(f"{golden.query_id} principal lacks case membership")
        for ref in golden.source_clause_refs:
            _verify_reference(ref, sources)
            source = sources[ref.source_id]
            if source.tenant_id != golden.principal_scope.tenant_id or golden.case_id not in source.case_ids:
                raise FixtureValidationError(f"{golden.query_id} references a source outside its case/tenant")
            if ref.reference_use == "expected_denial_only":
                if golden.principal_scope.principal_id in source.allowed_principal_ids:
                    raise FixtureValidationError(f"{golden.query_id} denial source is allowed for the test principal")
            elif source.allowed_principal_ids and golden.principal_scope.principal_id not in source.allowed_principal_ids:
                raise FixtureValidationError(f"{golden.query_id} references a source unavailable to its principal")
            if source.approval_state != "APPROVED" and ref.reference_use != "expected_denial_only":
                raise FixtureValidationError(f"{golden.query_id} cannot use unapproved source {source.source_id} as authority")
        if golden.accepted_policy_version_id:
            for version_id in golden.accepted_policy_version_id.split(";"):
                if version_id not in policy_version_ids:
                    raise FixtureValidationError(f"{golden.query_id} names unknown policy version {version_id}")
        _validate_expected_result(golden, observations, policy)


def _validate_expected_result(
    golden: GoldenCase,
    observations: dict[str, ObservationFixture],
    policy: PolicyFixture,
) -> None:
    setup = golden.setup
    query_id = golden.query_id
    if query_id == "T01":
        instant = datetime.fromisoformat(setup["transaction_occurred_at"].replace("Z", "+00:00"))
        observation = observations.get(setup.get("transaction_observation_id", ""))
        if observation is None or "transaction_occurred_at" not in observation.trusted_fields or observation.data.get("transaction_occurred_at") != setup["transaction_occurred_at"]:
            raise FixtureValidationError("T01 transaction time must match a trusted live observation")
        if instant < datetime.fromisoformat("2026-07-01T00:00:00+00:00"):
            raise FixtureValidationError("T01 must exercise the current policy against the historical lexical match")
        if golden.accepted_policy_version_id != "demo-reversal-2026-b":
            raise FixtureValidationError("T01 must select the current event-time 2026 policy")
    elif query_id == "T02":
        observation = observations.get(setup.get("transaction_observation_id", ""))
        if observation is None or "transaction_occurred_at" not in observation.trusted_fields or observation.data.get("transaction_occurred_at") != setup.get("transaction_occurred_at"):
            raise FixtureValidationError("T02 historical event time must match a trusted live observation")
        if golden.time_basis != "MIXED_TRANSACTION_OCCURRED_AT_AND_EVALUATION_AT" or golden.expected_policy_decision != "DISTINCT_TIME_BASES_RESOLVED":
            raise FixtureValidationError("T02 must retain independent event and evaluation time bases")
    elif query_id == "T03":
        candidates = policy.conflict_fixture["candidates"]
        candidate_ids = tuple(candidate["policy_version_id"] for candidate in candidates)
        if tuple(setup.get("candidate_policy_version_ids", ())) != candidate_ids:
            raise FixtureValidationError("T03 references unknown or mismatched conflict policy version IDs")
        observation = observations.get(setup.get("transaction_observation_id", ""))
        try:
            event_time = datetime.fromisoformat(setup["transaction_occurred_at"].replace("Z", "+00:00"))
        except (KeyError, AttributeError, ValueError) as exc:
            raise FixtureValidationError("T03 requires a valid trusted transaction time") from exc
        if (
            setup.get("tenant_id") != golden.principal_scope.tenant_id
            or setup.get("product") != "QR_DEMO"
            or setup.get("transaction_class") != "DEMO_STANDARD"
            or setup.get("time_basis") != "TRANSACTION_OCCURRED_AT"
            or observation is None
            or observation.case_id != golden.case_id
            or observation.tenant_id != golden.principal_scope.tenant_id
            or observation.operation != "get_transaction_status"
            or observation.status != "OK"
            or "transaction_occurred_at" not in observation.trusted_fields
            or observation.data.get("transaction_occurred_at") != setup["transaction_occurred_at"]
            or any(
                candidate["applicability"]["tenant_id"] != setup["tenant_id"]
                or candidate["applicability"]["product"] != setup["product"]
                or candidate["applicability"]["transaction_class"] != setup["transaction_class"]
                or candidate["applicability"]["time_basis"] != setup["time_basis"]
                or event_time < datetime.fromisoformat(candidate["applicability"]["valid_from"].replace("Z", "+00:00"))
                or (candidate["applicability"]["valid_to"] is not None and event_time >= datetime.fromisoformat(candidate["applicability"]["valid_to"].replace("Z", "+00:00")))
                for candidate in candidates
            )
            or golden.expected_policy_decision != "POLICY_CONFLICT"
            or golden.expected_disposition != "CONFLICT"
            or golden.accepted_policy_version_id is not None
        ):
            raise FixtureValidationError("T03 overlap without precedence must remain POLICY_CONFLICT")
    elif query_id == "T04":
        if setup.get("trusted") is not False or setup.get("time_source") != "customer_text" or golden.expected_policy_decision != "UNVERIFIED_TIME_SOURCE":
            raise FixtureValidationError("T04 cannot resolve policy from user-asserted transaction time")
    elif query_id == "T07":
        if golden.expected_disposition != "VERIFICATION_UNAVAILABLE" or not any(ref.reference_use == "expected_denial_only" for ref in golden.source_clause_refs):
            raise FixtureValidationError("T07 must record a denied restricted-source path")
    elif query_id == "T09":
        observation = observations.get(setup.get("settlement_observation_id", ""))
        if observation is None or observation.status != "TIMEOUT" or "settlement_state" in observation.data or golden.expected_policy_decision != "INCOMPLETE_INPUT" or golden.expected_disposition != "PARTIALLY_SUPPORTED":
            raise FixtureValidationError("T09 missing settlement must produce incomplete input and partial disposition")
        if any("reversal" in action.lower() and action.lower().startswith(("recommend", "execute")) for action in golden.forbidden_actions) is False:
            raise FixtureValidationError("T09 must forbid recommending or executing reversal")
    elif query_id == "T12":
        if setup.get("external_inventory_attested") is not False or golden.expected_disposition != "NOT_ESTABLISHED":
            raise FixtureValidationError("T12 cannot claim completeness without external inventory attestation")
    elif query_id == "T13":
        data_as_of = datetime.fromisoformat(setup["data_as_of"].replace("Z", "+00:00"))
        observed = datetime.fromisoformat(setup["observed_at"].replace("Z", "+00:00"))
        if data_as_of >= observed or golden.expected_disposition != "PARTIALLY_SUPPORTED":
            raise FixtureValidationError("T13 must preserve stale data_as_of despite a later observation time")
    elif query_id == "T21":
        if setup.get("historical_audit_authorized") is not True or golden.expected_policy_decision != "HISTORICAL_ONLY":
            raise FixtureValidationError("T21 must distinguish authorized historical access from current use")
    elif query_id == "T22":
        if setup.get("bi_result") != "NOT_FOUND" or setup.get("transaction_service_status") != "TIMEOUT" or golden.expected_policy_decision != "INCOMPLETE_INPUT":
            raise FixtureValidationError("T22 scoped BI negative plus transaction outage is incomplete, not universal absence")


def load_fixtures(root: Path) -> FixtureBundle:
    """Load and validate the complete synthetic corpus from repo or app root."""
    app_root = _application_root(Path(root))
    demo_root = (app_root / "data" / "demo").resolve()
    try:
        catalog = _parse_json(demo_root / "sample_cases.json", FixtureCatalog)
        policy = _parse_json(app_root / "config" / "policies" / "demo_reversal_v2.json", PolicyFixture)
        raw_goldens = [line for line in (demo_root / "goldens.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        goldens = tuple(GoldenCase.model_validate_json(line) for line in raw_goldens)
    except FixtureValidationError:
        raise
    except (ValidationError, OSError, json.JSONDecodeError) as exc:
        raise FixtureValidationError(f"unable to read fixture catalog: {exc}") from exc

    golden_ids = [golden.query_id for golden in goldens]
    if len(golden_ids) != len(set(golden_ids)):
        raise FixtureValidationError("duplicate golden query ID")
    if len(golden_ids) != 24 or set(golden_ids) != {f"T{i:02d}" for i in range(1, 25)}:
        raise FixtureValidationError("golden inventory must contain T01 through T24 exactly once")

    principal_map = _unique(catalog.principals, "principal_id", "principal ID")
    case_map = _unique(catalog.cases, "case_id", "case ID")
    observation_map = _unique(catalog.observations, "observation_id", "observation ID")
    if len({source.source_id for source in catalog.sources}) != len(catalog.sources):
        raise FixtureValidationError("duplicate source ID")
    loaded_sources: list[SourceFixture] = []
    for source_data in catalog.sources:
        relative = Path(source_data.path)
        if relative.is_absolute() or ".." in relative.parts or relative.suffix.lower() not in {".md", ".txt"}:
            raise FixtureValidationError(f"source path is not a contained Markdown/TXT path: {source_data.path}")
        path = (app_root / relative).resolve()
        if not path.is_relative_to(demo_root) or not path.is_file():
            raise FixtureValidationError(f"source path escapes demo corpus or is missing: {source_data.path}")
        raw = path.read_bytes()
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FixtureValidationError(f"source is not UTF-8: {source_data.path}") from exc
        loaded_sources.append(SourceFixture.model_validate({
            **source_data.model_dump(),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "byte_length": len(raw),
            "clauses": _extract_clause_spans(raw, source_data.source_id),
        }))
    sources = _unique(tuple(loaded_sources), "source_id", "source ID")
    for source in loaded_sources:
        for parent_id in source.supersedes:
            if parent_id not in sources or sources[parent_id].family_id != source.family_id:
                raise FixtureValidationError(f"source {source.source_id} supersedes unknown or different-family source")
    for golden in goldens:
        for reference in golden.source_clause_refs:
            _verify_reference(reference, sources)
    policy_version_ids = _validate_policy(policy, sources, principal_map)
    _validate_case_inventory(catalog, principal_map, case_map, sources, observation_map, goldens, policy_version_ids, policy)
    if len({golden.query_id for golden in goldens}) != len(goldens):
        raise FixtureValidationError("duplicate golden query ID")
    snapshots = catalog.mock_snapshots
    if set(snapshots) != set(case_map):
        raise FixtureValidationError("mock snapshot case inventory must match cases exactly")
    if not snapshots["case-42"].changing:
        raise FixtureValidationError("case-42 must model changing operational observations")
    for case_id, history in snapshots.items():
        seen_snapshot_ids: set[str] = set()
        previous_time: datetime | None = None
        for version in history.versions:
            if version.snapshot_id in seen_snapshot_ids:
                raise FixtureValidationError(f"duplicate mock snapshot ID: {version.snapshot_id}")
            seen_snapshot_ids.add(version.snapshot_id)
            if previous_time is not None and version.recorded_at <= previous_time:
                raise FixtureValidationError(f"mock snapshots for {case_id} must be ordered by recorded_at")
            previous_time = version.recorded_at
            for observation_id in (version.transaction, version.settlement, version.bi):
                if observation_id is not None and (observation_id not in observation_map or observation_map[observation_id].case_id != case_id):
                    raise FixtureValidationError(f"mock snapshot {version.snapshot_id} references an unknown or cross-case observation")
    for case_id, history in snapshots.items():
        if history.changing != (len(history.versions) > 1):
            raise FixtureValidationError(f"mock snapshot changing flag does not match version history for {case_id}")
    return FixtureBundle(
        root=app_root,
        principals=catalog.principals,
        cases=catalog.cases,
        sources=tuple(loaded_sources),
        observations=catalog.observations,
        mock_snapshots=catalog.mock_snapshots,
        policy=policy,
        goldens=goldens,
        annotation_status=catalog.annotation_status,
    )


def validate_fixtures(root: Path) -> FixtureSummary:
    """Return a deterministic count summary after full reference validation."""
    return load_fixtures(root).summary()
