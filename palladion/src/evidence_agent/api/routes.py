"""Source-management API and retrieval consumer; no model/tool/answer runtime."""
from __future__ import annotations

import hashlib
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from fastapi import APIRouter, Header, HTTPException, Request

from evidence_agent.api.schemas import Approval, Search, Upload
from evidence_agent.core.errors import PermissionDenied, ResourceConflict
from evidence_agent.core.models import Principal
from evidence_agent.ingest.metadata import validate_supersession_scope, validate_upload_metadata
from evidence_agent.ingest.pipeline import IngestPipeline
from evidence_agent.retrieval.hybrid import HybridSearch
from evidence_agent.storage.catalog import Catalog
from evidence_agent.storage.originals import OriginalStore
from evidence_agent.storage.registry import Registry
from evidence_agent.storage.sqlite import Database

router = APIRouter()


@contextmanager
def services(request: Request, authorization: str | None) -> Iterator[tuple[Registry, Catalog, Principal]]:
    # Opaque synthetic tokens are provisioned server-side, never accepted as identity fields.
    token = authorization.removeprefix("Bearer ") if authorization and authorization.startswith("Bearer ") else ""
    principal_id = request.app.state.tokens.get(token)
    if not principal_id:
        raise PermissionDenied
    root: Path = request.app.state.runtime_root
    with Database(root / "registry.sqlite") as database:
        registry = Registry(database, OriginalStore(root / "originals"))
        principal = registry.access.authenticate(principal_id)
        yield registry, Catalog(registry), principal


@router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def ready(request: Request) -> dict[str, str]:
    try:
        request.app.state.index.ensure_collection()
    except Exception as exc:
        raise HTTPException(503, "Retrieval dependency unavailable") from exc
    return {"status": "ready"}


@router.post("/sources", status_code=201)
def upload(body: Upload, request: Request, authorization: str | None = Header(default=None)) -> dict[str, str]:
    content = body.content.encode("utf-8")
    with services(request, authorization) as (registry, _, principal):
        validated = validate_upload_metadata(
            registry, principal, tenant_id=principal.tenant_id, case_id=body.case_id,
            family_id=body.family_id, content=content, filename=body.filename,
            content_type=body.mime_type, expected_sha256=body.sha256 or hashlib.sha256(content).hexdigest(),
            source_path=body.filename, owner_id=body.owner_id,
            allowed_principal_ids=tuple(body.allowed_principal_ids),
            valid_from=body.valid_from, valid_to=body.valid_to)
        revision = registry.register_source(
            principal, tenant_id=validated.tenant_id, case_id=validated.case_id,
            family_id=validated.family_id, content=validated.content, source_path=validated.source_path,
            owner_id=validated.owner_id, allowed_principal_ids=validated.allowed_principal_ids,
            valid_from=validated.valid_from, valid_to=validated.valid_to,
        )
        return {"revision_id": revision, "state": "STORED"}


@router.post("/sources/{revision_id}/approve")
def approve(revision_id: str, request: Request,
            body: Approval | None = None,
            authorization: str | None = Header(default=None)) -> dict[str, str]:
    with services(request, authorization) as (registry, catalog, principal):
        # Retry after interrupted indexing is allowed; approval is still independently checked.
        row = registry.source_metadata(principal, revision_id)
        if row["approval_status"] == "DRAFT":
            predecessor = body.supersedes_revision_id if body else None
            if predecessor:
                validate_supersession_scope(
                    registry, principal, predecessor_revision_id=predecessor,
                    successor_tenant_id=principal.tenant_id, successor_case_id=str(row["case_id"]),
                    successor_family_id=str(row["family_id"]),
                    applicability_scope={"tenant_id": principal.tenant_id, "case_id": str(row["case_id"])})
            registry.approve_source(principal, revision_id, supersedes_revision_id=predecessor,
                                    applicability_scope={"tenant_id": principal.tenant_id,
                                                         "case_id": str(row["case_id"])}
                                    if predecessor else None)
        elif row["approval_status"] != "APPROVED":
            raise ResourceConflict
        registry.access.authorize(principal, tenant_id=principal.tenant_id,
                                   case_id=str(row["case_id"]), grant="document:approve", role="admin")
        generation = IngestPipeline(catalog, request.app.state.index).index(principal, revision_id)
        return {"revision_id": revision_id, "generation": generation, "state": "READY"}


@router.post("/sources/{revision_id}/revoke")
def revoke(revision_id: str, request: Request,
           authorization: str | None = Header(default=None)) -> dict[str, str]:
    with services(request, authorization) as (registry, _, principal):
        registry.revoke_source(principal, revision_id)
        return {"revision_id": revision_id, "state": "REVOKED"}


@router.post("/search")
def search(body: Search, request: Request, authorization: str | None = Header(default=None)) -> object:
    with services(request, authorization) as (_, catalog, principal):
        return HybridSearch(catalog, request.app.state.index, request.app.state.ranker).search(
            principal, body.case_id, body.query, mode=body.mode, limit=body.limit)


@router.get("/evidence/{chunk_id}")
def evidence(chunk_id: str, case_id: str, request: Request,
             authorization: str | None = Header(default=None)) -> object:
    with services(request, authorization) as (_, catalog, principal):
        return HybridSearch(catalog, request.app.state.index).resolver.resolve(principal, case_id, chunk_id)


@router.get("/index-health")
def index_health(case_id: str, request: Request,
                 authorization: str | None = Header(default=None)) -> object:
    from evidence_agent.retrieval.coverage import source_coverage

    with services(request, authorization) as (registry, _, principal):
        return source_coverage(registry, principal, case_id, request.app.state.index)
