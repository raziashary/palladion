"""Explicit P10 real-service HTTP proof on fresh synthetic UUID resources only."""
from __future__ import annotations

import argparse
import base64
import io
import json
import tempfile
import uuid
from contextlib import closing
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from qdrant_client import QdrantClient

from evidence_agent.agent.llm import GroqModel, ModelTurn
from evidence_agent.agent.services import configure_agent, fixture_adapter
from evidence_agent.core.bootstrap import seed
from evidence_agent.graph.relations import TraversalLimits
from evidence_agent.live.gateway import load_config
from evidence_agent.main import create_app
from evidence_agent.memory.packet import build_packet
from evidence_agent.memory.store import CaseStore
from evidence_agent.policy.bootstrap import seed_policy_fixture
from evidence_agent.retrieval.graph_expand import GraphExpansion
from evidence_agent.settings import Settings
from evidence_agent.storage.catalog import Catalog
from evidence_agent.storage.neo4j import Neo4jIndex
from evidence_agent.storage.originals import OriginalStore
from evidence_agent.storage.qdrant import QdrantIndex
from evidence_agent.storage.registry import Registry
from evidence_agent.storage.sqlite import Database

APP = Path(__file__).resolve().parents[1]


class ObservedModel:
    """Forward actual Groq calls, retaining outcomes and consumption booleans only."""

    def __init__(self, model: GroqModel, attempts: list[dict[str, Any]]) -> None:
        self.model, self.attempts = model, attempts

    async def complete(self, messages: Any, tools: Any, *, final: bool = False,
                       before_send: Any = None) -> ModelTurn:
        attempt: dict[str, Any] = {"history_present": any('"conversation_turns": [{' in str(m.get("content", ""))
                                           for m in messages), "final": final, "status": "STARTED"}
        self.attempts.append(attempt)
        try:
            result = await self.model.complete(messages, tools, final=final, before_send=before_send)
        except BaseException as error:
            attempt.update(status=type(error).__name__, code=getattr(error, "code", None))
            raise
        attempt.update(status="RECEIVED", usage=result.usage)
        return result


def sample_pdf() -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"):
        DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 72 720 Td (P10 PDF source: verify exact provenance.) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    target = io.BytesIO()
    writer.write(target)
    return target.getvalue()


def run(destination: Path, live: bool) -> dict[str, Any]:
    report: dict[str, Any] = {"completed": False, "model": "openai/gpt-oss-20b" if live else None,
        "checks": {}, "failures": [], "live_enabled": live}
    collection = "p10_smoke_" + uuid.uuid4().hex
    partition = "p10_test_" + uuid.uuid4().hex
    index = QdrantIndex(url="http://127.0.0.1:16333", collection_name=collection,
                       model_cache_dir=str(APP / "runtime/model_cache"))
    backend = Neo4jIndex(partition=partition, timeout_seconds=10)
    report.update(collection=collection, partition=partition)
    checks = report["checks"]
    try:
        with tempfile.TemporaryDirectory(prefix="palladion-p10-") as temporary:
            root = Path(temporary)
            seed(root, APP, index, backend)
            with Database(root / "registry.sqlite") as database:
                registry = Registry(database, OriginalStore(root / "originals"))
                seed_policy_fixture(registry, APP)
            app = create_app(root, index, {"u": "uploader-a", "a": "admin-a", "r": "reader-a"},
                             graph=GraphExpansion(backend, TraversalLimits(timeout_seconds=10)))
            model = GroqModel.from_env_file(APP.parent / ".env", enabled=True,
                model="openai/gpt-oss-20b", call_interval_seconds=15) if live else None
            attempts: list[dict[str, Any]] = []
            report["model_attempts"] = attempts
            observed = ObservedModel(model, attempts) if model is not None else None
            configure_agent(app, model=observed, adapter=fixture_adapter(APP),
                config=load_config(APP / "config/adapters.yaml"),
                settings=Settings(enable_live_llm=live, model="openai/gpt-oss-20b",
                                  graph_enabled=True, graph_partition=partition, graph_timeout_seconds=10))
            with TestClient(app) as client:
                headers = {name: {"Authorization": "Bearer " + name} for name in ("u", "a", "r")}

                def upload(name: str, text: str, mime: str = "text/plain") -> str:
                    body = {"case_id": "case-42", "family_id": name, "filename": name + ".txt",
                            "content": text, "mime_type": mime, "owner_id": "uploader-a"}
                    response = client.post("/sources", headers=headers["u"], json=body)
                    assert response.status_code == 201, response.status_code
                    revision = response.json()["revision_id"]
                    response = client.post(f"/sources/{revision}/approve", headers=headers["a"])
                    assert response.status_code == 200, response.status_code
                    return str(revision)

                left_revision = upload("P10-ANCHOR-727", "Anchor procedure: verify all source references.")
                right_revision = upload("P10-TARGET-728", "This paragraph references the anchor procedure.")
                with Database(root / "registry.sqlite") as database:
                    registry = Registry(database, OriginalStore(root / "originals"))
                    admin = registry.access.authenticate("admin-a")
                    catalog = Catalog(registry)
                    left = catalog.chunks_for_revision(admin, left_revision)[0]
                    right = catalog.chunks_for_revision(admin, right_revision)[0]
                link = {"from_chunk_id": left.chunk_id, "to_chunk_id": right.chunk_id,
                    "relation_type": "REFERENCES", "evidence_chunk_id": right.chunk_id,
                    "revision_id": right_revision, "start_byte": right.start_byte,
                    "end_byte": right.end_byte, "quote": right.text}
                route = "/v1/admin/cases/case-42/graph-links"
                response = client.post(route, headers=headers["a"], json={"links": [link]})
                assert response.status_code == 200, response.status_code
                result = response.json()
                assert result["projection"] == "READY"
                edge = result["links"][0]["edge_id"]
                checks["graph_http_projection"] = True
                search = client.post("/search", headers=headers["r"], json={"case_id": "case-42",
                    "query": "P10-ANCHOR-727", "limit": 12, "require_graph": True})
                assert search.status_code == 200, search.status_code
                paths = search.json()["graph_paths"]
                assert any(edge in path["edge_ids"] for path in paths), search.json().get("warnings")
                checks["graph_search_consumed_http_link"] = True
                proof = client.get(f"/v1/cases/case-42/graph-links/{edge}", headers=headers["r"])
                assert proof.status_code == 200 and proof.json()["quote"] == right.text
                checks["graph_proof_readback"] = True
                raw = sample_pdf()
                body = {"case_id": "case-42", "family_id": "P10-PDF-729", "filename": "source.pdf",
                    "mime_type": "application/pdf", "content": base64.b64encode(raw).decode(),
                    "owner_id": "uploader-a"}
                response = client.post("/sources/import-pdf", headers=headers["u"], json=body)
                assert response.status_code == 201, response.status_code
                revision = response.json()["revision_id"]
                assert client.post(f"/sources/{revision}/approve", headers=headers["a"]).status_code == 200
                with Database(root / "registry.sqlite") as database:
                    registry = Registry(database, OriginalStore(root / "originals"))
                    chunk = Catalog(registry).chunks_for_revision(registry.access.authenticate("reader-a"), revision)[0]
                citation = client.get(f"/evidence/{chunk.chunk_id}", params={"case_id": "case-42"}, headers=headers["r"])
                assert citation.status_code == 200 and citation.json()["pdf_provenance"]["pages"][0]["page"] == 1
                assert client.get(f"/sources/{revision}/original-pdf", headers=headers["r"]).content == raw
                checks["real_index_pdf_citation_original"] = True
                if live:
                    first = client.post("/v1/cases/case-42/messages", headers=headers["r"],
                        json={"query": "I prefer concise answers."})
                    assert first.status_code == 200
                    boundary = len(attempts)
                    second = client.post("/v1/cases/case-42/messages", headers=headers["r"],
                        json={"query": "What did I ask earlier? Treat this only as conversation context, not evidence.",
                              "session_id": first.json()["session_id"]})
                    assert second.status_code == 200
                    checks["real_groq_prior_turn_input"] = any(
                        a["history_present"] and a["status"] == "RECEIVED" for a in attempts[boundary:])
                    report["provider"] = {"invocations": len(attempts),
                        "responses": sum(a["status"] == "RECEIVED" for a in attempts),
                        "last_failure": model.last_failure if model else None,
                        "rate_limits": model.last_rate_limits if model else None,
                        "first_budget": first.json()["budget"], "second_budget": second.json()["budget"]}
                    assert checks["real_groq_prior_turn_input"], report["provider"]
                    with Database(root / "registry.sqlite") as database:
                        registry = Registry(database, OriginalStore(root / "originals"))
                        packet = build_packet(CaseStore(registry, registry.access.authenticate("reader-a"),
                            "case-42", second.json()["session_id"]), "follow up")
                        assert len(packet.conversation_turns) == 2
                        checks["reopened_actual_groq_conversation"] = True
            report["completed"] = True
    except Exception as error:
        report["failures"].append({"type": type(error).__name__, "detail": str(error)[:1000]})
        raise
    finally:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
        index.close()
        # Fresh UUID-only cleanup; no preexisting collection/partition is reset.
        with closing(QdrantClient(url="http://127.0.0.1:16333", timeout=30)) as cleanup:
            if cleanup.collection_exists(collection):
                cleanup.delete_collection(collection)
        cleanup_graph = Neo4jIndex(partition=partition, timeout_seconds=10)
        try:
            cleanup_graph._run("MATCH(n) WHERE n.partition=$partition DETACH DELETE n")
        finally:
            cleanup_graph.close()
            backend.close()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", required=True)
    parser.add_argument("--enable-live-llm", action="store_true")
    parser.add_argument("--output", type=Path, default=APP / "runtime/p10-live.json")
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.enable_live_llm), indent=2))


if __name__ == "__main__":
    main()
