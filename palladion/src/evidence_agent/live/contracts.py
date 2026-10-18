"""Strict backend-owned operation contracts; no endpoint, credential or write arguments."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from evidence_agent.core.models import VersionedModel

Operation = Literal["get_transaction_status", "get_settlement_status", "get_incident_status",
                    "get_merchant_summary"]


class LookupRequest(VersionedModel):
    operation: Operation
    operation_version: Literal["1.0"] = "1.0"
    case_id: str = Field(min_length=1, max_length=100)
    target_id: str = Field(min_length=1, max_length=100)

    @field_validator("target_id")
    @classmethod
    def identifier(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Z][A-Z0-9-]{2,99}", value):
            raise ValueError("Invalid target identifier")
        return value


class CaseScope(VersionedModel):
    product: str = Field(min_length=1, max_length=100)
    transaction_class: str = Field(min_length=1, max_length=100)
    targets: dict[Operation, str]
    domain_events: dict[str, datetime] = Field(default_factory=dict)

    @field_validator("domain_events")
    @classmethod
    def aware_events(cls, value: dict[str, datetime]) -> dict[str, datetime]:
        if len(value) > 16 or any(t.tzinfo is None or t.utcoffset() is None for t in value.values()):
            raise ValueError("Bounded aware domain events required")
        return value


class OperationConfig(VersionedModel):
    owner: str = Field(min_length=1)
    source_system: str = Field(min_length=1)
    freshness_field: Literal["observed_at", "data_as_of"]
    max_age_seconds: int = Field(gt=0, le=86400)
    timeout_ms: int = Field(gt=0, le=10000)
    max_attempts: int = Field(ge=1, le=2)
    backoff_ms: int = Field(ge=0, le=100)
    max_response_bytes: int = Field(gt=0, le=16384)


class AdapterConfig(VersionedModel):
    operations: dict[Operation, OperationConfig]
    calls_per_minute: int = Field(gt=0, le=100)
    max_concurrent: int = Field(gt=0, le=4)
    max_pending: int = Field(gt=0, le=16)


class Snapshot(VersionedModel):
    """Upstream envelope; data shape is checked per named operation before persistence."""
    status: Literal["OK", "NOT_FOUND", "FORBIDDEN", "INVALID_ARGUMENT", "RATE_LIMITED",
                    "TIMEOUT", "UNAVAILABLE", "SCHEMA_MISMATCH"]
    data: dict[str, Any] = Field(default_factory=dict)
    source_event_at: datetime | None = None
    data_as_of: datetime | None = None

    @field_validator("source_event_at", "data_as_of")
    @classmethod
    def aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Timezone required")
        return value


class TransactionData(VersionedModel):
    transaction_id: str
    state: Literal["FAILED", "PENDING", "SUCCEEDED"]
    transaction_occurred_at: datetime

    @field_validator("transaction_occurred_at")
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timezone required")
        return value


class SettlementData(VersionedModel):
    settlement_id: str
    settlement_state: Literal["UNSETTLED", "PENDING", "SETTLED"]


class IncidentData(VersionedModel):
    incident_id: str
    state: Literal["OPEN", "INVESTIGATING", "RESOLVED"]


class MerchantData(VersionedModel):
    merchant_id: str
    result: Literal["FOUND", "NOT_FOUND"]


DATA_MODELS: dict[str, type[VersionedModel]] = {"get_transaction_status": TransactionData, "get_settlement_status": SettlementData,
               "get_incident_status": IncidentData, "get_merchant_summary": MerchantData}
TARGET_FIELDS = {"get_transaction_status": "transaction_id", "get_settlement_status": "settlement_id",
                 "get_incident_status": "incident_id", "get_merchant_summary": "merchant_id"}
