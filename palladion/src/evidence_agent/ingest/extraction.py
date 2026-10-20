"""Owned PDF process boundary and validated extracted-text provenance."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import sysconfig
from pathlib import Path
from threading import BoundedSemaphore
from typing import Any

from evidence_agent.core.errors import DependencyUnavailable, ValidationFailure
from evidence_agent.evaluation.process_owner import ProcessOwner
from evidence_agent.ingest.pdf_worker import MAX_INPUT, MAX_PAGES, MAX_TEXT, MEMORY_BYTES, PARSER

_ENV = {"SYSTEMROOT", "WINDIR", "PATH", "PATHEXT", "TEMP", "TMP", "USERPROFILE",
        "LOCALAPPDATA", "APPDATA", "HOMEDRIVE", "HOMEPATH"}
_PARSER_SLOTS = BoundedSemaphore(2)


def extract_pdf(raw: bytes) -> dict[str, Any]:
    """Parse once in a512MiB owned process with a10second wall deadline; no retries."""
    if not raw.startswith(b"%PDF-") or not 0 < len(raw) <= MAX_INPUT:
        raise ValidationFailure
    if not _PARSER_SLOTS.acquire(blocking=False):
        raise DependencyUnavailable("PDF parser capacity exhausted")
    environment = {k: v for k, v in os.environ.items() if k.upper() in _ENV}
    environment["PYTHONUTF8"] = "1"
    process = None
    owner = None
    try:
        owner = ProcessOwner(memory_bytes=MEMORY_BYTES)
        # Windows' venv redirector can spawn the interpreter before job assignment.
        # Start the real interpreter directly, with no site hooks/ambient Python path.
        executable = str(getattr(sys, "_base_executable", sys.executable)) if os.name == "nt" else sys.executable
        paths = json.dumps([str(Path(__file__).resolve().parents[2]), sysconfig.get_path("purelib")])
        bootstrap = ("import json,runpy,sys;sys.path[:0]=json.loads(sys.argv[1]);"
                     "runpy.run_module('evidence_agent.ingest.pdf_worker',run_name='__main__')")
        process = subprocess.Popen([executable, "-I", "-S", "-X", "utf8", "-c", bootstrap, paths],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, env=environment, start_new_session=os.name != "nt")
        owner.assign(process.pid)
        output, _ = process.communicate(raw, timeout=10)
        if process.returncode != 0 or len(output) > MAX_TEXT * 6 + 16384:
            raise ValidationFailure
        result: dict[str, Any] = json.loads(output)
        text = result["text"].encode("utf-8")
        pages = result["pages"]
        if (not 0 < len(text) <= MAX_TEXT or result["parser_version"] != PARSER or
                not 1 <= len(pages) <= MAX_PAGES):
            raise ValidationFailure
        end = -2
        for number, page in enumerate(pages, 1):
            if (page["page"] != number or page["start_byte"] != end + 2 or
                    not page["start_byte"] < page["end_byte"] <= len(text)):
                raise ValidationFailure
            text[page["start_byte"]:page["end_byte"]].decode("utf-8")
            end = page["end_byte"]
        if end != len(text):
            raise ValidationFailure
        return result
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError) as error:
        raise ValidationFailure from error
    finally:
        try:
            if owner is not None:
                owner.close(process.pid if process else None)
            if process is not None:
                if process.poll() is None:
                    process.kill()
                process.communicate()
        finally:
            _PARSER_SLOTS.release()
