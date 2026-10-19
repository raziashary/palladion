"""The shared Track A harness: chunks tile documents, the filter matches the manifest, budgets are enforced."""

from __future__ import annotations

import json
import random
import shutil
from itertools import pairwise
from pathlib import Path

import pytest

from benchmark.adapters.common import (
    DEFAULT_CHUNK_WORDS,
    PROVENANCE,
    AccessFilter,
    AdapterError,
    Chunk,
    Condition,
    PublishedView,
    build_chunks,
    candidate_from_chunk,
    chunk_document,
    count_words,
    enforce_budget,
)
from benchmark.contracts import EvidenceCandidate
from benchmark.eval.normalize import Match, PublishedCorpus, align, clause_spans


@pytest.fixture(scope="module")
def view(s_published: Path) -> PublishedView:
    return PublishedView.load(s_published)


@pytest.fixture(scope="module")
def chunks(view: PublishedView) -> list[Chunk]:
    return build_chunks(view)


# --------------------------------------------------------------------------- chunking


def test_chunks_tile_every_document_without_loss(view: PublishedView, chunks: list[Chunk]) -> None:
    by_doc: dict[str, list[Chunk]] = {}
    for chunk in chunks:
        by_doc.setdefault(chunk.doc_id, []).append(chunk)
    assert set(by_doc) == {r.doc_id for r in view.records}
    for document in view.documents():
        pieces = by_doc[document.record.doc_id]
        assert pieces[0].start == 0 and pieces[-1].end == len(document.text)
        assert all(a.end == b.start for a, b in pairwise(pieces))
        assert "".join(c.text for c in pieces) == document.text
        assert all(c.text == document.text[c.start : c.end] for c in pieces)
        assert all(c.words <= DEFAULT_CHUNK_WORDS for c in pieces)


def test_every_clause_belongs_to_at_least_one_chunk(view: PublishedView, chunks: list[Chunk]) -> None:
    held: dict[str, set[str]] = {}
    for chunk in chunks:
        held.setdefault(chunk.doc_id, set()).update(chunk.clauses)
    for document in view.documents():
        assert set(clause_spans(document.text)) <= held.get(document.record.doc_id, set())


def test_a_line_longer_than_the_limit_is_cut_at_word_boundaries() -> None:
    long_line = "4.1 " + " ".join(f"w{i}" for i in range(50))
    text = f"intro line\n{long_line}\nlast line\n"
    pieces = chunk_document("D", text, max_words=12)
    assert "".join(c.text for c in pieces) == text
    assert all(c.words <= 12 for c in pieces)
    holding = [c for c in pieces if "4.1" in c.clauses]
    assert len(holding) >= 4, "every piece of the long clause line lists the clause"
    words_in = [w for c in pieces for w in c.text.split()]
    assert words_in == text.split(), "no word is lost or split"


def test_chunk_ids_are_stable_and_unique(chunks: list[Chunk]) -> None:
    assert len({c.chunk_id for c in chunks}) == len(chunks)
    assert chunks[0].chunk_id == f"{chunks[0].doc_id}#{chunks[0].start}-{chunks[0].end}"


def test_empty_text_and_bad_limit() -> None:
    assert chunk_document("D", "") == []
    with pytest.raises(AdapterError):
        chunk_document("D", "text", max_words=0)


def test_counted_words_are_whitespace_words() -> None:
    assert count_words("a  b\nc\t d") == 4
    assert count_words("") == 0


# --------------------------------------------------------------------------- the view


def test_the_view_refuses_a_directory_with_annotation_or_generator_material(tmp_path: Path) -> None:
    (tmp_path / "corpus_manifest.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "annotations_dev").mkdir()
    with pytest.raises(AdapterError, match="annotation or generator"):
        PublishedView.load(tmp_path)


def test_the_view_refuses_a_directory_without_a_manifest(tmp_path: Path, s_published: Path) -> None:
    with pytest.raises(AdapterError, match="corpus_manifest"):
        PublishedView.load(tmp_path)
    with pytest.raises(AdapterError):
        PublishedView.load(s_published.parent)  # the snapshot root


def test_the_view_refuses_a_document_edited_after_publishing(tmp_path: Path, s_published: Path) -> None:
    copy = tmp_path / "published"
    shutil.copytree(s_published, copy)
    victim = next(copy.glob("docs/*.md"))
    victim.write_text(victim.read_text(encoding="utf-8") + "\nedited\n", encoding="utf-8")
    with pytest.raises(AdapterError, match="does not match its manifest"):
        PublishedView.load(copy)


def test_unknown_documents_are_refused(view: PublishedView) -> None:
    with pytest.raises(AdapterError):
        view.document("DOES-NOT-EXIST")


# --------------------------------------------------------------------------- the neutral filter


def raw_visibility(published: Path) -> dict[str, dict[str, bool]]:
    """Visibility computed straight from the JSON files, independently of the filter's code."""
    lines = (published / "corpus_manifest.jsonl").read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines]
    identity = json.loads((published / "identity_manifest.json").read_text(encoding="utf-8"))
    out: dict[str, dict[str, bool]] = {}
    for principal in identity["principals"]:
        out[principal["principal_id"]] = {
            r["doc_id"]: (not r["acl_tenants"] or principal["tenant_id"] in r["acl_tenants"])
            and (not r["acl_roles"] or principal["role_id"] in r["acl_roles"])
            for r in records
        }
    return out


def test_c2_filter_matches_the_manifest_for_every_principal(view: PublishedView, s_published: Path) -> None:
    expected = raw_visibility(s_published)
    access = AccessFilter(view, Condition.C2)
    denied_somewhere = 0
    for principal_id, by_doc in expected.items():
        for doc_id, visible in by_doc.items():
            assert access.allows(principal_id, doc_id) is visible
        denied_somewhere += sum(not v for v in by_doc.values())
        assert access.visible_documents(principal_id) == {d for d, v in by_doc.items() if v}
    assert denied_somewhere > 0, "the fixture must contain documents some principal may not see"


def test_c1_passes_everything_and_unknown_principals_are_refused(view: PublishedView) -> None:
    open_filter = AccessFilter(view, Condition.C1)
    principal = view.identity.principals[0].principal_id
    assert all(open_filter.allows(principal, r.doc_id) for r in view.records)
    assert open_filter.allows("nobody", view.records[0].doc_id), "C1 applies no filter, even to an unknown id"
    with pytest.raises(AdapterError):
        AccessFilter(view, Condition.C2).allows("nobody", view.records[0].doc_id)


# --------------------------------------------------------------------------- candidates


def test_candidates_from_chunks_earn_headline_identity_on_their_clauses(
    view: PublishedView, chunks: list[Chunk], s_published_corpus: PublishedCorpus
) -> None:
    checked = 0
    for chunk in chunks:
        if not chunk.clauses:
            continue
        record = view.document(chunk.doc_id).record
        candidate = candidate_from_chunk(chunk, record, 1, 1.5, "bm25")
        assert candidate.additional_metadata["provenance"] == PROVENANCE
        assert candidate.source_document_id == chunk.doc_id and candidate.source_sha256 == record.sha256
        got = align(candidate, s_published_corpus)
        assert got.match is Match.IDENTITY and got.locator_resolves
        assert set(chunk.clauses) <= got.clauses, chunk.chunk_id
        checked += 1
    assert checked > 100


def test_single_clause_chunks_use_the_clause_locator_and_others_character_ranges(
    view: PublishedView, chunks: list[Chunk]
) -> None:
    locators = {
        candidate_from_chunk(c, view.document(c.doc_id).record, 1, None, "bm25").locator
        for c in chunks[:400]
        if c.clauses
    }
    assert any(loc is not None and loc.startswith("clause:") for loc in locators)
    assert any(loc is not None and loc.startswith("chars:") for loc in locators)


# --------------------------------------------------------------------------- budgets


def ranked(view: PublishedView, chunks: list[Chunk], count: int, seed: int) -> list[EvidenceCandidate]:
    picks = random.Random(seed).sample(chunks, count)
    return [candidate_from_chunk(c, view.document(c.doc_id).record, i, None, "bm25") for i, c in enumerate(picks, 1)]


def test_a_bundle_inside_the_budget_is_kept_whole(view: PublishedView, chunks: list[Chunk]) -> None:
    bundle = ranked(view, chunks, 5, 1)
    result = enforce_budget(bundle, 10_000)
    assert [c.content for c in result.kept] == [c.content for c in bundle]
    assert not result.truncated and result.dropped == 0


def test_an_over_budget_bundle_is_truncated_and_flagged(view: PublishedView, chunks: list[Chunk]) -> None:
    bundle = ranked(view, chunks, 30, 2)
    result = enforce_budget(bundle, 400)
    assert result.truncated and result.dropped > 0
    assert result.words <= 400
    assert sum(count_words(c.content) for c in result.kept) == result.words
    assert [c.rank for c in result.kept] == list(range(1, len(result.kept) + 1))
    assert [c.content for c in result.kept] == [c.content for c in bundle[: len(result.kept)]]


def test_one_candidate_longer_than_the_budget_is_cut_and_says_so(view: PublishedView, chunks: list[Chunk]) -> None:
    big = max(chunks, key=lambda c: c.words)
    candidate = candidate_from_chunk(big, view.document(big.doc_id).record, 1, None, "bm25")
    result = enforce_budget([candidate], 10)
    assert result.kept[0].additional_metadata["truncated_from_words"] == big.words
    assert count_words(result.kept[0].content) == 10 and result.cut_words == big.words - 10 and result.truncated


def test_two_bundles_at_one_budget_differ_by_less_than_one_chunk(view: PublishedView, chunks: list[Chunk]) -> None:
    widest = max(c.words for c in chunks)
    for seed in range(20):
        a = enforce_budget(ranked(view, chunks, 40, seed), 500)
        b = enforce_budget(ranked(view, chunks, 40, seed + 100), 500)
        assert abs(a.words - b.words) <= widest
        assert a.words <= 500 and b.words <= 500


def test_a_budget_below_one_word_is_refused(view: PublishedView, chunks: list[Chunk]) -> None:
    with pytest.raises(AdapterError):
        enforce_budget(ranked(view, chunks, 2, 3), 0)
