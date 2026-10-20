"""Graph-specific metrics that the data supports, and the ones it does not (B06-T05.01, protocol 8.3 and 8.4).

Defined here, each with a perfect, an empty and a shuffled control in the tests:

- **hop completion**: for a question whose required evidence sits in two or more documents, the share of its slots a
  ranked list covers and whether it covers a complete set. Not applicable to a one-document question.
- **edge provenance validity**: the share of returned relations whose every cited source exists in the published corpus.
- **false-association rate**: the share of returned relations whose cited text does not mention both of its endpoints
  (or that cite nothing). A relation that asserts a link its own evidence does not make is an unsupported edge.
- **traversal cost per useful slot**: model calls and tokens spent at query time per gold slot the list covered.

Not defined, and printed as undefined with the missing data named, never estimated: relationship precision and recall,
typed-traversal correctness, wrong-node merge rate and hub pollution. A rate over no relations is ``None``: an arm that
returns no edges has no false-association rate, not a perfect one.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from benchmark.contracts import EvidenceCandidate
from benchmark.eval.citations import CITATION
from benchmark.eval.evidence_sets import SetScores, citable_slots, score_sets
from benchmark.eval.normalize import Alignment, PublishedCorpus, fold
from benchmark.fixtures.questions import GoldRecord

MIN_HOP_DOCUMENTS = 2


@dataclass(frozen=True)
class Undefined:
    """A metric the benchmark cannot compute, with the reason; it prints as undefined and is never a number."""

    metric: str
    reason: str


UNDEFINED_METRICS = (
    Undefined(
        "relationship_precision_recall",
        "the gold has no relation list per question in the arms' vocabularies; matching free-text relations to the "
        "world's typed edges needs an entity resolver that does not exist",
    ),
    Undefined(
        "typed_traversal_correctness",
        "only an arm that traverses the world's own typed edges could be scored, and no such arm runs (R7b is "
        "unsupported at the pin, BR34)",
    ),
    Undefined(
        "wrong_node_merge_rate",
        "the gold has no entity identity per mention (BADR-0024 dropped entity error), so a merge cannot be judged",
    ),
    Undefined(
        "hub_pollution",
        "no arm reports node degrees through the adapter contract, so a hub cannot be identified",
    ),
)


# --------------------------------------------------------------------------- hop completion


def is_multi_document(record: GoldRecord) -> bool:
    """True when the record's required evidence is spread over at least two documents."""
    docs = {alternative.doc_id for slot in citable_slots(record) for alternative in slot.alternatives}
    return len(docs) >= MIN_HOP_DOCUMENTS and len(citable_slots(record)) >= MIN_HOP_DOCUMENTS


@dataclass(frozen=True)
class HopCompletion:
    slots: int
    covered_fraction: float
    complete: bool


def hop_completion(record: GoldRecord, alignments: Sequence[Alignment], k: int) -> HopCompletion | None:
    """Hop completion of one question at K, or ``None`` when the question does not need two documents."""
    if not is_multi_document(record):
        return None
    scores: SetScores = score_sets(record, alignments, k)
    if scores.slot_coverage is None or scores.complete_set is None:
        return None
    return HopCompletion(scores.slots_total, scores.slot_coverage, scores.complete_set == 1.0)


# --------------------------------------------------------------------------- edges


@dataclass(frozen=True)
class EdgeScores:
    total: int
    resolved: int  # every cited source exists in the published corpus (and at least one is cited)
    grounded: int  # resolved, and the cited text mentions both endpoints

    @property
    def provenance_validity(self) -> float | None:
        return None if self.total == 0 else self.resolved / self.total

    @property
    def false_association_rate(self) -> float | None:
        return None if self.total == 0 else (self.total - self.grounded) / self.total


def edges_of(candidates: Iterable[EvidenceCandidate]) -> list[Mapping[str, object]]:
    """The typed edges the candidates carry; a plain passage carries none."""
    return [c.relation for c in candidates if c.relation is not None]


def _cited_text(corpus: PublishedCorpus, citation: str) -> str | None:
    found = CITATION.fullmatch(citation)
    doc = corpus.docs.get(found.group("doc")) if found else None
    if found is None or doc is None:
        return None
    clause = found.group("clause")
    if clause is None:
        return doc.text
    span = doc.clauses.get(clause)
    return None if span is None else doc.text[span[0] : span[1]]


def _mentions(body: str, name: str) -> bool:
    """Whether the folded name occurs in the folded text as whole words (an empty name is never grounded)."""
    needle = fold(name)
    return bool(needle) and re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", body) is not None


def score_edges(edges: Iterable[Mapping[str, object]], corpus: PublishedCorpus) -> EdgeScores:
    total = resolved = grounded = 0
    for edge in edges:
        total += 1
        ids = [str(i) for i in edge.get("supporting_ids", [])]  # type: ignore[attr-defined]
        texts = [_cited_text(corpus, i) for i in ids]
        if not ids or any(t is None for t in texts):
            continue
        resolved += 1
        body = fold(" ".join(t for t in texts if t is not None))
        if _mentions(body, str(edge["subject"])) and _mentions(body, str(edge["object"])):
            grounded += 1
    return EdgeScores(total, resolved, grounded)


# --------------------------------------------------------------------------- cost


@dataclass(frozen=True)
class TraversalCost:
    calls: float
    tokens: float
    useful_slots: float

    @property
    def calls_per_useful_slot(self) -> float | None:
        return None if self.useful_slots == 0 else self.calls / self.useful_slots

    @property
    def tokens_per_useful_slot(self) -> float | None:
        return None if self.useful_slots == 0 else self.tokens / self.useful_slots


def traversal_cost(per_question: Iterable[tuple[float, float, float]]) -> TraversalCost:
    """Sum (query-time model calls, query-time tokens, gold slots covered) over questions.

    No covered slot gives ``None`` for the ratios: a cost per nothing is not infinity and is not zero.
    """
    calls = tokens = useful = 0.0
    for c, t, u in per_question:
        if c < 0 or t < 0 or u < 0:
            raise ValueError("costs and covered slots cannot be negative")
        calls, tokens, useful = calls + c, tokens + t, useful + u
    return TraversalCost(calls, tokens, useful)
