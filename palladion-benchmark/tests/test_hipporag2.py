"""R4, HippoRAG 2 through the isolated worker: the upstream's own pipeline runs offline (B06-T01.01, BADR-0031).

The upstream runs for real in its own environment (``artifacts/comparators/env-HippoRAG``). Its LLM and embedding calls
go through the counting proxy to a fake provider that answers from canned replies; embeddings are the benchmark's
local ``HashingEncoder``. Nothing here reaches the network or a real model.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from support import HashingEncoder

from benchmark.adapters import hipporag2
from benchmark.adapters.common import AdapterError, Condition, PublishedView, build_chunks
from benchmark.adapters.worker import ComparatorWorker, WorkerError, python_worker_argv
from benchmark.contracts import RetrievalRequest
from benchmark.generator import TransportResponse
from benchmark.llm_proxy import CountingProxy, ProxyLimits, ProxyServer
from benchmark.run_manifest import ComparatorPin

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "comparators" / "hipporag2" / "worker.py"
COMPARATORS = ROOT / "comparators"
INTERPRETER = ROOT / "artifacts" / "comparators" / "env-HippoRAG" / "Scripts" / "python.exe"
MODEL = "qwen/qwen3.8-27b"
EMBED = "local-embedding"
TOKEN = "t" * 24
PIN = ComparatorPin.from_dict(
    {"repository": "https://github.com/OSU-NLP-Group/HippoRAG", "commit": "d5c8329422e0a0b834a15874545cb6a74b4f9b26",
     "lock_sha256": "d" * 64, "interpreter": "3.12.15", "native_config": {"mode": "test"}, "deviations": []}
)  # fmt: skip
needs_env = pytest.mark.skipif(not INTERPRETER.exists(), reason="the HippoRAG environment is not installed here")


# --------------------------------------------------------------------------- a fake provider


def chat_reply(content: str) -> TransportResponse:
    body = {
        "id": "fake-1", "object": "chat.completion", "created": 0, "model": MODEL,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }  # fmt: skip
    return TransportResponse(200, {}, json.dumps(body).encode())


def candidates_of(prompt: str) -> list[list[str]]:
    """The fact candidates the upstream put in the recognition-memory prompt (after its header)."""
    marker = "[[ ## fact_before_filter ## ]]\n"
    section = prompt[prompt.rindex(marker) + len(marker) :]
    payload, _ = json.JSONDecoder().raw_decode(section)
    facts: list[list[str]] = payload["fact"]
    return facts


class Canned:
    """Extraction replies are looked up by a word in the passage; recognition memory echoes its candidates."""

    def __init__(self, extraction: dict[str, dict[str, Any]], recognition_status: int = 200) -> None:
        self.extraction = extraction
        self.recognition_status = recognition_status
        self.calls = {"extraction": 0, "recognition": 0}

    def post(self, payload: Any) -> TransportResponse:
        prompt = json.dumps(payload["messages"], ensure_ascii=False)
        if "[[ ## question ## ]]" in prompt:
            self.calls["recognition"] += 1
            if self.recognition_status != 200:
                return TransportResponse(self.recognition_status, {}, b'{"error": "fake failure"}')
            facts = candidates_of(payload["messages"][-1]["content"])
            return chat_reply(
                "[[ ## fact_after_filter ## ]]\n" + json.dumps({"fact": facts}) + "\n\n[[ ## completed ## ]]"
            )
        self.calls["extraction"] += 1
        for word, reply in self.extraction.items():
            if word in prompt:
                return chat_reply(json.dumps(reply))
        return chat_reply(json.dumps({"named_entities": [], "triples": []}))


def proxy_for(provider: Canned, tmp_path: Path) -> ProxyServer:
    limits = ProxyLimits(
        max_calls=500, max_tokens=10_000_000, max_completion_tokens=700, pace_seconds=0.0, models=(MODEL,)
    )
    proxy = CountingProxy(
        provider, limits, record_path=tmp_path / "proxy.jsonl", embedder=HashingEncoder().embed_documents,
        embedding_model=EMBED,
    )  # fmt: skip
    return ProxyServer(proxy, token=TOKEN)


def direct_worker(tmp_path: Path, server: ProxyServer) -> ComparatorWorker:
    env = server.environment(llm_model=MODEL, embedding_model=EMBED)
    env["COMPARATOR_PROTOCOL"] = str(COMPARATORS / "protocol.py")
    return ComparatorWorker(
        python_worker_argv(WORKER, INTERPRETER), cwd=tmp_path, stderr_path=tmp_path / "worker.stderr", env=env
    )  # fmt: skip


@pytest.fixture
def synthetic(tmp_path: Path) -> Iterator[tuple[ComparatorWorker, Canned, ProxyServer]]:
    """A worker over four chunks: two identical texts (D1 and D2), one with a second fact, and one with no fact."""
    rows = [
        {"chunk_id": "D1#0-9", "doc_id": "D1", "text": "Ferrin Quill signed the Lantern contract in March."},
        {"chunk_id": "D2#0-9", "doc_id": "D2", "text": "Ferrin Quill signed the Lantern contract in March."},
        {"chunk_id": "D3#0-9", "doc_id": "D3", "text": "The Harbor depot ships spare Gears to Port Yarrow."},
        {"chunk_id": "D4#0-9", "doc_id": "D4", "text": "Harbor depot notes mention Lantern in passing."},
    ]
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    canned = Canned(
        {
            "Ferrin Quill signed": {
                "named_entities": ["Ferrin Quill", "Lantern contract"],
                "triples": [["Ferrin Quill", "signed", "Lantern contract"]],
            },
            "Harbor depot ships": {
                "named_entities": ["Harbor depot", "Port Yarrow"],
                "triples": [["Harbor depot", "ships", "Port Yarrow"]],
            },
        }
    )
    server = proxy_for(canned, tmp_path)
    server.start()
    worker = direct_worker(tmp_path, server)
    worker.start()
    yield worker, canned, server
    worker.stop()
    server.stop()


def build_synthetic(worker: ComparatorWorker, tmp_path: Path) -> dict[str, Any]:
    corpus = tmp_path / "corpus.jsonl"
    result = worker.request(
        "build", {"corpus": str(corpus), "workdir": str(tmp_path / "native"), "namespace": "t"}, timeout=600
    )
    assert isinstance(result, dict)
    return result


def retrieve(worker: ComparatorWorker, query: str, limit: int = 10) -> list[dict[str, Any]]:
    reply = worker.request("retrieve", {"query": query, "limit": limit}, timeout=120)
    hits: list[dict[str, Any]] = reply["hits"]
    return hits


# --------------------------------------------------------------------------- the factory (no environment needed)


def test_the_factory_launches_the_worker_script_with_the_declared_unsupported_affordances(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, Any] = {}

    returned = object()

    def fake_launch(arm_id: str, **kwargs: Any) -> object:
        captured["arm_id"] = arm_id
        captured["returned"] = returned
        captured.update(kwargs)
        return returned

    monkeypatch.setattr(hipporag2, "launch_arm", fake_launch)
    view = object()
    arm = hipporag2.build_hipporag2_arm(
        interpreter=tmp_path / "python", server=object(), pin=PIN, view=view,  # type: ignore[arg-type]
        work_dir=tmp_path, llm_model=MODEL, embedding_model=EMBED,
    )  # fmt: skip
    assert arm is captured["returned"] and captured["arm_id"] == "R4"
    assert captured["script"] == WORKER and WORKER.is_file()
    assert captured["unsupported"] == ("ACL_FILTER", "AS_OF_FILTER")
    assert captured["condition"] is Condition.C2 and captured["view"] is view


# --------------------------------------------------------------------------- the upstream pipeline


@needs_env
def test_the_upstream_index_and_retrieve_run_on_real_s_tier_chunks(tmp_path: Path, s_root: Path) -> None:
    clean = PublishedView.load(s_root / "published")
    subset = clean.records[:3]
    view = PublishedView(
        clean.root, subset, clean.identity, {r.doc_id: clean.document(r.doc_id).text for r in subset}
    )  # fmt: skip
    chunk_ids = {c.chunk_id for c in build_chunks(view)}
    provider = Canned({})
    server = proxy_for(provider, tmp_path)
    with server:
        arm = hipporag2.build_hipporag2_arm(
            interpreter=INTERPRETER, server=server, pin=PIN, view=view, work_dir=tmp_path / "arm",
            llm_model=MODEL, embedding_model=EMBED, build_timeout=900.0, query_timeout=300.0,
        )  # fmt: skip
        try:
            arm.build_index(str(view.root), "track_a")
            stats = arm.index_stats()
            question = view.identity.principals[0].principal_id
            request = RetrievalRequest(
                "q-0123456789abcdef", "what is the window", question, "snap-1", "2026-10-18T03:00:00Z", None, {},
                5, 4000,
            )  # fmt: skip
            got = arm.retrieve(request)
        finally:
            arm.close()
    native = stats["native"]
    assert native["hipporag_version"] == "2.0.0a5" and native["distinct_passages"] == len(chunk_ids)
    assert provider.calls["extraction"] == 2 * len(chunk_ids), "named entities and triples, one call each per chunk"
    assert provider.calls["recognition"] == 0, "no facts were extracted, so no recognition-memory call is made"
    doc_ids = {c.doc_id for c in build_chunks(view)}
    assert {c.source_document_id for c in got} <= doc_ids and 1 <= len(got) <= 5
    assert all(c.relation is None for c in got), "no fact, so no graph relation"
    assert "QUERY_LLM_CALLS=0" in arm.call_flags()


@needs_env
def test_identical_texts_stay_distinct_and_a_graph_relation_needs_both_names_in_the_hit(
    synthetic: tuple[ComparatorWorker, Canned, ProxyServer], tmp_path: Path
) -> None:
    worker, provider, _ = synthetic
    stats = build_synthetic(worker, tmp_path)
    assert stats["corpus_chunks"] == 4 and stats["distinct_passages"] == 3
    assert provider.calls["extraction"] == 2 * 3, "one NER and one triple call per distinct text"

    hits = retrieve(worker, "Who signed the Lantern contract?", limit=10)
    ids = [h["chunk_id"] for h in hits]
    assert sorted(ids) == ["D1#0-9", "D2#0-9", "D3#0-9", "D4#0-9"], "identical texts are both returned, once each"
    scores = {h["chunk_id"]: h["score"] for h in hits}
    assert scores["D1#0-9"] == scores["D2#0-9"], "identical text, identical score"
    assert ids.index("D1#0-9") < ids.index("D2#0-9"), "corpus order breaks the tie"
    assert provider.calls["recognition"] == 1, "one recognition-memory call for one query"

    by_id = {h["chunk_id"]: h["relation"] for h in hits}
    expected = {
        "subject": "ferrin quill", "predicate": "signed", "object": "lantern contract",
        "supporting_ids": ["D1#0-9", "D2#0-9"],
    }  # fmt: skip
    assert by_id["D1#0-9"] == expected and by_id["D2#0-9"] == expected
    assert by_id["D3#0-9"] == {
        "subject": "harbor depot",
        "predicate": "ships",
        "object": "port yarrow",
        "supporting_ids": ["D3#0-9"],
    }  # negative control: the second fact's names are in D3 only
    assert by_id["D4#0-9"] is None, "D4 holds one name of each fact and neither pair, so no relation"


@needs_env
def test_the_limit_is_honoured_and_a_limit_of_one_returns_one_hit(
    synthetic: tuple[ComparatorWorker, Canned, ProxyServer], tmp_path: Path
) -> None:
    worker, _, _ = synthetic
    build_synthetic(worker, tmp_path)
    assert len(retrieve(worker, "Lantern contract", limit=1)) == 1
    assert len(retrieve(worker, "Lantern contract", limit=3)) == 3


@needs_env
def test_a_failed_recognition_call_fails_the_query_instead_of_falling_back_silently(
    synthetic: tuple[ComparatorWorker, Canned, ProxyServer], tmp_path: Path
) -> None:
    worker, provider, _server = synthetic
    build_synthetic(worker, tmp_path)
    provider.recognition_status = 500
    with pytest.raises(WorkerError) as failed:
        retrieve(worker, "Who signed the Lantern contract?")
    assert failed.value.code == "WORKER_RecognitionMemoryError"
    provider.recognition_status = 200
    assert retrieve(worker, "Who signed the Lantern contract?"), (
        "the control: the same query succeeds once the fault is gone"
    )


@needs_env
def test_a_planted_gold_phrase_is_refused_before_the_upstream_is_contacted(tmp_path: Path, s_root: Path) -> None:
    clean = PublishedView.load(s_root / "published")
    doc = clean.documents()[0]
    tainted = PublishedView(
        clean.root, clean.records, clean.identity, {r.doc_id: clean.document(r.doc_id).text for r in clean.records}
    )  # fmt: skip
    tainted._texts[doc.record.doc_id] += "\nthe expected answer is 24 hours"
    server = proxy_for(Canned({}), tmp_path)
    with server:
        arm = hipporag2.build_hipporag2_arm(
            interpreter=INTERPRETER, server=server, pin=PIN, view=tainted, work_dir=tmp_path / "arm",
            llm_model=MODEL, embedding_model=EMBED,
        )  # fmt: skip
        try:
            with pytest.raises(AdapterError, match="gold-like"):
                arm.build_index(str(clean.root), "track_a")
        finally:
            arm.close()
    assert not (tmp_path / "arm" / "corpus.jsonl").exists(), "nothing was written for the upstream to read"
