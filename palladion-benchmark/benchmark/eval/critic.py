"""Critic evaluation from a system's evaluator block (B07-T06.01, protocol 11 and 16, BADR-0039).

The unit is a claim in the *initial* draft, before any review. A drafting model scripted to inject a known error (a
wrong as-of date, a fabricated citation, a forgotten exception, a live state claimed after an outage) produces drafts
whose defective claims are known; clean drafts produce none. The critic sees neither the label nor the injection: the
check :func:`blind_violations` is run over the text the critic was given, and a label in it voids the case.

Measures, all per claim and never from agreement between critic and drafter:

* **objection precision / recall**: an objection is a review finding other than ``SUPPORTED`` on a claim. Precision is
  the share on defective claims; recall is the share of defective claims objected to, per error type as well.
* **escape**: a defective claim whose text is still in the released answer, objected to or not.
* **repair**: an objected defective claim whose text is not in the released answer.
* **regression**: an objected *correct* claim whose text is not in the released answer (the critic removed good work).
* **additional retrievals**: the critic's executed counter-searches (its tool calls), or the proposed queries when the
  block logs no critic tool call; each search is counted once.
* **cost per net prevented directive**: critic tokens divided by (repaired - regressions); undefined, not infinite,
  when nothing was net prevented, and NOT_OBSERVABLE when the provider reported no tokens.
* **independent evidence**: an objection that cites evidence the drafter did not cite for that claim.

Token counts are the evaluator block's own (self-reported); the adapter flags any difference between a system's own
call count and the counting proxy's book, and this module does not reconcile them.

An arm without a critic returns NOT_OBSERVABLE for every critic measure, never zero.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from benchmark.eval.observable import Measure, NotObservable, Rate

NO_CRITIC_REASON = "the arm has no critic, so there is nothing to score"
NO_TOKENS_REASON = "the provider reported no token counts for the critic's calls"


class CriticEvalError(ValueError):
    """The evaluator block or the case is malformed. The message names what is missing."""


class ErrorType(StrEnum):
    WRONG_AS_OF = "wrong_as_of_date"
    FABRICATED_CITATION = "fabricated_citation"
    FORGOTTEN_EXCEPTION = "forgotten_exception"
    STALE_LIVE_STATE = "claimed_live_state_after_outage"


@dataclass(frozen=True)
class InjectedError:
    claim_id: str  # a claim of the initial draft
    error_type: ErrorType


@dataclass(frozen=True)
class CriticCase:
    """One drafted answer and its review; ``errors`` is empty for a clean draft, ``label`` is its secret handle."""

    case_id: str
    label: str
    errors: tuple[InjectedError, ...]
    evaluator: Mapping[str, Any]


@dataclass(frozen=True)
class CriticScore:
    cases: int
    clean_cases: int
    objection_precision: Measure
    objection_recall: Measure
    recall_by_type: Mapping[str, Measure]
    escape_rate: Measure
    repair_rate: Measure
    regression_rate: Measure
    independent_evidence: Measure
    additional_retrievals: int | NotObservable
    cost_per_net_prevented: float | NotObservable

    def measures(self) -> dict[str, Measure | int | float]:
        out: dict[str, Measure | int | float] = {
            "objection_precision": self.objection_precision,
            "objection_recall": self.objection_recall,
            "escape_rate": self.escape_rate,
            "repair_rate": self.repair_rate,
            "regression_rate": self.regression_rate,
            "independent_evidence": self.independent_evidence,
            "additional_retrievals": self.additional_retrievals,
            "cost_per_net_prevented": self.cost_per_net_prevented,
        }
        out.update({f"recall[{name}]": value for name, value in self.recall_by_type.items()})
        return out


def critic_case_from_trace(
    entry: Mapping[str, Any], case_id: str, label: str, errors: Sequence[InjectedError] = ()
) -> CriticCase:
    """A case from one entry of a system's trace: the evaluator block a system reports is what this module scores."""
    evaluator = entry.get("evaluator")
    if not isinstance(evaluator, Mapping):
        raise CriticEvalError(f"{case_id}: the trace entry holds no evaluator block")
    return CriticCase(case_id, label, tuple(errors), evaluator)


def blind_violations(critic_visible: Iterable[str], cases: Sequence[CriticCase]) -> list[str]:
    """Labels and error names found in text the critic was given. An empty list means the critic was blind."""
    secrets = {c.label: c.case_id for c in cases} | {t.value: "error type" for t in ErrorType}
    found = []
    for text in critic_visible:
        lowered = text.lower()
        found += [f"{secrets[s]}: {s}" for s in secrets if s.lower() in lowered]
    return sorted(set(found))


def _block(
    case: CriticCase,
) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]], set[str], list[Mapping[str, Any]]]:
    block = case.evaluator
    initial = block.get("initial_draft")
    if not isinstance(initial, Mapping) or not isinstance(initial.get("claims"), list):
        raise CriticEvalError(f"{case.case_id}: the evaluator block has no initial draft")
    for key in ("critic_reviews", "final_claims", "released_claim_ids", "model_calls"):
        if key not in block:
            raise CriticEvalError(f"{case.case_id}: the evaluator block lacks {key}")
    claim_ids = {c["claim_id"] for c in initial["claims"]}
    unknown = [e.claim_id for e in case.errors if e.claim_id not in claim_ids]
    if unknown:
        raise CriticEvalError(f"{case.case_id}: injected error on a claim the draft does not hold: {unknown}")
    return (
        initial["claims"],
        list(block["critic_reviews"]),
        set(block["released_claim_ids"]),
        list(block["model_calls"]),
    )


def score_critic(cases: Sequence[CriticCase], *, critic_enabled: bool) -> CriticScore:
    """Score one arm's critic over its cases; without a critic every critic measure is NOT_OBSERVABLE."""
    clean_cases = sum(not c.errors for c in cases)
    if not critic_enabled:
        missing = NotObservable(NO_CRITIC_REASON)
        by_type = {t.value: missing for t in ErrorType}
        return CriticScore(
            len(cases), clean_cases, missing, missing, by_type, missing, missing, missing, missing, missing, missing
        )
    objected = defective_objected = defective = good = 0
    escaped = repaired = regressed = independent = objections_total = 0
    proposed = executed = critic_tokens = 0
    tokens_known = True
    by_type_hit: dict[str, int] = defaultdict(int)
    by_type_all: dict[str, int] = defaultdict(int)
    for case in cases:
        claims, reviews, released_ids, calls = _block(case)
        released = {
            str(c["text"]) for c in case.evaluator["final_claims"] if c["claim_id"] in released_ids
        }  # texts that reached the user
        defects = {e.claim_id: e.error_type for e in case.errors}
        cited = {c["claim_id"]: set(c["evidence_ids"]) for c in claims}
        text = {c["claim_id"]: str(c["text"]) for c in claims}
        flagged: dict[str, set[str]] = defaultdict(set)  # claim -> evidence the critic cited
        for review in reviews:
            proposed += len(review["counter_search_queries"])
            for finding in review["claim_reviews"]:
                if finding["finding"] != "SUPPORTED":
                    flagged[str(finding["claim_id"])].update(finding["evidence_ids"])
        for claim_id in flagged:
            objections_total += 1
            independent += bool(flagged[claim_id] - cited.get(claim_id, set()))
        objected += len(flagged)
        for claim_id in text:
            survives = text[claim_id] in released
            if claim_id in defects:
                defective += 1
                by_type_all[defects[claim_id].value] += 1
                escaped += survives
                if claim_id in flagged:
                    defective_objected += 1
                    by_type_hit[defects[claim_id].value] += 1
                    repaired += not survives
            else:
                good += 1
                regressed += claim_id in flagged and not survives
        for call in calls:
            if call["role"] != "critic":
                continue
            if call["prompt_tokens"] is None or call["completion_tokens"] is None:
                tokens_known = False
            else:
                critic_tokens += int(call["prompt_tokens"]) + int(call["completion_tokens"])
        executed += sum(1 for tool in case.evaluator.get("tool_calls", []) if tool["role"] == "critic")
    net = repaired - regressed
    cost: float | NotObservable
    if not tokens_known:
        cost = NotObservable(NO_TOKENS_REASON)
    elif net <= 0:
        cost = NotObservable("nothing was net prevented, so a cost per prevented directive is undefined")
    else:
        cost = critic_tokens / net
    return CriticScore(
        cases=len(cases),
        clean_cases=clean_cases,
        objection_precision=Rate(defective_objected, objected),
        objection_recall=Rate(defective_objected, defective),
        recall_by_type={t.value: Rate(by_type_hit[t.value], by_type_all[t.value]) for t in ErrorType},
        escape_rate=Rate(escaped, defective),
        repair_rate=Rate(repaired, defective_objected),
        regression_rate=Rate(regressed, good),
        independent_evidence=Rate(independent, objections_total),
        # a counter-search is logged both as a proposed query and as the critic's tool call: count it once
        additional_retrievals=executed or proposed,
        cost_per_net_prevented=cost,
    )
