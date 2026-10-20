"""Builders shared by the metric tests: candidates that quote or cite gold clauses of the real S-tier fixture."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence

from benchmark.contracts import CaseResponse, Claim, EvidenceCandidate, RunStatus
from benchmark.eval.answer_case import AnswerCase
from benchmark.eval.normalize import PublishedCorpus
from benchmark.fixtures.answer_gold import AnswerGold
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


class HashingEncoder:
    """A deterministic stand-in embedding: hashed bag of words, unit length. For tests of the index, not of quality."""

    dimension = 384
    fingerprint = "hashing-encoder-test-only"

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for word in re.findall(r"[^\W_]+", text.casefold()):
            vector[int.from_bytes(hashlib.sha256(word.encode()).digest()[:4], "big") % self.dimension] += 1.0
        norm = math.sqrt(sum(x * x for x in vector)) or 1.0
        return [x / norm for x in vector]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


# --------------------------------------------------------------------------- answers (B05)


def citation_text(citation: Citation) -> str:
    return citation.doc_id if citation.clause_id == "doc" else f"{citation.doc_id}#{citation.clause_id}"


def gold_delivered(record: GoldRecord) -> frozenset[tuple[str, str]]:
    """Every unit the gold names, plus each document's whole-document unit: what a perfect retriever delivers."""
    return frozenset(
        {c.key for c in record.citation_gold_spans} | {(c.doc_id, "doc") for c in record.citation_gold_spans}
    )


def perfect_response(record: GoldRecord, gold: AnswerGold, **overrides: object) -> CaseResponse:
    """The answer the gold asks for: its claims, citing the gold spans, its action, outcome and versions."""
    cites = tuple(citation_text(c) for c in record.citation_gold_spans if not c.doc_id.startswith(LIVE_PREFIX))
    claims = tuple(
        Claim(f"c{i}", f"{u.kind.value} {dict(u.params)}", cites, kind=u.kind.value, params=dict(u.params))
        for i, u in enumerate(gold.units, start=1)
    )
    fields: dict[str, object] = {
        "question_id": record.question_id,
        "run_id": "run-test",
        "answer_text": "see claims",
        "evidence_status": record.allowed_statuses[0],
        "claims": claims,
        "used_evidence_ids": cites,
        "tool_calls": (),
        "critic": None,
        "model_invocations": None,
        "latency_ms": None,
        "cost_usd": None,
        "abstention_reason": record.missing_reasons[0] if record.missing_reasons else None,
        "action": gold.action.value,
        "policy_outcome": gold.policy_outcome,
        "version_ids": gold.version_ids,
    }
    return CaseResponse(**{**fields, **overrides})  # type: ignore[arg-type]


def make_case(
    record: GoldRecord,
    gold: AnswerGold,
    response: CaseResponse | None,
    *,
    delivered: frozenset[tuple[str, str]] | None = None,
    role_id: str = "support_l2",
    status: RunStatus = RunStatus.OK,
) -> AnswerCase:
    return AnswerCase(
        record, gold, status, response, gold_delivered(record) if delivered is None else delivered, role_id
    )
