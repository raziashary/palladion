"""Upload -> independent approval -> indexing -> canonical readback, all isolated."""
import base64
import hashlib
import os
import uuid
from contextlib import closing
from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from evidence_agent.storage.catalog import Catalog
from evidence_agent.storage.qdrant import QdrantIndex

from .test_extraction import pdf_bytes
from .test_pipeline import MemoryIndex
from .test_runtime_api import api as runtime_api


@pytest.fixture
def api(p03):
    yield from runtime_api.__wrapped__(p03)


def upload_body(filename, mime, content):
    return {"case_id": "case-42", "family_id": "formats-" + filename,
            "filename": filename, "mime_type": mime, "content": content, "owner_id": "uploader-a"}


@pytest.mark.parametrize("filename,mime,text", [
    ("a.json", "application/json", '{ "é": "value", "n": 1 }\n'),
    ("a.jsonl", "application/x-ndjson", '{"a":1}\n{"b":2}\n'),
    ("a.csv", "text/csv", 'a,b\r\n"x,y",z\r\n'),
    ("a.py", "text/plain", '# heading is code\nraise RuntimeError("never execute")\n'),
    ("a.yaml", "text/plain", 'items:\n  - source\n'),
])
def test_verbatim_formats_actual_upload_approve_citation(api, p03, filename, mime, text):
    client, app = api
    app.state.index = MemoryIndex()
    app.state.tokens["uploader-test"] = "uploader-a"
    headers = {"Authorization": "Bearer uploader-test"}
    response = client.post("/sources", headers=headers, json=upload_body(filename, mime, text))
    assert response.status_code == 201, response.text
    revision = response.json()["revision_id"]
    assert client.post(f"/sources/{revision}/approve", headers={"Authorization": "Bearer admin-test"}).status_code == 200
    chunks = Catalog(p03.registry).chunks_for_revision(p03.reader, revision)
    assert Catalog(p03.registry).eligible_generation_metadata(p03.reader, revision)["parser_version"] == "utf8-verbatim-v1"
    for chunk in chunks:
        result = client.get(f"/evidence/{chunk.chunk_id}", params={"case_id": "case-42"},
                            headers={"Authorization": "Bearer reader-test"})
        assert result.status_code == 200, result.text
        data = result.json()
        assert text.encode()[data["start_byte"]:data["end_byte"]] == data["text"].encode()
    assert p03.registry.read_source(p03.reader, revision) == text.encode()


def test_pdf_import_original_extracted_citation_and_revocation(api, p03):
    api[1].state.index = MemoryIndex()
    _pdf_round_trip(api, p03)


def _pdf_round_trip(api, p03):
    client, app = api
    app.state.tokens["uploader-test"] = "uploader-a"
    uploader = {"Authorization": "Bearer uploader-test"}
    reader = {"Authorization": "Bearer reader-test"}
    raw = pdf_bytes()
    body = upload_body("source.pdf", "application/pdf", base64.b64encode(raw).decode())
    assert client.post("/sources/import-pdf", headers=reader, json=body).status_code == 403
    response = client.post("/sources/import-pdf", headers=uploader, json=body)
    assert response.status_code == 201, response.text
    revision = response.json()["revision_id"]
    original_route = f"/sources/{revision}/original-pdf"
    assert client.get(original_route, headers=reader).status_code == 403


    assert client.post(f"/sources/{revision}/approve", headers={"Authorization": "Bearer admin-test"}).status_code == 200
    assert client.get(original_route, headers=reader).content == raw
    chunk = Catalog(p03.registry).chunks_for_revision(p03.reader, revision)[0]
    cited = client.get(f"/evidence/{chunk.chunk_id}", params={"case_id": "case-42"}, headers=reader)
    assert cited.status_code == 200, cited.text
    provenance = cited.json()["pdf_provenance"]
    assert provenance["offset_basis"] == "EXTRACTED_UTF8" and provenance["pages"][0]["page"] == 1
    assert provenance["original_sha256"] == hashlib.sha256(raw).hexdigest()
    assert provenance["extracted_sha256"] != provenance["original_sha256"]
    assert client.post("/sources/import-pdf", headers=uploader, json=body).status_code == 201
    p03.registry.revoke_source(p03.admin, revision)
    assert client.get(original_route, headers=reader).status_code == 403


@pytest.mark.skipif(not os.environ.get("PALLADION_TEST_QDRANT_URL"),
                    reason="Explicit isolated local Qdrant enablement required")
def test_actual_qdrant_pdf_import_citation_and_revocation(api, p03):
    url = os.environ["PALLADION_TEST_QDRANT_URL"]
    assert url == "http://127.0.0.1:16333"
    collection = "p10_pdf_" + uuid.uuid4().hex
    index = QdrantIndex(url=url, collection_name=collection,
        model_cache_dir=str(Path(__file__).parents[1] / "runtime/model_cache"))
    api[1].state.index = index
    try:
        _pdf_round_trip(api, p03)
    finally:
        index.close()
        with closing(QdrantClient(url=url, timeout=30)) as cleanup:
            # Only this test's newly created UUID collection, never existing data.
            if cleanup.collection_exists(collection):
                cleanup.delete_collection(collection)
