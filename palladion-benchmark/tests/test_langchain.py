"""E0: LangChain's in-memory vector store behind the worker, over real S-tier chunks (B07-T01.01, BADR-0040).

Every test runs the real LangChain components in ``artifacts/comparators/env-langchain``. There is no chat model in this
arm: the proxy serves the benchmark's local embedding stand-in (``HashingEncoder``), and a provider that fails if it is
ever called shows that nothing else leaves the process. No network is used except the loopback proxy.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from support import HashingEncoder

from benchmark.adapters.common import AccessFilter, Condition, PublishedView, build_chunks
from benchmark.adapters.langchain import UNSUPPORTED, build_langchain_arm
from benchmark.adapters.worker import ComparatorWorker, WorkerArm, WorkerError, python_worker_argv
from benchmark.contracts import RetrievalRequest
from benchmark.generator import TransportResponse
from benchmark.llm_proxy import CountingProxy, ProxyLimits, ProxyServer
from benchmark.run_manifest import ComparatorPin

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "comparators" / "langchain" / "worker.py"
PROTOCOL = ROOT / "comparators" / "protocol.py"
INTERPRETER = ROOT / "artifacts" / "comparators" / "env-langchain" / "Scripts" / "python.exe"
MODEL = "qwen/qwen3.8-27b"
EMBED = "paraphrase-multilingual-MiniLM-L12-v2"
TOKEN = "t" * 24
PIN = ComparatorPin.from_dict(
    {
        "repository": "https://pypi.org/project/langchain-core/",
        "commit": "",
        "lock_sha256": "d" * 64,
        "interpreter": "3.12.15",
        "native_config": {},
        "deviations": [],
        "packages": {"langchain-core": "1.6.7", "langgraph": "1.2.14"},
    }
)

pytestmark = pytest.mark.skipif(not INTERPRETER.is_file(), reason="the framework environment is not installed")


class NoChat:
    """A provider that must never be called: this arm makes no chat request."""

    def __init__(self) -> None:
        self.payloads: list[Any] = []

    def post(self, payload: Any) -> TransportResponse:
        self.payloads.append(payload)
        raise AssertionError("E0 made a chat request")


@pytest.fixture
def provider() -> NoChat:
    return NoChat()


@pytest.fixture
def server(tmp_path: Path, provider: NoChat) -> Iterator[ProxyServer]:
    limits = ProxyLimits(max_calls=10, max_tokens=100_000, max_completion_tokens=700, pace_seconds=0.0, models=(MODEL,))
    proxy = CountingProxy(
        provider,
        limits,
        record_path=tmp_path / "proxy.jsonl",
        embedder=HashingEncoder().embed_documents,
        embedding_model=EMBED,
    )
    running = ProxyServer(proxy, token=TOKEN)
    running.start()
    yield running
    running.stop()


def small_view(s_root: Path, documents: int = 3) -> PublishedView:
    full = PublishedView.load(s_root / "published")
    records = list(full.records[:documents])
    texts = {r.doc_id: full.document(r.doc_id).text for r in records}
    return PublishedView(full.root, records, full.identity, texts)


def request(view: PublishedView, query: str, limit: int = 5, principal: str | None = None) -> RetrievalRequest:
    who = principal or view.identity.principals[0].principal_id
    return RetrievalRequest("q-0123456789abcdef", query, who, "snap-1", "2026-10-18T03:00:00Z", None, {}, limit, 4000)


def arm_over(tmp_path: Path, server: ProxyServer, view: PublishedView, **kwargs: Any) -> WorkerArm:
    arm = build_langchain_arm(
        interpreter=INTERPRETER,
        server=server,
        pin=PIN,
        view=view,
        work_dir=tmp_path / "work",
        llm_model=MODEL,
        embedding_model=EMBED,
        build_timeout=300.0,
        query_timeout=120.0,
        **kwargs,
    )
    arm.build_index(str(view.root), "track_a")
    return arm


def test_the_chunk_a_query_repeats_is_ranked_first_by_the_real_vector_store(
    tmp_path: Path, s_root: Path, server: ProxyServer
) -> None:
    view = small_view(s_root)
    chunks = build_chunks(view)
    arm = arm_over(tmp_path, server, view)
    target = chunks[len(chunks) // 2]
    got = arm.retrieve(request(view, target.text))
    arm.close()
    assert got and got[0].additional_metadata["chunk_id"] == target.chunk_id
    scores = [c.native_score for c in got]
    ranked = [s for s in scores if s is not None]
    assert len(ranked) == len(scores) and ranked == sorted(ranked, reverse=True)


def test_building_costs_only_embeddings_and_the_pin_records_what_ran(
    tmp_path: Path, s_root: Path, server: ProxyServer, provider: NoChat
) -> None:
    view = small_view(s_root)
    arm = arm_over(tmp_path, server, view)
    stats = arm.index_stats()
    description = arm.describe()
    arm.close()
    assert stats["extraction_calls"] == 0 and stats["embedding_inputs"] == len(build_chunks(view))
    assert provider.payloads == []
    native = stats["native"]
    assert native["vector_store"] == "InMemoryVectorStore" and native["framework"]["langgraph"] == "1.2.14"
    assert description["comparator"]["packages"]["langgraph"] == "1.2.14"
    assert any("shared 120-word chunker" in d for d in description["comparator"]["deviations"])


def test_the_arm_declares_the_unsupported_affordances(tmp_path: Path, s_root: Path, server: ProxyServer) -> None:
    arm = arm_over(tmp_path, server, small_view(s_root))
    description = arm.describe()
    arm.close()
    assert tuple(UNSUPPORTED) == ("ACL_FILTER", "AS_OF_FILTER") == tuple(description["unsupported"])


def restricted_view(s_root: Path) -> tuple[PublishedView, str, str, str]:
    full = PublishedView.load(s_root / "published")
    access = AccessFilter(full, Condition.C2)
    hidden = next(
        r for r in full.records if any(not access.allows(p.principal_id, r.doc_id) for p in full.identity.principals)
    )
    records = [hidden, *[r for r in full.records if r.doc_id != hidden.doc_id][:2]]
    view = PublishedView(full.root, records, full.identity, {r.doc_id: full.document(r.doc_id).text for r in records})
    local = AccessFilter(view, Condition.C2)
    denied = next(p.principal_id for p in view.identity.principals if not local.allows(p.principal_id, hidden.doc_id))
    allowed = next(p.principal_id for p in view.identity.principals if local.allows(p.principal_id, hidden.doc_id))
    return view, hidden.doc_id, denied, allowed


def test_the_access_filter_acts_after_the_store_ranking_and_says_how_many_it_dropped(
    tmp_path: Path, s_root: Path, server: ProxyServer
) -> None:
    view, hidden, denied, allowed = restricted_view(s_root)
    arm = arm_over(tmp_path, server, view)
    query = next(c.text for c in build_chunks(view) if c.doc_id == hidden)  # a chunk of the hidden document
    allowed_result = arm.retrieve(request(view, query, limit=20, principal=allowed))
    filtered = arm.retrieve(request(view, query, limit=20, principal=denied))
    dropped = arm.last_notes["filtered_after_ranking"]
    arm.close()
    assert hidden in {c.source_document_id for c in allowed_result}, "the probe must reach the hidden document"
    assert hidden not in {c.source_document_id for c in filtered} and dropped >= 1


def test_the_hits_respect_the_limit_and_a_blank_query_is_refused_by_the_worker(
    tmp_path: Path, s_root: Path, server: ProxyServer
) -> None:
    view = small_view(s_root)
    arm = arm_over(tmp_path, server, view)
    assert len(arm.retrieve(request(view, "Meridian Switchworks warranty terms", limit=2))) <= 2
    arm.close()


def raw_worker(tmp_path: Path, server: ProxyServer) -> ComparatorWorker:
    env = server.environment(llm_model=MODEL, embedding_model=EMBED)
    env["COMPARATOR_PROTOCOL"] = str(PROTOCOL)
    worker = ComparatorWorker(
        python_worker_argv(WORKER, INTERPRETER), cwd=tmp_path, stderr_path=tmp_path / "worker.stderr", env=env
    )
    worker.start()
    return worker


def write_corpus(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return path


def test_a_corpus_that_is_malformed_or_has_duplicate_chunk_ids_is_refused_and_a_query_before_a_build_too(
    tmp_path: Path, server: ProxyServer
) -> None:
    worker = raw_worker(tmp_path, server)
    try:
        with pytest.raises(WorkerError, match="LangChainFault"):
            worker.request("retrieve", {"query": "anything", "limit": 3}, timeout=120)
        bad = write_corpus(tmp_path / "bad.jsonl", [{"chunk_id": "c-1", "doc_id": "d-1"}])
        with pytest.raises(WorkerError, match="LangChainFault"):
            worker.request("build", {"corpus": str(bad), "workdir": str(tmp_path / "n"), "namespace": "x"}, timeout=120)
        dup = write_corpus(
            tmp_path / "dup.jsonl",
            [{"chunk_id": "c-1", "doc_id": "d-1", "text": "one"}, {"chunk_id": "c-1", "doc_id": "d-2", "text": "two"}],
        )
        with pytest.raises(WorkerError, match="LangChainFault"):
            worker.request("build", {"corpus": str(dup), "workdir": str(tmp_path / "n"), "namespace": "x"}, timeout=120)
        ok = write_corpus(
            tmp_path / "ok.jsonl",
            [
                {"chunk_id": "c-1", "doc_id": "d-1", "text": "routers"},
                {"chunk_id": "c-2", "doc_id": "d-2", "text": "switches"},
            ],
        )
        built = worker.request(
            "build", {"corpus": str(ok), "workdir": str(tmp_path / "n"), "namespace": "x"}, timeout=120
        )
        assert built["documents"] == 2
        for bad_params in ({"query": "  ", "limit": 3}, {"query": "routers", "limit": 0}):
            with pytest.raises(WorkerError, match="LangChainFault"):
                worker.request("retrieve", bad_params, timeout=120)
        hits = worker.request("retrieve", {"query": "routers", "limit": 2}, timeout=120)["hits"]
        assert hits[0]["chunk_id"] == "c-1" and all(h["relation"] is None for h in hits)
    finally:
        worker.stop()


def test_the_worker_cannot_reach_a_host_outside_loopback(tmp_path: Path, server: ProxyServer) -> None:
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import importlib.util, os, socket\n"
        "spec = importlib.util.spec_from_file_location('p', os.environ['COMPARATOR_PROTOCOL'])\n"
        "p = importlib.util.module_from_spec(spec); spec.loader.exec_module(p); p.guard_network()\n"
        "try:\n    socket.create_connection(('example.com', 9), timeout=2); print('CONNECTED')\n"
        "except p.NetworkRefused:\n    print('REFUSED')\n",
        encoding="utf-8",
    )
    import subprocess

    done = subprocess.run(
        [str(INTERPRETER), "-I", str(probe)], capture_output=True, text=True, timeout=60, check=False,
        env={"COMPARATOR_PROTOCOL": str(PROTOCOL), "SYSTEMROOT": "C:\\Windows"},
    )  # fmt: skip
    assert done.stdout.strip() == "REFUSED", done.stderr
