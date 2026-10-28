"""P11-T02: chunks that carry their title, banners that do not waste a chunk, and safe re-indexing (ADR-0106)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from evidence_agent.core.errors import ResourceConflict
from evidence_agent.core.ids import digest_bytes
from evidence_agent.core.retrieval import TEXT_REPRESENTATION, Chunk, index_text
from evidence_agent.ingest.chunking import PACK_CHARS, chunk_blocks
from evidence_agent.ingest.parsing import PARSER_VERSION, ParsedBlock, parse_document, source_mime
from evidence_agent.ingest.pipeline import IngestPipeline
from evidence_agent.storage.qdrant import QdrantIndex

from .search_support import FILLER
from .test_pipeline import MemoryIndex, _setup
from .test_retrieval import _Client, _Encoder

BANNER = "> FICTIONAL: Meridian Switchworks is an invented company.\n\n"
POLICY = (
    BANNER + "# Reversal policy\n\n- Status: approved\n- Effective from: 2026-01-01\n\n"
    "## 4 Requirements\n\n4.1 A request after 24 hours is refused.\n\n4.2 Amounts above 10 are escalated.\n"
).encode("utf-8")
# The same policy with sections too long to share a chunk (see PACK_CHARS), so each section is a chunk of its own.
BIG_POLICY = (
    BANNER + f"# Reversal policy\n\n- Status: approved\n- Effective from: 2026-01-01\n- Notes: {FILLER}\n\n"
    f"## 4 Requirements\n\n4.1 A request after 24 hours is refused. {FILLER}\n\n"
    f"## 5 Escalation\n\n5.1 Amounts above 10 are escalated. {FILLER}\n"
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
    chunks = chunks_of(BIG_POLICY)
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
    chunk = next(c for c in chunks_of(BIG_POLICY) if "after 24 hours" in c.text)
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
                                   content=BIG_POLICY, source_path="policy.md", owner_id="uploader")
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


# ---------------------------------------------------------------- small sections share a chunk, whole (ADR-0106 addendum)


def test_small_neighbouring_sections_share_a_chunk_that_belongs_to_the_section_above_them() -> None:
    content = b"# Policy\n\n## A\n\nfirst clause.\n\n## B\n\nsecond clause.\n\n## C\n\nthird clause.\n"
    chunks = chunks_of(content)
    assert len(chunks) == 1 and all(clause in chunks[0].text for clause in ("first", "second", "third"))
    assert chunks[0].heading_path == ("Policy",) and chunks[0].section_id == "policy", "the shared titles"


def test_packing_fills_a_chunk_with_whole_sections_up_to_the_target_and_never_splits_one() -> None:
    def section(number: int) -> str:  # two paragraphs, about 420 characters in all
        words = [f"w{number}x{m}" for m in range(70)]
        return f"## Section {number}\n\n" + " ".join(words[:35]) + "\n\n" + " ".join(words[35:])

    content = ("# Packet\n\n" + "\n\n".join(section(n) for n in range(6)) + "\n").encode()
    chunks = chunks_of(content)
    assert len(chunks) > 1 and all(len(c.text) <= PACK_CHARS for c in chunks)
    assert all(c.text.startswith(("## ", "# ")) for c in chunks), "every chunk starts at a section boundary"
    assert sum(c.text.count("## Section") for c in chunks) == 6, "no section is dropped"
    for number in range(6):
        holders = {c.chunk_id for c in chunks if f"## Section {number}\n" in c.text}
        for marker in (f"w{number}x0 ", f"w{number}x69"):  # first and last words, either side of the paragraph break
            assert {c.chunk_id for c in chunks if marker in c.text} == holders, "a section is in one chunk"


def test_a_heading_that_fits_the_previous_chunk_does_not_leave_its_body_behind() -> None:
    previous = " ".join(f"a{n}" for n in range(230))  # a section of about 1,100 characters
    body = " ".join(f"b{n}" for n in range(300))  # a section too large to share the previous chunk
    chunks = chunks_of(f"# Policy\n\n## A\n\n{previous}\n\n## B\n\n{body}\n".encode())
    heading = next(c for c in chunks if "## B" in c.text)
    assert "b0 " in heading.text and "b299" in heading.text, "the heading and its body are one chunk"
    assert heading.heading_path == ("Policy", "B")
    assert not any(c.text.rstrip().endswith("## B") for c in chunks)


def test_a_heading_with_no_text_after_it_is_part_of_the_chunk_s_shared_path() -> None:
    chunks = chunks_of(b"# Policy\n\n## A\n\nclause a.\n\n## B\n")
    assert len(chunks) == 1 and chunks[0].text.rstrip().endswith("## B")
    assert chunks[0].heading_path == ("Policy",), "the chunk holds text of A and the title B, so only Policy is shared"


def test_a_section_larger_than_the_target_stays_whole_and_is_not_joined_by_its_neighbours() -> None:
    content = f"# Packet\n\n## Long\n\n{FILLER}\n\n## Short\n\nclause after.\n".encode()
    chunks = chunks_of(content)
    long_chunk = next(c for c in chunks if "pad0 " in c.text)
    assert "clause after" not in long_chunk.text and len(long_chunk.text) > PACK_CHARS


def test_blocks_that_overlap_are_never_joined_into_one_chunk() -> None:
    source = b"first words here and second words here"
    first = ParsedBlock("a", ("A",), source[:20].decode(), 0, 20, 1, 1, "paragraph")
    second = ParsedBlock("b", ("B",), source[10:].decode(), 10, len(source), 1, 1, "paragraph")
    chunks = chunk_blocks([first, second], source_bytes=source, tenant_id="tenant-a", case_id="case-1",
                          revision_id="rev-1", source_sha256=digest_bytes(source))
    assert [(c.start_byte, c.end_byte) for c in chunks] == [(0, 20), (10, len(source))]
