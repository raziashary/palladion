"""Source-preserving UTF-8 text, structured text and code parsing; never executes input."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath

from evidence_agent.core.errors import ValidationFailure

PARSER_VERSION = "mdtxt-v3"  # v2: lead blocks join the next chunk, sentence-aware splits; v3: small sections share a chunk (ADR-0106)
MAX_SOURCE_BYTES = 10 * 1024 * 1024
_MIME_BY_SUFFIX = {
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".txt": "text/plain",
    ".json": "application/json",
    ".jsonl": "application/x-ndjson",
    ".csv": "text/csv",
    ".tsv": "text/tab-separated-values",
}
_MIME_BY_SUFFIX.update(dict.fromkeys(
    (".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".c", ".h",
     ".cpp", ".cs", ".sql", ".sh", ".ps1", ".yaml", ".yml", ".toml", ".ini",
     ".cfg", ".xml", ".html", ".css", ".log"), "text/plain"))
_HEADING = re.compile(r"^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$")
_TABLE_SEPARATOR = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")


@dataclass(frozen=True, slots=True)
class ParsedBlock:
    """A contiguous original byte range and the heading path active there."""

    section_id: str
    heading_path: tuple[str, ...]
    text: str
    start_byte: int
    end_byte: int
    line_start: int
    line_end: int
    kind: str


def source_mime(filename: str) -> str:
    suffix = PurePosixPath(filename.replace("\\", "/")).suffix.lower()
    expected = _MIME_BY_SUFFIX.get(suffix)
    if expected is None:
        raise ValidationFailure
    return expected


def parser_version(filename: str) -> str:
    """Preserve legacy text identities; new opaque formats have their own parser identity."""
    source_mime(filename)
    suffix = PurePosixPath(filename.replace("\\", "/")).suffix.lower()
    return PARSER_VERSION if suffix in {".md", ".markdown", ".txt"} else "utf8-verbatim-v2"


def validate_source(content: bytes, filename: str, content_type: str) -> str:
    """Validate bounded UTF-8 source bytes and declared extension/MIME pair."""
    if not isinstance(content, bytes) or not content or len(content) > MAX_SOURCE_BYTES:
        raise ValidationFailure
    expected = source_mime(filename)
    declared = content_type.split(";", maxsplit=1)[0].strip().lower()
    if expected is None or declared != expected:
        raise ValidationFailure
    try:
        content.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValidationFailure from exc
    return expected


def parse_document(content: bytes, *, filename: str, content_type: str) -> tuple[ParsedBlock, ...]:
    """Parse supported source into exact UTF-8 byte spans and one-based lines.

    Markdown/TXT headings update the section path; tables remain contiguous blocks
    including their header and separator rows. Blank lines delimit those blocks.
    Structured/code formats use one verbatim block retaining all whitespace.
    """
    validate_source(content, filename, content_type)
    text = content.decode("utf-8")
    # Structured/code sources remain opaque text: no JSON reserialization, execution,
    # Markdown heading interpretation or loss of whitespace in quoted source spans.
    if PurePosixPath(filename.replace("\\", "/")).suffix.lower() not in {
        ".md", ".markdown", ".txt"
    }:
        if not text.strip():
            raise ValidationFailure
        return (ParsedBlock("root", (), text, 0, len(content), 1,
                            max(1, len(text.splitlines())), "verbatim"),)
    lines = text.splitlines(keepends=True)
    if not lines and text:
        lines = [text]
    offsets: list[tuple[int, int, int, str]] = []
    byte_offset = 0
    for line_number, line in enumerate(lines, start=1):
        encoded = line.encode("utf-8")
        offsets.append((byte_offset, byte_offset + len(encoded), line_number, line))
        byte_offset += len(encoded)

    blocks: list[ParsedBlock] = []
    heading_stack: list[str] = []
    index = 0
    while index < len(offsets):
        start, end, line_number, line = offsets[index]
        stripped = line.rstrip("\r\n")
        if not stripped.strip():
            index += 1
            continue
        heading = _HEADING.match(stripped)
        if heading:
            level = len(stripped.lstrip()[: len(stripped.lstrip()) - len(stripped.lstrip().lstrip("#"))])
            level = min(max(level, 1), 6)
            title = heading.group(1).strip()
            heading_stack = heading_stack[: level - 1]
            heading_stack.append(title)
            section_id = section_id_for(heading_stack)
            blocks.append(
                ParsedBlock(section_id, tuple(heading_stack), line, start, end, line_number, line_number, "heading")
            )
            index += 1
            continue

        stop = index + 1
        kind = "paragraph"
        if "|" in stripped and stop < len(offsets) and _TABLE_SEPARATOR.match(
            offsets[stop][3].rstrip("\r\n")
        ):
            kind = "table"
            stop += 1
            while stop < len(offsets):
                table_line = offsets[stop][3].rstrip("\r\n")
                if not table_line.strip() or "|" not in table_line:
                    break
                stop += 1
        else:
            # Keep list/procedure lines together and avoid joining unrelated blocks.
            is_list = bool(re.match(r"^\s*(?:[-*+] |\d+[.)] )", stripped))
            if is_list:
                kind = "procedure"
                while stop < len(offsets):
                    candidate = offsets[stop][3].rstrip("\r\n")
                    if not candidate.strip() or _HEADING.match(candidate):
                        break
                    if not re.match(r"^\s*(?:(?:[-*+] |\d+[.)] )| {2,}\S)", candidate):
                        break
                    stop += 1
            else:
                while stop < len(offsets):
                    candidate = offsets[stop][3].rstrip("\r\n")
                    if not candidate.strip() or _HEADING.match(candidate) or "|" in candidate:
                        break
                    if re.match(r"^\s*(?:[-*+] |\d+[.)] )", candidate):
                        break
                    stop += 1

        block_start = offsets[index][0]
        block_end = offsets[stop - 1][1]
        block_lines = "".join(item[3] for item in offsets[index:stop])
        blocks.append(
            ParsedBlock(
                section_id_for(heading_stack),
                tuple(heading_stack),
                block_lines,
                block_start,
                block_end,
                offsets[index][2],
                offsets[stop - 1][2],
                kind,
            )
        )
        index = stop

    if not blocks:
        raise ValidationFailure
    # Each returned range must decode to exactly the parser's text; this also
    # protects future parser edits from drifting across Unicode byte offsets.
    for block in blocks:
        if content[block.start_byte : block.end_byte].decode("utf-8") != block.text:
            raise RuntimeError("parser span does not reproduce original UTF-8 text")
    return tuple(blocks)


def section_id_for(path: Sequence[str]) -> str:
    """The identifier of the section a heading path names; `root` above the first heading."""
    if not path:
        return "root"
    return "/".join(_slug(part) for part in path)


def _slug(value: str) -> str:
    slug = re.sub(r"[^\w.-]+", "-", value.casefold(), flags=re.UNICODE).strip("-")
    return slug or "section"
