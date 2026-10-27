"""P11-T02: chunks that carry their title, banners that do not waste a chunk, and safe re-indexing (ADR-0106)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from evidence_agent.core.errors import ResourceConflict
from evidence_agent.core.ids import digest_bytes
from evidence_agent.core.retrieval import TEXT_REPRESENTATION, Chunk, index_text
from evidence_agent.ingest.chunking import chunk_blocks
from evidence_agent.ingest.parsing import PARSER_VERSION, parse_document, source_mime
from evidence_agent.ingest.pipeline import IngestPipeline
from evidence_agent.storage.qdrant import QdrantIndex

from .test_pipeline import MemoryIndex, _setup
from .test_retrieval import _Client, _Encoder

BANNER = "> FICTIONAL: Meridian Switchworks is an invented company.\n\n"
POLICY = (
    BANNER + "# Reversal policy\n\n- Status: approved\n- Effective from: 2026-01-01\n\n"
    "## 4 Requirements\n\n4.1 A request after 24 hours is refused.\n\n4.2 Amounts above 10 are escalated.\n"
).encode("utf-8")


def chunks_of(content: bytes, *, filename: str = "policy.md", max_chars: int = 2400) -> tuple[Chunk, ...]:
    blocks = parse_document(content, filename=filename, content_type=source_mime(filename))
    return chunk_blocks(blocks, source_bytes=content, tenant_id="tenant-a", case_id="case-1", revision_id="rev-1",
                        source_sha256=digest_bytes(content), max_chars=max_chars)


def test_a_banner_above_the_title_joins_the_first_chunk_instead_of_taking_one() -> None:
    chunks = chunks_of(POLICY)
    assert chunks[0].start_byte == 0 and chunks[0].text.startswith("> FICTIONAL")
    assert "# Reversal policy" in chunks[0].text, "banner, title and status are one chunk"
    assert not any(c.text.strip() == BANNER.strip() for c in chunks), "no chunk is only a banner"
    assert all(POLICY[c.start_byte:c.end_byte].decode() == c.text for c in chunks), "spans stay exact"


def test_a_heading_with_no_text_of_its_own_joins_the_block_below_it() -> None:
    chunks = chunks_of(b"# Title\n\n## Sub\n\nThe rule applies to refunds.\n")
    assert len(chunks) == 1 and chunks[0].text.startswith("# Title") and "refunds" in chunks[0].text
    assert chunks[0].section_id == "title/sub" and chunks[0].heading_path == ("Title", "Sub")


def test_every_chunk_knows_the_titles_above_it() -> None:
    chunks = chunks_of(POLICY, max_chars=120)
    requirement = next(c for c in chunks if "after 24 hours" in c.text)
    assert requirement.heading_path == ("Reversal policy", "4 Requirements")
    assert requirement.section_id == "reversal-policy/4-requirements"
    assert index_text(requirement) == "Reversal policy > 4 Requirements\n\n" + requirement.text
    untitled = chunks_of(b"Plain text without any heading.\n", filename="note.txt")[0]
    assert untitled.heading_path == () and index_text(untitled) == untitled.text


def test_an_oversized_block_is_cut_at_a_line_or_sentence_not_in_the_middle_of_a_word() -> None:
    sentences = " ".join(f"Sentence number {n} ends here." for n in range(12)) + "\n"
    chunks = chunks_of(sentences.encode(), filename="long.md", max_chars=100)
    assert len(chunks) > 1 and all(len(c.text) <= 100 for c in chunks)
    assert "".join(c.text for c in chunks) == sentences
    assert all(c.text.rstrip().endswith("here.") for c in chunks), "each cut follows a sentence end"
    word = ("x" * 250) + "\n"
    assert all(len(c.text) <= 100 for c in chunks_of(word.encode(), filename="word.md", max_chars=100))


# ---------------------------------------------------------------- what the index reads, what stays canonical


def test_the_index_reads_the_heading_path_but_stores_and_hashes_the_canonical_text() -> None:
    seen: list[str] = []

    class Spy(_Encoder):
        def embed_documents(self, texts: Any) -> list[list[float]]:
            listed = list(texts)
            seen.extend(listed)
            return super().embed_documents(listed)

    client = _Client()
    index = QdrantIndex(collection_name="ctx", client=client, encoder=Spy(), active_generation="gen")  # type: ignore[arg-type]
    chunk = next(c for c in chunks_of(POLICY, max_chars=120) if "after 24 hours" in c.text)
    index.ensure_collection()
    index.upsert([chunk], "gen", ())
    assert seen == ["Reversal policy > 4 Requirements\n\n" + chunk.text]
    point = next(call[1]["points"][0] for call in client.calls if call[0] == "upsert")
    assert point.vector["bm25"].text == seen[0]
    assert point.payload["content_sha256"] == chunk.content_sha256 == digest_bytes(chunk.text.encode())


def test_changing_what_the_index_reads_changes_the_representation_fingerprint(monkeypatch) -> None:
    def build() -> QdrantIndex:
        return QdrantIndex(collection_name="ctx", client=_Client(), encoder=_Encoder(), active_generation="gen")  # type: ignore[arg-type]

    index = build()
    assert index.representation_manifest["text_representation"] == TEXT_REPRESENTATION
    before = index.fingerprint
    assert build().fingerprint == before, "the same representation has the same fingerprint"
    monkeypatch.setattr("evidence_agent.storage.qdrant.TEXT_REPRESENTATION", "plain")
    assert build().fingerprint != before, "the indexed text is part of what the fingerprint pins"


# ---------------------------------------------------------------- re-indexing a populated database


@pytest.fixture
def revision(tmp_path: Path):  # type: ignore[no-untyped-def]
    database, registry, catalog, uploader, first, _ = _setup(tmp_path)
    admin = registry.access.authenticate("approver")
    new = registry.register_source(uploader, tenant_id="tenant-a", case_id="case-1", family_id="POL",
                                   content=POLICY, source_path="policy.md", owner_id="uploader")
    registry.approve_source(admin, new)
    try:
        yield database, catalog, uploader, new
    finally:
        database.close()


def rows(database) -> list[tuple[Any, ...]]:  # type: ignore[no-untyped-def]
    return [tuple(r) for r in database.connection.execute(
        "SELECT chunk_id, section_id, parent_id, neighbor_ids_json, parser_version, heading_path_json "
        "FROM p02_chunks ORDER BY start_byte")]


def test_a_chunk_stored_by_an_older_parser_is_relabelled_when_the_revision_is_indexed_again(revision) -> None:
    database, catalog, uploader, new = revision
    index = MemoryIndex()
    index.fingerprint = "a" * 64
    IngestPipeline(catalog, index).index(uploader, new)
    expected = [r for r in rows(database) if r[0] in {c.chunk_id for c in catalog.chunks_for_revision(uploader, new)}]
    assert {r[4] for r in expected} == {PARSER_VERSION} and any(json.loads(r[5]) for r in expected)
    database.connection.execute("UPDATE p02_chunks SET parser_version='mdtxt-v1', section_id='root', "
                                "parent_id=NULL, neighbor_ids_json='[]', heading_path_json='[]' WHERE revision_id=?",
                                (new,))
    IngestPipeline(catalog, index).index(uploader, new)
    assert [r for r in rows(database) if r[0] in {e[0] for e in expected}] == expected
    assert catalog.eligible_generation_metadata(uploader, new)["state"] == "READY"  # type: ignore[index]


def test_the_same_parser_cannot_relabel_a_stored_chunk_and_no_parser_can_change_its_span(revision) -> None:
    database, catalog, uploader, new = revision
    index = MemoryIndex()
    index.fingerprint = "a" * 64
    IngestPipeline(catalog, index).index(uploader, new)
    database.connection.execute("UPDATE p02_chunks SET section_id='tampered' WHERE revision_id=?", (new,))
    with pytest.raises(ResourceConflict):
        IngestPipeline(catalog, index).index(uploader, new)
    database.connection.execute("UPDATE p02_chunks SET parser_version='mdtxt-v1', text='tampered' WHERE revision_id=?",
                                (new,))
    with pytest.raises(ResourceConflict):
        IngestPipeline(catalog, index).index(uploader, new)


def test_chunks_read_back_from_the_catalog_keep_their_heading_path(revision) -> None:
    _, catalog, uploader, new = revision
    index = MemoryIndex()
    index.fingerprint = "a" * 64
    IngestPipeline(catalog, index).index(uploader, new)
    stored = catalog.chunks_for_revision(uploader, new)
    assert any(c.heading_path == ("Reversal policy", "4 Requirements") for c in stored)


def test_no_parser_version_can_move_a_stored_chunk_span(revision) -> None:
    database, catalog, uploader, new = revision
    index = MemoryIndex()
    index.fingerprint = "a" * 64
    IngestPipeline(catalog, index).index(uploader, new)
    database.connection.execute(
        "UPDATE p02_chunks SET parser_version='mdtxt-v1', end_byte=end_byte+1 WHERE chunk_id=("
        "SELECT chunk_id FROM p02_chunks WHERE revision_id=? ORDER BY start_byte LIMIT 1)", (new,))
    with pytest.raises(ResourceConflict):
        IngestPipeline(catalog, index).index(uploader, new)
