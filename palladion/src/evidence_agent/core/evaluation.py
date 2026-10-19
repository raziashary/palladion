"""Small, denominator-aware retrieval metrics for the synthetic P02 pilot."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence


def score_ranked_references(
    expected: Iterable[str],
    ranked: Iterable[str],
    *,
    cutoffs: Sequence[int] = (5, 10, 20),
    relevance: Mapping[str, float] | None = None,
) -> dict[str, float | None]:
    """Score unique canonical references; return ``None`` when gold is empty.

    Repeated predictions retain their first rank and never increase recall or DCG.
    This helper deliberately applies no pass threshold: pilot misses are measurements.
    """
    relevant = tuple(dict.fromkeys(expected))
    order = tuple(dict.fromkeys(ranked))
    if not relevant:
        return {**{f"recall_at_{k}": None for k in cutoffs}, "mrr": None,
                **{f"ndcg_at_{k}": None for k in cutoffs}}
    if any(k < 1 for k in cutoffs):
        raise ValueError("metric cutoffs must be positive")
    grades = {item: float((relevance or {}).get(item, 1.0)) for item in relevant}
    if any(not math.isfinite(grade) or grade < 0 for grade in grades.values()):
        raise ValueError("relevance grades must be finite and non-negative")
    positions = {item: rank for rank, item in enumerate(order, start=1)}
    result: dict[str, float | None] = {}
    for k in cutoffs:
        hits = sum(positions.get(item, k + 1) <= k for item in relevant)
        result[f"recall_at_{k}"] = hits / len(relevant)
        dcg = sum(
            (2 ** grades[item] - 1) / math.log2(rank + 1)
            for item, rank in positions.items()
            if rank <= k and item in grades
        )
        ideal = sorted(grades.values(), reverse=True)[:k]
        idcg = sum((2 ** grade - 1) / math.log2(rank + 1)
                   for rank, grade in enumerate(ideal, start=1))
        result[f"ndcg_at_{k}"] = dcg / idcg if idcg else 0.0
    first_rank = min((positions[item] for item in relevant if item in positions), default=None)
    result["mrr"] = 1 / first_rank if first_rank is not None else 0.0
    return result


def macro_average(rows: Iterable[Mapping[str, float | None]]) -> dict[str, float | None]:
    """Average each available metric over cases with an observed denominator."""
    materialized = tuple(rows)
    keys = tuple(dict.fromkeys(key for row in materialized for key in row))
    result: dict[str, float | None] = {}
    for key in keys:
        values = [value for row in materialized if (value := row.get(key)) is not None]
        result[key] = sum(values) / len(values) if values else None
    return result


def score_continuation(output: Mapping[str, object], packet: Mapping[str, object], *,
                       required_gaps: Sequence[str], current_value: str,
                       stale_value: str) -> dict[str, object]:
    """Exact synthetic controls, not semantic entailment or a research success threshold."""
    required = set(required_gaps)
    gaps = output.get("missing_requirements")
    questions = packet.get("open_questions")
    claims = output.get("verified_claims")
    if not isinstance(gaps, list) or not isinstance(questions, list) or not isinstance(claims, list):
        raise ValueError("Actual response/packet lists required")
    texts = [str(c.get("text", "")) for c in claims if isinstance(c, dict)]
    stale = sum(f": {stale_value} at " in text for text in texts)
    current = any(f": {current_value} at " in text for text in texts)
    packet_missing = sorted(required - set(questions))
    answer_missing = sorted(required - set(gaps))
    return {"required_gap_count": len(required), "packet_omitted_gaps": packet_missing,
        "answer_omitted_gaps": answer_missing,
        "packet_gap_recall": (len(required)-len(packet_missing))/len(required) if required else None,
        "answer_gap_recall": (len(required)-len(answer_missing))/len(required) if required else None,
        "stale_claim_count": stale, "current_observation_released": current,
        "completion": current and not stale and not answer_missing and
            output.get("disposition") == "PARTIALLY_SUPPORTED" and not output.get("verification_failures")}


def score_critic_output(output: Mapping[str, object], *, frozen_hash: str,
                        consumed_hash: str, expected_quote: str | None,
                        known_fact_id: str, initial_ids: Sequence[str], final_ids: Sequence[str],
                        initial_fact_retained: bool | None = None,
                        reviews: Sequence[Mapping[str, object]] = (),
                        known_valid_claim_ids: Sequence[str] = (),
                        known_invalid_claim_ids: Sequence[str] = ()) -> dict[str, object]:
    """Mechanical fixture outcomes only; unadjudicated semantic judgments stay unknown."""
    if len(frozen_hash) != 64 or frozen_hash != consumed_hash:
        raise ValueError("Paired critic inputs differ")
    claims, citations = output.get("verified_claims"), output.get("citations")
    failures = output.get("verification_failures")
    if not isinstance(claims, list) or not isinstance(citations, list):
        raise ValueError("Actual gate output required")
    retained = any(isinstance(c, dict) and known_fact_id in c.get("evidence_ids", []) and
                   "Last observed " in str(c.get("text", "")) for c in claims)
    corrected = (any(isinstance(c, dict) and expected_quote in str(c.get("text", "")) for c in claims)
                 if expected_quote is not None else None)
    findings: list[dict[str, object]] = []
    for review in reviews:
        entries = review.get("claim_reviews")
        if isinstance(entries, list):
            findings.extend(finding for finding in entries if isinstance(finding, dict))
    objections = [finding for finding in findings if finding.get("finding") != "SUPPORTED"]
    return {"initial_input_hash_equal": True, "known_fact_retained": retained,
        "known_fact_omitted": not retained, "mechanical_exception_quote_corrected": corrected,
        "scorer_version": "2.0",
        "known_fact_retention_loss_vs_off": initial_fact_retained and not retained if initial_fact_retained is not None else None,
        "mechanical_false_veto_vs_off": None,  # Omission alone cannot attribute a veto to the critic.
        "changed_evidence_ids": sorted(set(final_ids)-set(initial_ids)),
        "mechanical_false_objections": sum(f.get("claim_id") in known_valid_claim_ids for f in objections),
        "mechanical_invalid_associations_detected": sorted({str(f["claim_id"]) for f in objections
            if f.get("claim_id") in known_invalid_claim_ids}),
        "inventory_attested": output.get("inventory_attested"),
        "unadjudicated_semantic_correction": None, "unadjudicated_semantic_false_veto": None,
        "verification_failure_count": len(failures) if isinstance(failures, list) else None}
