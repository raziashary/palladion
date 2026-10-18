"""Serve the synthetic source/search API with explicitly provisioned local demo tokens."""
from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from evidence_agent.core.bootstrap import load_demo_tokens
from evidence_agent.main import create_app
from evidence_agent.retrieval.rerank import FastEmbedReranker
from evidence_agent.settings import load_settings
from evidence_agent.storage.qdrant import QdrantIndex


def main() -> None:
    settings = load_settings(Path(__file__).resolve().parents[1] / "config/settings.yaml")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("runtime/demo"))
    parser.add_argument("--url", default=settings.qdrant_url)
    parser.add_argument("--collection", default=settings.qdrant_collection)
    parser.add_argument("--port", type=int, default=18080)
    parser.add_argument("--rerank", action="store_true")
    args = parser.parse_args()
    index = QdrantIndex(url=args.url, collection_name=args.collection, bm25_profile=settings.bm25_profile)
    app = create_app(args.root, index, load_demo_tokens(args.root), FastEmbedReranker(enabled=args.rerank))
    try:
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    finally:
        index.close()


if __name__ == "__main__":
    main()
