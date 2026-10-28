"""Bounded synthetic source/search HTTP inputs; identity is server supplied."""
from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from evidence_agent.graph.relations import RelationType
from evidence_agent.storage.applicability import MAX_EXTRA_INSTANTS


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Upload(RequestModel):
    case_id: str = Field(min_length=1, max_length=100)
    family_id: str = Field(min_length=1, max_length=200)
    filename: str = Field(min_length=1, max_length=200)
    mime_type: Literal["text/markdown", "text/plain", "application/json", "application/x-ndjson",
                       "text/csv", "text/tab-separated-values"]
    content: str = Field(min_length=1, max_length=65536)
    owner_id: str = Field(min_length=1, max_length=100)
    allowed_principal_ids: list[str] = Field(default_factory=list, max_length=100)
    valid_from: str | None = None
    valid_to: str | None = None
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class Search(RequestModel):
    case_id: str = Field(min_length=1, max_length=100)
    query: str = Field(min_length=1, max_length=2048)
    mode: Literal["lexical", "dense", "hybrid", "reranked"] = "hybrid"
    limit: int = Field(default=12, ge=1, le=40)
    require_graph: bool = False
    as_of: AwareDatetime | None = Field(default=None, strict=False)
    applicability_instants: list[Annotated[AwareDatetime, Field(strict=False)]] = Field(
        default_factory=list, max_length=MAX_EXTRA_INSTANTS)
    token_budget: int | None = Field(default=None, ge=1, le=65536)
    reuse_physical_audit: bool = False


class PdfUpload(Upload):
    mime_type: Literal["application/pdf"]  # type: ignore[assignment]
    content: str = Field(min_length=1, max_length=2796204)


class Approval(RequestModel):
    supersedes_revision_id: str | None = Field(default=None, max_length=100)


class GraphLink(RequestModel):
    from_chunk_id: str = Field(min_length=1, max_length=100)
    to_chunk_id: str = Field(min_length=1, max_length=100)
    relation_type: RelationType
    evidence_chunk_id: str = Field(min_length=1, max_length=100)
    revision_id: str = Field(min_length=1, max_length=100)
    start_byte: int = Field(ge=0)
    end_byte: int = Field(gt=0)
    quote: str = Field(min_length=1, max_length=4096)


class GraphLinks(RequestModel):
    links: list[GraphLink] = Field(min_length=1, max_length=16)


class PrincipalProvision(RequestModel):
    principal_id: str = Field(min_length=1, max_length=100)
    grants: list[Literal["document:upload", "document:approve", "source:read", "case:read"]] = Field(
        default_factory=list, max_length=4)


class CaseProvision(RequestModel):
    case_id: str = Field(min_length=1, max_length=100)


class MembershipProvision(RequestModel):
    principal_id: str = Field(min_length=1, max_length=100)


class Message(RequestModel):
    query: str = Field(min_length=1, max_length=2048)
    session_id: str | None = Field(default=None,pattern=r"^sess_[0-9a-f]{32}$")


class ReleasedClaim(RequestModel):
    claim_id: str
    text: str
    evidence_ids: list[str]


class MessageResponse(RequestModel):
    case_id: str
    session_id: str | None = None
    trace_id: str
    disposition: Literal["SUPPORTED", "PARTIALLY_SUPPORTED", "CONFLICT", "NOT_ESTABLISHED", "VERIFICATION_UNAVAILABLE"]
    answer: str
    verified_claims: list[ReleasedClaim]
    hypotheses: list[dict[str, str]]
    missing_requirements: list[str]
    requirement_origins: dict[str, str]
    citations: list[dict[str, Any]]
    tool_status: dict[str, str]
    searched_scope: str
    inventory_attested: Literal[False]
    review_status: Literal["UNAVAILABLE_UNTIL_P06", "PASS", "CHALLENGE", "UNAVAILABLE"]
    next_steps: list[str]
    budget: dict[str, int]
    verification_failures: list[str]
    # Present only when the server was started in evaluator mode (ADR-0100); omitted otherwise.
    experiment: dict[str, Any] | None = None
    evaluator: dict[str, Any] | None = None


class PolicyClauseIn(RequestModel):
    revision_id: str = Field(min_length=1, max_length=100)
    section_id: str = Field(min_length=1, max_length=200)
    start_byte: int = Field(ge=0)
    end_byte: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class PolicyFactIn(RequestModel):
    name: str = Field(min_length=1, max_length=100)
    type: Literal["enum", "bool", "int", "float", "string"]
    operation: Literal["get_transaction_status", "get_settlement_status",
                       "get_incident_status", "get_merchant_summary"]
    field: str = Field(min_length=1, max_length=100)
    allowed_values: list[str] = Field(default_factory=list, max_length=32)
    max_age_seconds: int = Field(gt=0, le=86400)


class PolicyRuleIn(RequestModel):
    id: str = Field(min_length=1, max_length=100)
    predicate: dict[str, Any]
    outcome: str = Field(min_length=1, max_length=100)
    clause_index: int = Field(ge=0)


class PolicyCreate(RequestModel):
    """One policy version; the server derives the time source, author and, when omitted, the case scope."""
    version_id: str = Field(min_length=1, max_length=100)
    family_id: str = Field(min_length=1, max_length=100)
    case_ids: list[str] = Field(min_length=1, max_length=100)
    time_basis: Literal["TRANSACTION_OCCURRED_AT", "CASE_OPENED_AT", "EVALUATION_AT", "DOMAIN_EVENT_AT"]
    domain_event: str | None = Field(default=None, max_length=100)
    timestamp_max_age_seconds: int = Field(default=300, gt=0, le=86400)
    valid_from: AwareDatetime = Field(strict=False)
    valid_to: AwareDatetime | None = Field(default=None, strict=False)
    clauses: list[PolicyClauseIn] = Field(min_length=1, max_length=16)
    required_facts: list[PolicyFactIn] = Field(default_factory=list, max_length=32)
    rules: list[PolicyRuleIn] = Field(default_factory=list, max_length=64)
    default_outcome: str = Field(min_length=1, max_length=100)
    author_id: str | None = Field(default=None, max_length=100)
    product: str | None = Field(default=None, max_length=100)
    transaction_class: str | None = Field(default=None, max_length=100)


class PolicySupersede(RequestModel):
    predecessor_version_id: str = Field(min_length=1, max_length=100)
    case_id: str = Field(min_length=1, max_length=100)
    valid_from: AwareDatetime = Field(strict=False)
    reason: str = Field(min_length=1, max_length=200)
