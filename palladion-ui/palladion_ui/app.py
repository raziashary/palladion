"""The UI server: a small API in front of Palladion's, plus the static web app."""
from __future__ import annotations

import base64
import binascii
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from palladion_ui import __version__, policies
from palladion_ui.chat import Context, stream_chat
from palladion_ui.personas import Directory, Persona
from palladion_ui.settings import Settings
from palladion_ui.stack import Stack, StackError
from palladion_ui.store import Store
from palladion_ui.upstream import Upstream, UpstreamError

WEB_DIR = Path(__file__).resolve().parents[1] / "web"
COOKIE = "pui_persona"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]", "testserver"}

TEXT_TYPES = {".md": "text/markdown", ".markdown": "text/markdown", ".txt": "text/plain",
              ".json": "application/json", ".jsonl": "application/x-ndjson", ".csv": "text/csv",
              ".tsv": "text/tab-separated-values",
              **{ext: "text/plain" for ext in (
                  ".py .js .jsx .ts .tsx .java .go .rs .c .h .cpp .cs .sql .sh .ps1 .yaml .yml .toml .ini .cfg "
                  ".xml .html .css .log").split()}}
MAX_TEXT_CHARS = 65536
MAX_PDF_BASE64 = 2_796_204


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PersonaBody(Body):
    persona: str


class ModelBody(Body):
    model: str | None = None  # None means search only, with no model


class SessionBody(Body):
    case_id: str


class ChatBody(Body):
    case_id: str
    session_id: str | None = Field(default=None, pattern=r"^sess_[0-9a-f]{32}$")
    query: str = Field(min_length=1, max_length=2048)


class SearchBody(Body):
    case_id: str
    query: str = Field(min_length=1, max_length=2048)
    mode: str = "reranked"
    limit: int = Field(default=8, ge=1, le=40)


class UploadBody(Body):
    case_id: str
    family_id: str = Field(min_length=1, max_length=200)
    filename: str = Field(min_length=1, max_length=200)
    content: str | None = None
    content_base64: str | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    restrict_to: list[str] = Field(default_factory=list, max_length=100)


class ApproveBody(Body):
    case_id: str
    supersedes_revision_id: str | None = None


class CaseBody(Body):
    case_id: str


class SupersedeBody(Body):
    case_id: str
    predecessor_version_id: str
    valid_from: str
    reason: str = Field(min_length=1, max_length=200)


def _ctx(request: Request) -> Context:
    ctx: Context = request.app.state.ctx
    return ctx


def current_persona(request: Request) -> Persona:
    directory = _ctx(request).directory
    persona = directory.persona(request.cookies.get(COOKIE)) or directory.persona("reader-a")
    if persona is None:
        everyone = directory.personas()
        persona = everyone[0] if everyone else None
    if persona is None:
        raise HTTPException(503, "No demo identities were found. Provision Palladion's runtime first.")
    return persona


Me = Annotated[Persona, Depends(current_persona)]


def case_of(persona: Persona, case_id: str) -> str:
    if case_id not in persona.case_ids:
        raise HTTPException(403, f"{persona.id} is not a member of {case_id}.")
    return case_id


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"status": status, "code": code, "message": message}}, status_code=status)


def create_app(settings: Settings | None = None, *, upstream_factory: Callable[[], httpx.AsyncClient] | None = None,
               stack: Stack | None = None, autostart: bool = True, initial_model: str | None = None) -> FastAPI:
    """`initial_model` is an explicit request to start the agent with that model; without it nothing is paid for."""
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        client = upstream_factory() if upstream_factory else httpx.AsyncClient(
            base_url=settings.upstream_url, trust_env=False, timeout=30)
        ctx = Context(settings, Directory(settings.data_root, settings.fixtures_root), Store(settings.state_file),
                      Upstream(client), stack or Stack(settings))
        app.state.ctx = ctx
        if initial_model is not None and settings.managed:
            ctx.stack.begin(initial_model)
        elif autostart and settings.managed and not await ctx.upstream.alive():
            ctx.stack.begin(None)  # search-only: no model, no key, nothing to pay for
        yield
        await client.aclose()
        if settings.managed:
            await ctx.stack.shutdown()

    app = FastAPI(title="Palladion UI", version=__version__, lifespan=lifespan, docs_url=None, redoc_url=None)

    @app.middleware("http")
    async def guard(request: Request, call_next: Callable[..., Any]) -> Response:
        # A local tool: refuse other hosts (DNS rebinding) and cross-site writes (a custom header needs CORS).
        if request.headers.get("host", "").rsplit(":", 1)[0] not in LOCAL_HOSTS:
            return _error(403, "FORBIDDEN", "This UI only answers on localhost.")
        if (request.url.path.startswith("/api/") and request.method not in ("GET", "HEAD")
                and request.headers.get("x-palladion-ui") != "1"):
            return _error(403, "FORBIDDEN", "Missing X-Palladion-UI header.")
        response: Response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(UpstreamError)
    async def upstream_error(_: Request, error: UpstreamError) -> JSONResponse:
        return JSONResponse(error.public(), status_code=min(error.status, 599))

    @app.exception_handler(StackError)
    async def stack_error(_: Request, error: StackError) -> JSONResponse:
        return _error(409, "RUNTIME", str(error))

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, error: HTTPException) -> JSONResponse:
        return _error(error.status_code, "FORBIDDEN" if error.status_code == 403 else "ERROR", str(error.detail))

    # Who and what ---------------------------------------------------------------------------------------------

    @app.get("/api/bootstrap")
    async def bootstrap(request: Request, me: Me) -> dict[str, Any]:
        ctx = _ctx(request)
        return {"version": __version__, "persona": me.public(),
                "personas": [p.public() for p in ctx.directory.personas()],
                "cases": [c.public() for c in ctx.directory.cases_for(me)],
                "models": [{"id": model, "label": label} for model, label in settings.models],
                "runtime": await ctx.stack.status()}

    @app.post("/api/persona")
    async def switch_persona(request: Request, body: PersonaBody, response: Response) -> dict[str, Any]:
        persona = _ctx(request).directory.persona(body.persona)
        if persona is None:
            raise HTTPException(404, "Unknown identity.")
        response.set_cookie(COOKIE, persona.id, httponly=True, samesite="lax")
        return {"persona": persona.public()}

    @app.get("/api/runtime")
    async def runtime(request: Request) -> dict[str, Any]:
        return await _ctx(request).stack.status()

    @app.post("/api/runtime/model")
    async def choose_model(request: Request, body: ModelBody) -> dict[str, Any]:
        ctx = _ctx(request)
        ctx.stack.begin(body.model)
        return await ctx.stack.status()

    # Conversations --------------------------------------------------------------------------------------------

    @app.get("/api/sessions")
    async def sessions(request: Request, me: Me, case_id: str | None = None) -> dict[str, Any]:
        return {"sessions": _ctx(request).store.sessions(me.id, case_id)}

    @app.post("/api/sessions", status_code=201)
    async def new_session(request: Request, me: Me, body: SessionBody) -> dict[str, Any]:
        ctx = _ctx(request)
        case_of(me, body.case_id)
        made = await ctx.upstream.call("POST", f"/v1/cases/{body.case_id}/sessions", ctx.directory.token(me.id))
        return ctx.store.add_session(me.id, body.case_id, made["session_id"])

    @app.get("/api/sessions/{session_id}")
    async def session(request: Request, me: Me, session_id: str) -> dict[str, Any]:
        found = _ctx(request).store.session(me.id, session_id)
        if found is None:
            raise HTTPException(404, "No such session.")
        return found

    @app.post("/api/sessions/{session_id}/close")
    async def close_session(request: Request, me: Me, session_id: str, body: CaseBody) -> dict[str, Any]:
        ctx = _ctx(request)
        case_of(me, body.case_id)
        await ctx.upstream.call("POST", f"/v1/cases/{body.case_id}/sessions/{session_id}/close",
                                ctx.directory.token(me.id))
        ctx.store.close_session(me.id, session_id)
        return {"session_id": session_id, "closed": True}

    @app.post("/api/chat")
    async def chat(request: Request, me: Me, body: ChatBody) -> StreamingResponse:
        ctx = _ctx(request)
        case_of(me, body.case_id)
        session_id = body.session_id
        if session_id is None:
            made = await ctx.upstream.call("POST", f"/v1/cases/{body.case_id}/sessions", ctx.directory.token(me.id))
            session_id = made["session_id"]
            ctx.store.add_session(me.id, body.case_id, session_id)
        elif ctx.store.session(me.id, session_id) is None:
            raise HTTPException(404, "No such session.")
        return StreamingResponse(stream_chat(ctx, me, body.case_id, session_id, body.query),
                                 media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    # Evidence -------------------------------------------------------------------------------------------------

    @app.get("/api/evidence/{evidence_id}")
    async def evidence(request: Request, me: Me, evidence_id: str, case_id: str) -> Any:
        ctx = _ctx(request)
        return await ctx.upstream.call("GET", f"/v1/evidence/{evidence_id}", ctx.directory.token(me.id),
                                       params={"case_id": case_of(me, case_id)})

    @app.get("/api/evidence/{evidence_id}/clauses/{clause_index}")
    async def clause(request: Request, me: Me, evidence_id: str, clause_index: int, case_id: str,
                     version_id: str) -> Any:
        ctx = _ctx(request)
        return await ctx.upstream.call("GET", f"/v1/evidence/{evidence_id}/clauses/{clause_index}",
                                       ctx.directory.token(me.id),
                                       params={"case_id": case_of(me, case_id), "version_id": version_id})

    @app.get("/api/trace/{trace_id}")
    async def trace(request: Request, me: Me, trace_id: str, case_id: str) -> Any:
        ctx = _ctx(request)
        return await ctx.upstream.call("GET", f"/v1/traces/{trace_id}", ctx.directory.token(me.id),
                                       params={"case_id": case_of(me, case_id)})

    @app.post("/api/search")
    async def search(request: Request, me: Me, body: SearchBody) -> Any:
        ctx = _ctx(request)
        return await ctx.upstream.call(
            "POST", "/search", ctx.directory.token(me.id), timeout=90,
            json={"case_id": case_of(me, body.case_id), "query": body.query, "mode": body.mode, "limit": body.limit})

    # Ingestion ------------------------------------------------------------------------------------------------

    @app.get("/api/sources")
    async def sources(request: Request, me: Me, case_id: str) -> dict[str, Any]:
        ctx = _ctx(request)
        token = ctx.directory.token(me.id)
        case_of(me, case_id)
        listing = "palladion"
        try:
            rows = (await ctx.upstream.call("GET", f"/v1/cases/{case_id}/sources", token))["sources"]
        except UpstreamError as error:
            if error.status not in (404, 405):
                raise
            listing = "local"  # an older Palladion has no listing route: show only what this UI uploaded
            rows = ctx.store.sources_for_case(case_id)
        known = {row["revision_id"]: ctx.store.source(row["revision_id"]) or {} for row in rows}
        merged = [{**row, **{k: v for k, v in known[row["revision_id"]].items()
                             if k in ("size", "mime_type", "pdf", "pages", "approved_by", "approved_at",
                                      "generation", "uploaded_by")}} for row in rows]
        try:
            coverage = await ctx.upstream.call("GET", "/index-health", token, params={"case_id": case_id}, timeout=30)
        except UpstreamError:
            coverage = None
        return {"sources": merged, "coverage": coverage, "listing": listing}

    @app.post("/api/sources", status_code=201)
    async def upload(request: Request, me: Me, body: UploadBody) -> dict[str, Any]:
        ctx = _ctx(request)
        case_of(me, body.case_id)
        extension = Path(body.filename).suffix.lower()
        stamp = {"valid_from": f"{body.valid_from}T00:00:00Z" if body.valid_from else None,
                 "valid_to": f"{body.valid_to}T00:00:00Z" if body.valid_to else None}
        owner = ctx.store.family_owner(body.case_id, body.family_id) or me.id
        common = {"case_id": body.case_id, "family_id": body.family_id, "filename": body.filename,
                  "owner_id": owner, "allowed_principal_ids": body.restrict_to, **stamp}
        token = ctx.directory.token(me.id)
        if extension == ".pdf":
            if not body.content_base64 or len(body.content_base64) > MAX_PDF_BASE64:
                raise HTTPException(400, "A PDF must be 2 MiB or smaller.")
            try:
                base64.b64decode(body.content_base64, validate=True)
            except (ValueError, binascii.Error) as error:
                raise HTTPException(400, "The PDF could not be read.") from error
            made = await ctx.upstream.call("POST", "/sources/import-pdf", token, timeout=60,
                                           json={**common, "mime_type": "application/pdf",
                                                 "content": body.content_base64})
            size, mime = len(body.content_base64) * 3 // 4, "application/pdf"
        else:
            mime_type = TEXT_TYPES.get(extension)
            if mime_type is None:
                raise HTTPException(400, f"{extension or 'That file type'} is not supported. Use: "
                                         + ", ".join(sorted({*TEXT_TYPES, '.pdf'})))
            text = body.content
            if text is None and body.content_base64:
                try:
                    text = base64.b64decode(body.content_base64, validate=True).decode("utf-8")
                except (ValueError, binascii.Error) as error:
                    raise HTTPException(400, "The file is not UTF-8 text.") from error
            if not text or not text.strip():
                raise HTTPException(400, "The file is empty.")
            if len(text) > MAX_TEXT_CHARS:
                raise HTTPException(400, f"Text documents are limited to {MAX_TEXT_CHARS:,} characters; "
                                         "split this one, or use a PDF.")
            made = await ctx.upstream.call("POST", "/sources", token, json={**common, "mime_type": mime_type,
                                                                            "content": text})
            size, mime = len(text.encode("utf-8")), mime_type
        entry = {"revision_id": made["revision_id"], "case_id": body.case_id, "family_id": body.family_id,
                 "filename": body.filename, "owner_id": owner, "uploaded_by": me.id, "size": size,
                 "mime_type": mime, "pdf": extension == ".pdf", "pages": made.get("page_count")}
        ctx.store.remember_source(entry)
        return {**made, "filename": body.filename, "family_id": body.family_id, "owner_id": owner}

    @app.post("/api/sources/{revision_id}/approve")
    async def approve(request: Request, me: Me, revision_id: str, body: ApproveBody) -> Any:
        ctx = _ctx(request)
        case_of(me, body.case_id)
        payload = {"supersedes_revision_id": body.supersedes_revision_id} if body.supersedes_revision_id else None
        done = await ctx.upstream.call("POST", f"/sources/{revision_id}/approve", ctx.directory.token(me.id),
                                       json=payload, timeout=120)
        ctx.store.remember_source({"revision_id": revision_id, "approved_by": me.id,
                                   "generation": done.get("generation")})
        return done

    @app.post("/api/sources/{revision_id}/revoke")
    async def revoke(request: Request, me: Me, revision_id: str, body: CaseBody) -> Any:
        ctx = _ctx(request)
        case_of(me, body.case_id)
        return await ctx.upstream.call("POST", f"/sources/{revision_id}/revoke", ctx.directory.token(me.id))

    @app.get("/api/sources/{revision_id}/original-pdf")
    async def original_pdf(request: Request, me: Me, revision_id: str) -> Response:
        ctx = _ctx(request)
        raw = await ctx.upstream.raw("GET", f"/sources/{revision_id}/original-pdf", ctx.directory.token(me.id))
        return Response(raw.content, media_type="application/pdf",
                        headers={"Content-Disposition": "inline; filename=source.pdf"})

    # Policies -------------------------------------------------------------------------------------------------

    @app.get("/api/policies/meta")
    async def policy_meta() -> dict[str, Any]:
        return policies.meta()

    @app.get("/api/policies")
    async def policy_list(request: Request, me: Me, case_id: str) -> Any:
        ctx = _ctx(request)
        return await ctx.upstream.call("GET", "/v1/admin/policies", ctx.directory.token(me.id),
                                       params={"case_id": case_of(me, case_id)})

    @app.post("/api/policies/validate")
    async def policy_validate(draft: dict[str, Any]) -> dict[str, Any]:
        problems = policies.validate_draft(draft)
        return {"ok": not problems, "problems": problems}

    @app.post("/api/policies", status_code=201)
    async def policy_register(request: Request, me: Me, draft: dict[str, Any]) -> Any:
        ctx = _ctx(request)
        for case in draft.get("case_ids", []):
            case_of(me, str(case))
        problems = policies.validate_draft(draft)
        if problems:
            return JSONResponse({"error": {"status": 400, "code": "INVALID", "message": problems[0]["message"],
                                           "problems": problems}}, status_code=400)
        return await ctx.upstream.call("POST", "/v1/admin/policies", ctx.directory.token(me.id),
                                       json=policies.to_payload(draft))

    @app.post("/api/policies/{version_id}/revoke")
    async def policy_revoke(request: Request, me: Me, version_id: str, body: CaseBody) -> Any:
        ctx = _ctx(request)
        case_of(me, body.case_id)
        return await ctx.upstream.call("POST", f"/v1/admin/policies/{version_id}/revoke", ctx.directory.token(me.id))

    @app.post("/api/policies/{version_id}/supersede")
    async def policy_supersede(request: Request, me: Me, version_id: str, body: SupersedeBody) -> Any:
        ctx = _ctx(request)
        case_of(me, body.case_id)
        return await ctx.upstream.call(
            "POST", f"/v1/admin/policies/{version_id}/supersede", ctx.directory.token(me.id),
            json={"predecessor_version_id": body.predecessor_version_id, "case_id": body.case_id,
                  "valid_from": f"{body.valid_from}T00:00:00Z", "reason": body.reason})

    @app.get("/api/health")
    async def health(request: Request) -> dict[str, Any]:
        return {"ui": "ok", "palladion": await _ctx(request).upstream.alive()}

    if WEB_DIR.exists():
        app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app
