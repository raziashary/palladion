"""The comparator worker: bounded, killable, keyless, and metered by the proxy (B06-T00.02, BR14, BR36)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from benchmark.adapters.common import AccessFilter, AdapterError, Condition, PublishedView, build_chunks
from benchmark.adapters.worker import ComparatorWorker, WorkerArm, WorkerError, python_worker_argv
from benchmark.contracts import ArmUnavailable, ContractError, RetrievalRequest, RunStatus
from benchmark.generator import TransportResponse
from benchmark.llm_proxy import CountingProxy, ProxyError, ProxyLimits, ProxyServer
from benchmark.results_check import validate_run
from benchmark.run_manifest import ComparatorPin
from benchmark.runner import RunLedger
from benchmark.track_a import RunSpec, execute

STUB = Path(__file__).resolve().parent / "comparator_stub.py"
MODEL = "qwen/qwen3.8-27b"
TOKEN = "t" * 24
PIN = ComparatorPin.from_dict(
    {"repository": "https://github.com/example/stub", "commit": "c" * 40, "lock_sha256": "d" * 64,
     "interpreter": "3.12.5", "native_config": {"mode": "stub"}, "deviations": []}
)  # fmt: skip


def new_worker(tmp_path: Path, env: dict[str, str] | None = None, **kwargs: Any) -> ComparatorWorker:
    return ComparatorWorker(
        python_worker_argv(STUB), cwd=tmp_path, stderr_path=tmp_path / "worker.stderr", env=env, **kwargs
    )


@pytest.fixture
def worker(tmp_path: Path) -> Iterator[ComparatorWorker]:
    w = new_worker(tmp_path)
    w.start()
    yield w
    w.stop()


def alive(pid: int) -> bool:
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, check=False)
        return str(pid) in out.stdout
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


# --------------------------------------------------------------------------- the protocol


def write_corpus(tmp_path: Path) -> dict[str, str]:
    corpus = tmp_path / "corpus.jsonl"
    rows = [{"chunk_id": f"D{i}#0-9", "doc_id": f"D{i}", "text": f"alpha window {i}"} for i in range(1, 5)]
    corpus.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return {"corpus": str(corpus), "workdir": str(tmp_path / "native")}


def test_a_request_gets_its_reply_and_a_library_print_does_not_corrupt_the_stream(
    worker: ComparatorWorker, tmp_path: Path
) -> None:
    assert worker.request("build", write_corpus(tmp_path), timeout=20) == {"chunks": 4}
    hits = worker.request("retrieve", {"query": "alpha window", "limit": 2}, timeout=20)["hits"]
    assert len(hits) == 2 and set(hits[0]) == {"chunk_id", "score"}


def test_stop_ends_the_process(tmp_path: Path) -> None:
    w = new_worker(tmp_path)
    w.start()
    assert w.alive
    w.stop()
    assert not w.alive
    with pytest.raises(WorkerError) as caught:
        w.request("reply", {"value": 1}, timeout=5)
    assert caught.value.code == "WORKER_DEAD"


def test_an_unknown_op_is_an_error_by_name_and_the_worker_stays_usable(worker: ComparatorWorker) -> None:
    with pytest.raises(WorkerError) as caught:
        worker.request("teleport", {}, timeout=20)
    assert caught.value.code == "WORKER_LookupError" and worker.alive
    assert worker.request("reply", {"value": [1]}, timeout=20) == [1]


def test_a_failure_reports_the_exception_type_only_never_its_text(worker: ComparatorWorker) -> None:
    with pytest.raises(WorkerError) as caught:
        worker.request("boom", {}, timeout=20)
    assert caught.value.code == "WORKER_ValueError" and "CANARY" not in str(caught.value)
    assert worker.alive


# --------------------------------------------------------------------------- bounds


def test_a_hung_worker_is_killed_at_the_timeout_with_its_children(tmp_path: Path) -> None:
    w = new_worker(tmp_path)
    w.start()
    child = w.request("spawn", {}, timeout=20)["child_pid"]
    assert alive(child)
    began = time.monotonic()
    with pytest.raises(WorkerError) as caught:
        w.request("hang", {}, timeout=1.5)
    assert caught.value.code == "TIMEOUT" and time.monotonic() - began < 15
    assert not w.alive
    for _ in range(50):
        if not alive(child):
            break
        time.sleep(0.1)
    assert not alive(child), "the whole process tree is gone, not only the worker"
    w.stop()


def test_a_worker_that_exits_is_reported_as_exited(tmp_path: Path) -> None:
    w = new_worker(tmp_path)
    w.start()
    with pytest.raises(WorkerError) as caught:
        w.request("crash", {}, timeout=20)
    assert caught.value.code in {"EXITED", "TIMEOUT"} and not w.alive
    w.stop()


def test_a_reply_over_the_size_limit_kills_the_worker(tmp_path: Path) -> None:
    w = new_worker(tmp_path, max_line_bytes=10_000)
    w.start()
    with pytest.raises(WorkerError) as caught:
        w.request("big", {"bytes": 50_000}, timeout=20)
    assert caught.value.code == "REPLY_TOO_LARGE" and not w.alive
    w.stop()


def test_a_flood_of_non_protocol_lines_is_a_fault(tmp_path: Path) -> None:
    w = new_worker(tmp_path)
    w.start()
    with pytest.raises(WorkerError) as caught:
        w.request("noisy", {"lines": 1500}, timeout=20)
    assert caught.value.code == "TOO_MUCH_NOISE" and not w.alive
    w.stop()


def test_a_few_stray_lines_are_ignored(worker: ComparatorWorker) -> None:
    assert worker.request("noisy", {"lines": 5}, timeout=20) == "done"


# --------------------------------------------------------------------------- the key never reaches a worker


def test_the_workers_environment_holds_only_the_allowed_names_and_none_of_the_parents_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "gsk_PARENT_SECRET_CANARY")
    monkeypatch.setenv("SOME_TOKEN", "parent-token")
    w = new_worker(tmp_path, env={"OPENAI_BASE_URL": "http://127.0.0.1:1/v1", "OPENAI_API_KEY": TOKEN})
    w.start()
    names = w.request("environment", {}, timeout=20)
    w.stop()
    assert "GROQ_API_KEY" not in names and "SOME_TOKEN" not in names
    assert {"OPENAI_BASE_URL", "OPENAI_API_KEY"} <= set(names)


def test_stderr_is_kept_in_a_file_and_holds_no_protocol(tmp_path: Path) -> None:
    w = new_worker(tmp_path)
    w.start()
    with pytest.raises(WorkerError):
        w.request("boom", {}, timeout=20)
    w.stop()
    assert "ValueError" in (tmp_path / "worker.stderr").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- spend is metered outside the worker


class Provider:
    def __init__(self) -> None:
        self.calls = 0

    def post(self, payload: Any) -> TransportResponse:
        self.calls += 1
        body = {"model": MODEL, "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60}}  # fmt: skip
        return TransportResponse(200, {}, json.dumps(body).encode())


def served(provider: Provider, tmp_path: Path, **over: Any) -> ProxyServer:
    base: dict[str, Any] = {"max_calls": 4, "max_tokens": 100_000, "max_completion_tokens": 700, "pace_seconds": 0.0,
                            "models": (MODEL,)}  # fmt: skip
    proxy = CountingProxy(provider, ProxyLimits(**{**base, **over}), record_path=tmp_path / "proxy.jsonl")
    return ProxyServer(proxy, token=TOKEN)


def env_for(server: ProxyServer) -> dict[str, str]:
    return {"OPENAI_BASE_URL": server.base_url, "OPENAI_API_KEY": TOKEN}


def test_a_runaway_comparator_is_stopped_at_the_call_cap(tmp_path: Path) -> None:
    provider = Provider()
    with served(provider, tmp_path) as server:
        w = new_worker(tmp_path, env=env_for(server))
        w.start()
        statuses = w.request("spend", {"n": 30, "model": MODEL}, timeout=60)
        w.stop()
    assert statuses == {"200": 4, "403": 26} and provider.calls == 4


def test_a_killed_workers_spend_is_still_counted_and_still_capped(tmp_path: Path) -> None:
    provider = Provider()
    with served(provider, tmp_path, max_calls=3) as server:
        w = new_worker(tmp_path, env=env_for(server))
        w.start()
        with pytest.raises(WorkerError) as caught:
            w.request("spend", {"n": 1000, "model": MODEL, "pause": 0.2}, timeout=2.0)
        assert caught.value.code == "TIMEOUT"
        w.stop()
        counted = server._proxy.usage()["calls"]
    assert counted == provider.calls and 1 <= counted <= 3


def test_the_key_the_worker_holds_is_the_run_token_and_not_the_provider_key(tmp_path: Path) -> None:
    with served(Provider(), tmp_path) as server:
        env = env_for(server)
    assert env["OPENAI_API_KEY"] == TOKEN and "gsk_" not in json.dumps(env)


# --------------------------------------------------------------------------- the arm


class Scripted:
    """A worker whose replies are set by the test, to exercise the arm's own checks."""

    def __init__(self, reply: Any) -> None:
        self.reply = reply
        self.asked: list[tuple[str, dict[str, Any]]] = []

    def request(self, op: str, params: Any, *, timeout: float) -> Any:
        self.asked.append((op, dict(params)))
        return {"chunks": 0} if op == "build" else self.reply

    def stop(self) -> None: ...


def view_of(s_root: Path) -> PublishedView:
    return PublishedView.load(s_root / "published")


def hit(chunk_id: str, score: Any = 1.0, **extra: Any) -> dict[str, Any]:
    return {"chunk_id": chunk_id, "score": score, **extra}


def arm_over(
    worker: Any, s_root: Path, tmp_path: Path, *, usage: Any = dict, condition: Condition = Condition.C2
) -> WorkerArm:
    arm = WorkerArm(
        "R4", worker, PIN, view=view_of(s_root), work_dir=tmp_path / "work", models={"extraction": MODEL},
        usage=usage, condition=condition, query_timeout=30.0,
    )  # fmt: skip
    arm.build_index(str(s_root / "published"), "track_a")
    return arm


def request(view: PublishedView, query: str = "what is the window", limit: int = 10, budget: int = 4000) -> Any:
    principal = view.identity.principals[0].principal_id
    return RetrievalRequest(
        "q-0123456789abcdef", query, principal, "snap-1", "2026-10-18T03:00:00Z", None, {}, limit, budget
    )


def first_chunks(view: PublishedView, n: int, doc_ids: set[str] | None = None) -> list[Any]:
    chunks = [c for c in build_chunks(view) if doc_ids is None or c.doc_id in doc_ids]
    return chunks[:n]


def make_arm(
    tmp_path: Path, server: ProxyServer, s_root: Path, env: dict[str, str] | None = None, **kwargs: Any
) -> WorkerArm:
    w = new_worker(tmp_path, env={**env_for(server), **(env or {})})
    w.start()
    return WorkerArm(
        "R4", w, PIN, view=view_of(s_root), work_dir=tmp_path / "work", models={"extraction": MODEL},
        usage=server._proxy.usage, **kwargs,
    )  # fmt: skip


def test_the_comparator_is_handed_the_shared_chunks_and_nothing_else(tmp_path: Path, s_root: Path) -> None:
    worker = Scripted({"hits": []})
    arm = arm_over(worker, s_root, tmp_path)
    ((op, params),) = worker.asked
    assert op == "build" and set(params) == {"corpus", "workdir", "namespace"}
    rows = [json.loads(line) for line in Path(params["corpus"]).read_text(encoding="utf-8").splitlines()]
    shared = build_chunks(view_of(s_root))
    assert [r["chunk_id"] for r in rows] == [c.chunk_id for c in shared] and set(rows[0]) == {
        "chunk_id",
        "doc_id",
        "text",
    }
    assert arm.index_stats()["chunks"] == len(shared)


def test_a_corpus_with_a_gold_like_marker_is_refused_before_the_comparator_sees_it(
    tmp_path: Path, s_root: Path
) -> None:
    clean = view_of(s_root)
    doc = clean.documents()[0]
    tainted = PublishedView(
        clean.root, clean.records, clean.identity, {r.doc_id: clean.document(r.doc_id).text for r in clean.records}
    )
    tainted._texts[doc.record.doc_id] += "\nthe expected answer is 24 hours"
    worker = Scripted({"hits": []})
    arm = WorkerArm("R4", worker, PIN, view=tainted, work_dir=tmp_path / "work", models={}, usage=dict)  # type: ignore[arg-type]
    with pytest.raises(AdapterError, match="gold-like"):
        arm.build_index(str(clean.root), "track_a")
    assert worker.asked == [], "the worker was never contacted"


def test_a_build_from_another_directory_is_refused(tmp_path: Path, s_root: Path) -> None:
    arm = WorkerArm("R4", Scripted({}), PIN, view=view_of(s_root), work_dir=tmp_path / "w", models={}, usage=dict)  # type: ignore[arg-type]
    with pytest.raises(AdapterError, match="this arm was created with"):
        arm.build_index(str(tmp_path), "track_a")
    with pytest.raises(AdapterError, match="build_index must run"):
        arm.retrieve(request(view_of(s_root)))


def test_the_arm_reports_only_the_extraction_the_proxy_counted_during_the_build(tmp_path: Path, s_root: Path) -> None:
    provider = Provider()
    with served(provider, tmp_path, max_calls=10) as server:
        server._proxy.chat(json.dumps({"model": MODEL, "messages": [{"role": "user", "content": "before"}]}).encode())
        arm = make_arm(tmp_path, server, s_root, env={"STUB_BUILD_CALLS": "3", "STUB_MODEL": MODEL})
        arm.build_index(str(s_root / "published"), "track_a")
        stats = arm.index_stats()
        arm.close()
    assert stats["extraction_calls"] == 3 and stats["extraction_prompt_tokens"] == 150
    assert stats["extraction_completion_tokens"] == 30 and provider.calls == 4
    assert stats["build_ms"] > 0 and stats["build_cost_usd"] is None and stats["storage_bytes"] == 100
    assert stats["chunks"] > 0 and stats["native"] == {"chunks": stats["chunks"]}


def test_hits_become_candidates_with_harness_provenance_and_renumbered_ranks(tmp_path: Path, s_root: Path) -> None:
    view = view_of(s_root)
    chunks = first_chunks(view, 4)
    worker = Scripted(
        {"hits": [hit(chunks[2].chunk_id, 0.9), hit(chunks[0].chunk_id, 0.5), hit(chunks[3].chunk_id, None)]}
    )
    arm = arm_over(worker, s_root, tmp_path, condition=Condition.C1)
    got = arm.retrieve(request(view))
    assert [c.rank for c in got] == [1, 2, 3] and [c.native_score for c in got] == [0.9, 0.5, None]
    assert [c.additional_metadata["chunk_id"] for c in got] == [
        chunks[2].chunk_id,
        chunks[0].chunk_id,
        chunks[3].chunk_id,
    ]
    assert all(c.retrieval_channel == "R4" and c.source_document_id and c.source_sha256 and c.locator for c in got)
    assert all(c.relation is None for c in got)
    assert worker.asked[-1] == ("retrieve", {"query": "what is the window", "limit": 30})


def test_the_comparator_is_asked_for_more_hits_than_wanted_because_the_filter_acts_afterwards(
    tmp_path: Path, s_root: Path
) -> None:
    worker = Scripted({"hits": []})
    arm = arm_over(worker, s_root, tmp_path)
    arm.retrieve(request(view_of(s_root), limit=5))
    arm.retrieve(request(view_of(s_root), limit=80))
    assert [p["limit"] for op, p in worker.asked if op == "retrieve"] == [15, 100]


def test_a_document_the_principal_may_not_read_is_dropped_after_ranking_and_the_drop_is_flagged(
    tmp_path: Path, s_root: Path
) -> None:
    view = view_of(s_root)
    access = AccessFilter(view, Condition.C2)
    principal, hidden = next(
        (p.principal_id, d.record.doc_id)
        for p in view.identity.principals
        for d in view.documents()
        if not access.allows(p.principal_id, d.record.doc_id)
    )
    shown = next(d.record.doc_id for d in view.documents() if access.allows(principal, d.record.doc_id))
    hidden_chunk, shown_chunk = first_chunks(view, 1, {hidden})[0], first_chunks(view, 1, {shown})[0]
    worker = Scripted({"hits": [hit(hidden_chunk.chunk_id, 9.0), hit(shown_chunk.chunk_id, 1.0)]})
    arm = arm_over(worker, s_root, tmp_path)
    asked = RetrievalRequest("q-0123456789abcdef", "q", principal, "snap-1", "2026-10-18T03:00:00Z", None, {}, 10, 4000)
    got = arm.retrieve(asked)
    assert [c.source_document_id for c in got] == [shown] and got[0].rank == 1
    assert "FILTERED_AFTER_RANKING=1" in arm.call_flags()
    text_only = arm_over(worker, s_root, tmp_path / "c1", condition=Condition.C1)
    assert len(text_only.retrieve(asked)) == 2, "without the filter (C1) both are returned"


def test_the_common_evidence_budget_is_enforced_and_flagged(tmp_path: Path, s_root: Path) -> None:
    view = view_of(s_root)
    chunks = first_chunks(view, 3)
    worker = Scripted({"hits": [hit(c.chunk_id, 1.0) for c in chunks]})
    arm = arm_over(worker, s_root, tmp_path, condition=Condition.C1)
    got = arm.retrieve(request(view, budget=chunks[0].words + 1))
    assert len(got) == 1 and any(f.startswith("BUDGET_") for f in arm.call_flags())


def test_a_relation_travels_with_its_hit(tmp_path: Path, s_root: Path) -> None:
    view = view_of(s_root)
    chunk = first_chunks(view, 1)[0]
    edge = {"subject": "alpha", "predicate": "RELATES_TO", "object": "beta", "supporting_ids": [chunk.chunk_id]}
    arm = arm_over(
        Scripted({"hits": [hit(chunk.chunk_id, 1.0, relation=edge)]}), s_root, tmp_path, condition=Condition.C1
    )
    (got,) = arm.retrieve(request(view))
    assert got.relation is not None and got.relation["predicate"] == "RELATES_TO"


@pytest.mark.parametrize(
    "bad",
    [
        {"hits": "none"}, {}, [], "x", {"hits": [1]}, {"hits": [{"chunk_id": "no-such-chunk"}]},
        {"hits": [{"chunk_id": "x", "score": "high"}]}, {"hits": [{"chunk_id": "x", "score": True}]},
    ],
)  # fmt: skip
def test_a_reply_outside_the_protocol_or_naming_a_chunk_that_is_not_in_the_corpus_is_a_contract_error(
    tmp_path: Path, s_root: Path, bad: Any
) -> None:
    view = view_of(s_root)
    if (
        isinstance(bad, dict)
        and bad.get("hits")
        and isinstance(bad["hits"][0], dict)
        and bad["hits"][0]["chunk_id"] == "x"
    ):
        bad = {"hits": [{**bad["hits"][0], "chunk_id": first_chunks(view, 1)[0].chunk_id}]}
    arm = arm_over(Scripted(bad), s_root, tmp_path)
    with pytest.raises(ContractError):
        arm.retrieve(request(view))


def test_more_hits_than_were_asked_for_is_a_contract_error_and_a_duplicate_is_dropped(
    tmp_path: Path, s_root: Path
) -> None:
    view = view_of(s_root)
    chunks = first_chunks(view, 6)
    arm = arm_over(
        Scripted({"hits": [hit(chunks[0].chunk_id), hit(chunks[0].chunk_id), hit(chunks[1].chunk_id)]}),
        s_root, tmp_path, condition=Condition.C1,
    )  # fmt: skip
    assert [c.additional_metadata["chunk_id"] for c in arm.retrieve(request(view))] == [
        chunks[0].chunk_id,
        chunks[1].chunk_id,
    ]
    greedy = arm_over(
        Scripted({"hits": [hit(c.chunk_id) for c in chunks]}), s_root, tmp_path / "g", condition=Condition.C1
    )
    with pytest.raises(ContractError, match="more hits"):
        greedy.retrieve(request(view, limit=1))


def test_a_failed_request_is_a_contract_error_but_a_dead_worker_makes_the_arm_unavailable(
    tmp_path: Path, s_root: Path
) -> None:
    class Failing:
        def __init__(self, code: str) -> None:
            self.code = code

        def request(self, op: str, params: Any, *, timeout: float) -> Any:
            if op == "build":
                return {}
            raise WorkerError(self.code)

        def stop(self) -> None: ...

    view = view_of(s_root)
    with pytest.raises(ContractError):
        arm_over(Failing("WORKER_ValueError"), s_root, tmp_path).retrieve(request(view))
    for code in ("EXITED", "WORKER_DEAD", "REPLY_TOO_LARGE"):
        with pytest.raises(ArmUnavailable, match=code):
            arm_over(Failing(code), s_root, tmp_path / code).retrieve(request(view))
    with pytest.raises(TimeoutError):  # the ledger records TIMEOUT for this, not NOT_RUN
        arm_over(Failing("TIMEOUT"), s_root, tmp_path / "TIMEOUT").retrieve(request(view))


def test_a_hung_comparator_is_a_timeout_and_the_arm_is_unavailable_after_it(tmp_path: Path, s_root: Path) -> None:
    with served(Provider(), tmp_path) as server:
        arm = make_arm(tmp_path, server, s_root, query_timeout=1.5)
        arm.build_index(str(s_root / "published"), "track_a")
        view = view_of(s_root)
        with pytest.raises(TimeoutError):
            arm.retrieve(request(view, query="HANG"))
        with pytest.raises(ArmUnavailable, match="WORKER_DEAD"):
            arm.retrieve(request(view))
        arm.close()


def test_the_arm_describes_its_pin_models_and_what_it_cannot_do(tmp_path: Path, s_root: Path) -> None:
    scripted: Any = Scripted({})
    arm = WorkerArm(
        "R4", scripted, PIN, view=view_of(s_root), work_dir=tmp_path / "w", models={"extraction": MODEL},
        usage=dict, unsupported=["acl_filter inside the method"],
    )  # fmt: skip
    described = arm.describe()
    assert described["comparator"]["commit"] == "c" * 40 and described["models"] == {"extraction": MODEL}
    assert described["unsupported"] == ["acl_filter inside the method"] and described["condition"] == "C2"


def test_the_worker_arm_runs_through_the_real_runner_and_validates(tmp_path: Path, s_root: Path) -> None:
    provider = Provider()
    out = tmp_path / "run"
    with served(provider, tmp_path) as server:
        arm = make_arm(tmp_path, server, s_root)
        view = view_of(s_root)
        arm.build_index(str(view.root), "track_a")
        builds = [{"arm": "R4", "status": "BUILT", "stats": arm.index_stats()}]
        execute(RunSpec("run-w-0001", "smoke", Condition.C2, 10, 4000, s_root, out), {"R4": arm}, builds=builds)
        arm.close()
    finals = [r for r in RunLedger(out / "ledger.jsonl").records if r.is_final]
    assert finals and {r.status for r in finals} == {RunStatus.OK}
    assert "QUERY_LLM_CALLS=0" in {f for r in finals for f in r.flags}
    assert validate_run(out, root=s_root) == []


def test_python_worker_argv_uses_the_given_interpreter() -> None:
    assert python_worker_argv(STUB, Path("/x/python"))[0].replace("\\", "/") == "/x/python"
    assert python_worker_argv(STUB)[0] == sys.executable


def test_launch_arm_wires_the_worker_to_the_proxy_and_records_the_models(tmp_path: Path, s_root: Path) -> None:
    from benchmark.adapters.worker import launch_arm

    with served(Provider(), tmp_path) as server:
        arm = launch_arm(
            "R4", script=STUB, interpreter=Path(sys.executable), server=server, pin=PIN, view=view_of(s_root),
            work_dir=tmp_path / "work", llm_model=MODEL, embedding_model="local-minilm", unsupported=["acl_filter"],
            condition=Condition.C1,
        )  # fmt: skip
        try:
            arm.build_index(str(s_root / "published"), "track_a")
            got = arm.retrieve(request(view_of(s_root), limit=3))
            assert len(got) == 3 and arm.describe()["models"] == {"llm": MODEL, "embeddings": "local-minilm"}
            assert arm.describe()["unsupported"] == ["acl_filter"]
        finally:
            arm.close()


def test_the_proxy_gives_a_comparator_only_its_address_token_and_model_names(tmp_path: Path) -> None:
    with served(Provider(), tmp_path) as server:
        env = server.environment(llm_model=MODEL, embedding_model="local-minilm")
        assert set(env) == {"OPENAI_BASE_URL", "OPENAI_API_KEY", "COMPARATOR_LLM_MODEL", "COMPARATOR_EMBED_MODEL"}
        assert env["OPENAI_BASE_URL"].startswith("http://127.0.0.1:") and env["OPENAI_API_KEY"] == TOKEN
        with pytest.raises(ProxyError, match="approved list"):
            server.environment(llm_model="gpt-4o", embedding_model="x")
        assert server.usage()["calls"] == 0


def test_launch_arm_gives_the_worker_the_protocol_path_and_no_pythonpath(tmp_path: Path, s_root: Path) -> None:
    """A PYTHONPATH holding comparators/ would let comparators/lightrag shadow the installed package of that name."""
    from benchmark.adapters.worker import launch_arm

    with served(Provider(), tmp_path) as server:
        arm = launch_arm(
            "R4", script=STUB, interpreter=Path(sys.executable), server=server, pin=PIN, view=view_of(s_root),
            work_dir=tmp_path / "work", llm_model=MODEL, embedding_model="local-minilm",
        )  # fmt: skip
        try:
            names = arm._worker.request("environment", {}, timeout=20)
        finally:
            arm.close()
    assert "COMPARATOR_PROTOCOL" in names and "PYTHONPATH" not in names
    for expected in ("TIKTOKEN_CACHE_DIR", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "LITELLM_LOCAL_MODEL_COST_MAP"):
        assert expected in names


def test_a_relations_supporting_chunks_become_citations_the_graph_metrics_can_resolve(
    tmp_path: Path, s_root: Path
) -> None:
    from benchmark.eval.graph_metrics import score_edges
    from benchmark.eval.normalize import PublishedCorpus

    view = view_of(s_root)
    chunk = next(c for c in build_chunks(view) if len(c.clauses) == 1)
    wide = next(c for c in build_chunks(view) if len(c.clauses) != 1)
    edge = {"subject": "a", "predicate": "b", "object": "c", "supporting_ids": [chunk.chunk_id, wide.chunk_id]}
    arm = arm_over(
        Scripted({"hits": [hit(chunk.chunk_id, 1.0, relation=edge)]}), s_root, tmp_path, condition=Condition.C1
    )
    (got,) = arm.retrieve(request(view))
    assert got.relation is not None
    assert got.relation["supporting_ids"] == tuple(sorted({f"{chunk.doc_id}#{chunk.clauses[0]}", wide.doc_id}))
    corpus = PublishedCorpus.load(view.root)
    assert score_edges([got.relation], corpus).resolved == 1, "the citations resolve in the published corpus"


@pytest.mark.parametrize(
    "bad", [{"subject": "a"}, {"supporting_ids": "x"}, {"supporting_ids": ["no-such-chunk"]}, "edge"]
)
def test_a_malformed_relation_or_one_citing_a_chunk_outside_the_corpus_is_a_contract_error(
    tmp_path: Path, s_root: Path, bad: Any
) -> None:
    view = view_of(s_root)
    chunk = build_chunks(view)[0]
    arm = arm_over(
        Scripted({"hits": [hit(chunk.chunk_id, 1.0, relation=bad)]}), s_root, tmp_path, condition=Condition.C1
    )
    with pytest.raises(ContractError):
        arm.retrieve(request(view))


def test_the_pin_records_what_actually_ran_once_the_index_is_built(tmp_path: Path, s_root: Path) -> None:
    class Reporting(Scripted):
        def request(self, op: str, params: Any, *, timeout: float) -> Any:
            if op == "build":
                return {"mode": "hybrid", "deviations": ["no rerank model"], "llm": MODEL}
            return super().request(op, params, timeout=timeout)

    arm = arm_over(Reporting({"hits": []}), s_root, tmp_path)
    comparator = arm.describe()["comparator"]
    assert comparator["native_config"] == {"mode": "hybrid", "llm": MODEL}
    assert comparator["deviations"] == ["no rerank model"]
    assert comparator["commit"] == "c" * 40 and ComparatorPin.from_dict(comparator).lock_sha256 == "d" * 64


def test_the_worker_is_given_absolute_paths_because_it_runs_in_another_directory(
    tmp_path: Path, s_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    worker = Scripted({"hits": []})
    arm = WorkerArm("R4", worker, PIN, view=view_of(s_root), work_dir=Path("relative-work"), models={}, usage=dict)  # type: ignore[arg-type]
    arm.build_index(str(s_root / "published"), "track_a")
    ((_, params),) = worker.asked
    assert Path(params["corpus"]).is_absolute() and Path(params["workdir"]).is_absolute()
    assert Path(params["corpus"]).is_file()


# ------------------------------------------------------------------ the process is loopback-only; no key is read


NETWORK_PROBE = """
import importlib.util, socket, sys
spec = importlib.util.spec_from_file_location("p", {protocol!r})
p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p)
p.guard_network()
for host, port in (("example.com", 9), ("127.0.0.1", 9)):
    try:
        socket.create_connection((host, port), timeout=2)
        print(host, "CONNECTED")
    except p.NetworkRefused:
        print(host, "REFUSED")
    except OSError:
        print(host, "REACHED_NETWORK_LAYER")
"""


def test_the_protocol_guard_refuses_outside_loopback_and_lets_loopback_through() -> None:
    protocol = Path(__file__).resolve().parents[1] / "comparators" / "protocol.py"
    done = subprocess.run(
        [sys.executable, "-I", "-c", NETWORK_PROBE.format(protocol=str(protocol))],
        capture_output=True, text=True, timeout=60, check=False,
    )  # fmt: skip
    assert done.stdout.split() == ["example.com", "REFUSED", "127.0.0.1", "REACHED_NETWORK_LAYER"], done.stderr


@pytest.mark.parametrize("name", ["hipporag2", "graphrag", "lightrag"])
def test_every_comparator_worker_installs_the_guard_before_serving(name: str) -> None:
    text = (Path(__file__).resolve().parents[1] / "comparators" / name / "worker.py").read_text(encoding="utf-8")
    assert text.count("guard_network()") == 1 and text.index("guard_network()") < text.index("serve(")


def test_the_launcher_switches_off_litellm_reading_a_dotenv_file(tmp_path: Path, s_root: Path) -> None:
    from benchmark.adapters.worker import launch_arm

    with served(Provider(), tmp_path) as server:
        arm = launch_arm(
            "R4", script=STUB, interpreter=Path(sys.executable), server=server, pin=PIN, view=view_of(s_root),
            work_dir=tmp_path / "work", llm_model=MODEL, embedding_model="local-minilm",
        )  # fmt: skip
        try:
            assert arm._worker._extra_env["LITELLM_MODE"] == "PRODUCTION"
        finally:
            arm.close()


LITELLM_PROBE = """
import os, sys
lines = open({dotenv!r}, encoding="utf-8").read().splitlines()
names = {{l.split("=", 1)[0].strip() for l in lines if "=" in l and not l.lstrip().startswith("#")}}
before = set(os.environ)
import litellm
print(sorted(n for n in names if n in os.environ and n not in before))
"""


@pytest.mark.parametrize("environment", ["env-graphrag", "env-HippoRAG"])
def test_importing_litellm_in_a_comparator_environment_does_not_load_the_projects_dotenv(
    environment: str, tmp_path: Path
) -> None:
    root = Path(__file__).resolve().parents[1]
    interpreter = root / "artifacts" / "comparators" / environment / "Scripts" / "python.exe"
    if not interpreter.is_file() or not (root / ".env").is_file():
        pytest.skip("needs the comparator environment and a local .env to plant the key")
    probe = tmp_path / "probe_litellm.py"  # a script file: python-dotenv only walks up from a file, not from -c
    probe.write_text(LITELLM_PROBE.format(dotenv=str(root / ".env")), encoding="utf-8")
    base = {"PATH": os.environ.get("PATH", ""), "SYSTEMROOT": os.environ.get("SYSTEMROOT", "C:\\Windows")}

    def leaked(extra: dict[str, str]) -> str:
        done = subprocess.run(
            [str(interpreter), "-I", str(probe)], capture_output=True, text=True, timeout=600, check=False,
            env={**base, **extra}, cwd=tmp_path,
        )  # fmt: skip
        return done.stdout.strip()

    assert leaked({}) != "[]", "positive control: without the switch the import does load the key"
    assert leaked({"LITELLM_MODE": "PRODUCTION"}) == "[]"
