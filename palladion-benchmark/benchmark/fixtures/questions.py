"""Gold evidence graph, stratified question generation and family-grouped partitions (B02-T04.01 and B02-T04.02).

A question's gold is derived from the hidden world's rules (policy resolution, live mock, ACL), never from a language
model, and every cited span is resolved from the rendered clause offsets. Gold is evaluator-only: nothing in this module
is arm-visible except :func:`arm_request`, which is built from the principal, the case times and the question text.
Whole scenario families go to one split, decided before any question is written (protocol 5.2).
"""

from __future__ import annotations

import itertools
import json
import random
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, fields
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

from benchmark.contracts import (
    AbstentionReason,
    CaseRequest,
    ContractError,
    EvidenceStatus,
    Track,
    screen_arm_visible,
)
from benchmark.fixtures import digest_of, sha256_hex, to_plain
from benchmark.fixtures.knowledge import SNAPSHOT_TIME, AsOfBasis
from benchmark.fixtures.manifest import Split
from benchmark.fixtures.world import World

SNAPSHOT = SNAPSHOT_TIME
LIVE_PREFIX = "live:"


class Stratum(StrEnum):
    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"
    Q5 = "Q5"
    Q6 = "Q6"
    Q7 = "Q7"
    Q8 = "Q8"
    Q9 = "Q9"
    Q10 = "Q10"


class Answerability(StrEnum):
    ANSWERABLE = "ANSWERABLE"
    PARTIAL = "PARTIAL"
    UNANSWERABLE = "UNANSWERABLE"
    CONFLICT = "CONFLICT"
    BLOCKED_BY_ACL = "BLOCKED_BY_ACL"
    VERIFICATION_UNAVAILABLE = "VERIFICATION_UNAVAILABLE"


class SlotState(StrEnum):
    SATISFIABLE = "satisfiable"
    NO_SOURCE_BY_DESIGN = "no_source_by_design"
    BLOCKED_BY_ACL = "blocked_by_acl"
    LIVE_UNAVAILABLE = "live_unavailable"
    UNINDEXED = "unindexed"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


R = AbstentionReason
# Which negative mechanisms an answerability value may carry, and which evidence statuses it accepts.
ANSWERABILITY_RULES: Final[dict[Answerability, tuple[frozenset[AbstentionReason], frozenset[EvidenceStatus]]]] = {
    Answerability.ANSWERABLE: (frozenset(), frozenset({EvidenceStatus.SUPPORTED})),
    Answerability.PARTIAL: (
        frozenset({R.MISSING_CASE_INPUT, R.REQUIRED_LIVE_CHECK_UNAVAILABLE, R.NO_KNOWN_SUPPORT}),
        frozenset({EvidenceStatus.PARTIALLY_SUPPORTED, EvidenceStatus.NOT_ESTABLISHED}),
    ),
    Answerability.UNANSWERABLE: (
        frozenset({R.NO_KNOWN_SUPPORT, R.UNINDEXED_SOURCE, R.MISSING_CASE_INPUT}),
        frozenset({EvidenceStatus.NOT_ESTABLISHED}),
    ),
    Answerability.CONFLICT: (frozenset({R.SOURCE_CONFLICT}), frozenset({EvidenceStatus.CONFLICT})),
    Answerability.BLOCKED_BY_ACL: (frozenset({R.UNAUTHORIZED_SOURCE}), frozenset({EvidenceStatus.NOT_ESTABLISHED})),
    Answerability.VERIFICATION_UNAVAILABLE: (
        frozenset({R.REQUIRED_LIVE_CHECK_UNAVAILABLE}),
        frozenset({EvidenceStatus.VERIFICATION_UNAVAILABLE, EvidenceStatus.PARTIALLY_SUPPORTED}),
    ),
}
_SLOT_MECHANISM: Final[dict[SlotState, frozenset[AbstentionReason]]] = {
    SlotState.NO_SOURCE_BY_DESIGN: frozenset({R.NO_KNOWN_SUPPORT, R.MISSING_CASE_INPUT}),
    SlotState.BLOCKED_BY_ACL: frozenset({R.UNAUTHORIZED_SOURCE}),
    SlotState.LIVE_UNAVAILABLE: frozenset({R.REQUIRED_LIVE_CHECK_UNAVAILABLE}),
    SlotState.UNINDEXED: frozenset({R.UNINDEXED_SOURCE}),
}
ALL_TRACKS: Final = (Track.RETRIEVAL_ONLY.value, Track.CONTROLLED_QA.value, Track.NATIVE_END_TO_END.value)


_OPTIONAL_GOLD_FIELDS = frozenset({"source_case_id", "tags", "history_allowed"})


class GoldError(ValueError):
    """A gold record violates the evidence schema. The message names the rule, never a secret."""


@dataclass(frozen=True)
class Citation:
    """A clause span in one published document, resolved from rendered offsets. ``live:`` ids name live reads."""

    doc_id: str
    clause_id: str
    start: int
    end: int
    span_sha256: str

    @property
    def key(self) -> tuple[str, str]:
        return (self.doc_id, self.clause_id)


@dataclass(frozen=True)
class EvidenceSlot:
    slot: str
    state: SlotState
    mechanism: AbstentionReason | None
    alternatives: tuple[Citation, ...]

    def __post_init__(self) -> None:
        if self.state is SlotState.SATISFIABLE:
            if not self.alternatives or self.mechanism is not None:
                raise GoldError(f"slot {self.slot}: a satisfiable slot needs alternatives and no mechanism")
        elif self.alternatives or self.mechanism not in _SLOT_MECHANISM[self.state]:
            raise GoldError(f"slot {self.slot}: an unavailable slot needs a matching mechanism and no alternatives")


@dataclass(frozen=True)
class GoldRecord:
    question_id: str
    split: Split
    stratum: Stratum
    difficulty: int
    language: str
    scenario_family: str
    corpus_snapshot_id: str
    principal_id: str
    tenant_id: str
    authorized_partitions: tuple[str, ...]
    evaluation_time: str
    event_time: str | None
    case_open_time: str | None
    query: str
    answerability: Answerability
    missing_reasons: tuple[AbstentionReason, ...]
    required_claims: tuple[str, ...]
    forbidden_claims: tuple[str, ...]
    slots: tuple[EvidenceSlot, ...]
    minimal_sets: tuple[tuple[Citation, ...], ...]
    gold_as_of_basis: AsOfBasis | None
    gold_applicable_version_ids: tuple[str, ...]
    policy_outcome: str | None
    required_policy_inputs: tuple[str, ...]
    expected_live_snapshot: Mapping[str, Any] | None
    allowed_statuses: tuple[EvidenceStatus, ...]
    preferred_action: str
    abstention_note: str | None
    citation_gold_spans: tuple[Citation, ...]
    harm_severity: Severity
    allowed_actions: tuple[str, ...]
    inaccessible_sources: tuple[str, ...]
    track_eligibility: tuple[str, ...]
    twin_of: str | None
    source_case_id: str | None = None
    tags: tuple[str, ...] = field(default=())
    history_allowed: bool = False  # True only when the question itself asks for superseded versions

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> GoldRecord:
        """Rebuild a record from its serialised form. Unknown or missing fields are refused."""
        names = [f.name for f in fields(cls)]
        unknown = sorted(set(data) - set(names))
        missing = sorted(n for n in names if n not in data and n not in _OPTIONAL_GOLD_FIELDS)
        if unknown or missing:
            raise GoldError(f"gold record has unknown {unknown} or missing {missing} field(s)")

        def citations(items: Sequence[Mapping[str, Any]]) -> tuple[Citation, ...]:
            return tuple(Citation(**c) for c in items)

        values: dict[str, Any] = dict(data)
        values["split"] = Split(data["split"])
        values["stratum"] = Stratum(data["stratum"])
        values["answerability"] = Answerability(data["answerability"])
        values["missing_reasons"] = tuple(AbstentionReason(x) for x in data["missing_reasons"])
        values["slots"] = tuple(
            EvidenceSlot(
                s["slot"],
                SlotState(s["state"]),
                AbstentionReason(s["mechanism"]) if s["mechanism"] else None,
                citations(s["alternatives"]),
            )
            for s in data["slots"]
        )
        values["minimal_sets"] = tuple(citations(group) for group in data["minimal_sets"])
        values["gold_as_of_basis"] = AsOfBasis(data["gold_as_of_basis"]) if data["gold_as_of_basis"] else None
        values["allowed_statuses"] = tuple(EvidenceStatus(x) for x in data["allowed_statuses"])
        values["citation_gold_spans"] = citations(data["citation_gold_spans"])
        values["harm_severity"] = Severity(data["harm_severity"])
        for name in (
            "authorized_partitions", "required_claims", "forbidden_claims", "gold_applicable_version_ids",
            "required_policy_inputs", "allowed_actions", "inaccessible_sources", "track_eligibility", "tags",
        ):  # fmt: skip
            if name in values:
                values[name] = tuple(values[name])
        return cls(**values)

    def __post_init__(self) -> None:
        validate_gold(self)

    def to_dict(self) -> dict[str, Any]:
        return {k: to_plain(v) for k, v in self.__dict__.items()}

    @property
    def digest(self) -> str:
        """SHA-256 of the canonical record, so a label or a score can be tied to the exact gold it was made against."""
        return digest_of(self.to_dict())


def read_gold(path: Path, *, expected_sha256: str | None = None) -> tuple[GoldRecord, ...]:
    """Read an annotation file written by ``write_annotations``; the file digest is checked when one is given."""
    raw = path.read_bytes()
    if expected_sha256 is not None and sha256_hex(raw.decode("utf-8")) != expected_sha256:
        raise GoldError(f"{path.name} does not match its recorded digest")
    return tuple(GoldRecord.from_dict(json.loads(line)) for line in raw.decode("utf-8").splitlines() if line.strip())


def derive_minimal_sets(slots: Sequence[EvidenceSlot]) -> tuple[tuple[Citation, ...], ...]:
    """Every way to satisfy all satisfiable slots with one alternative each (AND across slots, OR within one)."""
    satisfiable = [s.alternatives for s in slots if s.state is SlotState.SATISFIABLE]
    if not satisfiable:
        return ()
    return tuple(tuple(combo) for combo in itertools.product(*satisfiable))


def _fail(r: GoldRecord, rule: str) -> GoldError:
    return GoldError(f"{r.question_id}: {rule}")


def _check_labels(r: GoldRecord) -> None:
    """Answerability, negative mechanisms and accepted statuses must fit together (protocol 6.1 and 6.2)."""
    reasons_allowed, statuses_allowed = ANSWERABILITY_RULES[r.answerability]
    if not set(r.missing_reasons) <= reasons_allowed or bool(r.missing_reasons) != bool(reasons_allowed):
        raise _fail(r, f"negative mechanism does not fit answerability {r.answerability.value}")
    if not r.allowed_statuses or not set(r.allowed_statuses) <= statuses_allowed:
        raise _fail(r, f"accepted statuses do not fit answerability {r.answerability.value}")
    slot_mechanisms = {s.mechanism for s in r.slots if s.mechanism is not None}
    if slot_mechanisms != set(r.missing_reasons) - {R.SOURCE_CONFLICT}:
        raise _fail(r, "slot mechanisms differ from the negative mechanisms")


def _check_slot_mix(r: GoldRecord) -> None:
    """Which mixture of satisfiable and unavailable slots each answerability requires."""
    gaps = [s for s in r.slots if s.state is not SlotState.SATISFIABLE]
    found = [s for s in r.slots if s.state is SlotState.SATISFIABLE]
    rules: dict[Answerability, tuple[bool, str]] = {
        Answerability.ANSWERABLE: (bool(found) and not gaps, "an answerable question needs every slot satisfiable"),
        Answerability.PARTIAL: (bool(found) and bool(gaps), "a partial question needs satisfiable and missing slots"),
        Answerability.UNANSWERABLE: (bool(gaps), "an unanswerable question needs an unavailable slot"),
        Answerability.BLOCKED_BY_ACL: (bool(gaps), "a blocked question needs an unavailable slot"),
        Answerability.VERIFICATION_UNAVAILABLE: (bool(gaps), "an unverifiable question needs an unavailable slot"),
        Answerability.CONFLICT: (len(found) >= 2, "a conflict needs two satisfiable sides"),
    }
    holds, message = rules[r.answerability]
    if not holds:
        raise _fail(r, message)
    if r.answerability is Answerability.BLOCKED_BY_ACL and not r.inaccessible_sources:
        raise _fail(r, "a blocked question must name the inaccessible sources")


def _check_evidence_sets(r: GoldRecord) -> None:
    cited = {c.key for s in r.slots for c in s.alternatives}
    if set(r.inaccessible_sources) & {doc for doc, _ in cited}:
        raise _fail(r, "forbidden gold: an inaccessible source is cited as accessible evidence")
    derived = {frozenset(c.key for c in combo) for combo in derive_minimal_sets(r.slots)}
    if derived != {frozenset(c.key for c in combo) for combo in r.minimal_sets}:
        raise _fail(r, "minimal evidence sets do not match the slots")
    if {c.key for c in r.citation_gold_spans} != cited:
        raise _fail(r, "citation spans must be exactly the cited alternatives")


def _check_metadata(r: GoldRecord) -> None:
    if not 1 <= r.difficulty <= 3:
        raise _fail(r, "difficulty must be 1 to 3")
    if r.answerability is Answerability.ANSWERABLE and not r.required_claims:
        raise _fail(r, "an answerable question needs required claims")
    if not r.track_eligibility or not set(r.track_eligibility) <= set(ALL_TRACKS):
        raise _fail(r, "unknown track")
    if r.twin_of == r.question_id:
        raise _fail(r, "a question cannot be its own twin")


def validate_gold(r: GoldRecord) -> None:
    """The evidence schema's invariants. Corpus-dependent checks live in validation.py."""
    _check_labels(r)
    _check_slot_mix(r)
    _check_evidence_sets(r)
    _check_metadata(r)


def check_authority(record: GoldRecord, world: World) -> None:
    """Only versions in force may satisfy a slot or be named applicable: a draft or withdrawn version never can."""
    versions = {v.version_id: v for v in world.knowledge.versions}
    for slot in record.slots:
        for citation in slot.alternatives:
            cited = versions.get(citation.doc_id)
            if cited is not None and not cited.in_force:
                raise _fail(record, f"slot {slot.slot} cites {cited.version_id}, which is not in force")
    for version_id in record.gold_applicable_version_ids:
        if version_id not in versions or not versions[version_id].in_force:
            raise _fail(record, f"{version_id} cannot be an applicable version")


# --------------------------------------------------------------------------- the arm-visible side


def arm_request(record: GoldRecord, world: World, *, max_evidence_tokens: int = 4000) -> CaseRequest:
    """What an arm may see of a question: text, principal, snapshot and times. Filters come from the principal alone."""
    principal = next(p for p in world.entities.principals if p.principal_id == record.principal_id)
    return CaseRequest(
        question_id=record.question_id,
        query=record.query,
        principal_id=record.principal_id,
        corpus_snapshot_id=record.corpus_snapshot_id,
        evaluation_time=record.evaluation_time,
        event_time=record.event_time,
        filters={"tenant_id": principal.tenant_id, "role": principal.role_id},
        max_evidence_tokens=max_evidence_tokens,
        episode_id=None,
        turn_index=0,
    )


FORBIDDEN_QUERY = re.compile(
    r"(?i)\b(unanswerable|answerable|conflict|stratum|blocked|abstain|partial|gold|expected answer|scenario)\b"
)
_DOC_ID = re.compile(r"\b(?:SOP|POL|EXC)-\d{3}\b|@v\d")
_ERROR_CODE = re.compile(r"MS-\d{4}")
_TXN_ID = re.compile(r"TXN-[A-Z]{3}-\d{5}")


def screen_query(text: str, stratum: Stratum, kind: str) -> None:
    """Refuse query text that tells an arm the answer class or carries identifiers outside their stratum."""
    try:
        screen_arm_visible("query", text)
    except ContractError as exc:
        raise GoldError(str(exc)) from None
    if FORBIDDEN_QUERY.search(text):
        raise GoldError("query uses answer-class vocabulary")
    if _DOC_ID.search(text) and kind != "exact_version":
        raise GoldError("query carries a document or version id outside the exact-id stratum")
    if _ERROR_CODE.search(text) and kind != "api_status":
        raise GoldError("query carries an error code outside the exact-id stratum")
    if _TXN_ID.search(text) and stratum is not Stratum.Q9:
        raise GoldError("query carries a transaction id outside the live-status stratum")


# --------------------------------------------------------------------------- partitions


def split_for_family(seed: int, tier: str, family: str, weights: Mapping[Split, int]) -> Split:
    """Deterministic split of a whole scenario family: a keyed hash mapped onto the weights."""
    total = sum(weights.values())
    point = int(sha256_hex(f"{seed}:{tier}:split:{family}")[:12], 16) % total
    for split, weight in weights.items():
        if point < weight:
            return split
        point -= weight
    raise GoldError("unreachable")


def check_partition(records: Sequence[GoldRecord], targets: Mapping[Split, int]) -> None:
    """No family spans two splits, and every stratum has exactly the target count in each split."""
    seen: dict[str, Split] = {}
    for r in records:
        if seen.setdefault(r.scenario_family, r.split) is not r.split:
            raise GoldError(f"scenario family {r.scenario_family} spans two splits")
    for stratum in Stratum:
        for split, want in targets.items():
            got = sum(1 for r in records if r.stratum is stratum and r.split is split)
            if got != want:
                raise GoldError(f"{stratum.value} has {got} questions in {split.value}, expected {want}")
        if any(r.stratum is stratum and r.split not in targets for r in records):
            raise GoldError(f"{stratum.value} has questions in a split outside the targets")


def language_labels(total: int, rng: random.Random) -> list[str]:
    """55/30/15 English, Indonesian, mixed over ``total`` questions by largest remainder, shuffled."""
    exact = {"en": total * 0.55, "id": total * 0.30, "mixed": total * 0.15}
    counts = {k: int(v) for k, v in exact.items()}
    for key in sorted(exact, key=lambda k: (counts[k] - exact[k], k))[: total - sum(counts.values())]:
        counts[key] += 1
    labels = [k for k, n in sorted(counts.items()) for _ in range(n)]
    rng.shuffle(labels)
    return labels
