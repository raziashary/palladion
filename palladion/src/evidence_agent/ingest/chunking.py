"""Deterministic exact-span chunking for parsed source blocks."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass

from evidence_agent.core.ids import chunk_id
from evidence_agent.core.retrieval import Chunk

from .parsing import ParsedBlock

DEFAULT_MAX_CHARS = 2400
_SENTENCE_END = re.compile(r"[.!?\u3002][\"')\]]*\s")
_EXCEPTION = re.compile(
    r"\b(?:except(?:ion)?|unless|however|provided that|notwithstanding|only if)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class _ChunkSpan:
    chunk_id: str
    section_id: str
    heading_path: tuple[str, ...]
    start_byte: int
    end_byte: int
    line_start: int
    line_end: int
    text: str
    content_sha256: str


def chunk_blocks(
    blocks: Sequence[ParsedBlock],
    *,
    source_bytes: bytes,
    tenant_id: str,
    case_id: str,
    revision_id: str,
    source_sha256: str,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> tuple[Chunk, ...]:
    """Group contiguous parsed blocks while retaining exact source spans.

    Exception clauses stay with the preceding rule when their exact source span
    fits the target. A heading or an untitled preamble (a banner above the first heading) joins the block that
    follows it when the two fit together in one chunk, and the chunk takes that block's section; otherwise, or when
    nothing follows, it is kept as its own chunk. Oversized blocks are split at Unicode
    character boundaries, preferring a line break, then a sentence end, then a space.
    """
    if not blocks or max_chars < 1:
        raise ValueError("blocks and a positive max_chars are required")

    groups: list[list[ParsedBlock]] = []
    for original in blocks:
        for block in _bounded_blocks(original, max_chars):
            current = groups[-1] if groups else None
            attached_exception = bool(current and _EXCEPTION.search(block.text))
            same_section = bool(current and current[-1].section_id == block.section_id)
            only_lead = bool(current and all(_is_lead(item) for item in current))
            contiguous = bool(current and block.start_byte >= current[-1].end_byte)
            combined_size = (
                len(source_bytes[current[0].start_byte : block.end_byte].decode("utf-8"))
                if current
                else 0
            )
            if (
                current
                and contiguous
                and combined_size <= max_chars
                and (attached_exception or same_section or only_lead)
            ):
                current.append(block)
            else:
                groups.append([block])

    raw: list[_ChunkSpan] = []
    for group in groups:
        start = group[0].start_byte
        end = group[-1].end_byte
        content = next((item for item in group if not _is_lead(item)), group[0])
        section_id = content.section_id
        text = source_bytes[start:end].decode("utf-8", errors="strict")
        identifier = chunk_id(tenant_id, revision_id, start, end)
        raw.append(
            _ChunkSpan(
                chunk_id=identifier,
                section_id=section_id,
                heading_path=content.heading_path,
                start_byte=start,
                end_byte=end,
                line_start=group[0].line_start,
                line_end=group[-1].line_end,
                text=text,
                content_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            )
        )

    # Continuation chunks in the same section link to that section's first chunk.
    first_by_section: dict[str, str] = {}
    for record in raw:
        first_by_section.setdefault(record.section_id, record.chunk_id)
    output: list[Chunk] = []
    for index, record in enumerate(raw):
        section_id = record.section_id
        first_id = first_by_section[section_id]
        parent_id = first_id if index and record.chunk_id != first_id else None
        neighbors = tuple(
            raw[neighbor].chunk_id
            for neighbor in (index - 1, index + 1)
            if 0 <= neighbor < len(raw)
        )
        output.append(
            Chunk(
                chunk_id=record.chunk_id,
                tenant_id=tenant_id,
                case_id=case_id,
                revision_id=revision_id,
                section_id=section_id,
                start_byte=record.start_byte,
                end_byte=record.end_byte,
                line_start=record.line_start,
                line_end=record.line_end,
                text=record.text,
                content_sha256=record.content_sha256,
                source_sha256=source_sha256,
                parent_id=parent_id,
                neighbor_ids=neighbors,
                heading_path=record.heading_path,
            )
        )
    return tuple(output)


def _is_lead(block: ParsedBlock) -> bool:
    """A heading or an untitled preamble says nothing alone; it belongs to the text that follows."""
    return block.kind == "heading" or (not block.heading_path and block.kind != "verbatim")


def _cut(text: str, start: int, max_chars: int) -> int:
    """End of the next piece: the last line break, else sentence end, else space in the window's second half."""
    limit = min(start + max_chars, len(text))
    if limit == len(text):
        return limit
    floor = start + max_chars // 2
    window = text[start:limit]
    newline = window.rfind("\n") + 1
    if start + newline > floor:
        return start + newline
    sentence_end = max((m.end() for m in _SENTENCE_END.finditer(window)), default=0)
    if start + sentence_end > floor:
        return start + sentence_end
    space = window.rfind(" ") + 1
    if start + space > floor:
        return start + space
    return limit


def _bounded_blocks(block: ParsedBlock, max_chars: int) -> tuple[ParsedBlock, ...]:
    """Split a parsed block on Unicode boundaries so no piece exceeds the target."""
    if len(block.text) <= max_chars:
        return (block,)

    pieces: list[ParsedBlock] = []
    char_start = 0
    byte_start = block.start_byte
    lines_before = 0  # newlines in the text before this piece, counted as pieces are cut
    while char_start < len(block.text):
        char_end = _cut(block.text, char_start, max_chars)
        text = block.text[char_start:char_end]
        byte_end = byte_start + len(text.encode("utf-8"))
        piece_line_start = block.line_start + lines_before
        lines_before += text.count("\n")
        piece_line_end = piece_line_start + text.count("\n") - int(text.endswith("\n"))
        pieces.append(
            ParsedBlock(
                section_id=block.section_id,
                heading_path=block.heading_path,
                text=text,
                start_byte=byte_start,
                end_byte=byte_end,
                line_start=piece_line_start,
                line_end=max(piece_line_start, piece_line_end),
                kind=block.kind,
            )
        )
        char_start = char_end
        byte_start = byte_end
    return tuple(pieces)
