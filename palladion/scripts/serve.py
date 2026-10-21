"""Serve the synthetic source/search API with explicitly provisioned local demo tokens."""
from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from evidence_agent.agent.experiments import ExperimentControls
from evidence_agent.agent.llm import DEFAULT_COMPLETION_CAP, GroqModel
from evidence_agent.agent.services import configure_agent, fixture_adapter
from evidence_agent.core.bootstrap import load_demo_tokens
from evidence_agent.core.clock import Clock, utc_clock
from evidence_agent.graph.relations import TraversalLimits
from evidence_agent.live.gateway import load_config
from evidence_agent.main import create_app
from evidence_agent.retrieval.graph_expand import GraphExpansion
from evidence_agent.retrieval.rerank import FastEmbedReranker
from evidence_agent.settings import Settings, load_settings
from evidence_agent.storage.neo4j import Neo4jIndex
from evidence_agent.storage.qdrant import QdrantIndex

APP_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SETTINGS = APP_ROOT / "config/settings.yaml"


def aware_instant(text: str) -> datetime:
    try:
        instant = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("not an ISO 8601 instant") from exc
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise argparse.ArgumentTypeError("the instant needs a UTC offset")
    return instant


def build_parser(settings: Settings) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", type=Path, default=DEFAULT_SETTINGS, help="Explicit settings file")
    parser.add_argument("--root", type=Path, default=Path("runtime/demo"))
    parser.add_argument("--url", default=settings.qdrant_url)
    parser.add_argument("--collection", default=settings.qdrant_collection)
    parser.add_argument("--port", type=int, default=18080)
    parser.add_argument("--rerank", action="store_true")
    parser.add_argument("--enable-graph", action="store_true", help="Explicit optional local graph treatment")
    parser.add_argument("--graph-partition", default=settings.graph_partition)
    parser.add_argument("--graph-timeout",type=float,default=settings.graph_timeout_seconds)
    parser.add_argument("--require-graph", action="store_true", help="Require graph relation verification")
    parser.add_argument("--model", choices=GroqModel.allowed_models, default=settings.model)
    parser.add_argument("--enable-live-llm", action="store_true", help="Explicitly load root .env and enable real Groq messages")
    parser.add_argument("--model-call-interval", type=float, default=0, help="Opt-in seconds between Groq dispatches")
    parser.add_argument("--model-base-url", default=None,
                        help="Counting-proxy address (http loopback only); the provider's address when omitted")
    parser.add_argument("--key-env", default=None,
                        help="Name of an environment variable holding the key, instead of the root .env file")
    parser.add_argument("--completion-cap", type=int, default=DEFAULT_COMPLETION_CAP, help="Completion tokens per call")
    parser.add_argument("--model-timeout", type=float, default=25, help="Seconds one model request may take")
    parser.add_argument("--request-timeout", type=int, default=settings.request_timeout_seconds,
                        help="Seconds one whole message investigation may take")
    parser.add_argument("--evaluator-arm", choices=("B4", "B5", "B6"), default=None,
                        help="Evaluator control arm fixed for every request (B4 no critic and no continuity, B5 no "
                             "critic, B6 full); never serving")
    parser.add_argument("--evaluation-time", default=None, type=aware_instant,
                        help="Fix the time every layer sees to this ISO 8601 instant with an offset (evaluator runs only)")
    parser.add_argument("--acknowledge-not-serving", action="store_true",
                        help="Required with --evaluator-arm: this server is a measurement instrument, not a service")
    return parser


def parse_args(argv: Sequence[str] | None = None) -> tuple[argparse.Namespace, Settings]:
    """Read the settings file named first, then the rest; options that need the live model require its enablement."""
    first = argparse.ArgumentParser(add_help=False)
    first.add_argument("--settings", type=Path, default=DEFAULT_SETTINGS)
    named, _ = first.parse_known_args(argv)
    settings = load_settings(named.settings)
    parser = build_parser(settings)
    args = parser.parse_args(argv)
    if args.model_call_interval and not args.enable_live_llm:
        parser.error("Model call spacing requires --enable-live-llm")
    if (args.model_base_url or args.key_env) and not args.enable_live_llm:
        parser.error("--model-base-url and --key-env require --enable-live-llm")
    if args.model_base_url and not args.key_env:
        parser.error("--model-base-url requires --key-env, so the root .env key is never sent to another address")
    if args.require_graph and not args.enable_graph:
        parser.error("--require-graph requires --enable-graph")
    if args.evaluator_arm and not (args.acknowledge_not_serving and args.enable_live_llm):
        parser.error("--evaluator-arm requires --acknowledge-not-serving and --enable-live-llm")
    if args.acknowledge_not_serving and not args.evaluator_arm:
        parser.error("--acknowledge-not-serving only applies with --evaluator-arm")
    if args.evaluation_time and not args.evaluator_arm:
        parser.error("--evaluation-time only applies with --evaluator-arm")
    try:
        settings = Settings.model_validate({**settings.model_dump(), "graph_enabled": args.enable_graph,
            "graph_required": args.require_graph, "graph_partition": args.graph_partition,
            "graph_timeout_seconds": args.graph_timeout, "request_timeout_seconds": args.request_timeout,
            **({"continuity_enabled": False} if args.evaluator_arm == "B4" else {})})
    except ValueError:
        parser.error("A setting is outside its allowed range")
    return args, settings


def build_model(args: argparse.Namespace) -> GroqModel:
    """The explicitly enabled model; its key comes from the named variable or the root .env, never both."""
    options = {"enabled": True, "model": args.model, "call_interval_seconds": args.model_call_interval,
               "base_url": args.model_base_url, "completion_cap": args.completion_cap, "timeout": args.model_timeout}
    if args.key_env:
        return GroqModel.from_environment(args.key_env, **options)
    return GroqModel.from_env_file(APP_ROOT.parent / ".env", **options)


def evaluation_clock(args: argparse.Namespace) -> Clock:
    """The wall clock, or the one instant an evaluator run fixed for every layer (ADR-0101)."""
    if args.evaluation_time is None:
        return utc_clock
    instant = args.evaluation_time
    return lambda: instant


def build_app(args: argparse.Namespace, settings: Settings, index: QdrantIndex,
              graph: GraphExpansion | None) -> FastAPI:
    """The application exactly as served: the live model, counted transport and evaluator arm only when asked for."""
    app = create_app(args.root, index, load_demo_tokens(args.root), FastEmbedReranker(enabled=args.rerank), graph,
                     evaluation_clock(args))
    app.state.graph_required = args.require_graph
    if args.enable_live_llm:
        configure_agent(app, model=build_model(args), adapter=fixture_adapter(APP_ROOT),
            config=load_config(APP_ROOT / "config/adapters.yaml"),
            settings=settings.model_copy(update={"enable_live_llm": True, "model": args.model}),
            experiment=ExperimentControls(arm=args.evaluator_arm, enabled=True) if args.evaluator_arm else None)
    return app


def main() -> None:
    args, settings = parse_args()
    graph = GraphExpansion(Neo4jIndex(uri=settings.neo4j_uri,partition=settings.graph_partition,
        timeout_seconds=settings.graph_timeout_seconds), TraversalLimits(hops=settings.graph_max_hops,
        fanout=settings.graph_fanout,nodes=settings.graph_max_nodes,edges=settings.graph_max_edges,
        timeout_seconds=settings.graph_timeout_seconds)) if args.enable_graph else None
    index = QdrantIndex(url=args.url, collection_name=args.collection, bm25_profile=settings.bm25_profile)
    try:
        uvicorn.run(build_app(args, settings, index, graph), host="127.0.0.1", port=args.port, log_level="warning")
    finally:
        index.close()
        if graph is not None:
            graph.backend.close()


if __name__ == "__main__":
    main()
