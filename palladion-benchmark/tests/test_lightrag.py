"""R6 LightRAG: the upstream's hybrid retrieval through the worker, offline (B06-T03.01, BADR-0031).

Every test runs the real upstream (LightRAG v1.5.7 in ``artifacts/comparators/env-LightRAG``) on a few real S-tier
chunks. The model is a fake provider behind the counting proxy that answers LightRAG's own extraction and keyword
prompts with canned, format-correct replies; embeddings come from the benchmark's local ``HashingEncoder``. No
network is used except the loopback proxy, and the tokenizer comes from the owner-approved cache.
"""

from __future__ import annotations

import itertools
import json
import re
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from support import HashingEncoder

from benchmark.adapters.common import AccessFilter, Condition, PublishedView, build_chunks
from benchmark.adapters.lightrag import UNSUPPORTED, build_lightrag_arm
from benchmark.adapters.worker import ComparatorWorker, WorkerArm, WorkerError, python_worker_argv
from benchmark.contracts import RetrievalRequest
from benchmark.generator import TransportResponse
from benchmark.llm_proxy import CountingProxy, ProxyLimits, ProxyServer
from benchmark.run_manifest import ComparatorPin

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "comparators" / "lightrag" / "worker.py"
PROTOCOL = ROOT / "comparators" / "protocol.py"
TIKTOKEN_CACHE = ROOT / "artifacts" / "comparators" / "tiktoken-cache"
INTERPRETER = ROOT / "artifacts" / "comparators" / "env-LightRAG" / "Scripts" / "python.exe"
MODEL = "qwen/qwen3.8-27b"
EMBED = "paraphrase-multilingual-MiniLM-L12-v2"
TOKEN = "t" * 24
DELIM = "<|#|>"
COMPLETE = "<|COMPLETE|>"
PIN = ComparatorPin.from_dict(
    {
        "repository": "https://github.com/HKUDS/LightRAG",
        "commit": "28ff1b05f2ac3f3e6fa14dd2cd33656579bd0c9c",
        "lock_sha256": "d" * 64,
        "interpreter": "3.12.15",
        "native_config": {"mode": "hybrid"},
        "deviations": [],
    }
)

pytestmark = pytest.mark.skipif(not INTERPRETER.is_file(), reason="the LightRAG environment is not installed")


class Canned:
    """A fake provider that answers LightRAG's extraction and keyword prompts in the upstream's formats."""

    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []

    def post(self, payload: Any) -> TransportResponse:
        self.payloads.append(dict(payload))
        body = {
            "id": "fake",
            "object": "chat.completion",
            "created": 0,
            "model": MODEL,
            "choices": [
                {"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": _answer(payload)}}
            ],
            "usage": {"prompt_tokens": 40, "completion_tokens": 20, "total_tokens": 60},
        }
        return TransportResponse(200, {"content-type": "application/json"}, json.dumps(body).encode())


def _answer(payload: dict[str, Any]) -> str:
    text = "\n".join(str(m.get("content", "")) for m in payload.get("messages", []))
    if "---Input Text---" in text:
        source = text.rsplit("---Input Text---", 1)[1]
        source = source.split("```")[1] if "```" in source else source
        names = list(dict.fromkeys(re.findall(r"[A-Z][a-z]+(?: [A-Z][a-z]+)*", source)))[:3]
        rows = [f"entity{DELIM}{n}{DELIM}concept{DELIM}{n} appears in the corpus" for n in names]
        rows += [
            f"relation{DELIM}{a}{DELIM}{b}{DELIM}related{DELIM}{a} is discussed with {b}"
            for a, b in itertools.pairwise(names)
        ]
        return "\n".join([*rows, COMPLETE])
    if "User Query:" in text:
        query = text.rsplit("User Query:", 1)[1].strip()
        words = list(dict.fromkeys(re.findall(r"[A-Za-z]{4,}", query)))
        return json.dumps({"high_level_keywords": words[:3], "low_level_keywords": words[:5]})
    return "A short summary of the entity."


@pytest.fixture
def provider() -> Canned:
    return Canned()


@pytest.fixture
def server(tmp_path: Path, provider: Canned) -> Iterator[ProxyServer]:
    limits = ProxyLimits(
        max_calls=2000, max_tokens=10_000_000, max_completion_tokens=700, pace_seconds=0.0, models=(MODEL,)
    )
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


def worker_env(server: ProxyServer) -> dict[str, str]:
    """The environment launch_arm gives a worker, for the tests that drive the worker directly."""
    env = server.environment(llm_model=MODEL, embedding_model=EMBED)
    env["COMPARATOR_PROTOCOL"] = str(PROTOCOL)
    env.update(
        {
            "TIKTOKEN_CACHE_DIR": str(TIKTOKEN_CACHE),
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "ANONYMIZED_TELEMETRY": "False",
            "DO_NOT_TRACK": "1",
        }
    )
    return env


def raw_worker(tmp_path: Path, server: ProxyServer) -> ComparatorWorker:
    worker = ComparatorWorker(
        python_worker_argv(WORKER, INTERPRETER),
        cwd=tmp_path,
        stderr_path=tmp_path / "worker.stderr",
        env=worker_env(server),
    )
    worker.start()
    return worker


def small_view(s_root: Path, documents: int = 3) -> PublishedView:
    full = PublishedView.load(s_root / "published")
    records = list(full.records[:documents])
    texts = {r.doc_id: full.document(r.doc_id).text for r in records}
    return PublishedView(full.root, records, full.identity, texts)


def write_corpus(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return path


def request(view: PublishedView, query: str, limit: int = 10, principal: str | None = None) -> RetrievalRequest:
    who = principal or view.identity.principals[0].principal_id
    return RetrievalRequest("q-0123456789abcdef", query, who, "snap-1", "2026-10-18T03:00:00Z", None, {}, limit, 4000)


def arm_over(tmp_path: Path, server: ProxyServer, view: PublishedView) -> WorkerArm:
    arm = build_lightrag_arm(
        interpreter=INTERPRETER,
        server=server,
        pin=PIN,
        view=view,
        work_dir=tmp_path / "work",
        llm_model=MODEL,
        embedding_model=EMBED,
        build_timeout=900.0,
        query_timeout=300.0,
    )
    arm.build_index(str(view.root), "track_a")
    return arm


# --------------------------------------------------------------------------- the upstream's own pipeline


def test_the_upstream_hybrid_retrieval_answers_from_its_graph_and_counts_its_calls(
    tmp_path: Path, s_root: Path, server: ProxyServer, provider: Canned
) -> None:
    view = small_view(s_root)
    arm = arm_over(tmp_path, server, view)
    stats = arm.index_stats()
    native = stats["native"]
    assert native["mode"] == "hybrid" and native["upstream"]["version"] == "1.5.7"
    assert native["upstream"]["commit"] == PIN.commit
    assert native["documents"] == len(build_chunks(view))
    assert native["documents_inserted"] == native["documents"] and native["chunk_ids_sharing_text"] == 0
    assert stats["extraction_calls"] > 0 and stats["embedding_inputs"] > 0
    got = arm.retrieve(request(view, "Meridian Switchworks warranty terms"))
    query_calls = arm.last_notes["query_llm_calls"]
    arm.close()
    ids = {c.chunk_id for c in build_chunks(view)}
    assert got and all(c.additional_metadata["chunk_id"] in ids for c in got)
    assert query_calls == 1  # the upstream's keyword step, counted; no answer is generated
    assert len([p for p in provider.payloads if "User Query:" in json.dumps(p["messages"])]) == 1


def test_a_graph_hit_names_entities_that_appear_in_its_supporting_chunk(
    tmp_path: Path, s_root: Path, server: ProxyServer
) -> None:
    view = small_view(s_root)
    arm = arm_over(tmp_path, server, view)
    texts = {c.chunk_id: c.text for c in build_chunks(view)}
    got = arm.retrieve(request(view, "Meridian Switchworks warranty terms", limit=20))
    arm.close()
    with_edge = [c for c in got if c.relation is not None]
    assert with_edge, "the upstream's relation rows should surface as graph edges"
    for candidate in with_edge:
        assert candidate.relation is not None
        chunk_id = candidate.additional_metadata["chunk_id"]
        assert candidate.relation["subject"] in texts[chunk_id] and candidate.relation["object"] in texts[chunk_id]
        assert tuple(candidate.relation["supporting_ids"]) == (candidate.source_document_id,)  # a citation


def test_a_query_the_corpus_cannot_answer_returns_no_hits_and_is_not_an_error(
    tmp_path: Path, s_root: Path, server: ProxyServer
) -> None:
    view = small_view(s_root)
    arm = arm_over(tmp_path, server, view)
    got = arm.retrieve(request(view, "zzqx vvbn kkpl"))
    arm.close()
    assert got == []


def test_the_arm_declares_the_unsupported_affordances_and_the_pin(
    tmp_path: Path, s_root: Path, server: ProxyServer
) -> None:
    arm = build_lightrag_arm(
        interpreter=INTERPRETER,
        server=server,
        pin=PIN,
        view=small_view(s_root),
        work_dir=tmp_path / "w",
        llm_model=MODEL,
        embedding_model=EMBED,
    )
    description = arm.describe()
    arm.close()
    assert tuple(UNSUPPORTED) == ("ACL_FILTER", "AS_OF_FILTER")
    assert description["unsupported"] == ["ACL_FILTER", "AS_OF_FILTER"]
    assert description["comparator"]["commit"] == PIN.commit


def test_every_model_call_is_to_the_approved_model_and_the_token_never_reaches_the_payload(
    tmp_path: Path, s_root: Path, server: ProxyServer, provider: Canned
) -> None:
    arm = arm_over(tmp_path, server, small_view(s_root, documents=2))
    arm.close()
    assert provider.payloads
    assert {p["model"] for p in provider.payloads} == {MODEL}
    assert all(TOKEN not in json.dumps(p) for p in provider.payloads)


def test_the_hits_respect_the_limit(tmp_path: Path, s_root: Path, server: ProxyServer) -> None:
    view = small_view(s_root)
    arm = arm_over(tmp_path, server, view)
    got = arm.retrieve(request(view, "Meridian Switchworks warranty terms", limit=2))
    arm.close()
    assert len(got) <= 2


def restricted_view(s_root: Path, others: int = 2) -> tuple[PublishedView, str, str, str]:
    """A small view with one document that some principal may not read, and a principal who may and one who may not."""
    full = PublishedView.load(s_root / "published")
    full_access = AccessFilter(full, Condition.C2)
    hidden = next(
        r for r in full.records
        if any(not full_access.allows(p.principal_id, r.doc_id) for p in full.identity.principals)
    )  # fmt: skip
    records = [hidden]
    records += [r for r in full.records if r.doc_id != hidden.doc_id][:others]
    texts = {r.doc_id: full.document(r.doc_id).text for r in records}
    view = PublishedView(full.root, records, full.identity, texts)
    access = AccessFilter(view, Condition.C2)
    denied = next(p.principal_id for p in view.identity.principals if not access.allows(p.principal_id, hidden.doc_id))
    allowed = next(p.principal_id for p in view.identity.principals if access.allows(p.principal_id, hidden.doc_id))
    return view, hidden.doc_id, denied, allowed


def test_the_access_filter_still_applies_after_the_upstream_ranking(
    tmp_path: Path, s_root: Path, server: ProxyServer
) -> None:
    view, hidden_doc, denied, allowed = restricted_view(s_root)
    arm = arm_over(tmp_path, server, view)
    query = " ".join(view.document(hidden_doc).text.split()[:12])
    seen_by_allowed = arm.retrieve(request(view, query, limit=20, principal=allowed))
    assert hidden_doc in {c.source_document_id for c in seen_by_allowed}, "the probe must reach the hidden document"
    filtered = arm.retrieve(request(view, query, limit=20, principal=denied))
    dropped = arm.last_notes["filtered_after_ranking"]
    arm.close()
    assert hidden_doc not in {c.source_document_id for c in filtered}
    assert dropped >= 1


# --------------------------------------------------------------------------- guards: positive and negative


def test_a_corpus_row_without_its_fields_is_refused_before_indexing(
    tmp_path: Path, server: ProxyServer, provider: Canned
) -> None:
    worker = raw_worker(tmp_path, server)
    try:
        corpus = write_corpus(tmp_path / "corpus.jsonl", [{"chunk_id": "c-1", "doc_id": "d-1"}])
        with pytest.raises(WorkerError, match="WORKER_LightRagFault"):
            worker.request(
                "build", {"corpus": str(corpus), "workdir": str(tmp_path / "n"), "namespace": "x"}, timeout=300
            )
    finally:
        worker.stop()
    assert provider.payloads == []


def test_duplicate_chunk_ids_are_refused_and_unique_ids_are_accepted(tmp_path: Path, server: ProxyServer) -> None:
    worker = raw_worker(tmp_path, server)
    try:
        dup = write_corpus(
            tmp_path / "dup.jsonl",
            [
                {"chunk_id": "c-1", "doc_id": "d-1", "text": "Meridian Switchworks sells routers."},
                {"chunk_id": "c-1", "doc_id": "d-2", "text": "Meridian Switchworks sells switches."},
            ],
        )
        with pytest.raises(WorkerError, match="WORKER_LightRagFault"):
            worker.request("build", {"corpus": str(dup), "workdir": str(tmp_path / "a"), "namespace": "x"}, timeout=300)
        ok = write_corpus(
            tmp_path / "ok.jsonl",
            [
                {"chunk_id": "c-1", "doc_id": "d-1", "text": "Meridian Switchworks sells routers."},
                {"chunk_id": "c-2", "doc_id": "d-2", "text": "Meridian Switchworks sells switches."},
            ],
        )
        built = worker.request(
            "build", {"corpus": str(ok), "workdir": str(tmp_path / "b"), "namespace": "x"}, timeout=300
        )
        assert built["documents"] == 2 and built["documents_inserted"] == 2
    finally:
        worker.stop()


def test_identical_chunk_texts_are_indexed_once_and_every_id_is_returned(tmp_path: Path, server: ProxyServer) -> None:
    text = "Meridian Switchworks publishes the Cascade Gateway handbook for field technicians."
    worker = raw_worker(tmp_path, server)
    try:
        corpus = write_corpus(
            tmp_path / "corpus.jsonl",
            [
                {"chunk_id": "c-1", "doc_id": "d-1", "text": text},
                {"chunk_id": "c-2", "doc_id": "d-2", "text": "Unrelated notes about Harbor Logistics depots."},
                {"chunk_id": "c-3", "doc_id": "d-3", "text": text},
            ],
        )
        built = worker.request(
            "build", {"corpus": str(corpus), "workdir": str(tmp_path / "n"), "namespace": "x"}, timeout=300
        )
        assert built["documents"] == 3 and built["documents_inserted"] == 2 and built["chunk_ids_sharing_text"] == 1
        reply = worker.request("retrieve", {"query": "Meridian Switchworks Cascade Gateway", "limit": 10}, timeout=300)
    finally:
        worker.stop()
    returned = [h["chunk_id"] for h in reply["hits"]]
    assert {"c-1", "c-3"} <= set(returned) and len(returned) == len(set(returned))


def test_a_retrieve_before_a_build_is_refused(tmp_path: Path, server: ProxyServer) -> None:
    worker = raw_worker(tmp_path, server)
    try:
        with pytest.raises(WorkerError, match="WORKER_LightRagFault"):
            worker.request("retrieve", {"query": "anything", "limit": 3}, timeout=60)
    finally:
        worker.stop()


def test_a_missing_package_is_reported_by_name_and_never_installed(tmp_path: Path) -> None:
    """The worker's import replaces pipmaster's installers: a request to install is refused with the name, offline."""
    probe = tmp_path / "probe.py"
    lines = [
        "import runpy, sys",
        f"runpy.run_path({str(WORKER)!r}, run_name='not_main')",
        "import pipmaster",
        "try:",
        "    pipmaster.install('package-that-does-not-exist')",
        "except ImportError as exc:",
        "    print('REFUSED', exc)",
        "    sys.exit(0)",
        "sys.exit(3)",
    ]
    probe.write_text("\n".join(lines) + "\n", encoding="utf-8")
    done = subprocess.run(
        [str(INTERPRETER), "-I", str(probe)], capture_output=True, text=True, timeout=120, check=False, cwd=tmp_path
    )
    assert done.returncode == 0, done.stderr[-500:]
    assert "REFUSED" in done.stdout and "package-that-does-not-exist" in done.stdout
