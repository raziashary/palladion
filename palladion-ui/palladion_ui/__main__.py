"""python -m palladion_ui — serve the UI and, by default, manage Qdrant and Palladion underneath it."""
from __future__ import annotations

import argparse

import uvicorn

from palladion_ui.app import create_app
from palladion_ui.settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, help="UI port (default 8765)")
    parser.add_argument("--upstream-port", type=int, help="Palladion API port (default 18480)")
    parser.add_argument("--no-manage", action="store_true",
                        help="Do not start or stop Palladion; point the UI at one that is already running")
    parser.add_argument("--model", help="Start the agent with this model now (explicit enablement); "
                                        "otherwise the runtime starts search-only and a model is chosen in the UI")
    args = parser.parse_args()
    base = Settings.from_env()
    values = {**base.__dict__}
    if args.port:
        values["port"] = args.port
    if args.upstream_port:
        values["upstream_port"] = args.upstream_port
    if args.no_manage:
        values["managed"] = False
    settings = Settings(**values)
    app = create_app(settings, initial_model=args.model)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="warning")


if __name__ == "__main__":
    main()
