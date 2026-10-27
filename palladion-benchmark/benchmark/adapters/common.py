"""The harness shared by the Track A arms (B04-T01.03, BADR-0025).

Every arm reads the published namespace and nothing else, cuts documents into the same chunks, counts evidence in the
same units, applies the same access filter and the same budget. Differences between arms are then differences in
ranking, not in parsing, access control or truncation.

* ``PublishedView`` loads and verifies the published namespace. It refuses a directory that holds annotation or
  generator material, so an arm cannot be built from the snapshot root.
* ``chunk_document`` tiles a document: consecutive chunks cover every character, a chunk holds whole lines unless one
  line exceeds the limit, and each chunk lists the clauses whose lines it holds.
* ``count_words`` is the counted-token unit (whitespace words); characters are reported beside it.
* ``AccessFilter`` is the neutral wrapper of protocol 3.2 (condition C2); condition C1 switches it off.
* ``enforce_budget`` truncates a ranked bundle to a word budget and says what it cut.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from benchmark.contracts import EvidenceCandidate
from benchmark.eval.normalize import clause_spans
from benchmark.fixtures.manifest import IdentityManifest, ManifestRecord, read_identity, read_records, verify_published

DEFAULT_CHUNK_WORDS = 120
FORBIDDEN_SIBLINGS = ("annotations", "generator")
PROVENANCE = "harness_attributed"


class AdapterError(ValueError):
    """An arm was set up or used in a way that would break the shared conditions. The message never holds secrets."""


class Condition(StrEnum):
    """Metadata condition of protocol 3.2: C1 text only (no access filter), C2 evidence governed (neutral filter)."""

    C1 = "C1"
    C2 = "C2"


def count_words(text: str) -> int:
    """The counted-token unit: whitespace-separated words."""
    return len(text.split())


@dataclass(frozen=True)
class Chunk:
    """A contiguous slice of one published document, with the clauses whose lines it holds."""

    chunk_id: str
    doc_id: str
    start: int
    end: int
    text: str
    clauses: tuple[str, ...]

    @property
    def words(self) -> int:
        return count_words(self.text)

    @property
    def characters(self) -> int:
        return len(self.text)


@dataclass(frozen=True)
class Document:
    record: ManifestRecord
    text: str


class PublishedView:
    """The published namespace as an arm may see it: manifest records, texts and the identity manifest."""

    def __init__(
        self, root: Path, records: Sequence[ManifestRecord], identity: IdentityManifest, texts: Mapping[str, str]
    ):
        self.root = root
        self.records = tuple(records)
        self.identity = identity
        self._texts = dict(texts)

    @classmethod
    def load(cls, published: Path) -> PublishedView:
        if not (published / "corpus_manifest.jsonl").is_file():
            raise AdapterError("an arm is built from a published directory that holds corpus_manifest.jsonl")
        held = sorted(p.name for p in published.iterdir() if p.name.startswith(FORBIDDEN_SIBLINGS))
        if held:
            raise AdapterError("the directory handed to an arm holds annotation or generator material")
        problems = verify_published(published)
        if problems:
            raise AdapterError(f"the published directory does not match its manifest: {problems[:3]}")
        records = read_records(published)
        texts = {r.doc_id: (published / r.path).read_text(encoding="utf-8") for r in records}
        return cls(published, records, read_identity(published), texts)

    def document(self, doc_id: str) -> Document:
        record = next((r for r in self.records if r.doc_id == doc_id), None)
        if record is None:
            raise AdapterError(f"unknown document {doc_id}")
        return Document(record, self._texts[doc_id])

    def documents(self) -> list[Document]:
        return [Document(r, self._texts[r.doc_id]) for r in self.records]

    def with_document(self, record: ManifestRecord, text: str) -> PublishedView:
        """A new view that also holds one more document; this view, and any arm built on it, is unchanged."""
        if any(r.doc_id == record.doc_id for r in self.records):
            raise AdapterError(f"{record.doc_id} is already in the view")
        return PublishedView(self.root, (*self.records, record), self.identity, {**self._texts, record.doc_id: text})


def chunk_document(doc_id: str, text: str, max_words: int = DEFAULT_CHUNK_WORDS) -> list[Chunk]:
    """Tile ``text`` into chunks that start where the previous one ended and end at the document's end.

    Lines are kept whole when they fit; a line longer than ``max_words`` is cut at word boundaries. A clause is listed
    for every chunk that holds any part of its line.
    """
    if max_words < 1:
        raise AdapterError("a chunk holds at least one word")
    if not text:
        return []
    spans = clause_spans(text)
    pieces: list[tuple[int, int]] = []  # (start, end) of lines including their newline
    position = 0
    for line in text.splitlines(keepends=True):
        pieces.append((position, position + len(line)))
        position += len(line)
    units: list[tuple[int, int]] = []
    for start, end in pieces:
        words = list(_word_spans(text, start, end))
        if len(words) <= max_words:
            units.append((start, end))
            continue
        cut = start
        for index in range(max_words, len(words), max_words):
            boundary = words[index][0]
            units.append((cut, boundary))
            cut = boundary
        units.append((cut, end))
    chunks: list[Chunk] = []
    chunk_start = units[0][0]
    chunk_end = chunk_start
    held_words = 0
    for start, end in units:
        unit_words = count_words(text[start:end])
        if held_words and held_words + unit_words > max_words:
            chunks.append(_make_chunk(doc_id, text, chunk_start, chunk_end, spans))
            chunk_start, held_words = start, 0
        chunk_end = end
        held_words += unit_words
    chunks.append(_make_chunk(doc_id, text, chunk_start, chunk_end, spans))
    return chunks


def _word_spans(text: str, start: int, end: int) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    position = start
    for word in text[start:end].split():
        found = text.index(word, position)
        spans.append((found, found + len(word)))
        position = found + len(word)
    return spans


def _make_chunk(doc_id: str, text: str, start: int, end: int, spans: Mapping[str, tuple[int, int]]) -> Chunk:
    clauses = tuple(c for c, (c_start, c_end) in spans.items() if c_start < end and c_end > start)
    return Chunk(f"{doc_id}#{start}-{end}", doc_id, start, end, text[start:end], clauses)


def build_chunks(view: PublishedView, max_words: int = DEFAULT_CHUNK_WORDS) -> list[Chunk]:
    chunks: list[Chunk] = []
    for document in view.documents():
        chunks.extend(chunk_document(document.record.doc_id, document.text, max_words))
    return chunks


class AccessFilter:
    """The neutral wrapper: a principal sees a document when its tenant and role pass the manifest's lists.

    An empty list means unrestricted on that axis. With ``Condition.C1`` the filter passes everything, which is the
    text-only condition; the choice is recorded with every run.
    """

    def __init__(self, view: PublishedView, condition: Condition = Condition.C2) -> None:
        self.condition = condition
        self._principals = {p.principal_id: p for p in view.identity.principals}
        self._acl = {r.doc_id: (r.acl_tenants, r.acl_roles) for r in view.records}

    def allows(self, principal_id: str, doc_id: str) -> bool:
        if self.condition is Condition.C1:
            return True
        principal = self._principals.get(principal_id)
        if principal is None:
            raise AdapterError(f"principal {principal_id} is not in the identity manifest")
        tenants, roles = self._acl[doc_id]
        return (not tenants or principal.tenant_id in tenants) and (not roles or principal.role_id in roles)

    def visible_documents(self, principal_id: str) -> frozenset[str]:
        return frozenset(d for d in self._acl if self.allows(principal_id, d))


def candidate_from_chunk(
    chunk: Chunk, record: ManifestRecord, rank: int, score: float | None, channel: str
) -> EvidenceCandidate:
    """A candidate carrying harness-attributed provenance: the published document, its hash and the exact place."""
    locator = f"clause:{chunk.clauses[0]}" if len(chunk.clauses) == 1 else f"chars:{chunk.start}-{chunk.end}"
    return EvidenceCandidate(
        source_version_id=record.version_id,
        locator=locator,
        content=chunk.text,
        rank=rank,
        native_score=score,
        retrieval_channel=channel,
        evidence_path=(),
        native_citation_supported=False,
        additional_metadata={"provenance": PROVENANCE, "chunk_id": chunk.chunk_id, "words": chunk.words},
        source_document_id=record.doc_id,
        source_sha256=record.sha256,
    )


@dataclass(frozen=True)
class BudgetResult:
    kept: tuple[EvidenceCandidate, ...]
    words: int
    dropped: int
    cut_words: int  # words removed from a candidate that alone exceeded the budget

    @property
    def truncated(self) -> bool:
        return self.dropped > 0 or self.cut_words > 0


def enforce_budget(candidates: Sequence[EvidenceCandidate], max_words: int) -> BudgetResult:
    """Keep ranked candidates while their words fit the budget; cut the first one if it alone is too long.

    Candidates keep their rank order and ranks are renumbered 1..n so the runner's contract holds. A candidate that was
    cut says so in its metadata.
    """
    if max_words < 1:
        raise AdapterError("a budget holds at least one word")
    kept: list[EvidenceCandidate] = []
    used = cut = 0
    for candidate in candidates:
        words = count_words(candidate.content)
        if used + words <= max_words:
            kept.append(candidate)
            used += words
            continue
        if not kept:
            shortened = " ".join(candidate.content.split()[:max_words])
            meta = {**candidate.additional_metadata, "truncated_from_words": words}
            kept.append(_replace(candidate, content=shortened, additional_metadata=meta))
            used, cut = max_words, words - max_words
        break
    dropped = len(candidates) - len(kept)
    if dropped and kept:
        meta = {**kept[-1].additional_metadata, "budget_dropped": dropped}
        kept[-1] = _replace(kept[-1], additional_metadata=meta)
    renumbered = tuple(_replace(c, rank=i) for i, c in enumerate(kept, start=1))
    return BudgetResult(renumbered, used, dropped, cut)


def _replace(candidate: EvidenceCandidate, **changes: object) -> EvidenceCandidate:
    data = {**candidate.to_dict(), **changes}
    return EvidenceCandidate.from_dict(data)


def flags_from_notes(notes: Mapping[str, Any]) -> tuple[str, ...]:
    """Short ledger flags for what an arm did to its latest result: truncation, filtering, exact keys, warnings."""
    flags: list[str] = []
    if notes.get("truncated"):
        flags.append("BUDGET_TRUNCATED")
    if notes.get("dropped"):
        flags.append(f"BUDGET_DROPPED={notes['dropped']}")
    if notes.get("cut_words"):
        flags.append(f"BUDGET_CUT={notes['cut_words']}")
    if notes.get("filtered_after_ranking"):
        flags.append(f"FILTERED_AFTER_RANKING={notes['filtered_after_ranking']}")
    if notes.get("acl_leaked"):
        flags.append(f"ACL_LEAKED={notes['acl_leaked']}")
    if notes.get("foreign_dropped"):
        flags.append(f"FOREIGN_DROPPED={notes['foreign_dropped']}")
    if notes.get("exact_key_chunks"):
        flags.append(f"EXACT_KEY_CHUNKS={len(notes['exact_key_chunks'])}")
    flags += [f"PALLADION_WARNING={w}"[:80] for w in notes.get("palladion_warnings", ())]
    return tuple(flags)
