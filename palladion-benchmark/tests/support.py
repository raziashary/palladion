"""Builders shared by the metric tests: candidates that quote or cite gold clauses of the real S-tier fixture."""

from __future__ import annotations

from collections.abc import Sequence

from benchmark.contracts import EvidenceCandidate
from benchmark.eval.normalize import PublishedCorpus
from benchmark.fixtures.questions import LIVE_PREFIX, Citation, GoldRecord, SlotState


def make_candidate(content: str, rank: int, **fields: object) -> EvidenceCandidate:
    base: dict[str, object] = {
        "source_version_id": None,
        "locator": None,
        "content": content,
        "rank": rank,
        "native_score": None,
        "retrieval_channel": "bm25",
        "evidence_path": (),
        "native_citation_supported": False,
        "additional_metadata": {},
    }
    return EvidenceCandidate(**{**base, **fields})  # type: ignore[arg-type]


def cited(corpus: PublishedCorpus, citation: Citation, rank: int) -> EvidenceCandidate:
    """A candidate that names the cited document and clause and carries that clause's published text."""
    doc = corpus.docs[citation.doc_id]
    if citation.clause_id == "doc":
        return make_candidate(doc.text, rank, source_document_id=citation.doc_id, locator="doc")
    start, end = doc.clauses[citation.clause_id]
    return make_candidate(
        doc.text[start:end], rank, source_document_id=citation.doc_id, locator=f"clause:{citation.clause_id}"
    )


def oracle(corpus: PublishedCorpus, record: GoldRecord, first: int = 1) -> list[EvidenceCandidate]:
    """One candidate per first alternative of each document slot, in slot order."""
    picks = [
        s.alternatives[0]
        for s in record.slots
        if s.state is SlotState.SATISFIABLE and not s.alternatives[0].doc_id.startswith(LIVE_PREFIX)
    ]
    return [cited(corpus, c, first + i) for i, c in enumerate(picks)]


def renumber(candidates: Sequence[EvidenceCandidate]) -> list[EvidenceCandidate]:
    return [make_candidate(**{**c.to_dict(), "rank": i}) for i, c in enumerate(candidates, start=1)]
