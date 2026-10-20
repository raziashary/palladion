"""Bounded digital-text PDF extraction child; no file paths, network or credentials."""
from __future__ import annotations

import io
import json
import os
import sys

MAX_INPUT = 2 * 1024 * 1024
MAX_TEXT = 256 * 1024
MAX_PAGES = 50
MEMORY_BYTES = 512 * 1024 * 1024
PARSER = "pypdf-6.21.0-text-v1"


def main() -> None:
    # Parent assigns its Windows memory-limited job before sending any input.
    raw = sys.stdin.buffer.read(MAX_INPUT + 1)
    if os.name != "nt":
        import resource
        getattr(resource, "setrlimit")(getattr(resource, "RLIMIT_AS"), (MEMORY_BYTES, MEMORY_BYTES))
    from pypdf import PdfReader
    if not raw.startswith(b"%PDF-") or len(raw) > MAX_INPUT:
        raise ValueError("Invalid PDF bounds")
    reader = PdfReader(io.BytesIO(raw), strict=True)
    if reader.is_encrypted or not 1 <= len(reader.pages) <= MAX_PAGES:
        raise ValueError("Unsupported PDF")
    parts, pages = [], []
    offset = 0
    for number, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        if not text.strip():
            raise ValueError("OCR required or empty page")
        encoded = text.encode("utf-8")
        if offset + len(encoded) > MAX_TEXT:
            raise ValueError("PDF text bound")
        pages.append({"page": number, "start_byte": offset, "end_byte": offset + len(encoded)})
        parts.append(text)
        offset += len(encoded) + 2  # Explicit UTF8 page separator, not original PDF bytes.
    result = {"text": "\n\n".join(parts), "pages": pages, "parser_version": PARSER}
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(2)
