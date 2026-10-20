"""Denominator-aware metrics and immutable evidence contracts for synthetic studies."""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
import statistics
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any


def score_categories(expected: Sequence[str], predicted: Sequence[str]) -> dict[str, Any]:
    """Exact category counts; episodic retention is abstention from durable promotion."""
    categories = ("EPISODIC", "SEMANTIC", "PROCEDURAL")
    if not expected or len(expected) != len(predicted) or any(
        item not in categories for item in (*expected, *predicted)
    ):
        raise ValueError("Nonempty aligned category labels required")
    result: dict[str, Any] = {"count": len(expected),
                              "episodic_retention": predicted.count("EPISODIC") / len(predicted)}
    for category in categories:
        tp = sum(a == b == category for a, b in zip(expected, predicted, strict=True))
        fp = sum(a != category and b == category for a, b in zip(expected, predicted, strict=True))
        fn = sum(a == category and b != category for a, b in zip(expected, predicted, strict=True))
        result[category] = {"tp": tp, "fp": fp, "fn": fn,
                            "precision": tp / (tp + fp) if tp + fp else None,
                            "recall": tp / (tp + fn) if tp + fn else None}
    return result


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


def score_observed_packet(expected: Iterable[str], ranked: Iterable[str], *,
                          limit: int) -> dict[str, Any]:
    """Measure only a bounded final packet, never unobserved candidate ranks."""
    order = tuple(dict.fromkeys(ranked))
    if not 1 <= limit <= 20 or len(order) > limit:
        raise ValueError("Observed packet exceeds its declared limit")
    metrics = score_ranked_references(expected, order, cutoffs=(limit,))
    packet_mrr = metrics.pop("mrr")
    return {"scope": "FINAL_PACKET", "observed_limit": limit, "returned": len(order),
            **metrics, "packet_mrr": packet_mrr, "candidate_mrr": None,
            "unobserved_cutoffs": {str(k): None for k in (5, 10, 20) if k > limit},
            "unavailable_reason": "CANDIDATE_STAGES_NOT_CAPTURED"}


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
        "inventory_attested_measurement": "TELEMETRY_CONTRACT_ONLY",
        "unadjudicated_completeness_assertion_accuracy": None,
        "unadjudicated_semantic_correction": None, "unadjudicated_semantic_false_veto": None,
        "verification_failure_count": len(failures) if isinstance(failures, list) else None}


def canonical_digest(value: object) -> str:
    """Hash a portable JSON value; reject non-finite numbers rather than serializing NaN."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def fuse_fixed_rankings(dense: Sequence[Mapping[str, Any]], sparse: Sequence[Mapping[str, Any]],
                       *, method: str = "rrf") -> list[str]:
    """One declared fusion on immutable scored lists; never fuse already fused output."""
    if method not in {"rrf", "minmax_combsum"} or max(len(dense),len(sparse))>100:
        raise ValueError("Unknown or unbounded fusion treatment")
    scores: dict[str,float] = {}
    for channel in (dense,sparse):
        parsed: list[tuple[str,float]] = []
        for row in channel:
            identifier, score = row.get("chunk_id"),row.get("score")
            if (not isinstance(identifier,str) or not identifier or
                    not isinstance(score,(int,float)) or isinstance(score,bool) or not math.isfinite(score)):
                raise ValueError("Unique scored raw candidates required")
            parsed.append((identifier,float(score)))
        if len({identifier for identifier,_ in parsed}) != len(parsed):
            raise ValueError("Unique scored raw candidates required")
        values = [score for _,score in parsed]
        low, high = min(values,default=0),max(values,default=0)
        for rank,(identifier,score) in enumerate(parsed,start=1):
            contribution = (1/(60+rank) if method=="rrf" else
                            (score-low)/(high-low) if high>low else 1.0)
            scores[identifier] = scores.get(identifier,0)+contribution
    return sorted(scores,key=lambda identifier:(-scores[identifier],identifier))


def measured_rate(numerator: int | None, denominator: int | None, *,
                  unknown_reason: str | None = None) -> dict[str, Any]:
    """Missing annotation and a measured zero are different observations."""
    if numerator is None or denominator is None:
        if numerator is not None or denominator is not None or not unknown_reason:
            raise ValueError("Unknown measurements require both counts absent and a reason")
        return {"numerator": None, "denominator": None, "value": None,
                "status": "UNKNOWN", "reason": unknown_reason}
    if type(numerator) is not int or type(denominator) is not int or not 0 <= numerator <= denominator:
        raise ValueError("Invalid measurement counts")
    return {"numerator": numerator, "denominator": denominator,
            "value": numerator / denominator if denominator else None,
            "status": "MEASURED" if denominator else "NOT_APPLICABLE",
            "reason": None if denominator else "ZERO_DENOMINATOR"}


def latency_summary(samples: Sequence[float]) -> dict[str, Any]:
    """Linear sample percentiles with explicit n; small pilots are not capacity evidence."""
    if any(not math.isfinite(x) or x < 0 for x in samples):
        raise ValueError("Latency must be finite and non-negative")
    ordered = sorted(samples)
    def percentile(p: float) -> float | None:
        if not ordered:
            return None
        position = (len(ordered) - 1) * p
        low = int(position)
        return ordered[low] + (ordered[min(low + 1, len(ordered)-1)]-ordered[low]) * (position-low)
    return {"n": len(ordered), "p50": percentile(.5), "p95": percentile(.95),
            "method": "linear_sample_percentile", "capacity_claim": False}


def clustered_difference(rows: Sequence[Mapping[str, Any]], *, seed: int = 17,
                         resamples: int = 1000) -> dict[str, Any]:
    """Paired differences bootstrap case clusters, never individual repeated generations."""
    if not 100 <= resamples <= 10000:
        raise ValueError("Bounded bootstrap resamples required")
    clusters: dict[str, list[float]] = {}
    missing = 0
    for row in rows:
        if not isinstance(row.get("case_id"), str) or not row["case_id"]:
            raise ValueError("Case cluster ID required")
        control, treatment = row.get("control"), row.get("treatment")
        if control is None or treatment is None:
            missing += 1
            continue
        if any(type(v) not in {float, int} or not math.isfinite(v) for v in (control,treatment)):
            raise ValueError("Finite paired observations required")
        clusters.setdefault(row["case_id"], []).append(float(treatment)-float(control))
    means = [statistics.mean(values) for values in clusters.values()]
    if not means:
        return {"case_clusters": 0, "missing_pairs": missing, "difference": None,
                "interval95": None, "method": "case_cluster_bootstrap"}
    generator = random.Random(seed)
    draws = sorted(statistics.mean(generator.choices(means, k=len(means))) for _ in range(resamples))
    return {"case_clusters": len(means), "missing_pairs": missing,
        "difference": statistics.mean(means),
        "interval95": [draws[int(.025*(resamples-1))],draws[int(.975*(resamples-1))]],
        "method": "case_cluster_bootstrap", "seed": seed, "resamples": resamples,
        "generalization_claim": False}


def validate_study_split(cases: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
    """Reject shared families, identical normalized documents and near-duplicate leakage."""
    ids: set[str] = set()
    families: dict[str, str] = {}
    documents: list[tuple[str, set[str]]] = []
    split: dict[str, list[str]] = {"development": [], "evaluation": []}
    for case in cases:
        identifier, family, phase, text = (case.get(k) for k in ("case_id","family_id","split","document"))
        if (not all(isinstance(x, str) and x.strip() for x in (identifier,family,phase,text))
                or phase not in split or identifier in ids):
            raise ValueError("Unique cases and valid family/split/document required")
        assert isinstance(identifier,str) and isinstance(family,str) and isinstance(phase,str)
        assert isinstance(text,str)
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}",identifier):
            raise ValueError("Contained study case ID required")
        if family in families and families[family] != phase:
            raise ValueError("Document family crosses study splits")
        families[family] = phase
        ids.add(identifier)
        supplied = [text]+[value for key,value in case.items() if key.endswith("_document")]
        for document in supplied:
            if not isinstance(document,str) or not document.strip() or len(document)>16384:
                raise ValueError("Bounded nonempty supplied document required")
            tokens = set(document.lower().split())
            for previous_phase, previous in documents:
                if previous_phase != phase and len(tokens & previous) / len(tokens | previous) >= .8:
                    raise ValueError("Near-duplicate document crosses study splits")
            documents.append((phase,tokens))
        split[phase].append(identifier)
    if not all(split.values()):
        raise ValueError("Both development and evaluation families required")
    return split


_MANIFEST_FIELDS = {"schema_version", "study_id", "phase", "annotation_status", "revision",
    "dirty_patch_sha256", "corpus_sha256", "gold_sha256", "split_sha256", "protocol_sha256",
    "model", "prompt_sha256", "dependency_lock_sha256", "scope_sha256", "representations",
    "generations", "hardware", "cache", "randomness", "budgets", "treatments", "created_at"}


def validate_run_manifest(manifest: Mapping[str, Any]) -> None:
    """A replayable run discloses unavailable measurements explicitly and binds its inputs."""
    if set(manifest) != _MANIFEST_FIELDS or manifest["schema_version"] != "p08.1":
        raise ValueError("Incomplete or unknown run manifest")
    for name, value in manifest.items():
        if name.endswith("sha256") and (not isinstance(value,str) or len(value)!=64 or
                                        any(c not in "0123456789abcdef" for c in value)):
            raise ValueError("Invalid manifest digest: " + name)
    if manifest["phase"] not in {"development", "evaluation"}:
        raise ValueError("Unknown study phase")
    if manifest["annotation_status"] != "PILOT_NOT_HUMAN_ADJUDICATED":
        raise ValueError("Independent annotation contract not supplied for an adjudicated claim")
    if not manifest["treatments"] or not manifest["budgets"] or not manifest["randomness"]:
        raise ValueError("Treatment, budget and repetition plan required")
    canonical_digest(dict(manifest))


def score_study_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Read actual persisted response records; errors stay in denominators and slices."""
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    seen: set[tuple[object,object,object]] = set()
    for row in rows:
        required = {"case_id","arm","repetition","status","response","elapsed_seconds",
                    "calls","usage","citation_readback","expected_disposition","slices"}
        if not required.issubset(row):
            raise ValueError("Missing actual output/denominator fields")
        if row["status"] == "RECEIVED" and not isinstance(row["response"],dict):
            raise ValueError("Received run has no actual response")
        key = (row["case_id"],row["arm"],row["repetition"])
        if key in seen:
            raise ValueError("Duplicate study observation")
        seen.add(key)
        grouped.setdefault(str(row["arm"]), []).append(row)
    result: dict[str, Any] = {}
    def known_tokens(record: Mapping[str, Any]) -> int:
        usages = record.get("attempt_usage")
        if usages is None:
            usages = [record["usage"]]
        return sum(value["total_tokens"] for value in usages if isinstance(value,dict)
                   and type(value.get("total_tokens")) is int)
    for arm, observations in grouped.items():
        ok = [r for r in observations if r["status"] == "RECEIVED"]
        response_rows = [r for r in ok if isinstance(r["response"],dict)]
        correct = sum(r["response"].get("disposition")==r["expected_disposition"] for r in response_rows)
        attempts = sum(int(r["calls"]) for r in observations)
        tokens = [r["usage"].get("total_tokens") for r in observations if isinstance(r["usage"],dict)]
        slices: dict[str, list[str]] = {}
        for row in observations:
            for label in row["slices"]:
                slices.setdefault(str(label),[]).append(str(row["case_id"]))
        result[arm] = {"attempted_runs": len(observations), "received_runs": len(ok),
            "failed_runs": len(observations)-len(ok),
            "disposition_accuracy_all_attempts": measured_rate(correct,len(observations)),
            "citation_readback": measured_rate(sum(bool(r["citation_readback"]) for r in observations),len(observations)),
            "latency_seconds": latency_summary([float(r["elapsed_seconds"]) for r in observations]),
            "model_calls": attempts,
            "known_received_tokens": sum(known_tokens(r) for r in observations),
            "usage_missing_runs": sum(t is None for t in tokens),
            "usage_missing_attempts":sum(not isinstance(u,dict) or type(u.get("total_tokens")) is not int
                for r in observations for u in r["attempt_usage"])
                if all("attempt_usage" in r for r in observations) else None,
            "semantic_support_precision": measured_rate(None,None,unknown_reason="NO_INDEPENDENT_HUMAN_LABELS"),
            "unsupported_material_claim_rate": measured_rate(None,None,unknown_reason="NO_INDEPENDENT_HUMAN_LABELS"),
            "human_usefulness": measured_rate(None,None,unknown_reason="NO_INDEPENDENT_HUMAN_RATINGS"),
            "case_ids_by_slice": slices, "billing": {"value": None,"status":"UNVERIFIED"}}
        result[arm]["unsupported_operational_action_rate"] = measured_rate(None,None,
            unknown_reason="NO_INDEPENDENT_HUMAN_LABELS")
        result[arm]["causal_false_veto_rate"] = measured_rate(None,None,
            unknown_reason="NO_ADJUDICATED_COUNTERFACTUAL")
        quote_rows = [r for r in observations if r.get("expected_quote")]
        def quote_present(record: Mapping[str, Any]) -> bool:
            response = record.get("response")
            return isinstance(response,dict) and any(isinstance(c,dict) and
                record["expected_quote"] in str(c.get("text",""))
                for c in response.get("verified_claims",[]))
        result[arm]["mechanical_exact_quote_recovery"] = measured_rate(
            sum(quote_present(r) for r in quote_rows),len(quote_rows))
        result[arm]["exact_citation_resolvability"] = measured_rate(
            sum(int(r.get("citations_valid",0)) for r in observations),
            sum(int(r.get("citations_attempted",0)) for r in observations))
        result[arm]["verified_claim_coverage"] = measured_rate(sum(bool(r["response"].get("verified_claims"))
            for r in response_rows),len(observations))
        answerable = [r for r in observations if "answerable" in r["slices"]]
        unanswerable = [r for r in observations if "unanswerable" in r["slices"]]
        abstained = [r for r in response_rows if r["response"].get("disposition") in
                     {"NOT_ESTABLISHED","VERIFICATION_UNAVAILABLE"}]
        result[arm]["abstention_precision"] = measured_rate(
            sum("unanswerable" in r["slices"] for r in abstained),len(abstained))
        result[arm]["abstention_recall"] = measured_rate(
            sum(r in abstained for r in unanswerable),len(unanswerable))
        result[arm]["answerable_case_count"] = len(answerable)
        result[arm]["metrics_by_slice"] = {label:{
            "runs":len(subset),"received":sum(r["status"]=="RECEIVED" for r in subset),
            "disposition_accuracy_all_attempts":measured_rate(sum(isinstance(r["response"],dict) and
                r["response"].get("disposition")==r["expected_disposition"] for r in subset),len(subset)),
            "latency_seconds":latency_summary([float(r["elapsed_seconds"]) for r in subset]),
            "model_calls":sum(int(r["calls"]) for r in subset),
            "known_received_tokens":sum(known_tokens(r) for r in subset)}
            for label in slices for subset in [[r for r in observations if label in r["slices"]]]}
    return result


def reconcile_integrity_tests(reports: Sequence[Path], controls: Mapping[str, Sequence[str]]) -> dict[str, Any]:
    """Reconcile declared checks against actual JUnit consumers; names do not prove semantics."""
    if set(controls)!={f"T{i:02d}" for i in range(1,25)} or any(not checks for checks in controls.values()):
        raise ValueError("Exact T01–T24 declared checks required")
    observed: dict[str,list[tuple[str,str]]] = {}
    for path in reports:
        if path.stat().st_size>16*1024*1024:
            raise ValueError("Bounded JUnit artifact required")
        root = ET.fromstring(path.read_text(encoding="utf-8"))
        for case in root.iter("testcase"):
            name = case.get("classname","").split("tests.")[-1]+"."+case.get("name","")
            status = ("FAIL" if case.find("failure") is not None or case.find("error") is not None else
                      "SKIP" if case.find("skipped") is not None else "PASS")
            observed.setdefault(name,[]).append((status,str(path)))
    result = {}
    for identifier,checks in controls.items():
        entries: list[dict[str, Any]] = []
        for check in checks:
            matching = {node:events for node,events in observed.items() if node.split("[")[0]==check}
            if not matching:
                entries.append({"check":check,"state":"NOT_RUN","observations":[]})
            for node,events in matching.items():
                statuses = {status for status,_ in events}
                state = "FAIL" if "FAIL" in statuses else "PASS" if "PASS" in statuses else "SKIP"
                entries.append({"check":node,"state":state,"observations":events})
        result[identifier] = {"state":"PASS" if all(e["state"]=="PASS" for e in entries) else
            "FAIL" if any(e["state"]=="FAIL" for e in entries) else "PARTIAL","checks":entries}
    return {"cases":result,"all_declared_checks_pass":all(row["state"]=="PASS" for row in result.values()),
            "semantic_certification":False,"input_reports":[str(p) for p in reports]}
