"""Run an explicitly enabled synthetic compatibility probe against a local Qdrant."""

from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from collections.abc import Sequence

from qdrant_client import QdrantClient

from evidence_agent.core.models import Principal
from evidence_agent.core.retrieval import Chunk
from evidence_agent.storage.qdrant import QdrantIndex

_TENANT = "p02-probe-tenant"
_CASE = "p02-probe-case"
_PRINCIPAL = "p02-probe-principal"
_GENERATION = "p02-probe-generation"


def _chunk(chunk_id: str, text: str) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        tenant_id=_TENANT,
        case_id=_CASE,
        revision_id="p02-probe-revision",
        section_id="synthetic",
        start_byte=0,
        end_byte=len(text.encode("utf-8")),
        line_start=1,
        line_end=1,
        text=text,
        content_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        source_sha256="b" * 64,
    )


def _run(url: str) -> dict[str, object]:
    result: dict[str, object] = {"profiles": {}}
    profile_results: dict[str, object] = {}
    principal = Principal(
        principal_id=_PRINCIPAL,
        tenant_id=_TENANT,
        allowed_case_ids=(_CASE,),
    )
    chunks = (
        _chunk("p02-probe-en", "Refund requests require a receipt for review."),
        _chunk("p02-probe-id", "Permintaan pengembalian dana memerlukan kuitansi."),
    )
    for profile in ("english", "no_stemming"):
        collection = f"p02_probe_{profile}_{uuid.uuid4().hex[:12]}"
        client = QdrantClient(url=url, timeout=10)
        index = QdrantIndex(
            url=url,
            collection_name=collection,
            bm25_profile=profile,
            active_generation=_GENERATION,
            client=client,
        )
        try:
            index.upsert(chunks, _GENERATION, (_PRINCIPAL,))
            readback = index.readback(_TENANT, "p02-probe-revision", _GENERATION)
            hybrid_queries = {}
            lexical_queries = {}
            for label, text in (
                ("english", "receipt required for refund"),
                ("indonesian", "kuitansi untuk pengembalian dana"),
            ):
                hybrid = index.query(text, principal, _CASE, mode="hybrid", limit=5)
                lexical = index.query(text, principal, _CASE, mode="lexical", limit=5)
                hybrid_queries[label] = [hit.chunk_id for hit in hybrid]
                lexical_queries[label] = [hit.chunk_id for hit in lexical]
            profile_results[profile] = {
                "fingerprint": index.fingerprint,
                "readback_chunk_count": len(readback),
                "hybrid_queries": hybrid_queries,
                "lexical_queries": lexical_queries,
                "health": index.health(),
            }
        finally:
            if client.collection_exists(collection):
                client.delete_collection(collection_name=collection)
            index.close()
    result["profiles"] = profile_results
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:16333")
    parser.add_argument(
        "--run",
        action="store_true",
        help="explicitly create, query and delete unique synthetic p02_probe_* collections",
    )
    args = parser.parse_args(argv)
    if not args.run:
        parser.error("--run is required before this probe mutates a uniquely named collection")
    print(json.dumps(_run(args.url), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
