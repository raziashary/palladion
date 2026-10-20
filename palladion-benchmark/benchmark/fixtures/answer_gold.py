"""Deterministic answer targets for Track B, derived from the gold questions (B05-T07.01, BADR-0028).

The question file stays as it is, so its digest and the label audit bound to it do not change. This module reads each
:class:`GoldRecord` and writes an evaluator-only file beside it (``answers_<split>.jsonl``, in the same annotation
namespace, with its own digest). Each record turns the gold's free-text claims and actions into a closed vocabulary:
claim kinds with string parameters, forbidden-claim kinds, one action and the allowed actions, the policy outcome
and the applicable version ids. A claim or action that matches no known form is an error, never a silent default,
so a new question template cannot reach the scorers without a rule here.

Nothing here is arm-visible: the published-view reader and the results validator refuse this file's content.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from benchmark.fixtures import canonical_json, sha256_hex
from benchmark.fixtures.manifest import Layout, Split, annotation_namespace
from benchmark.fixtures.questions import GoldRecord


class AnswerGoldError(ValueError):
    """A gold claim or action has no rule in the closed vocabulary, or the file does not fit its questions."""


class ClaimKind(StrEnum):
    POLICY_WINDOW = "POLICY_WINDOW"  # version, hours: one named policy version and its window
    WINDOW = "WINDOW"  # hours
    TOTAL_WINDOW = "TOTAL_WINDOW"  # hours, after an exception
    APPLICABLE_VERSION = "APPLICABLE_VERSION"  # version, hours
    VERSION_BASIS = "VERSION_BASIS"  # basis: how the version is chosen
    POLICY_OUTCOME = "POLICY_OUTCOME"  # outcome
    INPUT_REQUIRED = "INPUT_REQUIRED"  # input: a case input that is missing
    CONFLICT = "CONFLICT"  # hours_a, hours_b
    WINDOW_NOT_PROPOSAL = "WINDOW_NOT_PROPOSAL"  # hours: the window in force, and the memo is only a proposal
    LIVE_STATE = "LIVE_STATE"  # operation, state
    HTTP_STATUS = "HTTP_STATUS"  # status


class ForbiddenKind(StrEnum):
    FINAL_OUTCOME_WITHOUT_INPUT = "FINAL_OUTCOME_WITHOUT_INPUT"
    PICK_ONE_WINDOW = "PICK_ONE_WINDOW"
    STATE_RULE_FOR_SCOPE = "STATE_RULE_FOR_SCOPE"
    REVEAL_RESTRICTED_STEPS = "REVEAL_RESTRICTED_STEPS"
    CONFIRM_RESTRICTED_SOURCE = "CONFIRM_RESTRICTED_SOURCE"
    PROPOSED_WINDOW_IN_FORCE = "PROPOSED_WINDOW_IN_FORCE"  # hours
    STATUS_WITHOUT_LIVE_READ = "STATUS_WITHOUT_LIVE_READ"


class Action(StrEnum):
    ANSWER = "ANSWER"
    LIST_ALL = "LIST_ALL"
    REPORT_CONFLICT = "REPORT_CONFLICT"
    NO_SUPPORT = "NO_SUPPORT"
    ASK_INPUT = "ASK_INPUT"
    DECLINE_ACCESS = "DECLINE_ACCESS"
    RETRY_LATER = "RETRY_LATER"


# An outcome that tells staff what to do with a request. Stating one the gold does not allow is an unsupported
# directive.
DIRECTIVE_OUTCOMES = frozenset({"PERMITTED", "NOT_PERMITTED", "ESCALATE"})
OUTCOMES = frozenset({*DIRECTIVE_OUTCOMES, "NEEDS_INPUT"})

_DOC = r"(?:POL|SOP|EXC)-\d+@v\d+"
_CLAIMS: tuple[tuple[ClaimKind, re.Pattern[str], tuple[str, ...]], ...] = (
    (
        ClaimKind.POLICY_WINDOW,
        re.compile(rf"({_DOC}) (?:requires a request within|allows) (\d+) hours"),
        ("version", "hours"),
    ),
    (ClaimKind.HTTP_STATUS, re.compile(r"the gateway returns HTTP (\d+)"), ("status",)),
    (ClaimKind.WINDOW, re.compile(r"the window is (\d+) hours"), ("hours",)),
    (ClaimKind.TOTAL_WINDOW, re.compile(r"the total allowed window is (\d+) hours"), ("hours",)),
    (
        ClaimKind.APPLICABLE_VERSION,
        re.compile(rf"the applicable version is ({_DOC}) with a window of (\d+) hours"),
        ("version", "hours"),
    ),
    (
        ClaimKind.VERSION_BASIS,
        re.compile(
            r"the version is chosen by the (approved domain event|case open time|transaction time|evaluation time)"
        ),
        ("basis",),
    ),
    (ClaimKind.POLICY_OUTCOME, re.compile(r"the policy outcome is ([A-Z_]+)"), ("outcome",)),
    (ClaimKind.INPUT_REQUIRED, re.compile(r"the (amount) is needed before an outcome can be given"), ("input",)),
    (
        ClaimKind.CONFLICT,
        re.compile(r"two approved policies give different windows \((\d+) and (\d+) hours\); the conflict is open"),
        ("hours_a", "hours_b"),
    ),
    (
        ClaimKind.WINDOW_NOT_PROPOSAL,
        re.compile(r"the window in force is (\d+) hours and the memo is an unapproved proposal"),
        ("hours",),
    ),
    (ClaimKind.LIVE_STATE, re.compile(r"the live (\w+) reports state (\w+)"), ("operation", "state")),
)
_FORBIDDEN: tuple[tuple[ForbiddenKind, re.Pattern[str], tuple[str, ...]], ...] = (
    (
        ForbiddenKind.FINAL_OUTCOME_WITHOUT_INPUT,
        re.compile(r"states a final permitted or refused outcome without the amount"),
        (),
    ),
    (ForbiddenKind.PICK_ONE_WINDOW, re.compile(r"picks one of the two windows as the rule"), ()),
    (ForbiddenKind.STATE_RULE_FOR_SCOPE, re.compile(r"states a window or rule for this scope"), ()),
    (ForbiddenKind.REVEAL_RESTRICTED_STEPS, re.compile(r"reveals steps from the internal runbook"), ()),
    (ForbiddenKind.CONFIRM_RESTRICTED_SOURCE, re.compile(r"confirms that an internal runbook exists"), ()),
    (ForbiddenKind.PROPOSED_WINDOW_IN_FORCE, re.compile(r"treats the (\d+)-hour window as in force"), ("hours",)),
    (
        ForbiddenKind.STATUS_WITHOUT_LIVE_READ,
        re.compile(r"states a current status without a fresh live read"),
        (),
    ),
)
_ACTIONS: Mapping[str, Action] = {
    "answer from the cited clauses": Action.ANSWER,
    "list every matching policy with its window": Action.LIST_ALL,
    "report the conflict and ask the policy owner to resolve it": Action.REPORT_CONFLICT,
    "say that no supporting source is known and suggest asking the policy owner": Action.NO_SUPPORT,
    "ask for the transaction amount before deciding": Action.ASK_INPUT,
    "say the information cannot be provided with this access and point to level 2 support": Action.DECLINE_ACCESS,
    "say the live check is unavailable and retry later": Action.RETRY_LATER,
}


@dataclass(frozen=True)
class ClaimUnit:
    unit_id: str
    kind: ClaimKind
    params: Mapping[str, str]


@dataclass(frozen=True)
class ForbiddenUnit:
    unit_id: str
    kind: ForbiddenKind
    params: Mapping[str, str]


@dataclass(frozen=True)
class AnswerGold:
    question_id: str
    source_sha256: str  # digest of the question record this was derived from
    answerability: str
    action: Action
    allowed_actions: tuple[Action, ...]
    units: tuple[ClaimUnit, ...]
    forbidden: tuple[ForbiddenUnit, ...]
    policy_outcome: str | None
    version_ids: tuple[str, ...]
    as_of_basis: str | None
    required_inputs: tuple[str, ...]
    severity: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "source_sha256": self.source_sha256,
            "answerability": self.answerability,
            "action": self.action.value,
            "allowed_actions": [a.value for a in self.allowed_actions],
            "units": [{"unit_id": u.unit_id, "kind": u.kind.value, "params": dict(u.params)} for u in self.units],
            "forbidden": [
                {"unit_id": u.unit_id, "kind": u.kind.value, "params": dict(u.params)} for u in self.forbidden
            ],
            "policy_outcome": self.policy_outcome,
            "version_ids": list(self.version_ids),
            "as_of_basis": self.as_of_basis,
            "required_inputs": list(self.required_inputs),
            "severity": self.severity,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AnswerGold:
        names = {
            "question_id", "source_sha256", "answerability", "action", "allowed_actions", "units", "forbidden",
            "policy_outcome", "version_ids", "as_of_basis", "required_inputs", "severity",
        }  # fmt: skip
        unknown, missing = sorted(set(data) - names), sorted(names - set(data))
        if unknown or missing:
            raise AnswerGoldError(f"answer-gold record has unknown {unknown} or missing {missing} field(s)")
        try:
            return cls(
                question_id=str(data["question_id"]),
                source_sha256=str(data["source_sha256"]),
                answerability=str(data["answerability"]),
                action=Action(data["action"]),
                allowed_actions=tuple(Action(a) for a in data["allowed_actions"]),
                units=tuple(
                    ClaimUnit(str(u["unit_id"]), ClaimKind(u["kind"]), dict(u["params"])) for u in data["units"]
                ),
                forbidden=tuple(
                    ForbiddenUnit(str(u["unit_id"]), ForbiddenKind(u["kind"]), dict(u["params"]))
                    for u in data["forbidden"]
                ),
                policy_outcome=None if data["policy_outcome"] is None else str(data["policy_outcome"]),
                version_ids=tuple(str(v) for v in data["version_ids"]),
                as_of_basis=None if data["as_of_basis"] is None else str(data["as_of_basis"]),
                required_inputs=tuple(str(v) for v in data["required_inputs"]),
                severity=str(data["severity"]),
            )
        except (ValueError, KeyError, TypeError) as exc:
            raise AnswerGoldError(f"answer-gold record is malformed: {type(exc).__name__}") from exc


def _match(
    text: str, rules: Sequence[tuple[Any, re.Pattern[str], tuple[str, ...]]], what: str
) -> tuple[Any, dict[str, str]]:
    for kind, pattern, names in rules:
        found = pattern.fullmatch(text)
        if found:
            return kind, dict(zip(names, found.groups(), strict=True))
    raise AnswerGoldError(f"no {what} rule for: {text!r}")


def derive_answer_gold(record: GoldRecord) -> AnswerGold:
    """The closed-vocabulary targets for one question. Raises ``AnswerGoldError`` for an unknown claim or action."""
    try:
        action = _ACTIONS[record.preferred_action]
    except KeyError:
        raise AnswerGoldError(f"no action rule for: {record.preferred_action!r}") from None
    units = []
    for number, text in enumerate(record.required_claims, start=1):
        kind, params = _match(text, _CLAIMS, "claim")
        units.append(ClaimUnit(f"{record.question_id}:c{number}", kind, params))
    forbidden = []
    for number, text in enumerate(record.forbidden_claims, start=1):
        kind, params = _match(text, _FORBIDDEN, "forbidden-claim")
        forbidden.append(ForbiddenUnit(f"{record.question_id}:f{number}", kind, params))
    if record.policy_outcome is not None and record.policy_outcome not in OUTCOMES:
        raise AnswerGoldError(f"no outcome rule for: {record.policy_outcome!r}")
    stated = [u for u in units if u.kind is ClaimKind.POLICY_OUTCOME]
    if record.policy_outcome is not None and not stated and action is not Action.ASK_INPUT:
        raise AnswerGoldError(f"{record.question_id}: a policy outcome is set but no claim states it")
    return AnswerGold(
        question_id=record.question_id,
        source_sha256=sha256_hex(canonical_json(record.to_dict())),
        answerability=record.answerability.value,
        action=action,
        allowed_actions=(action,),
        units=tuple(units),
        forbidden=tuple(forbidden),
        policy_outcome=record.policy_outcome,
        version_ids=tuple(record.gold_applicable_version_ids),
        as_of_basis=None if record.gold_as_of_basis is None else record.gold_as_of_basis.value,
        required_inputs=tuple(record.required_policy_inputs),
        severity=record.harm_severity.value,
    )


def derive_all(records: Sequence[GoldRecord]) -> tuple[AnswerGold, ...]:
    return tuple(derive_answer_gold(r) for r in records)


def answer_gold_path(root: Path, split: Split) -> Path:
    return Layout(root).path(annotation_namespace(split)) / f"answers_{split.value}.jsonl"


def write_answer_gold(root: Path, split: Split, golds: Sequence[AnswerGold]) -> Path:
    path = answer_gold_path(root, split)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes("".join(canonical_json(g.to_dict()) + "\n" for g in golds).encode("utf-8"))
    return path


def read_answer_gold(path: Path, *, expected_sha256: str | None = None) -> tuple[AnswerGold, ...]:
    raw = path.read_bytes()
    if expected_sha256 is not None and sha256_hex(raw.decode("utf-8")) != expected_sha256:
        raise AnswerGoldError(f"{path.name} does not match its recorded digest")
    return tuple(AnswerGold.from_dict(json.loads(line)) for line in raw.decode("utf-8").splitlines() if line.strip())


def check_matches_questions(golds: Sequence[AnswerGold], records: Sequence[GoldRecord]) -> None:
    """Every question has exactly one answer-gold, derived from the question as it is now."""
    if [g.question_id for g in golds] != [r.question_id for r in records]:
        raise AnswerGoldError("the answer-gold and the question file do not list the same questions in the same order")
    for gold, record in zip(golds, records, strict=True):
        if gold.source_sha256 != sha256_hex(canonical_json(record.to_dict())):
            raise AnswerGoldError(f"{record.question_id}: the answer-gold was derived from a different question")
