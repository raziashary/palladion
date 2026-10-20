"""Run a third-party comparator as a subprocess behind a line-delimited JSON protocol (B06-T00.02, BR14, BR36).

The comparator lives in its own environment and can only reach a model through the counting proxy
(``benchmark.llm_proxy``). This module is the benchmark's side: it starts the process with a minimal environment (the
provider key is never in it), sends one request at a time, bounds the time and the size of every reply, and kills the
whole process tree when a request times out or the reply is unusable. A killed worker is not restarted by itself: the
arm that owns it becomes unavailable, which the Runner records as a result, never a zero.

``WorkerArm`` turns a worker into the three-method retriever adapter the harness already runs.
"""

from __future__ import annotations

import contextlib
import json
import os
import queue
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import IO, Any

from benchmark.adapters.common import (
    DEFAULT_CHUNK_WORDS,
    AccessFilter,
    AdapterError,
    Chunk,
    Condition,
    PublishedView,
    build_chunks,
    candidate_from_chunk,
    enforce_budget,
    flags_from_notes,
)
from benchmark.contracts import (
    ArmUnavailable,
    ContractError,
    EvidenceCandidate,
    RetrievalRequest,
    screen_arm_visible,
)
from benchmark.llm_proxy import ProxyServer
from benchmark.run_manifest import ComparatorPin

MAX_LINE_BYTES = 8 * 1024 * 1024
MAX_NOISE_LINES = 1000  # lines on stdout that are not protocol; a library that prints a lot is a fault, not progress
MAX_STDERR_BYTES = 16 * 1024 * 1024
_SAFE_ENV = ("PATH", "SYSTEMROOT", "SYSTEMDRIVE", "TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE", "LANG", "LC_ALL")


class WorkerError(RuntimeError):
    """A worker failed. ``code`` is a fixed label; it never holds a reply, a prompt or a key."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _kill_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False)
    else:
        with contextlib.suppress(ProcessLookupError):
            kill_group = getattr(os, "killpg")  # absent on Windows, where the branch above runs  # noqa: B009
            kill_group(process.pid, 9)  # SIGKILL
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


class ComparatorWorker:
    """One comparator process. Requests are serial; the reader thread and the queue make every wait bounded."""

    def __init__(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        stderr_path: Path,
        env: Mapping[str, str] | None = None,
        max_line_bytes: int = MAX_LINE_BYTES,
    ) -> None:
        self._argv = list(argv)
        self._cwd = cwd
        self._stderr_path = stderr_path
        self._extra_env = dict(env or {})
        self._max_line = max_line_bytes
        self._process: subprocess.Popen[bytes] | None = None
        self._replies: queue.Queue[dict[str, Any] | BaseException] = queue.Queue()
        self._reader: threading.Thread | None = None
        self._stderr_file: IO[bytes] | None = None
        self._next_id = 0
        self._dead: str | None = None
        self._noise = 0

    # -- life ----------------------------------------------------------------------------------

    def start(self) -> None:
        if self._process is not None:
            raise WorkerError("ALREADY_STARTED")
        env = {k: os.environ[k] for k in _SAFE_ENV if k in os.environ}
        env.update(self._extra_env)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        self._stderr_path.parent.mkdir(parents=True, exist_ok=True)
        self._stderr_file = self._stderr_path.open("ab")
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        self._process = subprocess.Popen(
            self._argv,
            cwd=self._cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self._stderr_file,
            creationflags=flags,
            start_new_session=os.name != "nt",
        )
        self._reader = threading.Thread(target=self._read_loop, name="comparator-reader", daemon=True)
        self._reader.start()

    @property
    def alive(self) -> bool:
        return self._process is not None and self._process.poll() is None and self._dead is None

    def kill(self, reason: str = "KILLED") -> None:
        self._dead = self._dead or reason
        if self._process is not None:
            _kill_tree(self._process)

    def stop(self, timeout: float = 10.0) -> None:
        """Ask the worker to end; kill the process tree if it does not."""
        try:
            if self.alive:
                self.request("stop", {}, timeout=timeout)
        except WorkerError:
            pass
        finally:
            self.kill("STOPPED")
            if self._process is not None and self._process.stdin is not None:
                self._process.stdin.close()
            if self._stderr_file is not None:
                self._stderr_file.close()

    def stderr_bytes(self) -> int:
        return self._stderr_path.stat().st_size if self._stderr_path.exists() else 0

    # -- requests ------------------------------------------------------------------------------

    def request(self, op: str, params: Mapping[str, Any], *, timeout: float) -> Any:
        """Send one request and wait at most ``timeout`` seconds. A timeout kills the worker."""
        if self._process is None or self._process.stdin is None:
            raise WorkerError("NOT_STARTED")
        if self._dead is not None:
            raise WorkerError("WORKER_DEAD")
        self._next_id += 1
        ident = self._next_id
        line = json.dumps({"id": ident, "op": op, "params": dict(params)}) + "\n"
        try:
            self._process.stdin.write(line.encode("utf-8"))
            self._process.stdin.flush()
        except OSError:
            self.kill("PIPE_BROKEN")
            raise WorkerError("WORKER_DEAD") from None
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self.kill("TIMEOUT")
                raise WorkerError("TIMEOUT")
            try:
                item = self._replies.get(timeout=min(remaining, 0.5))
            except queue.Empty:
                if self._process.poll() is not None:
                    self.kill("EXITED")
                    raise WorkerError("EXITED") from None
                if self.stderr_bytes() > MAX_STDERR_BYTES:
                    self.kill("STDERR_TOO_LARGE")
                    raise WorkerError("STDERR_TOO_LARGE") from None
                continue
            if isinstance(item, BaseException):
                self.kill("BAD_REPLY")
                raise WorkerError(str(item)) from None
            if item.get("id") != ident:
                continue  # a late reply to an earlier request
            if item.get("ok") is not True:
                error = item.get("error")
                code = error.get("code") if isinstance(error, dict) else None
                raise WorkerError(f"WORKER_{str(code)[:60]}" if isinstance(code, str) else "WORKER_ERROR")
            return item.get("result")

    def _read_loop(self) -> None:
        assert self._process is not None and self._process.stdout is not None
        stream = self._process.stdout
        while True:
            raw = stream.readline(self._max_line + 1)
            if not raw:
                return
            if len(raw) > self._max_line and not raw.endswith(b"\n"):
                self._replies.put(WorkerError("REPLY_TOO_LARGE"))
                return
            try:
                message = json.loads(raw)
            except ValueError:
                self._noise += 1
                if self._noise > MAX_NOISE_LINES:
                    self._replies.put(WorkerError("TOO_MUCH_NOISE"))
                    return
                continue
            if isinstance(message, dict) and "id" in message:
                self._replies.put(message)
            else:
                self._noise += 1

    def __enter__(self) -> ComparatorWorker:
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.stop()


# --------------------------------------------------------------------------- the arm

OVERFETCH = 3  # hits asked of a comparator per hit wanted, because the access filter acts after its ranking
MAX_HITS = 100
_UNAVAILABLE = {"TIMEOUT", "EXITED", "WORKER_DEAD", "PIPE_BROKEN", "REPLY_TOO_LARGE", "BAD_REPLY", "TOO_MUCH_NOISE"}


class WorkerArm:
    """A comparator seen through the harness's retriever surface: build, retrieve, index_stats, describe.

    The comparator indexes exactly the chunks every other arm uses (the shared chunker, published text only) and answers
    with chunk ids and scores; this class maps those back to candidates with harness-attributed provenance, applies the
    neutral access filter after the comparator's ranking (its outputs carry no document id to filter on, BR35) and
    enforces the common evidence budget. ``usage`` returns the proxy's counters, so the cost of building the index
    (extraction calls and tokens) and of each query (model calls at query time) is measured by the one component that
    cannot be bypassed.
    """

    def __init__(
        self,
        arm_id: str,
        worker: ComparatorWorker,
        pin: ComparatorPin,
        *,
        view: PublishedView,
        work_dir: Path,
        models: Mapping[str, str],
        usage: Callable[[], Mapping[str, int]],
        condition: Condition = Condition.C2,
        chunk_words: int = DEFAULT_CHUNK_WORDS,
        unsupported: Sequence[str] = (),
        build_timeout: float = 3600.0,
        query_timeout: float = 120.0,
    ) -> None:
        self.arm_id = arm_id
        self._worker = worker
        self._pin = pin
        self._view = view
        self._work_dir = work_dir
        self._models = dict(models)
        self._usage = usage
        self._condition = condition
        self._chunk_words = chunk_words
        self._unsupported = tuple(unsupported)
        self._build_timeout = build_timeout
        self._query_timeout = query_timeout
        self._access = AccessFilter(view, condition)
        self._chunks: dict[str, Chunk] = {}
        self._stats: dict[str, Any] = {}
        self.last_notes: dict[str, Any] = {}

    # -- build ---------------------------------------------------------------------------------

    def build_index(self, source_manifest_uri: str, index_namespace: str) -> None:
        if Path(source_manifest_uri).resolve() != self._view.root.resolve():
            raise AdapterError("the index is built from the published directory this arm was created with")
        chunks = build_chunks(self._view, self._chunk_words)
        rows = [{"chunk_id": c.chunk_id, "doc_id": c.doc_id, "text": c.text} for c in chunks]
        try:
            screen_arm_visible("corpus", [row["text"] for row in rows])
        except ContractError:
            raise AdapterError("the corpus handed to a comparator contains a gold-like marker") from None
        self._work_dir.mkdir(parents=True, exist_ok=True)
        corpus_path = self._work_dir / "corpus.jsonl"
        corpus_path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        native_dir = self._work_dir / "native"
        before = dict(self._usage())
        started = time.perf_counter()
        try:
            native = self._worker.request(
                "build",
                {"corpus": str(corpus_path), "workdir": str(native_dir), "namespace": index_namespace},
                timeout=self._build_timeout,
            )
        except WorkerError as exc:
            raise ArmUnavailable(f"{self.arm_id} could not build its index: {exc.code}") from None
        after = dict(self._usage())
        self._chunks = {c.chunk_id: c for c in chunks}
        self._stats = {
            "build_ms": (time.perf_counter() - started) * 1000.0,
            "build_cost_usd": None,
            "extraction_calls": after.get("calls", 0) - before.get("calls", 0),
            "extraction_prompt_tokens": after.get("prompt_tokens", 0) - before.get("prompt_tokens", 0),
            "extraction_completion_tokens": after.get("completion_tokens", 0) - before.get("completion_tokens", 0),
            "embedding_inputs": after.get("embedding_inputs", 0) - before.get("embedding_inputs", 0),
            "storage_bytes": _directory_bytes(native_dir),
            "chunks": len(chunks),
            "native": native if isinstance(native, dict) else {},
        }

    # -- query ---------------------------------------------------------------------------------

    def retrieve(self, request: RetrievalRequest) -> list[EvidenceCandidate]:
        if not self._chunks:
            raise AdapterError("build_index must run before retrieve")
        before = dict(self._usage())
        wanted = min(MAX_HITS, request.limit * OVERFETCH)
        try:
            reply = self._worker.request(
                "retrieve", {"query": request.query, "limit": wanted}, timeout=self._query_timeout
            )
        except WorkerError as exc:
            if exc.code in _UNAVAILABLE:
                raise ArmUnavailable(f"{self.arm_id} worker failed: {exc.code}") from None
            raise ContractError(f"{self.arm_id} could not answer: {exc.code}") from None
        after = dict(self._usage())
        hits = self._hits(reply, wanted)
        visible = [h for h in hits if self._access.allows(request.principal_id, self._chunks[h["chunk_id"]].doc_id)]
        candidates = []
        for rank, hit in enumerate(visible[: request.limit], start=1):
            chunk = self._chunks[hit["chunk_id"]]
            record = self._view.document(chunk.doc_id).record
            made = candidate_from_chunk(chunk, record, rank, hit["score"], self.arm_id)
            candidates.append(made if hit["relation"] is None else replace(made, relation=hit["relation"]))
        bundle = enforce_budget(candidates, request.max_evidence_tokens)
        self.last_notes = {
            "truncated": bundle.truncated,
            "dropped": bundle.dropped,
            "cut_words": bundle.cut_words,
            "filtered_after_ranking": len(hits) - len(visible),
            "query_llm_calls": after.get("calls", 0) - before.get("calls", 0),
        }
        return list(bundle.kept)

    def _hits(self, reply: Any, wanted: int) -> list[dict[str, Any]]:
        if not isinstance(reply, dict) or not isinstance(reply.get("hits"), list):
            raise ContractError(f"{self.arm_id} returned a reply outside the protocol")
        seen: set[str] = set()
        hits: list[dict[str, Any]] = []
        for raw in reply["hits"]:
            if not isinstance(raw, dict) or raw.get("chunk_id") not in self._chunks:
                raise ContractError(f"{self.arm_id} returned a chunk that is not in the corpus")
            score = raw.get("score")
            if score is not None and (isinstance(score, bool) or not isinstance(score, int | float)):
                raise ContractError(f"{self.arm_id} returned a score that is not a number")
            if raw["chunk_id"] in seen:
                continue
            seen.add(raw["chunk_id"])
            hits.append(
                {"chunk_id": raw["chunk_id"], "score": None if score is None else float(score),
                 "relation": self._relation(raw.get("relation"))}
            )  # fmt: skip
        if len(hits) > wanted:
            raise ContractError(f"{self.arm_id} returned more hits than were asked for")
        return hits

    def _relation(self, raw: Any) -> dict[str, Any] | None:
        """A comparator's edge with its supporting chunk ids rewritten as citations (document, and clause if one)."""
        if raw is None:
            return None
        if not isinstance(raw, dict) or not isinstance(raw.get("supporting_ids"), list):
            raise ContractError(f"{self.arm_id} returned a relation outside the protocol")
        citations = []
        for chunk_id in raw["supporting_ids"]:
            chunk = self._chunks.get(chunk_id)
            if chunk is None:
                raise ContractError(f"{self.arm_id} supports a relation with a chunk that is not in the corpus")
            citations.append(f"{chunk.doc_id}#{chunk.clauses[0]}" if len(chunk.clauses) == 1 else chunk.doc_id)
        return {**raw, "supporting_ids": sorted(set(citations))}

    def index_stats(self) -> dict[str, Any]:
        return dict(self._stats)

    def describe(self) -> dict[str, Any]:
        return {
            "arm": self.arm_id,
            "kind": "third-party comparator in an isolated worker",
            "comparator": self._pin.to_dict(),
            "models": dict(self._models),
            "unsupported": list(self._unsupported),
            "chunk_words": self._chunk_words,
            "condition": self._condition.value,
        }

    def call_flags(self) -> tuple[str, ...]:
        notes = self.last_notes
        return (*flags_from_notes(notes), f"QUERY_LLM_CALLS={notes.get('query_llm_calls', 0)}")

    def close(self) -> None:
        self._worker.stop()


def _directory_bytes(path: Path | None) -> int | None:
    if path is None or not path.is_dir():
        return None
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def launch_arm(
    arm_id: str,
    *,
    script: Path,
    interpreter: Path,
    server: ProxyServer,
    pin: ComparatorPin,
    view: PublishedView,
    work_dir: Path,
    llm_model: str,
    embedding_model: str,
    unsupported: Sequence[str] = (),
    condition: Condition = Condition.C2,
    chunk_words: int = DEFAULT_CHUNK_WORDS,
    build_timeout: float = 3600.0,
    query_timeout: float = 120.0,
) -> WorkerArm:
    """Start a comparator's worker in its own environment, wired to the proxy, and return the arm that drives it.

    The worker gets the proxy's address and per-run token, the two model names, and the directory holding
    the path of ``comparators/protocol.py`` in ``COMPARATOR_PROTOCOL``. It never gets the provider key.
    """
    env = server.environment(llm_model=llm_model, embedding_model=embedding_model)
    comparators = Path(__file__).resolve().parents[2] / "comparators"
    # Not PYTHONPATH: a directory named like the package (comparators/lightrag) would shadow the installed one.
    env["COMPARATOR_PROTOCOL"] = str(comparators / "protocol.py")
    # The only files a comparator may need from outside are the two tokenizer encodings the owner approved (OQ14),
    # already in this cache; everything else that would fetch from the network is switched off.
    env["TIKTOKEN_CACHE_DIR"] = str(
        Path(__file__).resolve().parents[2] / "artifacts" / "comparators" / "tiktoken-cache"
    )
    env.update(
        {
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "ANONYMIZED_TELEMETRY": "False",
            "DO_NOT_TRACK": "1",
            "LITELLM_LOCAL_MODEL_COST_MAP": "True",
        }
    )
    work_dir.mkdir(parents=True, exist_ok=True)
    worker = ComparatorWorker(
        python_worker_argv(script, interpreter), cwd=work_dir, stderr_path=work_dir / "worker.stderr", env=env
    )
    worker.start()
    return WorkerArm(
        arm_id,
        worker,
        pin,
        view=view,
        work_dir=work_dir,
        models={"llm": llm_model, "embeddings": embedding_model},
        usage=server.usage,
        condition=condition,
        chunk_words=chunk_words,
        unsupported=unsupported,
        build_timeout=build_timeout,
        query_timeout=query_timeout,
    )


def python_worker_argv(script: Path, interpreter: Path | None = None) -> list[str]:
    """The command that runs a worker script with a given interpreter (this one by default)."""
    return [str(interpreter or sys.executable), "-u", str(script)]
