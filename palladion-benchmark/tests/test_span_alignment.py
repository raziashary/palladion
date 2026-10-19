"""Chunk-to-span normalization, the gold reader and the new candidate fields (B03-T01.01)."""

from __future__ import annotations

from pathlib import Path

import pytest

from benchmark.contracts import ContractError, EvidenceCandidate
from benchmark.eval.normalize import (
    DOC_UNIT,
    OVERLAP_THRESHOLD,
    Alignment,
    Locator,
    Match,
    PublishedCorpus,
    PublishedDoc,
    align,
    clause_spans,
    fold,
    parse_locator,
    read_candidates,
    shingles,
)
from benchmark.fixtures import sha256_hex
from benchmark.fixtures.documents import Document
from benchmark.fixtures.manifest import ManifestRecord, Split, read_records, write_annotations
from benchmark.fixtures.questions import GoldError, GoldRecord, read_gold


def candidate(content: str, rank: int = 1, **fields: object) -> EvidenceCandidate:
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


def synthetic_corpus() -> PublishedCorpus:
    """Two documents with the same clause text: an authoritative policy and an unapproved memo that quotes it."""
    rule = "4.1 A request may be processed only if it is raised within seventy two hours of the transaction."
    other = "4.2 Amounts above five million rupiah must be escalated to level two before any decision is taken."
    text = f"> notice\n\n# Title\n\n- Document type: policy\n\n## 4 Requirements\n{rule}\n{other}\n"
    memo = f"> notice\n\n# Memo\n\n- Document type: memo\n\nPlease note: requests are taken within 72 hours.\n{other}\n"
    docs = {}
    for doc_id, body in (("POL-1@v1", text), ("ART-memo", memo)):
        record = ManifestRecord(
            doc_id,
            f"docs/{doc_id}.md",
            sha256_hex(body),
            doc_id,
            "policy",
            "approved",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            (),
            (),
            len(body.split()),
        )
        docs[doc_id] = PublishedDoc(record, body, clause_spans(body))
    return PublishedCorpus(docs)


RULE_TEXT = "A request may be processed only if it is raised within seventy two hours of the transaction."


# --------------------------------------------------------------------------- grammar and folding


@pytest.mark.parametrize(
    "text,expected",
    [
        ("clause:4.1", Locator("clause", clause="4.1")),
        ("chars:10-40", Locator("chars", span=(10, 40))),
        ("doc", Locator("doc")),
        (None, Locator("doc")),
    ],
)
def test_valid_locators_parse(text: str | None, expected: Locator) -> None:
    assert parse_locator(text) == expected


@pytest.mark.parametrize("text", ["4.1", "clause:4", "chars:10", "clause:4.1;drop", "page 3", ""])
def test_anything_outside_the_grammar_is_rejected(text: str) -> None:
    assert parse_locator(text) is None


def test_folding_removes_case_whitespace_and_unicode_form_differences() -> None:
    assert fold("  Café\n\tCLOSED ") == fold("café closed") == "café closed"
    assert shingles("a b") == frozenset()  # too short to carry a shingle
    assert len(shingles("one two three four")) == 2


def test_clause_spans_match_the_spans_the_generator_recorded(
    s_published_corpus: PublishedCorpus, s_corpus: tuple[Document, ...]
) -> None:
    checked = 0
    for doc in (d for d in s_corpus if d.authoritative):
        found = s_published_corpus.docs[doc.doc_id].clauses
        for clause in doc.clauses:
            if clause.clause_id.count(".") == 1:
                assert found[clause.clause_id] == (clause.start, clause.end)
                checked += 1
    assert checked > 500


# --------------------------------------------------------------------------- identity from provenance


def test_a_clause_locator_credits_exactly_that_clause() -> None:
    corpus = synthetic_corpus()
    got = align(candidate(RULE_TEXT, source_document_id="POL-1@v1", locator="clause:4.1"), corpus)
    assert got.match is Match.IDENTITY and got.clauses == {"4.1"} and got.locator_resolves
    assert ("POL-1@v1", "4.1") in got.units() and ("POL-1@v1", "4.2") not in got.units()
    assert ("POL-1@v1", DOC_UNIT) in got.units()  # identity to a document also credits its whole-document unit


def test_a_character_range_credits_the_clauses_it_overlaps_enough() -> None:
    corpus = synthetic_corpus()
    doc = corpus.docs["POL-1@v1"]
    start, end = doc.clauses["4.1"]
    inside = align(candidate("x y z", source_document_id="POL-1@v1", locator=f"chars:{start + 3}-{end - 3}"), corpus)
    assert inside.clauses == {"4.1"}
    spanning = align(
        candidate("x y z", source_document_id="POL-1@v1", locator=f"chars:{start}-{doc.clauses['4.2'][1]}"), corpus
    )
    assert spanning.clauses == {"4.1", "4.2"}  # a chunk that holds two clauses credits both
    mostly = align(candidate("x y z", source_document_id="POL-1@v1", locator=f"chars:{start + 4}-{end + 10}"), corpus)
    assert "4.1" in mostly.clauses and OVERLAP_THRESHOLD == 0.8


def test_a_range_mostly_outside_a_clause_does_not_credit_it() -> None:
    corpus = synthetic_corpus()
    doc = corpus.docs["POL-1@v1"]
    first, second = doc.clauses["4.1"], doc.clauses["4.2"]
    middle = (first[0] + first[1]) // 2
    straddling = align(
        candidate("x y z", source_document_id="POL-1@v1", locator=f"chars:{middle}-{(second[0] + second[1]) // 2}"),
        corpus,
    )
    assert straddling.match is Match.IDENTITY and straddling.locator_resolves
    assert straddling.clauses == frozenset(), "about half of the range lies in each clause, below the threshold"
    assert straddling.units() == {("POL-1@v1", DOC_UNIT)}


def test_text_alignment_needs_most_of_the_candidate_to_lie_in_the_document() -> None:
    corpus = synthetic_corpus()
    mostly_rule = align(candidate(f"{RULE_TEXT} then extra"), corpus)
    assert mostly_rule.match is Match.ALIGNMENT and mostly_rule.overlap >= OVERLAP_THRESHOLD
    diluted = align(candidate(f"{RULE_TEXT} plus a long unrelated tail about weather travel plans and lunch"), corpus)
    assert diluted.match is Match.NONE and 0.0 < diluted.overlap < OVERLAP_THRESHOLD


def test_a_document_locator_credits_the_document_and_only_the_clauses_its_text_reproduces() -> None:
    corpus = synthetic_corpus()
    bare = align(candidate("anything", source_document_id="POL-1@v1", locator="doc"), corpus)
    assert bare.match is Match.IDENTITY and bare.clauses == frozenset()
    assert bare.units() == {("POL-1@v1", DOC_UNIT)}, "naming a document is not citing its clauses"
    quoting = align(candidate(RULE_TEXT, source_document_id="POL-1@v1", locator="doc"), corpus)
    assert quoting.clauses == {"4.1"} and ("POL-1@v1", "4.2") not in quoting.units()
    unlocated = align(candidate(RULE_TEXT, source_document_id="POL-1@v1"), corpus)
    assert unlocated.clauses == {"4.1"}


def test_a_chunk_holding_two_clauses_credits_both_by_text() -> None:
    corpus = synthetic_corpus()
    doc = corpus.docs["POL-1@v1"]
    start, end = doc.clauses["4.1"][0], doc.clauses["4.2"][1]
    got = align(candidate(doc.text[start:end]), corpus)
    assert got.match is Match.ALIGNMENT and got.clauses == {"4.1", "4.2"}


def test_a_live_id_is_not_a_document_claim() -> None:
    got = align(candidate("txn state is failed", source_document_id="live:txn-1", locator="doc"), synthetic_corpus())
    assert not got.claimed_provenance and got.locator_resolves is None and got.match is Match.NONE


def test_identity_to_one_document_still_records_text_alignment_to_another() -> None:
    corpus = synthetic_corpus()
    memo = align(candidate(RULE_TEXT, source_document_id="ART-memo", locator="doc"), corpus)
    assert memo.match is Match.IDENTITY and memo.doc_id == "ART-memo"
    assert memo.text_doc_id == "POL-1@v1" and ("POL-1@v1", "4.1") in memo.text_units()
    assert ("POL-1@v1", "4.1") not in memo.units(), "text never earns identity credit"


def test_partial_text_of_a_document_is_exposure_even_below_the_alignment_threshold() -> None:
    corpus = synthetic_corpus()
    words = RULE_TEXT.split()
    partial = " ".join(words[:8]) + " then entirely unrelated words about weather travel lunch and gardens today"
    got = align(candidate(partial), corpus)
    assert got.match is Match.NONE and "POL-1@v1" in got.exposed_docs


def test_a_clause_number_repeated_in_one_document_is_refused() -> None:
    with pytest.raises(ValueError, match="twice"):
        clause_spans("4.1 first rule here\n4.1 second rule here\n")


def test_a_version_id_alone_is_provenance_for_an_authoritative_document() -> None:
    got = align(candidate(RULE_TEXT, source_version_id="POL-1@v1", locator="clause:4.2"), synthetic_corpus())
    assert got.match is Match.IDENTITY and got.clauses == {"4.2"}


def test_a_fabricated_locator_is_caught_and_earns_no_identity() -> None:
    corpus = synthetic_corpus()
    for locator in ("clause:9.9", "chars:9000-9100", "page 3"):
        got = align(candidate("two words", source_document_id="POL-1@v1", locator=locator), corpus)
        assert got.match is not Match.IDENTITY and got.locator_resolves is False and got.claimed_provenance
    ghost = align(candidate("two words", source_document_id="NOPE-1@v1", locator="clause:4.1"), corpus)
    assert ghost.match is Match.NONE and ghost.locator_resolves is False


def test_a_wrong_content_hash_voids_the_provenance_claim() -> None:
    corpus = synthetic_corpus()
    good = corpus.docs["POL-1@v1"].record.sha256
    assert (
        align(candidate("x y z", source_document_id="POL-1@v1", locator="doc", source_sha256=good), corpus).match
        is Match.IDENTITY
    )
    bad = align(candidate("x y z", source_document_id="POL-1@v1", locator="doc", source_sha256="0" * 64), corpus)
    assert bad.match is not Match.IDENTITY and bad.locator_resolves is False


def test_native_citation_is_reported_only_when_the_identity_resolves() -> None:
    corpus = synthetic_corpus()
    native = align(
        candidate(RULE_TEXT, source_document_id="POL-1@v1", locator="clause:4.1", native_citation_supported=True),
        corpus,
    )
    assert native.native
    broken = align(
        candidate(RULE_TEXT, source_document_id="POL-1@v1", locator="clause:9.9", native_citation_supported=True),
        corpus,
    )
    assert not broken.native
    with pytest.raises(ContractError, match="source id"):
        candidate(RULE_TEXT, native_citation_supported=True)  # no phantom citation without any source id
    assert (
        candidate(RULE_TEXT, source_document_id="POL-1@v1", native_citation_supported=True).source_document_id
        == "POL-1@v1"
    )


# --------------------------------------------------------------------------- alignment from text


def test_differently_chunked_identical_text_aligns_to_the_same_clause() -> None:
    corpus = synthetic_corpus()
    whole = align(candidate(RULE_TEXT), corpus)
    first_half = RULE_TEXT[: len(RULE_TEXT) // 2 + 10]
    second_half = RULE_TEXT[len(RULE_TEXT) // 2 - 10 :]
    reflowed = "  ".join(RULE_TEXT.split(" ")).upper()
    for text in (first_half, second_half, reflowed):
        got = align(candidate(text), corpus)
        assert got.match is Match.ALIGNMENT and got.doc_id == whole.doc_id and got.clauses == whole.clauses == {"4.1"}


def test_text_alone_never_earns_identity_and_never_a_native_citation() -> None:
    got = align(candidate(RULE_TEXT, native_citation_supported=False), synthetic_corpus())
    assert (
        got.match is Match.ALIGNMENT and not got.native and not got.claimed_provenance and got.locator_resolves is None
    )


def test_a_stale_copy_earns_alignment_credit_and_no_identity_credit() -> None:
    corpus = synthetic_corpus()
    quoted = align(candidate(RULE_TEXT, source_document_id="ART-memo", locator="doc"), corpus)
    assert quoted.match is Match.IDENTITY and quoted.doc_id == "ART-memo"  # identity to the memo, not to the policy
    assert ("POL-1@v1", "4.1") not in quoted.units()
    unattributed = align(candidate(RULE_TEXT), corpus)
    assert unattributed.match is Match.ALIGNMENT


def test_unrelated_and_very_short_text_aligns_to_nothing() -> None:
    corpus = synthetic_corpus()
    assert align(candidate("completely unrelated words about weather and travel plans"), corpus).match is Match.NONE
    assert align(candidate("a b"), corpus).match is Match.NONE
    assert Alignment(1, Match.NONE, None).units() == frozenset()


# --------------------------------------------------------------------------- the real published corpus


def test_every_authoritative_document_aligns_to_itself_by_identity_and_by_text(
    s_published_corpus: PublishedCorpus, s_corpus: tuple[Document, ...]
) -> None:
    sample = [d for d in s_corpus if d.authoritative][:40]
    for doc in sample:
        clause = doc.clauses[0]
        by_identity = align(
            candidate("x y z", source_document_id=doc.doc_id, locator=f"clause:{clause.clause_id}"), s_published_corpus
        )
        assert (doc.doc_id, clause.clause_id) in by_identity.units()
        line = doc.text[clause.start : clause.end].split(" ", 1)[1]
        by_text = align(candidate(line), s_published_corpus)
        assert by_text.match is Match.ALIGNMENT and by_text.clauses


def test_read_candidates_rebuilds_candidates_from_a_ledger_payload() -> None:
    payload = [candidate(RULE_TEXT, rank=1, source_document_id="POL-1@v1", locator="clause:4.1").to_dict()]
    rebuilt = read_candidates(payload)
    assert rebuilt[0].source_document_id == "POL-1@v1" and rebuilt[0].locator == "clause:4.1"
    assert read_candidates(None) == [] and read_candidates("x") == []


# --------------------------------------------------------------------------- the contract fields and the gold reader


def test_the_new_candidate_fields_are_optional_and_validated() -> None:
    plain = candidate("text here")
    assert plain.source_document_id is None and plain.source_sha256 is None
    assert EvidenceCandidate.from_dict(plain.to_dict()) == plain
    with pytest.raises(ContractError, match="SHA-256"):
        candidate("text", source_sha256="ABC")
    with pytest.raises(ContractError, match="identifier"):
        candidate("text", source_document_id="bad id with spaces")


def test_gold_records_read_back_exactly(s_questions: tuple[GoldRecord, ...]) -> None:
    for record in s_questions:
        assert GoldRecord.from_dict(record.to_dict()) == record
    assert len({r.digest for r in s_questions}) == len(s_questions)


def test_a_gold_record_with_an_unknown_or_missing_field_is_refused(s_questions: tuple[GoldRecord, ...]) -> None:
    plain = s_questions[0].to_dict()
    with pytest.raises(GoldError, match="unknown"):
        GoldRecord.from_dict({**plain, "surprise": 1})
    with pytest.raises(GoldError, match="missing"):
        GoldRecord.from_dict({k: v for k, v in plain.items() if k != "slots"})


def test_gold_read_from_disk_checks_the_file_digest(tmp_path: Path, s_questions: tuple[GoldRecord, ...]) -> None:
    path = write_annotations(tmp_path, Split.SMOKE, [r.to_dict() for r in s_questions])
    good = sha256_hex(path.read_text(encoding="utf-8"))
    assert read_gold(path, expected_sha256=good) == s_questions
    assert read_gold(path) == s_questions
    with pytest.raises(GoldError, match="digest"):
        read_gold(path, expected_sha256="0" * 64)


def test_the_published_manifest_carries_the_recorded_interval_of_authoritative_versions(s_published: Path) -> None:
    records = read_records(s_published)
    versions = [r for r in records if r.version_id]
    assert versions and all(r.recorded_from for r in versions)
    assert all(r.recorded_from is None for r in records if r.version_id is None)
