"""Typed contracts shared by the harness, the adapters and the scorers.

Contracts are standard-library frozen dataclasses with strict validation (protocol section 7.1).
They tighten the protocol's sketches in recorded ways (BADR-0016): ``native_citation_supported`` is
a required field backed by a source version, request filters are an allowlist, and nested mappings
are deep-copied into read-only forms. Nothing here reads gold, the network or the environment.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from datetime import UTC, datetime
from enum import Enum, StrEnum
from types import MappingProxyType
from typing import Any, Protocol, TypeVar, runtime_checkable

E = TypeVar("E", bound=Enum)


class ContractError(ValueError):
    """A value violates a contract. The message names the field, never a secret."""


class ArmUnavailable(RuntimeError):
    """The arm cannot run now (service down, access missing). Recorded as NOT_RUN."""


class CapabilityUnsupported(RuntimeError):
    """The arm lacks a capability the case needs. Recorded as FEATURE_NOT_SUPPORTED."""


class TransientInfrastructureError(RuntimeError):
    """A classified transient fault (network blip, throttle). The only error a retry rule may retry."""


# --------------------------------------------------------------------------- enumerations


class RunStatus(StrEnum):
    """Outcome of one (arm, case) execution. Every status other than OK is a result, never a zero."""

    OK = "OK"
    NOT_RUN = "NOT_RUN"
    UNSUPPORTED = "UNSUPPORTED"
    FEATURE_NOT_SUPPORTED = "FEATURE_NOT_SUPPORTED"
    INVALID_RUN = "INVALID_RUN"
    TIMEOUT = "TIMEOUT"


class ErrorOrigin(StrEnum):
    """Who is responsible for a failure, so harness faults are analysed apart from arm faults."""

    HARNESS = "HARNESS"
    PROVIDER = "PROVIDER"
    ARM = "ARM"


class EvidenceStatus(StrEnum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    CONFLICT = "CONFLICT"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"
    VERIFICATION_UNAVAILABLE = "VERIFICATION_UNAVAILABLE"


class AbstentionReason(StrEnum):
    """Protocol section 6.2: five negative mechanisms plus unresolved conflict."""

    NO_KNOWN_SUPPORT = "NO_KNOWN_SUPPORT"
    UNINDEXED_SOURCE = "UNINDEXED_SOURCE"
    UNAUTHORIZED_SOURCE = "UNAUTHORIZED_SOURCE"
    MISSING_CASE_INPUT = "MISSING_CASE_INPUT"
    REQUIRED_LIVE_CHECK_UNAVAILABLE = "REQUIRED_LIVE_CHECK_UNAVAILABLE"
    SOURCE_CONFLICT = "SOURCE_CONFLICT"


class Track(StrEnum):
    RETRIEVAL_ONLY = "retrieval_only"
    CONTROLLED_QA = "controlled_qa"
    NATIVE_END_TO_END = "native_end_to_end"


class CacheCondition(StrEnum):
    COLD = "cold"
    WARM = "warm"
    HOT = "hot"


class MetadataCondition(StrEnum):
    C1_TEXT_ONLY = "C1"
    C2_EVIDENCE_GOVERNED = "C2"


# --------------------------------------------------------------------------- validation helpers

# Arm-visible request fields are an allowlist; anything else (and anything that reads like gold) is refused.
ALLOWED_FILTER_KEYS = frozenset(
    {"tenant_id", "role", "document_state", "as_of_basis", "language", "source_types", "metadata_condition"}
)
_GOLD_KEY_FRAGMENTS = (
    "gold",
    "expected",
    "required_evidence",
    "required_claim",
    "forbidden_claim",
    "answerability",
    "citation_span",
    "minimal_evidence",
    "outcome_label",
    "harm_severity",
    "missing_reason",
)
# Substring-based for the multi-word markers; 'gold' must stand alone so gold_answer is caught but Goldman is not.
_GOLD_VALUE_MARKERS = re.compile(
    r"(?i)(?<![a-z])gold(?![a-z])|expected[ _-]?answer|required[ _-]?evidence|forbidden[ _-]?claim|answerability|"
    r"minimal[ _-]?evidence|outcome[ _-]?label"
)
# Identifiers handed to arms are pseudonymous: a fixed prefix plus hex, so no split name, scenario family or
# stratum can ride along (BI01, BI03). Free-text query content is screened by fixture validation (B02), not here.
QUESTION_ID = re.compile(r"q-[0-9a-f]{8,32}")
EPISODE_ID = re.compile(r"ep-[0-9a-f]{8,32}")
_IDENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@#/-]{0,127}")
MAX_TEXT = 16_384


def _normalise_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.lower())


def _name(owner: str, field_name: str) -> str:
    return f"{owner}.{field_name}"


def require_text(name: str, value: object, *, max_len: int = MAX_TEXT, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ContractError(f"{name} must be a string")
    if not allow_empty and not value.strip():
        raise ContractError(f"{name} must not be empty")
    if len(value) > max_len:
        raise ContractError(f"{name} exceeds {max_len} characters")
    return value


def require_ident(name: str, value: object) -> str:
    text = require_text(name, value, max_len=128)
    if not _IDENT.fullmatch(text):
        raise ContractError(f"{name} is not a valid identifier")
    return text


def require_question_id(name: str, value: object) -> str:
    text = require_text(name, value, max_len=64)
    if not QUESTION_ID.fullmatch(text):
        raise ContractError(f"{name} must be a pseudonymous id such as 'q-3f9a1c2b'")
    return text


def require_episode_id(name: str, value: object) -> str:
    text = require_text(name, value, max_len=64)
    if not EPISODE_ID.fullmatch(text):
        raise ContractError(f"{name} must be a pseudonymous id such as 'ep-0a1b2c3d'")
    return text


def require_int(name: str, value: object, *, minimum: int = 0, maximum: int | None = None) -> int:
    if type(value) is not int:  # bool and float are refused on purpose
        raise ContractError(f"{name} must be an integer")
    if value < minimum or (maximum is not None and value > maximum):
        raise ContractError(f"{name} out of range")
    return value


def optional_int(name: str, value: object, *, minimum: int = 0) -> int | None:
    return None if value is None else require_int(name, value, minimum=minimum)


def optional_float(name: str, value: object, *, minimum: float = 0.0) -> float | None:
    """A finite float or int (never a bool); ``None`` stays ``None`` and is never coerced to zero."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ContractError(f"{name} must be a number or null")
    number = float(value)
    if not math.isfinite(number) or number < minimum:
        raise ContractError(f"{name} must be finite and at least {minimum}")
    return number


def require_bool(name: str, value: object) -> bool:
    if type(value) is not bool:
        raise ContractError(f"{name} must be a boolean")
    return value


def normalise_timestamp(name: str, value: object) -> str:
    """Accept an ISO-8601 string with an explicit offset; return it in UTC with a trailing Z."""
    text = require_text(name, value, max_len=64)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ContractError(f"{name} is not an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContractError(f"{name} must carry an explicit timezone")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def optional_timestamp(name: str, value: object) -> str | None:
    return None if value is None else normalise_timestamp(name, value)


def enum_member(enum_type: type[E], name: str, value: object) -> E:
    if isinstance(value, enum_type):
        return value
    if isinstance(value, str):
        try:
            return enum_type(value)
        except ValueError:
            pass
    raise ContractError(f"{name} is not a known {enum_type.__name__}")


def freeze(name: str, value: object, *, _depth: int = 0) -> Any:
    """Deep-copy a JSON-like value into read-only forms (mappings, tuples) or refuse it."""
    if _depth > 8:
        raise ContractError(f"{name} is nested too deeply")
    if value is None or isinstance(value, str | bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ContractError(f"{name} contains a non-finite number")
        return value
    if isinstance(value, Mapping):
        items: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ContractError(f"{name} keys must be strings")
            items[key] = freeze(f"{name}.{key}", item, _depth=_depth + 1)
        return MappingProxyType(items)
    if isinstance(value, list | tuple):
        return tuple(freeze(f"{name}[]", item, _depth=_depth + 1) for item in value)
    raise ContractError(f"{name} holds an unsupported type")


def thaw(value: Any) -> Any:
    """Inverse of :func:`freeze`, producing plain JSON-ready containers."""
    if isinstance(value, Mapping):
        return {key: thaw(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [thaw(item) for item in value]
    return value


def reject_unknown(owner: str, data: Mapping[str, object], allowed: Sequence[str]) -> None:
    unknown = sorted(set(data) - set(allowed))
    if unknown:
        raise ContractError(f"{owner} has unknown field(s): {', '.join(unknown)}")


def field_names(cls: type) -> list[str]:
    return [f.name for f in fields(cls)]


def screen_arm_visible(name: str, value: Any) -> None:
    """Refuse gold-like keys and gold-like marker words anywhere inside an arm-visible structure."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalised = _normalise_key(str(key))
            if any(fragment in normalised for fragment in _GOLD_KEY_FRAGMENTS):
                raise ContractError(f"{name} contains a gold-like key")
            screen_arm_visible(f"{name}.{key}", item)
    elif isinstance(value, tuple | list):
        for item in value:
            screen_arm_visible(name, item)
    elif isinstance(value, str) and _GOLD_VALUE_MARKERS.search(value):
        raise ContractError(f"{name} contains a gold-like marker")


def _build_filters(owner: str, value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError(f"{owner}.filters must be a mapping")
    unknown = sorted(set(value) - ALLOWED_FILTER_KEYS)
    if unknown:
        raise ContractError(f"{owner}.filters has key(s) outside the arm-visible allowlist: {', '.join(unknown)}")
    frozen = freeze(f"{owner}.filters", value)
    screen_arm_visible(f"{owner}.filters", frozen)
    return frozen  # type: ignore[no-any-return]


# --------------------------------------------------------------------------- retrieval contracts


@dataclass(frozen=True)
class RetrievalRequest:
    """What an arm is allowed to see for one retrieval call. No gold, no split, no outcome label."""

    question_id: str
    query: str
    principal_id: str
    corpus_snapshot_id: str
    evaluation_time: str
    event_time: str | None
    filters: Mapping[str, Any]
    limit: int
    max_evidence_tokens: int

    def __post_init__(self) -> None:
        o = "RetrievalRequest"
        set_ = object.__setattr__
        set_(self, "question_id", require_question_id(_name(o, "question_id"), self.question_id))
        set_(self, "query", require_text(_name(o, "query"), self.query))
        set_(self, "principal_id", require_ident(_name(o, "principal_id"), self.principal_id))
        set_(self, "corpus_snapshot_id", require_ident(_name(o, "corpus_snapshot_id"), self.corpus_snapshot_id))
        set_(self, "evaluation_time", normalise_timestamp(_name(o, "evaluation_time"), self.evaluation_time))
        set_(self, "event_time", optional_timestamp(_name(o, "event_time"), self.event_time))
        set_(self, "filters", _build_filters(o, self.filters))
        set_(self, "limit", require_int(_name(o, "limit"), self.limit, minimum=1, maximum=100))
        set_(
            self,
            "max_evidence_tokens",
            require_int(_name(o, "max_evidence_tokens"), self.max_evidence_tokens, minimum=1),
        )

    def to_dict(self) -> dict[str, Any]:
        return {name: thaw(getattr(self, name)) for name in field_names(type(self))}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RetrievalRequest:
        reject_unknown(cls.__name__, data, field_names(cls))
        return cls(**{name: data[name] for name in field_names(cls) if name in data})


_CANDIDATE_OPTIONAL = ("evidence_path", "additional_metadata", "source_document_id", "source_sha256")


@dataclass(frozen=True)
class EvidenceCandidate:
    """One ranked piece of evidence. Citation support must be declared, not assumed."""

    source_version_id: str | None
    locator: str | None
    content: str
    rank: int
    native_score: float | None
    retrieval_channel: str
    evidence_path: tuple[str, ...]
    native_citation_supported: bool
    additional_metadata: Mapping[str, Any]
    source_document_id: str | None = None
    source_sha256: str | None = None

    def __post_init__(self) -> None:
        o = "EvidenceCandidate"
        set_ = object.__setattr__
        if self.source_version_id is not None:
            set_(self, "source_version_id", require_ident(_name(o, "source_version_id"), self.source_version_id))
        if self.locator is not None:
            set_(self, "locator", require_text(_name(o, "locator"), self.locator, max_len=512))
        set_(self, "content", require_text(_name(o, "content"), self.content, max_len=1_000_000, allow_empty=True))
        set_(self, "rank", require_int(_name(o, "rank"), self.rank, minimum=1))
        set_(self, "native_score", optional_float(_name(o, "native_score"), self.native_score, minimum=-1e18))
        set_(self, "retrieval_channel", require_ident(_name(o, "retrieval_channel"), self.retrieval_channel))
        path = freeze(_name(o, "evidence_path"), list(self.evidence_path))
        if not all(isinstance(item, str) for item in path):
            raise ContractError(f"{o}.evidence_path must hold strings")
        set_(self, "evidence_path", path)
        set_(
            self,
            "native_citation_supported",
            require_bool(_name(o, "native_citation_supported"), self.native_citation_supported),
        )
        set_(self, "additional_metadata", freeze(_name(o, "additional_metadata"), self.additional_metadata))
        if self.source_document_id is not None:
            set_(self, "source_document_id", require_ident(_name(o, "source_document_id"), self.source_document_id))
        if self.source_sha256 is not None:
            set_(self, "source_sha256", require_text(_name(o, "source_sha256"), self.source_sha256, max_len=64))
            if not re.fullmatch(r"[0-9a-f]{64}", self.source_sha256):
                raise ContractError(f"{o}.source_sha256 must be a lower-case SHA-256")
        if self.native_citation_supported and self.source_version_id is None and self.source_document_id is None:
            raise ContractError(f"{o}: a native citation claim needs a source id (no phantom citations)")

    def to_dict(self) -> dict[str, Any]:
        return {name: thaw(getattr(self, name)) for name in field_names(type(self))}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> EvidenceCandidate:
        reject_unknown(cls.__name__, data, field_names(cls))
        missing = [n for n in field_names(cls) if n not in data and n not in _CANDIDATE_OPTIONAL]
        if missing:
            raise ContractError(f"{cls.__name__} is missing field(s): {', '.join(missing)}")
        values = {name: data[name] for name in field_names(cls) if name in data}
        values.setdefault("evidence_path", ())
        values.setdefault("additional_metadata", {})
        return cls(**values)


@runtime_checkable
class RetrieverAdapter(Protocol):
    """Deliberately small adapter surface from protocol section 7.1."""

    def build_index(self, source_manifest_uri: str, index_namespace: str) -> None: ...

    def retrieve(self, request: RetrievalRequest) -> list[EvidenceCandidate]: ...

    def index_stats(self) -> dict[str, Any]: ...


# --------------------------------------------------------------------------- case contracts


@dataclass(frozen=True)
class CaseRequest:
    """Arm-visible input for a system arm. Same barrier as :class:`RetrievalRequest`."""

    question_id: str
    query: str
    principal_id: str
    corpus_snapshot_id: str
    evaluation_time: str
    event_time: str | None
    filters: Mapping[str, Any]
    max_evidence_tokens: int
    episode_id: str | None
    turn_index: int

    def __post_init__(self) -> None:
        o = "CaseRequest"
        set_ = object.__setattr__
        set_(self, "question_id", require_question_id(_name(o, "question_id"), self.question_id))
        set_(self, "query", require_text(_name(o, "query"), self.query))
        set_(self, "principal_id", require_ident(_name(o, "principal_id"), self.principal_id))
        set_(self, "corpus_snapshot_id", require_ident(_name(o, "corpus_snapshot_id"), self.corpus_snapshot_id))
        set_(self, "evaluation_time", normalise_timestamp(_name(o, "evaluation_time"), self.evaluation_time))
        set_(self, "event_time", optional_timestamp(_name(o, "event_time"), self.event_time))
        set_(self, "filters", _build_filters(o, self.filters))
        set_(
            self,
            "max_evidence_tokens",
            require_int(_name(o, "max_evidence_tokens"), self.max_evidence_tokens, minimum=1),
        )
        if self.episode_id is not None:
            set_(self, "episode_id", require_episode_id(_name(o, "episode_id"), self.episode_id))
        set_(self, "turn_index", require_int(_name(o, "turn_index"), self.turn_index, minimum=0))

    def to_dict(self) -> dict[str, Any]:
        return {name: thaw(getattr(self, name)) for name in field_names(type(self))}


@dataclass(frozen=True)
class Claim:
    id: str
    text: str
    citations: tuple[str, ...]

    def __post_init__(self) -> None:
        set_ = object.__setattr__
        set_(self, "id", require_ident("Claim.id", self.id))
        set_(self, "text", require_text("Claim.text", self.text))
        citations = freeze("Claim.citations", list(self.citations))
        if not all(isinstance(item, str) and item for item in citations):
            raise ContractError("Claim.citations must hold non-empty strings")
        set_(self, "citations", citations)


@dataclass(frozen=True)
class ToolCall:
    name: str
    status: str

    def __post_init__(self) -> None:
        set_ = object.__setattr__
        set_(self, "name", require_ident("ToolCall.name", self.name))
        set_(self, "status", require_ident("ToolCall.status", self.status))


@dataclass(frozen=True)
class CriticReport:
    enabled: bool
    calls: int | None
    objections: tuple[str, ...]

    def __post_init__(self) -> None:
        set_ = object.__setattr__
        set_(self, "enabled", require_bool("CriticReport.enabled", self.enabled))
        set_(self, "calls", optional_int("CriticReport.calls", self.calls))
        objections = freeze("CriticReport.objections", list(self.objections))
        if not all(isinstance(item, str) for item in objections):
            raise ContractError("CriticReport.objections must hold strings")
        set_(self, "objections", objections)
        if not self.enabled and self.calls:
            raise ContractError("CriticReport: a disabled critic cannot report calls")


@dataclass(frozen=True)
class ModelInvocations:
    """Self-reported model call counts; ``None`` means not observed, never zero."""

    main: int | None
    critic: int | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "main", optional_int("ModelInvocations.main", self.main))
        object.__setattr__(self, "critic", optional_int("ModelInvocations.critic", self.critic))


@dataclass(frozen=True)
class CaseResponse:
    """Protocol section 18.1. ``None`` latency or cost means not observed and is kept as ``None``."""

    question_id: str
    run_id: str
    answer_text: str
    evidence_status: EvidenceStatus
    claims: tuple[Claim, ...]
    used_evidence_ids: tuple[str, ...]
    tool_calls: tuple[ToolCall, ...]
    critic: CriticReport | None
    model_invocations: ModelInvocations | None
    latency_ms: float | None
    cost_usd: float | None
    abstention_reason: AbstentionReason | None

    def __post_init__(self) -> None:
        o = "CaseResponse"
        set_ = object.__setattr__
        set_(self, "question_id", require_question_id(_name(o, "question_id"), self.question_id))
        set_(self, "run_id", require_ident(_name(o, "run_id"), self.run_id))
        set_(self, "answer_text", require_text(_name(o, "answer_text"), self.answer_text, allow_empty=True))
        set_(self, "evidence_status", enum_member(EvidenceStatus, _name(o, "evidence_status"), self.evidence_status))
        set_(self, "claims", tuple(self.claims))
        if not all(isinstance(c, Claim) for c in self.claims):
            raise ContractError(f"{o}.claims must hold Claim objects")
        used = freeze(_name(o, "used_evidence_ids"), list(self.used_evidence_ids))
        if not all(isinstance(item, str) and item for item in used):
            raise ContractError(f"{o}.used_evidence_ids must hold non-empty strings")
        set_(self, "used_evidence_ids", used)
        set_(self, "tool_calls", tuple(self.tool_calls))
        if not all(isinstance(t, ToolCall) for t in self.tool_calls):
            raise ContractError(f"{o}.tool_calls must hold ToolCall objects")
        set_(self, "latency_ms", optional_float(_name(o, "latency_ms"), self.latency_ms))
        set_(self, "cost_usd", optional_float(_name(o, "cost_usd"), self.cost_usd))
        if self.abstention_reason is not None:
            set_(
                self,
                "abstention_reason",
                enum_member(AbstentionReason, _name(o, "abstention_reason"), self.abstention_reason),
            )
            if self.evidence_status is EvidenceStatus.SUPPORTED:
                raise ContractError(f"{o}: a SUPPORTED answer cannot carry an abstention reason")
        if self.critic is not None and not isinstance(self.critic, CriticReport):
            raise ContractError(f"{o}.critic must be a CriticReport")
        if self.model_invocations is not None and not isinstance(self.model_invocations, ModelInvocations):
            raise ContractError(f"{o}.model_invocations must be ModelInvocations")

    def to_dict(self) -> dict[str, Any]:
        def convert(value: Any) -> Any:
            if isinstance(value, Enum):
                return value.value
            if hasattr(value, "__dataclass_fields__"):
                return {name: convert(getattr(value, name)) for name in field_names(type(value))}
            if isinstance(value, tuple | list):
                return [convert(item) for item in value]
            return value

        return {name: convert(getattr(self, name)) for name in field_names(type(self))}


@dataclass(frozen=True)
class UsageReport:
    """What a system says it consumed. Every value is self-reported until independently observed."""

    main_calls: int | None
    critic_calls: int | None
    tool_calls: int | None
    prompt_tokens: int | None
    completion_tokens: int | None
    cost_usd: float | None

    def __post_init__(self) -> None:
        for name in ("main_calls", "critic_calls", "tool_calls", "prompt_tokens", "completion_tokens"):
            object.__setattr__(self, name, optional_int(f"UsageReport.{name}", getattr(self, name)))
        object.__setattr__(self, "cost_usd", optional_float("UsageReport.cost_usd", self.cost_usd))


@runtime_checkable
class SystemAdapter(Protocol):
    """Optional extension for Track C systems (protocol section 7.1)."""

    def answer(self, case: CaseRequest) -> CaseResponse: ...

    def reset_case(self, case_id: str) -> None: ...

    def report_usage(self) -> UsageReport: ...

    def report_trace(self) -> list[dict[str, Any]]: ...


# --------------------------------------------------------------------------- failure mapping


def classify_exception(exc: BaseException) -> tuple[RunStatus, ErrorOrigin, str]:
    """Map an exception raised by an arm to a run state, an origin and a fixed code.

    The code is a fixed label (never exception text) so provider or arm prose cannot leak into records.
    """
    if isinstance(exc, ArmUnavailable):
        return RunStatus.NOT_RUN, ErrorOrigin.ARM, "ARM_UNAVAILABLE"
    if isinstance(exc, CapabilityUnsupported):
        return RunStatus.FEATURE_NOT_SUPPORTED, ErrorOrigin.ARM, "CAPABILITY_UNSUPPORTED"
    if isinstance(exc, TimeoutError):
        return RunStatus.TIMEOUT, ErrorOrigin.ARM, "DEADLINE_EXCEEDED"
    if isinstance(exc, TransientInfrastructureError):
        return RunStatus.INVALID_RUN, ErrorOrigin.PROVIDER, "TRANSIENT_FAULT_RETRIES_EXHAUSTED"
    if isinstance(exc, ContractError):
        return RunStatus.INVALID_RUN, ErrorOrigin.ARM, "CONTRACT_VIOLATION"
    return RunStatus.INVALID_RUN, ErrorOrigin.ARM, "UNHANDLED_" + type(exc).__name__[:40]
