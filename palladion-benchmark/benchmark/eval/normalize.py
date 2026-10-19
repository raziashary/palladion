"""Map returned evidence candidates onto published documents and clauses (B03-T01.01, BADR-0024).

Two kinds of credit are kept apart. *Identity* comes from the candidate's own provenance: a published document id and a
locator that resolves inside that document. *Alignment* comes from matching the candidate's text against the corpus,
computed for every candidate whatever it claims. Headline metrics use identity only, so a stale copy or an unapproved
memo that quotes an authoritative clause earns alignment credit and no identity credit (protocol 7.1, 8.2). A third
view, ``exposed_docs``, lists every document whose text the candidate reproduces in part; leakage uses it.

Locator grammar: ``clause:<n.n>`` (a numbered clause), ``chars:<start>-<end>`` (offsets in the text) or ``doc``
(the document, no clause named: the clauses credited are the ones its text reproduces). Text is folded (NFC,
case-folded, whitespace collapsed) before alignment. A span matches a clause when it lies inside it, contains it, or has
at least ``OVERLAP_THRESHOLD`` of its own length inside it. Text matches a clause when at least that share of the
candidate's 3-word shingles occur in the clause, or that share of the clause's shingles occur in the candidate (a chunk
holding two clauses credits both). A claimed ``live:`` id is not a document and is treated as no claim.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from benchmark.contracts import EvidenceCandidate
from benchmark.fixtures.manifest import ManifestRecord, read_records
from benchmark.fixtures.questions import LIVE_PREFIX

OVERLAP_THRESHOLD = 0.8
EXPOSURE_SHARE = 0.3  # a candidate reproducing this share of a document's phrases is treated as showing it
SHINGLE_WORDS = 3
DOC_UNIT = "doc"
_CLAUSE_LINE = re.compile(r"^(\d+\.\d+) ", re.MULTILINE)
_LOCATOR = re.compile(r"^(?:clause:(?P<clause>\d+\.\d+)|chars:(?P<start>\d+)-(?P<end>\d+)|(?P<doc>doc))$")


def fold(text: str) -> str:
    """NFC, case-folded, whitespace collapsed: the form text is compared in."""
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def shingles(text: str) -> frozenset[str]:
    words = fold(text).split()
    return frozenset(" ".join(words[i : i + SHINGLE_WORDS]) for i in range(max(0, len(words) - SHINGLE_WORDS + 1)))


def clause_spans(text: str) -> dict[str, tuple[int, int]]:
    """Character span of each numbered clause line in a published document."""
    spans: dict[str, tuple[int, int]] = {}
    for found in _CLAUSE_LINE.finditer(text):
        end = text.find("\n", found.start())
        if found.group(1) in spans:
            raise ValueError(f"clause {found.group(1)} occurs twice in one document")
        spans[found.group(1)] = (found.start(), len(text) if end < 0 else end)
    return spans


@dataclass(frozen=True)
class PublishedDoc:
    record: ManifestRecord
    text: str
    clauses: Mapping[str, tuple[int, int]]


class PublishedCorpus:
    """The published namespace as a scorer sees it: manifest records, document text, clause spans, a shingle index."""

    def __init__(self, docs: Mapping[str, PublishedDoc]) -> None:
        self.docs = dict(docs)
        self._index: dict[str, set[str]] | None = None

    @classmethod
    def load(cls, published: Path) -> PublishedCorpus:
        docs: dict[str, PublishedDoc] = {}
        for record in read_records(published):
            text = (published / record.path).read_text(encoding="utf-8")
            docs[record.doc_id] = PublishedDoc(record, text, clause_spans(text))
        return cls(docs)

    @property
    def index(self) -> Mapping[str, set[str]]:
        if self._index is None:
            built: dict[str, set[str]] = defaultdict(set)
            for doc_id, doc in self.docs.items():
                for shingle in shingles(doc.text):
                    built[shingle].add(doc_id)
            self._index = dict(built)
        return self._index


class Match(StrEnum):
    IDENTITY = "identity"
    ALIGNMENT = "alignment"
    NONE = "none"


@dataclass(frozen=True)
class Locator:
    kind: str  # clause, chars or doc
    clause: str | None = None
    span: tuple[int, int] | None = None


def parse_locator(locator: str | None) -> Locator | None:
    """The locator in grammar form, ``doc`` when absent, or ``None`` when it is not in the grammar."""
    if locator is None:
        return Locator("doc")
    found = _LOCATOR.match(locator.strip())
    if found is None:
        return None
    if found.group("clause"):
        return Locator("clause", clause=found.group("clause"))
    if found.group("start"):
        return Locator("chars", span=(int(found.group("start")), int(found.group("end"))))
    return Locator("doc")


@dataclass(frozen=True)
class Alignment:
    """How one candidate relates to the corpus.

    Identity (``match``, ``doc_id``, ``clauses``) comes from the candidate's own provenance. Text alignment
    (``text_doc_id``, ``text_clauses``) is computed for every candidate, whatever it claims, and is credited only in the
    separately reported alignment metrics. ``exposed_docs`` are all documents whose text the candidate reproduces in
    part, used to decide leakage.
    """

    rank: int
    match: Match
    doc_id: str | None
    clauses: frozenset[str] = field(default_factory=frozenset)
    overlap: float = 0.0
    claimed_provenance: bool = False
    locator_resolves: bool | None = None  # None when the candidate claimed no provenance
    native: bool = False
    text_doc_id: str | None = None
    text_clauses: frozenset[str] = field(default_factory=frozenset)
    exposed_docs: frozenset[str] = field(default_factory=frozenset)

    def units(self) -> frozenset[tuple[str, str]]:
        """Gold units credited by identity: the named clauses, and the whole-document unit of the document."""
        if self.doc_id is None or self.match is not Match.IDENTITY:
            return frozenset()
        return frozenset((self.doc_id, c) for c in self.clauses) | {(self.doc_id, DOC_UNIT)}

    def text_units(self) -> frozenset[tuple[str, str]]:
        """Gold units the candidate's text reproduces, whatever it claims to be."""
        if self.text_doc_id is None:
            return frozenset()
        return frozenset((self.text_doc_id, c) for c in self.text_clauses) | {(self.text_doc_id, DOC_UNIT)}


def _inside(candidate: tuple[int, int], clause: tuple[int, int]) -> bool:
    start, end = candidate
    c_start, c_end = clause
    length = max(1, end - start)
    shared = max(0, min(end, c_end) - max(start, c_start))
    contains = start <= c_start and end >= c_end
    return contains or (start >= c_start and end <= c_end) or shared / length >= OVERLAP_THRESHOLD


def _text_clauses(doc: PublishedDoc, wanted: frozenset[str]) -> frozenset[str]:
    """Clauses of ``doc`` the candidate text lies in, or that lie in the candidate text (a chunk of two clauses)."""
    credited: set[str] = set()
    for clause, (start, end) in doc.clauses.items():
        clause_grams = shingles(doc.text[start:end])
        if wanted & clause_grams and (
            len(wanted & clause_grams) / len(wanted) >= OVERLAP_THRESHOLD
            or (clause_grams and len(wanted & clause_grams) / len(clause_grams) >= OVERLAP_THRESHOLD)
        ):
            credited.add(clause)
    return frozenset(credited)


def _resolve(doc: PublishedDoc, locator: Locator, wanted: frozenset[str]) -> tuple[bool, frozenset[str]]:
    """Whether the locator points inside the document, and which clauses a candidate at that place credits.

    A ``doc`` locator names the document only; the clauses it credits are the ones its text reproduces.
    """
    if locator.kind == "doc":
        return True, _text_clauses(doc, wanted)
    if locator.kind == "clause":
        assert locator.clause is not None
        return (locator.clause in doc.clauses), frozenset({locator.clause} & set(doc.clauses))
    assert locator.span is not None
    start, end = locator.span
    if not 0 <= start < end <= len(doc.text):
        return False, frozenset()
    return True, frozenset(c for c, span in doc.clauses.items() if _inside((start, end), span))


def _text_shares(wanted: frozenset[str], corpus: PublishedCorpus) -> dict[str, float]:
    """Share of the candidate's shingles that occur in each document."""
    votes: dict[str, int] = defaultdict(int)
    for shingle in wanted:
        for doc_id in corpus.index.get(shingle, ()):
            votes[doc_id] += 1
    return {doc_id: count / len(wanted) for doc_id, count in votes.items()} if wanted else {}


def align(candidate: EvidenceCandidate, corpus: PublishedCorpus) -> Alignment:
    """Identity from provenance when it resolves, text alignment alongside it, and the documents it leaks."""
    wanted = shingles(candidate.content)
    shares = _text_shares(wanted, corpus)
    best = max(sorted(shares), key=lambda d: shares[d]) if shares else None
    text_doc = best if best is not None and shares[best] >= OVERLAP_THRESHOLD else None
    text_clauses = _text_clauses(corpus.docs[text_doc], wanted) if text_doc is not None else frozenset()
    exposed = frozenset(d for d, share in shares.items() if share >= EXPOSURE_SHARE)
    claimed = candidate.source_document_id or candidate.source_version_id
    if claimed is not None and claimed.startswith(LIVE_PREFIX):
        claimed = None  # a live read is not a document; Track A has nothing to resolve it against
    doc = corpus.docs.get(claimed) if claimed else None
    resolves: bool | None = None
    if claimed is not None:
        locator = parse_locator(candidate.locator)
        hash_ok = candidate.source_sha256 is None or (doc is not None and candidate.source_sha256 == doc.record.sha256)
        if doc is not None and locator is not None and hash_ok:
            resolves, clauses = _resolve(doc, locator, wanted)
            if resolves:
                return Alignment(
                    candidate.rank, Match.IDENTITY, claimed, clauses, 1.0, True, True,
                    candidate.native_citation_supported, text_doc, text_clauses, exposed | {claimed},
                )  # fmt: skip
        resolves = False
    overlap = shares[best] if best is not None else 0.0
    if text_doc is None:
        return Alignment(
            candidate.rank, Match.NONE, None, frozenset(), overlap, claimed is not None, resolves,
            False, None, frozenset(), exposed,
        )  # fmt: skip
    return Alignment(
        candidate.rank, Match.ALIGNMENT, text_doc, text_clauses, overlap, claimed is not None, resolves,
        False, text_doc, text_clauses, exposed,
    )  # fmt: skip


def align_all(candidates: list[EvidenceCandidate], corpus: PublishedCorpus) -> list[Alignment]:
    return [align(c, corpus) for c in candidates]


def read_candidates(payload: object) -> list[EvidenceCandidate]:
    """Candidates from a ledger payload (the list of dicts a retrieval arm returned)."""
    if not isinstance(payload, list):
        return []
    return [EvidenceCandidate.from_dict(item) for item in payload]
