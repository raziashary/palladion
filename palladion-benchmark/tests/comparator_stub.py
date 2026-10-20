"""A stand-in comparator for the worker tests: it speaks the protocol and misbehaves on request (never a real model)."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_spec = importlib.util.spec_from_file_location(
    "comparator_protocol",
    os.environ.get("COMPARATOR_PROTOCOL", str(Path(__file__).resolve().parents[1] / "comparators" / "protocol.py")),
)
assert _spec is not None and _spec.loader is not None
_protocol = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_protocol)
serve = _protocol.serve

CHUNKS: list[dict[str, Any]] = []


def _chat_once(model: str) -> int:
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": "hi"}]}).encode()
    request = urllib.request.Request(
        os.environ["OPENAI_BASE_URL"] + "/chat/completions", data=body, method="POST",
        headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"], "Content-Type": "application/json"},
    )  # fmt: skip
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return int(response.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)


def build(params: dict[str, Any]) -> Any:
    print("a library printing to stdout")  # must not corrupt the protocol
    CHUNKS.clear()
    with open(params["corpus"], encoding="utf-8") as handle:
        CHUNKS.extend(json.loads(line) for line in handle)
    for _ in range(int(os.environ.get("STUB_BUILD_CALLS", "0"))):
        _chat_once(os.environ["STUB_MODEL"])
    Path(params["workdir"]).mkdir(parents=True, exist_ok=True)
    Path(params["workdir"], "index.bin").write_bytes(b"x" * 100)
    return {"chunks": len(CHUNKS)}


def retrieve(params: dict[str, Any]) -> Any:
    query = str(params["query"])
    if query == "HANG":
        time.sleep(3600)
    words = set(query.lower().split())
    ranked = sorted(CHUNKS, key=lambda c: (-len(words & set(c["text"].lower().split())), c["chunk_id"]))
    hits: list[dict[str, Any]] = [
        {"chunk_id": c["chunk_id"], "score": float(len(words & set(c["text"].lower().split())))}
        for c in ranked[: int(params["limit"])]
    ]
    if "RELATION" in query and hits:
        hits[0]["relation"] = {
            "subject": "alpha", "predicate": "RELATES_TO", "object": "beta", "supporting_ids": [hits[0]["chunk_id"]]
        }  # fmt: skip
    return {"hits": hits}


def reply(params: dict[str, Any]) -> Any:
    """Answer with whatever the test asks for, so the client's checks can be exercised."""
    return params["value"]


def spend(params: dict[str, Any]) -> Any:
    """Call the chat endpoint ``n`` times through the proxy, as a runaway comparator would."""
    statuses: dict[str, int] = {}
    for _ in range(int(params["n"])):
        code = _chat_once(str(params["model"]))
        statuses[str(code)] = statuses.get(str(code), 0) + 1
        time.sleep(float(params.get("pause", 0)))
    return statuses


def hang(params: dict[str, Any]) -> Any:
    time.sleep(3600)


def spawn(params: dict[str, Any]) -> Any:
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(3600)"])
    return {"child_pid": child.pid}


def boom(params: dict[str, Any]) -> Any:
    raise ValueError("SECRET-CANARY-IN-AN-EXCEPTION")


def crash(params: dict[str, Any]) -> Any:
    os._exit(3)


def noisy(params: dict[str, Any]) -> Any:
    sys.__stdout__.write("not json at all\n" * int(params["lines"]))  # type: ignore[union-attr]
    sys.__stdout__.flush()  # type: ignore[union-attr]
    return "done"


def big(params: dict[str, Any]) -> Any:
    return "x" * int(params["bytes"])


def environment(params: dict[str, Any]) -> Any:
    return sorted(os.environ)


if __name__ == "__main__":
    serve(
        {
            "build": build, "retrieve": retrieve, "reply": reply, "spend": spend, "hang": hang, "spawn": spawn,
            "boom": boom, "crash": crash, "noisy": noisy, "big": big, "environment": environment,
        }
    )  # fmt: skip
