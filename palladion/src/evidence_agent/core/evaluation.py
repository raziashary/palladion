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
