"""R5 GraphRAG Local: the upstream's own indexing and local context builder, through the worker (B06-T02.01).

These tests run the real worker in the approved GraphRAG environment. Models are a fake provider behind the counting
proxy, and embeddings are the benchmark's local ``HashingEncoder`` behind the proxy's embedder, so nothing leaves this
machine. The fake answers extraction prompts with GraphRAG's own record format, built from capitalised names that
really occur in each chunk.
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from support import HashingEncoder

from benchmark.adapters.common import Condition, PublishedView, build_chunks
from benchmark.adapters.graphrag import UNSUPPORTED, WORKER, build_graphrag_arm
from benchmark.adapters.worker import ComparatorWorker, WorkerArm, WorkerError, python_worker_argv
from benchmark.contracts import RetrievalRequest
from benchmark.generator import TransportResponse
from benchmark.llm_proxy import CountingProxy, ProxyLimits, ProxyServer
from benchmark.run_manifest import ComparatorPin

ROOT = Path(__file__).resolve().parents[1]
INTERPRETER = ROOT / "artifacts" / "comparators" / "env-graphrag" / "Scripts" / "python.exe"
MODEL = "qwen/qwen3.8-27b"
EMBED = "local-embedding"
TOKEN = "g" * 24
ALLOWED_CHAT_KEYS = {
    "model", "messages", "temperature", "top_p", "response_format", "max_tokens", "max_completion_tokens", "seed",
    "stop", "reasoning_effort", "n",
}  # fmt: skip
PIN = ComparatorPin.from_dict(
    {"repository": "https://github.com/microsoft/graphrag", "commit": "5faaaf4f5685fa2056fa8c3bf9342cb089f2942f",
     "lock_sha256": "d" * 64, "interpreter": "3.12.15", "native_config": {"mode": "local"}, "deviations": []}
)  # fmt: skip
WORKER_ENV = {"LITELLM_LOCAL_MODEL_COST_MAP": "True", "ANONYMIZED_TELEMETRY": "False", "DO_NOT_TRACK": "1",
              "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}  # fmt: skip
NAME = re.compile(r"[A-Z][a-z]+(?: [A-Z][a-z]+)+")


def extraction_reply(prompt: str) -> str:
    """GraphRAG record format: an entity per name in the chunk text, and one relation between the first two."""
    text = prompt.rsplit("Text:", 1)[-1]
    names = list(dict.fromkeys(NAME.findall(text)))[:4]
    records = [f'("entity"<|>{name.upper()}<|>ORGANIZATION<|>An organisation named in the text.)' for name in names]
    if len(names) >= 2:
        records.append(f'("relationship"<|>{names[0].upper()}<|>{names[1].upper()}<|>They are named together.<|>5)')
    return "##".join(records) + "<|COMPLETE|>" if records else "<|COMPLETE|>"


class Provider:
    """The fake chat provider: GraphRAG's extraction format for extraction prompts, a plain summary otherwise."""

    def __init__(self) -> None:
        self.calls = 0
        self.keys: set[str] = set()
        self.models: set[str] = set()

    def post(self, payload: Any) -> TransportResponse:
        self.calls += 1
        self.keys |= set(payload)
        self.models.add(str(payload.get("model")))
        content = str(payload["messages"][-1]["content"])
        reply = extraction_reply(content) if "Entity_types:" in content else "A short summary of the description."
        body = {"id": "fake", "object": "chat.completion", "created": 0, "model": MODEL,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": reply}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60}}  # fmt: skip
        return TransportResponse(200, {"content-type": "application/json"}, json.dumps(body).encode())


@pytest.fixture(scope="module")
def graph_server(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[ProxyServer, Provider]]:
    provider = Provider()
    encoder = HashingEncoder()
    proxy = CountingProxy(
        provider,
        ProxyLimits(
            max_calls=10_000, max_tokens=10_000_000, max_completion_tokens=700, pace_seconds=0.0, models=(MODEL,)
        ),
        record_path=tmp_path_factory.mktemp("proxy") / "proxy.jsonl",
        embedder=encoder.embed_documents,
        embedding_model=EMBED,
    )  # fmt: skip
    server = ProxyServer(proxy, token=TOKEN)
    server.start()
    yield server, provider
    server.stop()


def worker_env(server: ProxyServer, cache: Path) -> dict[str, str]:
    env = {"OPENAI_BASE_URL": server.base_url, "OPENAI_API_KEY": TOKEN, "COMPARATOR_LLM_MODEL": MODEL,
           "COMPARATOR_EMBED_MODEL": EMBED, "TIKTOKEN_CACHE_DIR": str(cache), **WORKER_ENV}  # fmt: skip
    return {**env, "COMPARATOR_PROTOCOL": str(ROOT / "comparators" / "protocol.py")}


def view_of(s_root: Path) -> PublishedView:
    return PublishedView.load(s_root / "published")


def request(view: PublishedView, query: str, limit: int = 10) -> RetrievalRequest:
    principal = view.identity.principals[0].principal_id
    return RetrievalRequest(
        "q-0123456789abcdef", query, principal, "snap-1", "2026-10-18T03:00:00Z", None, {}, limit, 4000
    )  # fmt: skip


@pytest.fixture(scope="module")
def cache_dir() -> Path:
    cache = ROOT / "artifacts" / "comparators" / "tiktoken-cache"
    assert (cache / "fb374d419588a4632f3f557e76b4b70aebbca790").is_file(), "the approved o200k_base encoding is missing"
    return cache


@pytest.fixture(scope="module")
def built(
    graph_server: tuple[ProxyServer, Provider], cache_dir: Path, s_root: Path, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[tuple[WorkerArm, Provider, PublishedView]]:
    server, provider = graph_server
    view = view_of(s_root)
    work = tmp_path_factory.mktemp("graphrag-work")
    arm = build_graphrag_arm(
        interpreter=INTERPRETER, server=server, pin=PIN, view=view, work_dir=work, llm_model=MODEL,
        embedding_model=EMBED, condition=Condition.C1, build_timeout=900.0, query_timeout=900.0,
    )  # fmt: skip
    arm.build_index(str(s_root / "published"), "track_a")
    yield arm, provider, view
    arm.close()


# --------------------------------------------------------------------------- the adapter


def test_the_adapter_names_the_worker_and_declares_what_it_cannot_do(
    tmp_path: Path, graph_server: Any, s_root: Path
) -> None:
    server, _ = graph_server
    arm = build_graphrag_arm(
        interpreter=INTERPRETER, server=server, pin=PIN, view=view_of(s_root), work_dir=tmp_path, llm_model=MODEL,
        embedding_model=EMBED,
    )  # fmt: skip
    assert WORKER.name == "worker.py" and WORKER.parent.name == "graphrag"
    assert arm.arm_id == "R5" and arm.describe()["unsupported"] == list(UNSUPPORTED)
    assert set(UNSUPPORTED) == {"ACL_FILTER", "AS_OF_FILTER"}
    arm.close()


# --------------------------------------------------------------------------- the upstream runs


def test_the_index_is_built_by_the_upstream_pipeline_and_the_native_block_records_it(built: Any) -> None:
    arm, provider, view = built
    native = arm.index_stats()["native"]
    assert native["method"].startswith("graphrag standard indexing")
    assert native["package"]["graphrag"] == "3.3.0"
    assert native["search"] == "local context builder only (no answer LLM call)"
    assert native["community_reports"] is False
    assert native["documents"] == len(build_chunks(view)) == native["text_units"]
    assert native["entities"] > 0 and native["relationships"] > 0
    assert native["vector_size"] == HashingEncoder.dimension
    assert "deviations" in native and len(native["deviations"]) >= 5
    assert provider.models == {MODEL}, "every chat call named the approved model"


def test_extraction_reached_the_proxy_with_only_allowed_parameters(built: Any) -> None:
    _, provider, _ = built
    assert provider.keys, "the fake provider saw no chat payloads"
    assert provider.keys <= ALLOWED_CHAT_KEYS, (
        f"litellm sent parameters the proxy refuses: {provider.keys - ALLOWED_CHAT_KEYS}"
    )


def test_retrieval_returns_corpus_chunk_ids_in_the_local_context_order(built: Any) -> None:
    arm, _, view = built
    corpus_ids = {c.chunk_id for c in build_chunks(view)}
    before = arm._usage()["calls"]
    got = arm.retrieve(request(view, "which organisation is named with which", limit=5))
    assert got, "local search returned no evidence for a question about named organisations"
    assert all(c.additional_metadata["chunk_id"] in corpus_ids for c in got)
    assert len({c.additional_metadata["chunk_id"] for c in got}) == len(got), "a chunk appeared twice"
    assert [
        c.additional_metadata["chunk_id"]
        for c in arm.retrieve(request(view, "which organisation is named with which", limit=5))
    ] == [c.additional_metadata["chunk_id"] for c in got], "the same question must rank the same chunks"
    assert arm._usage()["calls"] == before, "query time made a chat call; local search must not answer"


def test_a_relation_is_carried_only_when_both_names_occur_in_its_supporting_chunk(built: Any) -> None:
    arm, _, view = built
    chunks = {c.chunk_id: c.text.casefold() for c in build_chunks(view)}
    related = []
    for candidate in arm.retrieve(request(view, "organisation named together with another organisation", limit=10)):
        if candidate.relation is None:
            continue
        related.append(candidate)
        relation = candidate.relation
        chunk_id = candidate.additional_metadata["chunk_id"]
        doc_id = chunk_id.split("#")[0]
        assert [i.split("#")[0] for i in relation["supporting_ids"]] == [doc_id], "cited as the hit's own document"
        text = chunks[chunk_id]
        assert relation["subject"].casefold() in text and relation["object"].casefold() in text
    assert related, "no hit carried a relation although the fake extractor named pairs in the text"


RELATION_PROBE = """
import importlib.util, os
spec = importlib.util.spec_from_file_location("graphrag_worker", {worker!r})
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
text = "the alpha switch feeds the beta bridge"
edges = [("alpha", "beta", {{"u1"}}), ("alpha", "gamma", {{"u1"}}), ("alpha", "beta", {{"u2"}})]
print("BOTH", module._relation("c1", "u1", edges[:1], text) is not None)
print("ONE_MISSING", module._relation("c1", "u1", edges[1:2], text) is None)
print("OTHER_UNIT", module._relation("c1", "u1", edges[2:], text) is None)
"""


def test_a_relation_needs_both_names_in_the_chunk_and_the_chunk_in_the_relationship(
    tmp_path: Path, cache_dir: Path
) -> None:
    """Negative controls against the worker's own rule: a missing end, or another text unit, gives no relation."""
    code = RELATION_PROBE.format(worker=str(WORKER))
    env = {
        "PATH": os.environ.get("PATH", ""), "SYSTEMROOT": os.environ.get("SYSTEMROOT", "C:\Windows"),
        "NLTK_DATA": str(tmp_path), "TIKTOKEN_CACHE_DIR": str(cache_dir),
        "COMPARATOR_PROTOCOL": str(ROOT / "comparators" / "protocol.py"), **WORKER_ENV,
    }  # fmt: skip
    done = subprocess.run(
        [str(INTERPRETER), "-I", "-c", code], capture_output=True, text=True, timeout=900, env=env, cwd=tmp_path,
        check=False,
    )  # fmt: skip
    assert done.stdout.split() == ["BOTH", "True", "ONE_MISSING", "True", "OTHER_UNIT", "True"], (
        done.stdout + done.stderr
    )


def test_a_question_about_nothing_in_the_index_still_returns_ranked_chunks_or_none(built: Any) -> None:
    arm, _, view = built
    got = arm.retrieve(request(view, "zzqx unknownterm", limit=3))
    assert len(got) <= 3


def test_the_worker_refuses_retrieval_before_a_build(tmp_path: Path, graph_server: Any, cache_dir: Path) -> None:
    server, _ = graph_server
    worker = ComparatorWorker(
        python_worker_argv(WORKER, INTERPRETER), cwd=tmp_path, stderr_path=tmp_path / "worker.stderr",
        env=worker_env(server, cache_dir),
    )  # fmt: skip
    worker.start()
    try:
        with pytest.raises(WorkerError) as caught:
            worker.request("retrieve", {"query": "anything", "limit": 3}, timeout=900)
        assert caught.value.code == "WORKER_NotBuilt"
    finally:
        worker.stop()


# --------------------------------------------------------------------------- the network guard


GUARD_PROBE = """
import socket, sys
sys.path.insert(0, {worker_dir!r})
import worker
try:
    socket.create_connection(({host!r}, {port}), timeout=2)
    print("CONNECTED")
except worker.NetworkRefused as exc:
    print("REFUSED", type(exc).__name__)
"""


def probe(host: str, port: int, tmp_path: Path, cache_dir: Path) -> subprocess.CompletedProcess[str]:
    code = GUARD_PROBE.format(worker_dir=str(WORKER.parent), host=host, port=port)
    env = {
        "PATH": os.environ.get("PATH", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", "C:\\Windows"),
        "NLTK_DATA": str(tmp_path),  # nltk wants a data directory when imported and the probe has no home directory
        "TIKTOKEN_CACHE_DIR": str(cache_dir),
        "COMPARATOR_PROTOCOL": str(ROOT / "comparators" / "protocol.py"),
        **WORKER_ENV,
    }
    return subprocess.run(
        [str(INTERPRETER), "-I", "-c", code], capture_output=True, text=True, timeout=900, env=env, cwd=tmp_path,
        check=False,
    )  # fmt: skip


def test_a_lookup_outside_loopback_is_refused_and_its_host_is_logged(tmp_path: Path, cache_dir: Path) -> None:
    done = probe("example.com", 9, tmp_path, cache_dir)
    assert "REFUSED NetworkRefused" in done.stdout, done.stdout + done.stderr
    assert "NETWORK_REFUSED host='example.com'" in done.stderr


def test_a_loopback_connection_is_not_refused_by_the_guard(tmp_path: Path, cache_dir: Path) -> None:
    """Positive control: the guard lets loopback through, so the refusal above is the guard's, not a broken probe."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        done = probe("127.0.0.1", listener.getsockname()[1], tmp_path, cache_dir)
    assert "CONNECTED" in done.stdout, done.stdout + done.stderr
