"""The worker side of the comparator protocol: one JSON object per line on stdin, one per line on stdout.

This file uses the standard library only, because it runs inside a comparator's own environment (HippoRAG, GraphRAG,
LightRAG), not the benchmark's. ``serve`` moves everything a library prints to stderr, so stdout carries nothing but
protocol lines, and it reports a failed request by the exception's type name alone: a message could carry a prompt, a
passage or a key.

Request:  {"id": 1, "op": "build", "params": {...}}
Reply:    {"id": 1, "ok": true, "result": ...}  or  {"id": 1, "ok": false, "error": {"code": "ValueError"}}
The op "stop" ends the loop.
"""

from __future__ import annotations

import json
import sys
import traceback
from collections.abc import Callable, Mapping
from typing import Any, TextIO

Handler = Callable[[dict[str, Any]], Any]


def serve(handlers: Mapping[str, Handler], stdin: TextIO | None = None, stdout: TextIO | None = None) -> None:
    source = stdin or sys.stdin
    sink = stdout or sys.stdout
    if stdout is None:
        sys.stdout = sys.stderr  # a library's print() must never land in the protocol stream
    for line in source:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            ident, op = request["id"], request["op"]
            params = request.get("params", {})
        except (ValueError, KeyError, TypeError):
            sink.write(json.dumps({"id": None, "ok": False, "error": {"code": "BadRequest"}}) + "\n")
            sink.flush()
            continue
        if op == "stop":
            sink.write(json.dumps({"id": ident, "ok": True, "result": None}) + "\n")
            sink.flush()
            return
        handler = handlers.get(op)
        try:
            if handler is None:
                raise LookupError(op)
            reply = {"id": ident, "ok": True, "result": handler(params)}
            text = json.dumps(reply)
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)  # the stack goes to the worker's stderr log, never to the protocol
            text = json.dumps({"id": ident, "ok": False, "error": {"code": type(exc).__name__[:60]}})
        sink.write(text + "\n")
        sink.flush()
