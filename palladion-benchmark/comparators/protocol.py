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
import socket
import sys
import traceback
from collections.abc import Callable, Mapping
from typing import Any, TextIO

Handler = Callable[[dict[str, Any]], Any]


LOOPBACK = frozenset({"127.0.0.1", "::1", "localhost"})


class NetworkRefused(OSError):
    """A non-loopback lookup or connection was attempted. The message is fixed; the host goes to stderr."""


def _is_loopback(host: object) -> bool:
    return host is None or host == "" or str(host) in LOOPBACK


def _refuse(host: object, port: object) -> None:
    print(f"NETWORK_REFUSED host={host!r} port={port!r}", file=sys.stderr, flush=True)
    raise NetworkRefused("NETWORK_REFUSED")


def guard_network() -> None:
    """Refuse every name lookup and connection that leaves the loopback interface, for the worker's whole lifetime.

    The counting proxy is a comparator's only route to a model; this makes that true of the process, not only of the
    environment it was given (a library that read a key from somewhere else still could not reach the provider)."""
    real_getaddrinfo = socket.getaddrinfo
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def getaddrinfo(host: Any, port: Any, *args: Any, **kwargs: Any) -> Any:
        if not _is_loopback(host):
            _refuse(host, port)
        return real_getaddrinfo(host, port, *args, **kwargs)

    def connect(self: socket.socket, address: Any) -> None:
        if isinstance(address, tuple) and not _is_loopback(address[0]):
            _refuse(address[0], address[1])
        real_connect(self, address)

    def connect_ex(self: socket.socket, address: Any) -> int:
        if isinstance(address, tuple) and not _is_loopback(address[0]):
            _refuse(address[0], address[1])
        return real_connect_ex(self, address)

    socket.getaddrinfo = getaddrinfo  # type: ignore[assignment]
    socket.socket.connect = connect  # type: ignore[method-assign]
    socket.socket.connect_ex = connect_ex  # type: ignore[method-assign]


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
