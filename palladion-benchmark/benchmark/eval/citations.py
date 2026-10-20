"""Citation metrics for one answer (B05-T01.01, protocol 9.2, BADR-0028).

A citation is a string ``<document>[#<clause>]`` (for example ``POL-015@v2#4.1``) or a ``live:`` read. Each one is
checked against the published registry and against what the generator was shown, never against the answer's own words:

* ``VALID`` the document and clause exist and the unit was delivered; ``FABRICATED`` the document or clause does not
  exist or the string is not in the grammar; ``OUTSIDE_BUNDLE`` it exists but the generator was not shown it.
* accessibility (the principal may read it), authority (an approved or retired version can govern; drafts, proposals,
  withdrawn and non-normative documents cannot), temporal applicability (the cited version is the gold's applicable one
  where the question has one), granularity (a clause, not a whole document) and gold support (the cited unit is one the
  gold names) are reported per pair.

Entailment needs labels: a label store may be passed in, pairs without a label are counted, never scored. Stability
needs two index generations and is not run in B05. Precision and recall always come with their denominators; claims
that cite nothing are counted apart from claims that cite wrongly, and a false uncited claim is counted by the claim
scorer, so it cannot vanish by never being cited.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeAlias

from benchmark.eval.answer_case import AnswerCase
from benchmark.eval.evidence_sets import Unit, citable_slots
from benchmark.eval.normalize import DOC_UNIT, PublishedCorpus
from benchmark.fixtures.answer_gold import ClaimKind
from benchmark.fixtures.questions import LIVE_PREFIX, derive_minimal_sets

CITATION = re.compile(r"(?P<doc>[A-Za-z0-9][A-Za-z0-9_.:@-]*)(?:#(?P<clause>\d+\.\d+))?")
AUTHORITATIVE_STATES = frozenset({"approved", "retired"})
# Claims that rest on no document: a missing input and a live read. Every other claim needs a source.
UNSOURCED_KINDS = frozenset({ClaimKind.INPUT_REQUIRED.value, ClaimKind.LIVE_STATE.value})
LabelKey: TypeAlias = tuple[str, str, str, str]  # (question id, arm, claim id, citation)
Labels = Mapping[LabelKey, bool]  # the cited span supports the claim


class CitationStatus(StrEnum):
    VALID = "VALID"
    FABRICATED = "FABRICATED"
    OUTSIDE_BUNDLE = "OUTSIDE_BUNDLE"
    LIVE = "LIVE"


@dataclass(frozen=True)
class CitationCheck:
    claim_id: str
    citation: str
    status: CitationStatus
    unit: Unit | None
    accessible: bool | None
    authoritative: bool | None
    applicable: bool | None  # None when the question has no applicable-version gold or the document is not a version
    clause_level: bool
    gold_supported: bool | None

    @property
    def sound(self) -> bool:
        """Valid, readable by the principal and able to govern: a citation a claim can rest on.

        A document that cannot govern (a proposal, a draft) still counts when the gold itself names it, as it does to
        show that a memo is only a proposal.
        """
        return (
            self.status is CitationStatus.VALID
            and self.accessible is True
            and (self.authoritative is True or self.gold_supported is True)
        )


@dataclass(frozen=True)
class CitationScore:
    question_id: str
    checks: tuple[CitationCheck, ...]
    unsupported_ids: tuple[str, ...]  # source-requiring claims with no sound citation
    claims: int
    uncited_claims: int
    source_requiring_claims: int
    supported_claims: int  # source-requiring claims with at least one sound citation
    precision: float | None  # gold-supported share of valid citations
    recall: float | None  # supported_claims / source_requiring_claims
    granularity: float | None  # clause-level share of valid citations
    diversity: float | None  # gold documents cited / gold documents
    set_complete: bool | None  # some minimal evidence set is wholly cited
    entailed: int
    not_entailed: int
    unlabelled: int

    def count(self, status: CitationStatus) -> int:
        return sum(1 for c in self.checks if c.status is status)

    @property
    def fabricated(self) -> int:
        return self.count(CitationStatus.FABRICATED) + self.count(CitationStatus.OUTSIDE_BUNDLE)

    @property
    def inaccessible(self) -> int:
        return sum(1 for c in self.checks if c.accessible is False)

    @property
    def unauthoritative(self) -> int:
        """Citations to something that cannot govern and that the gold does not name."""
        return sum(1 for c in self.checks if c.authoritative is False and c.gold_supported is not True)

    @property
    def inapplicable(self) -> int:
        return sum(1 for c in self.checks if c.applicable is False)


def _gold_units(case: AnswerCase) -> set[Unit]:
    return {c.key for c in case.record.citation_gold_spans}


def _visible(corpus: PublishedCorpus, doc_id: str, tenant_id: str, role_id: str) -> bool:
    record = corpus.docs[doc_id].record
    return (not record.acl_tenants or tenant_id in record.acl_tenants) and (
        not record.acl_roles or role_id in record.acl_roles
    )


def _applicable(case: AnswerCase, corpus: PublishedCorpus, doc_id: str) -> bool | None:
    """Whether a cited version is the one the gold names, for a document that is a version of a gold family."""
    applicable = case.record.gold_applicable_version_ids
    if not applicable or case.record.history_allowed:
        return None
    families = {corpus.docs[v].record.family_id for v in applicable if v in corpus.docs} - {None}
    if corpus.docs[doc_id].record.family_id not in families:
        return None
    return doc_id in applicable


def check_citation(
    case: AnswerCase, corpus: PublishedCorpus, claim_id: str, citation: str, gold_units: set[Unit]
) -> CitationCheck:
    if citation.startswith(LIVE_PREFIX):
        return CitationCheck(claim_id, citation, CitationStatus.LIVE, None, None, None, None, False, None)
    found = CITATION.fullmatch(citation)
    doc_id = found.group("doc") if found else None
    clause = found.group("clause") if found else None
    doc = corpus.docs.get(doc_id) if doc_id else None
    if found is None or doc is None or doc_id is None or (clause is not None and clause not in doc.clauses):
        return CitationCheck(claim_id, citation, CitationStatus.FABRICATED, None, None, None, None, False, None)
    unit: Unit = (doc_id, clause or DOC_UNIT)
    shown = unit in case.delivered or (clause is None and any(d == doc_id for d, _ in case.delivered))
    status = CitationStatus.VALID if shown else CitationStatus.OUTSIDE_BUNDLE
    return CitationCheck(
        claim_id,
        citation,
        status,
        unit,
        _visible(corpus, doc_id, case.record.tenant_id, case.role_id)
        and doc_id not in case.record.inaccessible_sources,
        doc.record.registry_state in AUTHORITATIVE_STATES,
        _applicable(case, corpus, doc_id),
        clause is not None,
        unit in gold_units or (clause is None and any(d == doc_id for d, _ in gold_units)),
    )


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def score_citations(case: AnswerCase, corpus: PublishedCorpus, labels: Labels | None = None) -> CitationScore:
    """Citation metrics for a completed answer. A pair that did not complete has no citations and no score."""
    if not case.completed or case.response is None:
        raise ValueError("a citation score needs a completed answer")
    gold_units = _gold_units(case)
    checks: list[CitationCheck] = []
    uncited = needing = supported = 0
    unsupported: list[str] = []
    for claim in case.response.claims:
        mine = [check_citation(case, corpus, claim.id, c, gold_units) for c in claim.citations]
        checks.extend(mine)
        if not claim.citations:
            uncited += 1
        if claim.kind in UNSOURCED_KINDS:
            continue
        needing += 1
        sound = any(check.sound for check in mine)
        supported += sound
        if not sound:
            unsupported.append(claim.id)
    valid = [c for c in checks if c.status is CitationStatus.VALID]
    cited_units = {c.unit for c in valid if c.unit is not None}
    gold_docs = {doc for doc, _ in gold_units}
    cited_docs = {doc for doc, _ in cited_units}
    slots = citable_slots(case.record)
    complete: bool | None = None
    if slots:
        complete = any(all(c.key in cited_units for c in group) for group in derive_minimal_sets(slots))
    labelled = [
        (case.record.question_id, case.arm, c.claim_id, c.citation) for c in checks if c.status is CitationStatus.VALID
    ]
    verdicts = [labels[key] for key in labelled if labels is not None and key in labels]
    return CitationScore(
        question_id=case.record.question_id,
        checks=tuple(checks),
        unsupported_ids=tuple(unsupported),
        claims=len(case.response.claims),
        uncited_claims=uncited,
        source_requiring_claims=needing,
        supported_claims=supported,
        precision=_ratio(sum(1 for c in valid if c.gold_supported), len(valid)),
        recall=_ratio(supported, needing),
        granularity=_ratio(sum(1 for c in valid if c.clause_level), len(valid)),
        diversity=_ratio(len(cited_docs & gold_docs), len(gold_docs)),
        set_complete=complete,
        entailed=sum(1 for v in verdicts if v),
        not_entailed=sum(1 for v in verdicts if not v),
        unlabelled=len(labelled) - len(verdicts),
    )
