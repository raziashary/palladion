"""Authenticated source, evidence and bounded agent runtime API."""
from __future__ import annotations

import base64
import binascii
import hashlib
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Annotated, Iterator

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import AwareDatetime

from evidence_agent.api.schemas import (
    Approval,
    CaseProvision,
    GraphLinks,
    MembershipProvision,
    Message,
    MessageResponse,
    PdfUpload,
    PrincipalProvision,
    Search,
    Upload,
)
from evidence_agent.core.errors import PermissionDenied, ResourceConflict
from evidence_agent.core.models import Principal
from evidence_agent.ingest.metadata import validate_supersession_scope, validate_upload_metadata
from evidence_agent.ingest.pipeline import IngestPipeline
from evidence_agent.retrieval.hybrid import HybridSearch
from evidence_agent.storage.applicability import MAX_EXTRA_INSTANTS, Applicability
from evidence_agent.storage.catalog import Catalog
from evidence_agent.storage.originals import OriginalStore
from evidence_agent.storage.registry import Registry
from evidence_agent.storage.sqlite import Database

router = APIRouter()


@router.post("/v1/admin/cases/{case_id}/graph-links")
def register_graph_links(case_id: str, body: GraphLinks, request: Request,
                         authorization: str | None = Header(default=None)) -> object:
    """Register up to16 typed, source-proven navigation candidates atomically.

    Current case-member admins need document:approve and read access to both endpoints
    and exact proof source/version/span. Repeats are idempotent; changed proof conflicts.
    Graph-enabled publication is reconciled before READY. Graph-off returns NOT_ENABLED.
    SUPERSEDES is navigation only and never changes deterministic policy precedence.
    """
    from evidence_agent.graph.registry import GraphRegistry
    with services(request, authorization) as (registry, catalog, principal):
        graph = GraphRegistry(catalog, principal, case_id)
        identifiers = graph.register_links([link.model_dump() for link in body.links])
        expansion = request.app.state.graph
        if expansion is not None:
            revisions = {graph.chunk(identifier).revision_id for link in body.links
                         for identifier in (link.from_chunk_id, link.to_chunk_id, link.evidence_chunk_id)}
            for revision in sorted(revisions):
                IngestPipeline(catalog, request.app.state.index, expansion.backend).index(principal, revision)
        with registry.database.transaction():
            proofs = [graph.link_provenance(identifier) for identifier in identifiers]
        return {"links": proofs, "projection": "READY" if expansion is not None else "NOT_ENABLED"}


@router.get("/v1/cases/{case_id}/graph-links/{edge_id}")
def graph_link(case_id: str, edge_id: str, request: Request,
               authorization: str | None = Header(default=None)) -> object:
    """Read an HTTP-created link's exact proof under current endpoint/source ACLs."""
    from evidence_agent.graph.registry import GraphRegistry
    with services(request, authorization) as (registry, catalog, principal):
        with registry.database.transaction():
            return GraphRegistry(catalog, principal, case_id).link_provenance(edge_id)


@contextmanager
def services(request: Request, authorization: str | None) -> Iterator[tuple[Registry, Catalog, Principal]]:
    # Opaque synthetic tokens are provisioned server-side, never accepted as identity fields.
    token = authorization.removeprefix("Bearer ") if authorization and authorization.startswith("Bearer ") else ""
    principal_id = request.app.state.tokens.get(token)
    if not principal_id:
        raise PermissionDenied
    root: Path = request.app.state.runtime_root
    with Database(root / "registry.sqlite") as database:
        registry = Registry(database, OriginalStore(root / "originals"), request.app.state.clock)
        principal = registry.access.authenticate(principal_id)
        yield registry, Catalog(registry), principal


@router.get("/health/live")
@router.get("/health")
def live() -> dict[str, str]:
    """Report process liveness; no authentication or dependency/provider calls.

    `/health` and `/health/live` are aliases. A healthy process may still be unready.
    """
    return {"status": "ok"}


@router.get("/health/ready")
@router.get("/ready")
def ready(request: Request) -> dict[str, str]:
    """Check SQLite, Qdrant and explicit model configuration without generating text.

    `/ready` and `/health/ready` return503 when any required check fails. An explicitly
    disabled model boundary is reported as disabled; no credentials/config are returned.
    """
    try:
        path = request.app.state.runtime_root / "registry.sqlite"
        # Read-only probe: readiness must not initialize or migrate a registry.
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)) as connection:
            if (connection.execute("PRAGMA application_id").fetchone()[0] != Database.APPLICATION_ID or
                    connection.execute("PRAGMA user_version").fetchone()[0] != Database.SCHEMA_VERSION):
                raise RuntimeError("Registry not initialized")
            connection.execute("SELECT case_id FROM cases LIMIT 1").fetchall()
        request.app.state.index.ensure_collection()
        agent = getattr(request.app.state, "agent_services", None)
        if agent is None:
            raise RuntimeError("Model boundary not explicitly configured")
        if request.app.state.graph_required and (request.app.state.graph is None or
                not request.app.state.graph.backend.ready()):
            raise RuntimeError("Required graph unavailable")
    except Exception as exc:
        raise HTTPException(503, "Required dependency or runtime configuration unavailable") from exc
    return {"status": "ready", "model_boundary": "enabled" if agent.model is not None else "disabled"}


@router.post("/sources", status_code=201)
def upload(body: Upload, request: Request, authorization: str | None = Header(default=None)) -> dict[str, str]:
    """Register immutable source bytes as a draft, returning revision ID/state (201).

    Requires the current tenant/case uploader and document:upload grant. Metadata,
    UTF-8 bytes/hash and source ACL are validated; this does not approve or publish it.
    """
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


@router.post("/sources/import-pdf", status_code=201)
def import_pdf(body: PdfUpload, request: Request,
               authorization: str | None = Header(default=None)) -> object:
    """Import base64 digital-text PDF as a draft with original/page provenance.

    Requires current case document:upload before extraction.2MiB/50pages/256KiB text,
    10seconds/512MiB child cap. Rejects encrypted/scanned/empty/unsupported documents.
    Independent approval and reconciled indexing are still required for citation reads.
    """
    from evidence_agent.ingest.extraction import extract_pdf
    with services(request, authorization) as (registry, _, principal):
        registry.access.authorize(principal, tenant_id=principal.tenant_id,
                                   case_id=body.case_id, grant="document:upload")
        try:
            raw = base64.b64decode(body.content, validate=True)
        except (ValueError, binascii.Error) as error:
            raise ValueError("Invalid PDF encoding") from error
        if not body.filename.lower().endswith(".pdf") or (
            body.sha256 is not None and hashlib.sha256(raw).hexdigest() != body.sha256
        ):
            raise ValueError("PDF filename/hash mismatch")
        extraction = extract_pdf(raw)
        text = extraction["text"].encode()
        validated = validate_upload_metadata(registry, principal,
            tenant_id=principal.tenant_id, case_id=body.case_id, family_id=body.family_id,
            content=text, filename=body.filename + ".txt", content_type="text/plain",
            expected_sha256=hashlib.sha256(text).hexdigest(), source_path=body.filename + ".txt",
            owner_id=body.owner_id, allowed_principal_ids=tuple(body.allowed_principal_ids),
            valid_from=body.valid_from, valid_to=body.valid_to)
        revision = registry.register_extraction(principal, original=raw, filename=body.filename,
            extraction=extraction, tenant_id=principal.tenant_id, case_id=validated.case_id,
            family_id=validated.family_id, owner_id=validated.owner_id,
            allowed_principal_ids=validated.allowed_principal_ids,
            valid_from=validated.valid_from, valid_to=validated.valid_to)
        return {"revision_id": revision, "state": "STORED",
                "original_sha256": hashlib.sha256(raw).hexdigest(),
                "extracted_sha256": hashlib.sha256(text).hexdigest(),
                "page_count": len(extraction["pages"]), "offset_basis": "EXTRACTED_UTF8"}


@router.get("/sources/{revision_id}/original-pdf")
def original_pdf(revision_id: str, request: Request,
                 authorization: str | None = Header(default=None)) -> Response:
    """Read the immutable original PDF only under current approved source ACLs."""
    with services(request, authorization) as (registry, _, principal):
        with registry.database.transaction():
            provenance = registry.extraction_provenance(principal, revision_id)
            if provenance is None:
                raise HTTPException(404, "No PDF provenance")
            return Response(registry.originals.read(provenance["original_sha256"]),
                media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=source.pdf"})


@router.post("/v1/admin/principals")
def provision_principal(body: PrincipalProvision, request: Request,
                        authorization: str | None = Header(default=None)) -> object:
    """Current tenant admin maps a tenant-local subject key to a non-admin profile.

    The submitted principal_id is a local subject key; use the returned tenant-bound
    opaque principal_id in memberships, source ACLs and operator token mappings.
    No token is issued. Grants cannot exceed the issuer's. Conflicting creation returns409; repeats return
    current access without restoring revoked grants. Opaque tokens remain operator-owned.
    """
    with services(request, authorization) as (registry, _, principal):
        return registry.provision_principal(principal, body.principal_id, tuple(body.grants))


@router.post("/v1/admin/cases")
def provision_case(body: CaseProvision, request: Request,
                   authorization: str | None = Header(default=None)) -> object:
    """Current tenant admin creates a case and its own initial membership atomically.

    Repeats require current case membership and never restore a revoked membership.
    This does not create operational scope, policy, source access or credentials.
    """
    with services(request, authorization) as (registry, _, principal):
        registry.provision_case(principal, body.case_id)
        return {"case_id": body.case_id}


@router.post("/v1/admin/cases/{case_id}/memberships")
def provision_membership(case_id: str, body: MembershipProvision, request: Request,
                         authorization: str | None = Header(default=None)) -> object:
    """Current case-member tenant admin adds an existing same-tenant principal.

    A revoked membership remains revoked on repeat (active=false); source ACLs and
    grants remain independent. Models have no provisioning capability.
    """
    with services(request, authorization) as (registry, _, principal):
        active = registry.provision_membership(principal, case_id, body.principal_id)
        return {"case_id": case_id, "principal_id": body.principal_id, "active": active}


@router.post("/sources/{revision_id}/approve")
def approve(revision_id: str, request: Request,
            body: Approval | None = None,
            authorization: str | None = Header(default=None)) -> dict[str, object]:
    """Approve a scoped draft and publish its reconciled retrieval generation.

    Requires the existing independent source-approval authority and current source
    access. Optional supersession must name a compatible predecessor/scope. Returns
    revision state/generation; retries can finish interrupted indexing, never bypass approval.
    """
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
        graph = request.app.state.graph
        generation = IngestPipeline(catalog, request.app.state.index,
            graph.backend if graph is not None else None).index(principal, revision_id)
        from evidence_agent.storage.exact import ExactIndex
        aliases = ExactIndex(catalog).register_approved(principal, revision_id)
        return {"revision_id": revision_id, "generation": generation, "state": "READY",
                "aliases": {"registered": aliases.registered, "truncated": aliases.truncated}}


@router.post("/sources/{revision_id}/revoke")
def revoke(revision_id: str, request: Request,
           authorization: str | None = Header(default=None)) -> dict[str, str]:
    """Revoke a source under current approval authority and return its new state.

    Canonical revocation immediately blocks readers even while derived index data remains.
    """
    with services(request, authorization) as (registry, _, principal):
        registry.revoke_source(principal, revision_id)
        return {"revision_id": revision_id, "state": "REVOKED"}


@router.post("/search")
def search(body: Search, request: Request, authorization: str | None = Header(default=None)) -> object:
    """Retrieve bounded approved passages for a current case/source reader.

    Returns ranked canonical passages, coverage and degradation diagnostics. No LLM is
    invoked; ranking/no hits establish neither truth nor organization-wide absence.
    Optional as_of selects document applicability, never trusted operational event
    time; optional applicability_instants (at most seven) add instants at which a revision may
    apply, so an older version that governed an earlier case time can be returned
    (ADR-0102); current ACL/approval/revocation still apply. Optional token_budget counts
    whole returned passages with the disclosed retrieval tokenizer, not provider tokens.
    Explicit reuse_physical_audit may reuse a healthy audit for at most5seconds from
    its original start, with mode/time disclosed; current canonical checks still run.
    """
    with services(request, authorization) as (_, catalog, principal):
        return HybridSearch(catalog, request.app.state.index, request.app.state.ranker,
            request.app.state.graph).search(principal, body.case_id, body.query, mode=body.mode,
            limit=body.limit, as_of=body.as_of, also_at=body.applicability_instants,
            token_budget=body.token_budget,
            reuse_physical_audit=body.reuse_physical_audit,
            require_graph=body.require_graph or request.app.state.graph_required)


@router.get("/evidence/{chunk_id}")
def evidence(chunk_id: str, case_id: str, request: Request,
             as_of: AwareDatetime | None = None,
             applicability_instants: Annotated[list[AwareDatetime] | None, Query(max_length=MAX_EXTRA_INSTANTS)] = None,
             authorization: str | None = Header(default=None)) -> object:
    """Resolve a P02 document citation to exact approved immutable bytes and metadata.

    Rechecks current case/source access, generation and hashes. Denied/stale references
    cannot expose source text. Other evidence kinds use the versioned reader below.
    """
    with services(request, authorization) as (registry, catalog, principal):
        return HybridSearch(catalog, request.app.state.index).resolver.resolve(
            principal, case_id, chunk_id,
            applicability=Applicability.at(as_of or registry.clock(), applicability_instants or ()))


@router.get("/index-health")
def index_health(case_id: str, request: Request,
                 reuse_physical_audit: bool = False,
                 authorization: str | None = Header(default=None)) -> object:
    """Return supplied-source index coverage to an authorized current case reader.

    Coverage describes registered supplied material, not completeness of all real knowledge.
    Default fresh; explicit reuse_physical_audit enables at most5second physical reuse
    with timestamp/status disclosure, without reusing current canonical authorization.
    """
    from evidence_agent.retrieval.coverage import source_coverage

    with services(request, authorization) as (registry, _, principal):
        return source_coverage(registry, principal, case_id, request.app.state.index,
                               reuse_physical_audit=reuse_physical_audit)


@router.post("/v1/cases/{case_id}/messages", response_model=MessageResponse, response_model_exclude_unset=True)
async def message(case_id: str, body: Message, request: Request,
                   authorization: str | None = Header(default=None)) -> object:
    """Run one bounded investigation for the authenticated current case member.

    Uses server-owned identity, four read tools and deterministic release checks; returns
    disposition, admitted claims/citations, gaps and consumed budgets. Explicitly disabled
    runtime returns503. A200 response may honestly report insufficient verification.
    """
    with services(request, authorization) as (registry, _, principal):
        registry.access.authorize(principal, tenant_id=principal.tenant_id, case_id=case_id, grant="case:read")
    runtime_services = getattr(request.app.state, "agent_services", None)
    if runtime_services is None:
        raise HTTPException(503, "Agent runtime explicitly disabled")
    runtime = runtime_services.begin(principal.principal_id, case_id,body.session_id)
    return await runtime.answer(body.query)


@router.post("/v1/cases/{case_id}/sessions", status_code=201)
def start_session(case_id: str, request: Request,
                  authorization: str | None = Header(default=None)) -> dict[str,str]:
    """Start a private conversation for the authenticated current case member.

    Closes only that owner's previous active case session, preserving all audit rows.
    Episodic recall starts empty; authorized private preferences and case evidence remain.
    No model call or company-policy promotion occurs.
    """
    from evidence_agent.memory.sessions import Sessions
    with services(request,authorization) as (registry,_,principal):
        return {"session_id":Sessions(registry,principal,case_id).start(),"status":"ACTIVE"}


@router.post("/v1/cases/{case_id}/sessions/{session_id}/close")
def close_session(case_id: str, session_id: str, request: Request,
                  authorization: str | None = Header(default=None)) -> dict[str,str]:
    """Close an owned conversation idempotently under current case membership.

    Another member, including an admin, cannot close this owner's session. Further
    messages using its ID are denied; omitted IDs resolve to a new active session.
    """
    from evidence_agent.memory.sessions import Sessions
    with services(request,authorization) as (registry,_,principal):
        Sessions(registry,principal,case_id).close(session_id)
        return {"session_id":session_id,"status":"CLOSED"}


@router.get("/v1/evidence/{evidence_id}")
def runtime_evidence(evidence_id: str, case_id: str, request: Request,
                     authorization: str | None = Header(default=None)) -> object:
    """Read a currently authorized document, live observation, policy or case-event handle.

    Revalidates canonical provenance/freshness/applicability; returns exact document bytes
    or scoped typed metadata. Old memory/policy references grant no operational permission.
    """
    from evidence_agent.retrieval.evidence import public_citation, read_runtime_evidence
    with services(request, authorization) as (_, catalog, principal):
        agent = getattr(request.app.state, "agent_services", None)
        freshness = {} if agent is None else {k: v.max_age_seconds for k, v in agent.config.operations.items()}
        item = read_runtime_evidence(HybridSearch(catalog, request.app.state.index), principal,
                                     case_id, evidence_id, freshness_seconds=freshness)
        view = public_citation(item)
        if item["kind"] == "DOCUMENT":
            view["text"] = item["text"]
        elif item["kind"] == "LIVE_OBSERVATION":
            view.update(data=item["data"], valid=item["valid"])
        elif item["kind"] == "CASE_EVENT":
            view.update(context=item["event"], authority="NONE", verification="REQUIRES_RECHECK")
        else:
            view.update(clause_count=len(item["clause_refs"]), action_permission=False)
        return view


@router.get("/v1/cases/{case_id}/timeline")
def timeline(case_id: str, request: Request, authorization: str | None = Header(default=None)) -> object:
    """Read recent persisted case-runtime event metadata as a current case member.

    Excludes raw questions, prompts, source/tool payloads and rejected draft diagnostics.
    This operational timeline is distinct from the admin-only developer trace.
    """
    from evidence_agent.memory.store import CaseStore
    with services(request, authorization) as (registry, _, principal):
        # Timeline omits prompts, rejected proposals, raw tool data and developer diagnostics.
        events = CaseStore(registry, principal, case_id).recent(limit=20,session_only=False)
        return [{"event_id": e["event_id"], "kind": e["kind"], "at": e["at"],
            "trace_id": e["payload"]["trace_id"],
            "status": e["payload"].get("status") or e["payload"].get("disposition"),
            "main_used": e["payload"].get("main_used"),
            "review_status": e["payload"].get("review_status"),
            "critic_used": e["payload"].get("budget", {}).get("critic_used"),
            "critic_search_used": e["payload"].get("budget", {}).get("critic_search_used")} for e in events]


@router.get("/v1/evidence/{evidence_id}/clauses/{clause_index}")
def policy_clause(evidence_id: str, clause_index: int, version_id: str, case_id: str,
                   request: Request, authorization: str | None = Header(default=None)) -> object:
    """Read exact approved clause bytes cited by this currently admissible policy decision.

    Requires current case/source access and a version/index present in that decision's
    selected or unresolved-candidate references. Returns offsets/text without action permission.
    """
    from evidence_agent.policy.registry import PolicyRegistry, PolicySpec
    from evidence_agent.retrieval.evidence import read_runtime_evidence
    with services(request, authorization) as (registry, catalog, principal):
        item = read_runtime_evidence(HybridSearch(catalog, request.app.state.index), principal, case_id, evidence_id)
        if item["kind"] != "POLICY_DECISION" or not any(
                r["version_id"] == version_id and r["clause_index"] == clause_index for r in item["clause_refs"]):
            raise PermissionDenied
        row = registry.database.connection.execute(
            "SELECT decision_table_json FROM policy_versions WHERE tenant_id=? AND version_id=?",
            (principal.tenant_id, version_id)).fetchone()
        if row is None:
            raise PermissionDenied
        spec = PolicySpec.model_validate_json(row[0])
        clause = spec.clauses[clause_index]
        return {"evidence_id": evidence_id, "version_id": version_id, "revision_id": clause.revision_id,
            "section_id": clause.section_id, "start_byte": clause.start_byte, "end_byte": clause.end_byte,
            "text": PolicyRegistry(registry).read_clause(principal, clause), "action_permission": False}


@router.get("/v1/traces/{trace_id}")
def developer_trace(trace_id: str, case_id: str, request: Request,
                    authorization: str | None = Header(default=None)) -> object:
    """Read redacted runtime/retrieval diagnostics as a current admin AND case member.

    Binds trace ownership through scoped persisted events; missing/foreign references are
    denied. Returns bounded labels/counts/timing, never raw prompts, rejected prose or source data.
    """
    from evidence_agent.telemetry.audit import AuditLog
    with services(request, authorization) as (registry, _, principal):
        return AuditLog(registry).read_case_trace(principal, case_id, trace_id)
