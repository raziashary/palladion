"""Serve the synthetic source/search API with explicitly provisioned local demo tokens."""
from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from evidence_agent.agent.llm import GroqModel
from evidence_agent.agent.services import configure_agent, fixture_adapter
from evidence_agent.core.bootstrap import load_demo_tokens
from evidence_agent.live.gateway import load_config
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
    parser.add_argument("--model", choices=GroqModel.allowed_models, default=settings.model)
    parser.add_argument("--enable-live-llm", action="store_true", help="Explicitly load root .env and enable real Groq messages")
    parser.add_argument("--model-call-interval", type=float, default=0, help="Opt-in seconds between Groq dispatches")
    args = parser.parse_args()
    if args.model_call_interval and not args.enable_live_llm:
        parser.error("Model call spacing requires --enable-live-llm")
    index = QdrantIndex(url=args.url, collection_name=args.collection, bm25_profile=settings.bm25_profile)
    try:
        app = create_app(args.root, index, load_demo_tokens(args.root), FastEmbedReranker(enabled=args.rerank))
        if args.enable_live_llm:
            app_root = Path(__file__).resolve().parents[1]
            configure_agent(app, model=GroqModel.from_env_file(app_root.parent / ".env", enabled=True, model=args.model, call_interval_seconds=args.model_call_interval),
                adapter=fixture_adapter(app_root), config=load_config(app_root / "config/adapters.yaml"),
                settings=settings.model_copy(update={"enable_live_llm": True, "model": args.model}))
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    finally:
        index.close()


if __name__ == "__main__":
    main()
