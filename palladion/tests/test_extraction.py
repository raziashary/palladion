"""Actual isolated pypdf worker; original files never execute."""
import io
import os
import subprocess
import sys

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from evidence_agent.core.errors import DependencyUnavailable, ValidationFailure
from evidence_agent.evaluation.process_owner import ProcessOwner
from evidence_agent.ingest import extraction
from evidence_agent.ingest.extraction import extract_pdf


def pdf_bytes(*, encrypted=False, blank=False, texts=None):
    writer = PdfWriter()
    for text in texts if texts is not None else (
            "Published procedure: verify citations.", "Second page: compare evidence."):
        page = writer.add_blank_page(width=612, height=792)
        if not blank:
            font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
            page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"):
                DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
            stream = DecodedStreamObject()
            stream.set_data(f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode())
            page[NameObject("/Contents")] = writer._add_object(stream)
    if encrypted:
        writer.encrypt("synthetic-password")
    target = io.BytesIO()
    writer.write(target)
    return target.getvalue()


def test_actual_pdf_child_preserves_extracted_page_spans():
    result = extract_pdf(pdf_bytes())
    assert result["parser_version"] == "pypdf-6.21.0-text-v1"
    encoded = result["text"].encode()
    assert len(result["pages"]) == 2
    assert encoded[result["pages"][0]["start_byte"]:result["pages"][0]["end_byte"]].decode() == "Published procedure: verify citations."
    assert "Second page" in encoded[result["pages"][1]["start_byte"]:].decode()


@pytest.mark.parametrize("raw", [b"not a PDF", b"%PDF-corrupt", b"%PDF-" + b"x" * (2 * 1024 * 1024)],
                         ids=["wrong-format", "corrupt", "oversize"])
def test_reject_invalid_and_oversize_pdf(raw):
    with pytest.raises(ValidationFailure):
        extract_pdf(raw)


@pytest.mark.parametrize("options", [{"encrypted": True}, {"blank": True}])
def test_reject_encrypted_and_ocr_required_pdf(options):
    with pytest.raises(ValidationFailure):
        extract_pdf(pdf_bytes(**options))


def test_parser_capacity_is_bounded_and_released():
    slots = extraction._PARSER_SLOTS
    assert slots.acquire(blocking=False) and slots.acquire(blocking=False)
    try:
        with pytest.raises(DependencyUnavailable):
            extract_pdf(b"%PDF-bounded")
    finally:
        slots.release()
        slots.release()
    assert slots.acquire(blocking=False)
    slots.release()


def test_actual_pdf_page_limit_accepts_50_and_rejects_51():
    result = extract_pdf(pdf_bytes(texts=["Source page."] * 50))
    assert len(result["pages"]) == 50
    with pytest.raises(ValidationFailure):
        extract_pdf(pdf_bytes(texts=["Source page."] * 51))


def test_actual_pdf_extracted_output_limit_is_distinct_from_input_limit():
    # Small PDF wrappers still cannot publish more than256KiB of extracted UTF8.
    from evidence_agent.ingest.pdf_worker import MAX_INPUT, MAX_TEXT

    raw = pdf_bytes(texts=["a" * (MAX_TEXT + 1)])
    assert len(raw) < MAX_INPUT
    with pytest.raises(ValidationFailure):
        extract_pdf(raw)


@pytest.mark.skipif(os.name != "nt", reason="Windows hard job memory cap; POSIX worker uses RLIMIT_AS")
def test_actual_windows_job_enforces_memory_cap():
    owner = ProcessOwner(memory_bytes=128 * 1024 * 1024)
    process = subprocess.Popen([str(sys._base_executable), "-I", "-S", "-c",
        "import sys; sys.stdin.buffer.read(); small=bytearray(32*1024*1024); print('SMALL_OK',flush=True)\n"
        "try: allocation=bytearray(256*1024*1024)\n"
        "except MemoryError: print('MEMORY_LIMIT',flush=True);sys.exit(23)\n"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        owner.assign(process.pid)
        output, _ = process.communicate(b"", timeout=5)
        assert process.returncode == 23 and output.splitlines() == [b"SMALL_OK", b"MEMORY_LIMIT"]
    finally:
        owner.close(process.pid)
        if process.poll() is None:
            process.kill()
        process.wait()


def test_deadline_terminates_and_reaps_the_owned_child(monkeypatch):
    original = subprocess.Popen
    processes = []

    def stalled(command, **kwargs):
        process = original([str(getattr(sys, "_base_executable", sys.executable)), "-I", "-S", "-c",
            "import sys,time;sys.stdin.buffer.read();time.sleep(60)"], **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(extraction.subprocess, "Popen", stalled)
    with pytest.raises(ValidationFailure) as failure:
        extract_pdf(b"%PDF-test-deadline")
    assert isinstance(failure.value.__cause__, subprocess.TimeoutExpired)
    assert len(processes) == 1 and processes[0].poll() is not None
