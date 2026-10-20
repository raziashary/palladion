"""One answer to be scored: the question, its answer-gold, what the generator was shown and what it said (B05).

The scorers of B05 (citations, claims, policy, abstention) all read this one record, so they cannot disagree about
what was delivered or whether the run completed. ``delivered`` holds the gold-addressable units (document, clause)
that the delivered evidence credits by identity, plus the whole-document unit of each document, exactly as Track A
credits retrieval; an answer may cite only what it was shown.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from benchmark.contracts import CaseResponse, EvidenceCandidate, RunStatus
from benchmark.eval.evidence_sets import Unit
from benchmark.eval.normalize import PublishedCorpus, align_all
from benchmark.fixtures.answer_gold import AnswerGold
from benchmark.fixtures.questions import GoldRecord


@dataclass(frozen=True)
class AnswerCase:
    record: GoldRecord
    gold: AnswerGold
    status: RunStatus
    response: CaseResponse | None  # present only when the run completed
    delivered: frozenset[Unit]
    role_id: str
    code: str | None = None
    arm: str = ""  # the arm whose answer this is; keys the labels so two arms' claims never share one

    @property
    def completed(self) -> bool:
        return self.status is RunStatus.OK and self.response is not None


def delivered_units(candidates: Sequence[EvidenceCandidate], corpus: PublishedCorpus) -> frozenset[Unit]:
    """The units the evidence shown to the generator credits by identity."""
    units: set[Unit] = set()
    for alignment in align_all(list(candidates), corpus):
        units |= alignment.units()
    return frozenset(units)
