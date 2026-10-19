"""Trusted synthetic setup shared by real seed, evaluation and integration consumers."""
from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import TYPE_CHECKING

from evidence_agent.core.fixtures import load_fixtures
from evidence_agent.core.retrieval import SearchIndex
from evidence_agent.ingest.pipeline import IngestPipeline
from evidence_agent.storage.catalog import Catalog
from evidence_agent.storage.originals import OriginalStore
from evidence_agent.storage.registry import Registry
from evidence_agent.storage.sqlite import Database

if TYPE_CHECKING:
    from evidence_agent.storage.neo4j import Neo4jIndex


def seed(runtime_root: Path, fixture_root: Path, index: SearchIndex,
         graph: Neo4jIndex | None = None) -> dict[str, str]:
    """Idempotently register fixtures. Never restore revoked grants/approvals or reset a store."""
    bundle = load_fixtures(fixture_root)
    runtime_root.mkdir(parents=True, exist_ok=True)
    revisions: dict[str, str] = {}
    indexed_chunks = {}
    with Database(runtime_root / "registry.sqlite") as database:
        registry = Registry(database, OriginalStore(runtime_root / "originals"))
        catalog = Catalog(registry)
        for principal in bundle.principals:
            registry.bootstrap_principal(principal)
        for case in bundle.cases:
            registry.bootstrap_case(case.tenant_id, case.case_id)
            for principal_id in case.allowed_principal_ids:
                registry.bootstrap_membership(registry.access.authenticate(principal_id), case.case_id)
        for source in bundle.sources:
            uploader = next(p for p in bundle.principals if p.tenant_id == source.tenant_id
                            and "document:upload" in p.grants)
            actor = registry.access.authenticate(uploader.principal_id)
            revision = registry.register_source(
                actor, tenant_id=source.tenant_id, case_id=source.case_ids[0],
                family_id=source.family_id, content=(fixture_root / source.path).read_bytes(),
                source_path=source.path, owner_id=source.approved_by or actor.principal_id,
                allowed_principal_ids=source.allowed_principal_ids,
                valid_from=source.valid_from.isoformat() if source.valid_from else None,
                valid_to=source.valid_to.isoformat() if source.valid_to else None)
            revisions[source.source_id] = revision
            if source.approval_state != "APPROVED":
                continue
            admin = registry.access.authenticate(source.approved_by or "")
            metadata = registry.source_metadata(admin, revision)
            if metadata["approval_status"] == "DRAFT":
                registry.approve_source(admin, revision)
            if metadata["approval_status"] == "REVOKED":
                continue
            IngestPipeline(catalog, index, graph).index(admin, revision)
            chunks = catalog.chunks_for_revision(admin, revision)
            indexed_chunks[source.source_id] = chunks
            for chunk in chunks:
                catalog.add_alias(admin, source.source_id, revision, chunk.chunk_id)
                catalog.add_alias(admin, source.family_id, revision, chunk.chunk_id)
                for clause_id, clause in source.clauses.items():
                    if chunk.start_byte <= clause.span_start < chunk.end_byte:
                        catalog.add_alias(admin, clause_id, revision, chunk.chunk_id)
        admin = registry.access.authenticate("admin-a")
        if "SOP-2026-B" in indexed_chunks and "EX-2026-04" in indexed_chunks:
            origin = next(chunk for chunk in indexed_chunks["SOP-2026-B"] if "S26-REVERSAL" in chunk.text)
            target = next(chunk for chunk in indexed_chunks["EX-2026-04"] if "EX-SETTLEMENT-DELAY" in chunk.text)
            catalog.add_context_link(admin, origin.chunk_id, target.chunk_id)
        if graph is not None:
            from evidence_agent.graph.registry import GraphRegistry
            from evidence_agent.ingest.graph_extract import extract_registered_links
            for case in bundle.cases:
                case_admin=next((p for p in bundle.principals if p.tenant_id==case.tenant_id and
                    "admin" in p.roles and case.case_id in p.allowed_case_ids),None)
                if case_admin is not None:
                    extract_registered_links(GraphRegistry(catalog,
                        registry.access.authenticate(case_admin.principal_id),case.case_id))
            for source in bundle.sources:
                if source.source_id in indexed_chunks:
                    actor=registry.access.authenticate(source.approved_by or "")
                    IngestPipeline(catalog,index,graph).index(actor,revisions[source.source_id])
    token_path = runtime_root / "demo_auth.json"
    if not token_path.exists():
        # Exclusive create avoids overwriting a concurrent seed's credential mapping.
        try:
            with token_path.open("x", encoding="utf-8") as stream:
                json.dump({secrets.token_urlsafe(24): p.principal_id for p in bundle.principals}, stream)
        except FileExistsError:
            pass
    return revisions


def load_demo_tokens(runtime_root: Path) -> dict[str, str]:
    """Explicit local synthetic authentication input; never ambient credential discovery."""
    value = json.loads((runtime_root / "demo_auth.json").read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not value or any(
            not isinstance(key, str) or not isinstance(principal, str) for key, principal in value.items()):
        raise ValueError("Invalid synthetic token mapping")
    return value
