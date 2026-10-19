"""Ranking and provenance-aware retrieval metrics (B03-T03.01 and B03-T03.02, protocol 8.1 and 8.3).

A candidate has gain 1 when it newly satisfies a required slot of the record and 0 otherwise (binary relevance,
duplicates earn nothing, BADR-0024). Every ranking metric is ``None`` when the record has no citable slot.
Provenance metrics read the published manifest for access and registry state, so a leak is decided by the corpus and
not by the arm's own claim.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from benchmark.contracts import EvidenceCandidate
from benchmark.eval.evidence_sets import citable_slots, covered_slots, matched_units, score_sets, slot_is_covered
from benchmark.eval.normalize import Alignment, Match, PublishedCorpus, fold, shingles
from benchmark.fixtures.questions import Answerability, GoldRecord

UNAUTHORITATIVE_STATES = frozenset({"draft", "unapproved_proposal", "withdrawn"})
NEAR_COPY = 0.75
RETRIEVAL_METRICS = (
    "precision_at_k", "recall_at_k", "mrr", "ndcg_at_k", "map_at_k", "success_at_k",
    "slot_coverage_at_k", "complete_set_at_k",
    "valid_source_recall", "wrong_vintage_intrusion", "forbidden_source_exposure", "authority_confusion",
    "exception_recall", "conflicting_pair_recall", "citation_locator_resolution",
    "evidence_density", "evidence_token_efficiency",
)  # fmt: skip


def slot_kind(name: str, kinds: Mapping[str, str]) -> str | None:
    """Protocol 6.1 kind of a generator slot name: an exact entry, or the name without its last ``_part``."""
    return kinds.get(name) or kinds.get(name.rsplit("_", 1)[0])


# --------------------------------------------------------------------------- ranking


@dataclass(frozen=True)
class RankingScores:
    returned: int
    precision: float | None
    recall: float | None
    mrr: float | None
    ndcg: float | None
    map: float | None
    success: float | None


def _credited(alignment: Alignment, include_alignment: bool) -> frozenset[tuple[str, str]]:
    return alignment.units() | alignment.text_units() if include_alignment else alignment.units()


def rank_gains(
    record: GoldRecord, alignments: Sequence[Alignment], k: int, *, include_alignment: bool = False
) -> list[int]:
    """Gain of each returned candidate in rank order: 1 if it satisfies a slot no earlier candidate satisfied."""
    slots = citable_slots(record)
    done: set[str] = set()
    gains: list[int] = []
    for alignment in sorted((a for a in alignments if a.rank <= k), key=lambda a: a.rank):
        units = _credited(alignment, include_alignment)
        fresh = {s.slot for s in slots if s.slot not in done and any(c.key in units for c in s.alternatives)}
        done |= fresh
        gains.append(1 if fresh else 0)
    return gains


def score_ranking(
    record: GoldRecord, alignments: Sequence[Alignment], k: int, *, include_alignment: bool = False
) -> RankingScores:
    slots = citable_slots(record)
    returned = sum(1 for a in alignments if a.rank <= k)
    if not slots:
        return RankingScores(returned, None, None, None, None, None, None)
    gains = rank_gains(record, alignments, k, include_alignment=include_alignment)
    hits = sum(gains)
    wanted = {c.key for s in slots for c in s.alternatives}
    relevant = sum(
        1 for a in alignments if a.rank <= k and _credited(a, include_alignment) & wanted
    )  # a repeat of a relevant chunk is still relevant; only the gain-based metrics treat it as redundant
    precision = relevant / returned if returned else 0.0
    recall = len(covered_slots(record, alignments, k, include_alignment=include_alignment)) / len(slots)
    first = next((i for i, g in enumerate(gains, start=1) if g), None)
    ideal = sum(1 / math.log2(i + 1) for i in range(1, min(len(slots), k) + 1))
    dcg = sum(g / math.log2(i + 1) for i, g in enumerate(gains, start=1))
    running = 0
    ap_sum = 0.0
    for i, g in enumerate(gains, start=1):
        running += g
        ap_sum += g * running / i
    return RankingScores(
        returned=returned,
        precision=precision,
        recall=recall,
        mrr=1 / first if first else 0.0,
        ndcg=dcg / ideal,
        map=ap_sum / min(len(slots), k),
        success=float(hits > 0),
    )


# --------------------------------------------------------------------------- provenance


@dataclass(frozen=True)
class ProvenanceScores:
    valid_source_recall: float | None
    wrong_vintage_count: int | None
    wrong_vintage_intrusion: float | None
    forbidden_exposure_count: int
    authority_confusion_count: int
    exception_recall: float | None
    conflicting_pair_recall: float | None
    citation_locator_resolution: float | None
    evidence_density: float | None
    evidence_token_efficiency: float | None
    words_returned: int


def _visible(corpus: PublishedCorpus, doc_id: str, tenant_id: str, role_id: str) -> bool:
    record = corpus.docs[doc_id].record
    return (not record.acl_tenants or tenant_id in record.acl_tenants) and (
        not record.acl_roles or role_id in record.acl_roles
    )


def _per_thousand_words(value: float, words: int) -> float:
    """Evidence per thousand words returned; returning nothing earns nothing and is not a missing value."""
    return value / (words / 1000) if words else 0.0


def _leaks(alignment: Alignment, record: GoldRecord, corpus: PublishedCorpus, role_id: str) -> bool:
    """A candidate leaks when it names a forbidden document, or reproduces part of forbidden text that no document the
    principal may see also contains (near-duplicates of authorised text are not leaks)."""

    def forbidden(doc_id: str) -> bool:
        return doc_id in record.inaccessible_sources or not _visible(corpus, doc_id, record.tenant_id, role_id)

    if alignment.match is Match.IDENTITY and alignment.doc_id is not None and forbidden(alignment.doc_id):
        return True
    reproduced = alignment.exposed_docs
    return any(forbidden(d) for d in reproduced) and all(forbidden(d) for d in reproduced)


def _distinct_words(candidates: Sequence[EvidenceCandidate]) -> int:
    """Whitespace words of the candidates after collapsing near-identical passages (protocol 8.4)."""
    kept: list[frozenset[str]] = []
    seen_short: set[str] = set()
    total = 0
    for candidate in candidates:
        grams = shingles(candidate.content)
        folded = fold(candidate.content)
        if not folded or folded in seen_short:
            continue
        if grams and any(len(grams & other) / len(grams) >= NEAR_COPY for other in kept):
            continue
        kept.append(grams)
        seen_short.add(folded)
        total += len(candidate.content.split())
    return total


def score_provenance(
    record: GoldRecord,
    candidates: Sequence[EvidenceCandidate],
    alignments: Sequence[Alignment],
    corpus: PublishedCorpus,
    *,
    role_id: str,
    kinds: Mapping[str, str],
    k: int,
) -> ProvenanceScores:
    top = [a for a in alignments if a.rank <= k]
    shown = [a for a in top if a.match is not Match.NONE and a.doc_id in corpus.docs]
    slots = citable_slots(record)
    units = matched_units(alignments, k)

    exposed = sum(1 for a in top if _leaks(a, record, corpus, role_id))
    required_docs = {c.doc_id for c in record.citation_gold_spans}
    confused = sum(
        1
        for a in shown
        if a.doc_id not in required_docs and corpus.docs[str(a.doc_id)].record.registry_state in UNAUTHORITATIVE_STATES
    )
    covered = [s for s in slots if slot_is_covered(s, units)]
    valid_recall = (
        sum(
            any(c.key in units and _visible(corpus, c.doc_id, record.tenant_id, role_id) for c in s.alternatives)
            for s in covered
        )
        / len(slots)
        if slots
        else None
    )
    families = {corpus.docs[v].record.family_id for v in record.gold_applicable_version_ids if v in corpus.docs} - {
        None
    }
    intrusions: int | None = None
    if families:
        intrusions = sum(
            1
            for a in shown
            if not record.history_allowed
            and corpus.docs[str(a.doc_id)].record.family_id in families
            and a.doc_id not in record.gold_applicable_version_ids
        )
    exception_slots = [s for s in slots if slot_kind(s.slot, kinds) == "exception"]
    sides = [s for s in slots if slot_kind(s.slot, kinds) == "conflict_side"]
    claimed = [a for a in top if a.claimed_provenance]
    sets = score_sets(record, alignments, k)
    words = sum(len(c.content.split()) for c in candidates if c.rank <= k)
    distinct = _distinct_words([c for c in candidates if c.rank <= k])
    return ProvenanceScores(
        valid_source_recall=valid_recall,
        wrong_vintage_count=intrusions,
        wrong_vintage_intrusion=None if intrusions is None else (intrusions / len(shown) if shown else 0.0),
        forbidden_exposure_count=exposed,
        authority_confusion_count=confused,
        exception_recall=(sum(slot_is_covered(s, units) for s in exception_slots) / len(exception_slots))
        if exception_slots
        else None,
        conflicting_pair_recall=(
            sum(slot_is_covered(s, units) for s in sides) / len(sides)
            if sides and record.answerability is Answerability.CONFLICT
            else None
        ),
        citation_locator_resolution=(sum(bool(a.locator_resolves) for a in claimed) / len(claimed))
        if claimed
        else None,
        evidence_density=_per_thousand_words(len(covered), distinct) if slots else None,
        evidence_token_efficiency=_per_thousand_words(sets.complete_set, words)
        if sets.complete_set is not None
        else None,
        words_returned=words,
    )
