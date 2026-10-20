"""Explicit application factory; imports load no credentials, models or services."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Mapping

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from evidence_agent.api.routes import router
from evidence_agent.core.errors import EvidenceAgentError
from evidence_agent.core.retrieval import SearchIndex
from evidence_agent.retrieval.graph_expand import GraphExpansion
from evidence_agent.retrieval.hybrid import Ranker


@asynccontextmanager
async def lifecycle(app: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        runtime = getattr(app.state, "agent_services", None)
        if runtime is not None:
            runtime.close()
        if app.state.graph is not None:
            app.state.graph.backend.close()


def create_app(runtime_root: Path, index: SearchIndex, tokens: Mapping[str, str],
               ranker: Ranker | None = None, graph: GraphExpansion | None = None) -> FastAPI:
    app = FastAPI(title="Palladion evidence prototype", docs_url=None, redoc_url=None, lifespan=lifecycle)
    app.state.runtime_root = runtime_root.resolve()
    app.state.index = index
    app.state.tokens = dict(tokens)
    app.state.ranker = ranker
    app.state.graph = graph
    app.state.graph_required = False

    @app.middleware("http")
    async def bounded_body(request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Require truthful framing and cap bytes before JSON parsing; streaming is bounded too.
        if request.method in {"POST", "PUT", "PATCH"}:
            limit = 3 * 1024 * 1024 if request.url.path == "/sources/import-pdf" else 128 * 1024
            content = bytearray()
            async for piece in request.stream():
                content.extend(piece)
                if len(content) > limit:
                    return JSONResponse({"detail": "Request too large"}, status_code=413)
            request._body = bytes(content)
        return await call_next(request)

    @app.exception_handler(EvidenceAgentError)
    async def domain_error(request: Request, exc: EvidenceAgentError) -> JSONResponse:
        status = {"PERMISSION_DENIED": 403, "VALIDATION_ERROR": 400,
                  "CONFLICT": 409, "UNAVAILABLE": 503}.get(exc.code.value, 500)
        return JSONResponse({"detail": exc.user_summary}, status_code=status)

    @app.exception_handler(ValueError)
    async def invalid_input(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse({"detail": "Invalid request"}, status_code=400)

    app.include_router(router)
    return app
