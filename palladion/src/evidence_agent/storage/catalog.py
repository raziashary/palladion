"""Canonical P02 chunk catalog and exact index-generation reconciliation."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

from evidence_agent.core.errors import PermissionDenied, ResourceConflict, ValidationFailure
from evidence_agent.core.ids import chunk_id as canonical_chunk_id
from evidence_agent.core.models import Principal
from evidence_agent.core.retrieval import Chunk
from evidence_agent.storage.applicability import Applicability
from evidence_agent.storage.registry import Registry, acl_allows
from evidence_agent.storage.sqlite import utc_now

MAX_COVERAGE_CHUNKS = 100000
MAX_ELIGIBLE_REVISIONS = 10000
# Columns of a stored chunk row in `_chunk_values` order; the span columns are canonical and never change.
_CHUNK_COLUMNS = ("tenant_id", "revision_id", "case_id", "section_id", "start_byte", "end_byte", "line_start",
                  "line_end", "text", "content_sha256", "source_sha256", "parent_id", "neighbor_ids_json",
                  "parser_version", "heading_path_json")
_SPAN_COLUMNS = ("tenant_id", "revision_id", "case_id", "start_byte", "end_byte", "line_start", "line_end", "text",
                 "content_sha256", "source_sha256")
MAX_ALIAS_ROWS = 5000
MAX_ALIAS_LENGTH = 256


@dataclass(frozen=True)
class AliasHit:
    """A chunk reached through an exact alias; `defining` when the alias is its revision's own family or revision ID."""

    chunk_id: str
    revision_id: str
    defining: bool


class Catalog:
    """Persist canonical chunks and publish only exact, acknowledged generations."""

    def __init__(self, registry: Registry) -> None:
        self.registry = registry
        self.database = registry.database

    def stage_generation(
        self,
        principal: Principal,
        revision_id: str,
        chunks: Sequence[Chunk],
        *,
        source_bytes: bytes,
        fingerprint: str,
        parser_version: str,
        graph_enabled: bool = False,
        graph_manifest: Mapping[str, str] | None = None,
    ) -> str:
        """Persist expected chunks and return a deterministic retry-safe generation."""
        source = self.registry.source_metadata(principal, revision_id)
        self._require_approved(source)
        if (
            not chunks
            or not fingerprint
            or not parser_version
            or graph_enabled and not graph_manifest
            or not graph_enabled and graph_manifest is not None
            or hashlib.sha256(source_bytes).hexdigest() != source["content_sha256"]
        ):
            raise ValidationFailure
        expected: dict[str, str] = {}
        previous_end = -1
        for chunk in chunks:
            if (
                chunk.tenant_id != source["tenant_id"]
                or chunk.case_id != source["case_id"]
                or chunk.revision_id != revision_id
                or chunk.source_sha256 != source["content_sha256"]
                or chunk.start_byte < 0
                or chunk.end_byte > len(source_bytes)
                or chunk.start_byte < previous_end
                or chunk.chunk_id
                != canonical_chunk_id(chunk.tenant_id, revision_id, chunk.start_byte, chunk.end_byte)
                or source_bytes[chunk.start_byte : chunk.end_byte].decode("utf-8") != chunk.text
                or hashlib.sha256(chunk.text.encode("utf-8")).hexdigest() != chunk.content_sha256
                or chunk.chunk_id in expected
            ):
                raise ValidationFailure
            span = source_bytes[chunk.start_byte : chunk.end_byte]
            expected_line_start = source_bytes[: chunk.start_byte].count(b"\n") + 1
            newline_count = span.count(b"\n")
            expected_line_end = expected_line_start + newline_count - int(span.endswith(b"\n"))
            if chunk.line_start != expected_line_start or chunk.line_end != expected_line_end:
                raise ValidationFailure
            expected[chunk.chunk_id] = chunk.content_sha256
            previous_end = chunk.end_byte
        manifest_hash = _manifest_hash(expected)
        generation_payload = json.dumps(
            [revision_id, source["content_sha256"], fingerprint, parser_version, manifest_hash],
            separators=(",", ":"),
        )
        if graph_enabled:
            assert graph_manifest is not None
            if (len(graph_manifest) > 8192 or any(not isinstance(k,str) or not k or
                    len(k)>120 or not isinstance(v,str) or len(v)!=64 for k,v in graph_manifest.items())):
                raise ValidationFailure
            generation_payload += "|graph-v1|" + _manifest_hash(graph_manifest)
        generation = "gen_" + hashlib.sha256(generation_payload.encode("utf-8")).hexdigest()
        now = utc_now()
        with self.database.transaction() as connection:
            source = self.registry.source_metadata(principal, revision_id)
            self._require_approved(source)
            existing = connection.execute(
                "SELECT fingerprint, parser_version, expected_count, expected_manifest_sha256 "
                "FROM index_generations WHERE tenant_id = ? AND revision_id = ? AND generation = ?",
                (source["tenant_id"], revision_id, generation),
            ).fetchone()
            if existing is not None and tuple(existing) != (
                fingerprint,
                parser_version,
                len(chunks),
                manifest_hash,
            ):
                raise ResourceConflict
            if existing is None:
                connection.execute(
                    "INSERT INTO index_generations "
                    "(tenant_id, revision_id, generation, fingerprint, parser_version, graph_enabled, "
                    "required_backends_json, state, expected_count, expected_manifest_sha256, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, 'INDEXING', ?, ?, ?)",
                    (
                        source["tenant_id"], revision_id, generation, fingerprint, parser_version,
                        int(graph_enabled), json.dumps(["qdrant", "neo4j"] if graph_enabled else ["qdrant"],
                            separators=(",", ":")), len(chunks), manifest_hash, now,
                    ),
                )
            else:
                connection.execute(
                    "UPDATE index_generations SET state = 'INDEXING', ready_at = NULL "
                    "WHERE tenant_id = ? AND revision_id = ? AND generation = ?",
                    (source["tenant_id"], revision_id, generation),
                )
                connection.execute(
                    "DELETE FROM index_backend_manifests "
                    "WHERE tenant_id = ? AND revision_id = ? AND generation = ?",
                    (source["tenant_id"], revision_id, generation),
                )
            if graph_enabled:
                assert graph_manifest is not None
                for identifier, digest in graph_manifest.items():
                    connection.execute("INSERT OR IGNORE INTO index_graph_expectations VALUES(?,?,?,?,?)",
                        (source["tenant_id"],revision_id,generation,identifier,digest))
            for chunk in chunks:
                existing_chunk = connection.execute(
                    "SELECT tenant_id, revision_id, case_id, section_id, start_byte, end_byte, "
                    "line_start, line_end, text, content_sha256, source_sha256, parent_id, "
                    "neighbor_ids_json, parser_version, heading_path_json FROM p02_chunks WHERE chunk_id = ?",
                    (chunk.chunk_id,),
                ).fetchone()
                values = _chunk_values(chunk, parser_version)
                if existing_chunk is None:
                    connection.execute(
                        "INSERT INTO p02_chunks "
                        "(chunk_id, tenant_id, revision_id, case_id, section_id, start_byte, end_byte, "
                        "line_start, line_end, text, content_sha256, source_sha256, parent_id, "
                        "neighbor_ids_json, parser_version, heading_path_json) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (chunk.chunk_id, *values),
                    )
                elif tuple(existing_chunk) != values:
                    # The span, text and hashes are canonical and never change. How a newer parser labels and links
                    # the same span (section, parent, neighbours, heading path) may, once, per parser version.
                    named = dict(zip(_CHUNK_COLUMNS, values))
                    if existing_chunk["parser_version"] == parser_version or any(
                        existing_chunk[column] != named[column] for column in _SPAN_COLUMNS
                    ):
                        raise ResourceConflict
                    connection.execute(
                        "UPDATE p02_chunks SET section_id = ?, parent_id = ?, neighbor_ids_json = ?, "
                        "parser_version = ?, heading_path_json = ? WHERE chunk_id = ?",
                        (named["section_id"], named["parent_id"], named["neighbor_ids_json"],
                         named["parser_version"], named["heading_path_json"], chunk.chunk_id),
                    )
                connection.execute(
                    "INSERT OR IGNORE INTO index_generation_chunks "
                    "(tenant_id, revision_id, generation, chunk_id, content_sha256) VALUES (?, ?, ?, ?, ?)",
                    (source["tenant_id"], revision_id, generation, chunk.chunk_id, chunk.content_sha256),
                )
            persisted = connection.execute(
                "SELECT chunk_id, content_sha256 FROM index_generation_chunks "
                "WHERE tenant_id = ? AND revision_id = ? AND generation = ? ORDER BY chunk_id",
                (source["tenant_id"], revision_id, generation),
            ).fetchall()
            if _manifest_hash({row["chunk_id"]: row["content_sha256"] for row in persisted}) != manifest_hash:
                raise ResourceConflict
            connection.execute(
                "UPDATE document_revisions SET index_state = 'INDEXING', index_generation = ? "
                "WHERE tenant_id = ? AND revision_id = ?",
                (generation, source["tenant_id"], revision_id),
            )
        return generation

    def mark_failed(self, principal: Principal, revision_id: str, generation: str) -> None:
        """Keep an interrupted generation explicitly unpublishable."""
        source = self.registry.source_metadata(principal, revision_id)
        with self.database.transaction() as connection:
            cursor = connection.execute(
                "UPDATE index_generations SET state = 'FAILED', ready_at = NULL "
                "WHERE tenant_id = ? AND revision_id = ? AND generation = ? AND state <> 'READY'",
                (source["tenant_id"], revision_id, generation),
            )
            if cursor.rowcount != 1:
                raise ResourceConflict
            connection.execute(
                "UPDATE document_revisions SET index_state = 'FAILED' "
                "WHERE tenant_id = ? AND revision_id = ? AND index_generation = ?",
                (source["tenant_id"], revision_id, generation),
            )

    def reconcile(
        self,
        principal: Principal,
        revision_id: str,
        generation: str,
        readback: Mapping[str, str],
        *,
        backend: str = "qdrant",
    ) -> bool:
        """Compare exact backend ID/hash readback, then publish atomically."""
        if backend not in {"qdrant", "neo4j"}:
            raise ValidationFailure
        source = self.registry.source_metadata(principal, revision_id)
        tenant_id = str(source["tenant_id"])
        with self.database.transaction() as connection:
            source = self.registry.source_metadata(principal, revision_id)
            self._require_approved(source)
            if source["index_generation"] != generation:
                raise ResourceConflict
            row = connection.execute(
                "SELECT expected_count, expected_manifest_sha256, required_backends_json, state "
                "FROM index_generations WHERE tenant_id = ? AND revision_id = ? AND generation = ?",
                (tenant_id, revision_id, generation),
            ).fetchone()
            if row is None or row["state"] not in {"INDEXING", "FAILED"}:
                raise ResourceConflict
            expected_rows = connection.execute(
                "SELECT chunk_id, content_sha256 FROM index_generation_chunks "
                "WHERE tenant_id = ? AND revision_id = ? AND generation = ? ORDER BY chunk_id",
                (tenant_id, revision_id, generation),
            ).fetchall()
            expected = {item["chunk_id"]: item["content_sha256"] for item in expected_rows}
            canonical_chunks_valid = (len(expected) == row["expected_count"] and
                                      _manifest_hash(expected) == row["expected_manifest_sha256"])
            if backend not in json.loads(row["required_backends_json"]):
                raise ValidationFailure
            if backend == "neo4j":
                expected = {r[0]:r[1] for r in connection.execute(
                    "SELECT item_id,sha256 FROM index_graph_expectations WHERE tenant_id=? AND revision_id=? AND generation=?",
                    (tenant_id,revision_id,generation))}
            exact = dict(readback)
            valid = (
                canonical_chunks_valid
                and bool(expected)
                and exact == expected
            )
            if not valid:
                connection.execute(
                    "UPDATE index_generations SET state = 'FAILED', ready_at = NULL "
                    "WHERE tenant_id = ? AND revision_id = ? AND generation = ?",
                    (tenant_id, revision_id, generation),
                )
                connection.execute(
                    "UPDATE document_revisions SET index_state = 'FAILED' "
                    "WHERE tenant_id = ? AND revision_id = ? AND index_generation = ?",
                    (tenant_id, revision_id, generation),
                )
                return False
            connection.execute(
                "INSERT OR REPLACE INTO index_backend_manifests "
                "(tenant_id, revision_id, generation, backend, expected_count, "
                "expected_manifest_sha256, confirmed_count, confirmed_manifest_sha256, acknowledged_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    tenant_id,
                    revision_id,
                    generation,
                    backend,
                    len(expected),
                    _manifest_hash(expected),
                    len(exact),
                    _manifest_hash(exact),
                    utc_now(),
                ),
            )
            required = tuple(json.loads(row["required_backends_json"]))
            acknowledgments = {
                item["backend"]: (item["expected_count"], item["expected_manifest_sha256"],
                                  item["confirmed_count"], item["confirmed_manifest_sha256"])
                for item in connection.execute(
                    "SELECT backend, expected_count, expected_manifest_sha256, confirmed_count, confirmed_manifest_sha256 "
                    "FROM index_backend_manifests WHERE tenant_id = ? AND revision_id = ? AND generation = ?",
                    (tenant_id, revision_id, generation),
                )
            }
            if not all(
                backend_name in acknowledgments
                and acknowledgments[backend_name][:2] == acknowledgments[backend_name][2:]
                for backend_name in required
            ):
                return False
            now = utc_now()
            connection.execute(
                "UPDATE index_generations SET state = 'READY', ready_at = ? "
                "WHERE tenant_id = ? AND revision_id = ? AND generation = ?",
                (now, tenant_id, revision_id, generation),
            )
            connection.execute(
                "UPDATE document_revisions SET index_state = 'READY', index_generation = ? "
                "WHERE tenant_id = ? AND revision_id = ?",
                (generation, tenant_id, revision_id),
            )
            return True

    def get_chunk(self, principal: Principal, chunk_id: str) -> Chunk:
        """Return a typed canonical chunk only after current source ACL checks."""
        row = self.database.connection.execute(
            "SELECT * FROM p02_chunks WHERE chunk_id = ? AND tenant_id = ?",
            (chunk_id, principal.tenant_id),
        ).fetchone()
        if row is None:
            raise PermissionDenied
        source = self.registry.source_metadata(principal, row["revision_id"])
        self._require_approved(source)
        return _to_chunk(row)

    def chunks_for_revision(self, principal: Principal, revision_id: str) -> tuple[Chunk, ...]:
        """Return persisted chunks in original order after current ACL checks."""
        source = self.registry.source_metadata(principal, revision_id)
        self._require_approved(source)
        rows = self.database.connection.execute(
            "SELECT * FROM p02_chunks WHERE tenant_id = ? AND revision_id = ? ORDER BY start_byte, end_byte",
            (principal.tenant_id, revision_id),
        ).fetchall()
        return tuple(_to_chunk(row) for row in rows)

    def generation_for_revision(
        self, principal: Principal, revision_id: str
    ) -> dict[str, object] | None:
        """Return the newest generation, including failed state for retry callers."""
        self.registry.source_metadata(principal, revision_id)
        row = self.database.connection.execute(
            "SELECT * FROM index_generations WHERE tenant_id = ? AND revision_id = ? "
            "ORDER BY created_at DESC, generation DESC LIMIT 1",
            (principal.tenant_id, revision_id),
        ).fetchone()
        return _generation_record(row) if row is not None else None

    def manifest_for_generation(
        self, principal: Principal, revision_id: str, generation: str
    ) -> dict[str, str]:
        """Return the persisted exact expected chunk-ID to content-hash manifest."""
        self.registry.source_metadata(principal, revision_id)
        rows = self.database.connection.execute(
            "SELECT chunk_id, content_sha256 FROM index_generation_chunks "
            "WHERE tenant_id = ? AND revision_id = ? AND generation = ? ORDER BY chunk_id",
            (principal.tenant_id, revision_id, generation),
        ).fetchall()
        if not rows:
            raise ResourceConflict
        return {row["chunk_id"]: row["content_sha256"] for row in rows}

    def coverage_manifests(
        self, principal: Principal, case_id: str, revisions: Mapping[str, str]
    ) -> dict[tuple[str, str], dict[str, str]]:
        """Revalidate current coverage scope and load bounded canonical manifests.

        Called after physical readback: no network work occurs under this transaction.
        Missing, revoked, private or replaced generations cannot become healthy coverage.
        """
        if len(revisions) > 10000 or any(not r or not g for r, g in revisions.items()):
            raise ValidationFailure
        result: dict[tuple[str, str], dict[str, str]] = {}
        count = 0
        with self.database.transaction() as connection:
            self.registry.access.authorize(principal, tenant_id=principal.tenant_id,
                                           case_id=case_id, grant="source:read")
            items = list(revisions.items())
            for start in range(0, len(items), 64):
                batch = dict(items[start:start + 64])
                placeholders = ",".join("?" for _ in batch)
                rows = connection.execute(
                    "SELECT d.revision_id,d.index_generation,d.acl_json,d.approval_status,"
                    "a.status AS approval_record_status,m.chunk_id,m.content_sha256 "
                    "FROM document_revisions d LEFT JOIN approval_records a "
                    "ON a.approval_record_id=d.approval_record_id AND a.tenant_id=d.tenant_id "
                    "AND a.revision_id=d.revision_id LEFT JOIN index_generation_chunks m "
                    "ON m.tenant_id=d.tenant_id AND m.revision_id=d.revision_id "
                    "AND m.generation=d.index_generation WHERE d.tenant_id=? AND d.case_id=? "
                    f"AND d.index_state='READY' AND d.revision_id IN ({placeholders})",
                    (principal.tenant_id, case_id, *batch),
                )
                found: set[str] = set()
                for row in rows:
                    count += 1
                    if count > MAX_COVERAGE_CHUNKS:
                        raise ResourceConflict
                    allowed = json.loads(row["acl_json"]).get("allowed_principal_ids", [])
                    if (row["approval_status"] != "APPROVED"
                            or row["approval_record_status"] != "APPROVED"
                            or allowed and principal.principal_id not in allowed
                            or batch[row["revision_id"]] != row["index_generation"]):
                        raise PermissionDenied
                    if row["chunk_id"] is None:
                        raise ResourceConflict
                    found.add(row["revision_id"])
                    result.setdefault((row["revision_id"], row["index_generation"]), {})[
                        row["chunk_id"]] = row["content_sha256"]
                if found != set(batch):
                    raise PermissionDenied
        return result

    def eligible_generation_metadata(
        self, principal: Principal, revision_id: str
    ) -> dict[str, object] | None:
        """Return a generation only when canonical revision and manifest are READY."""
        source = self.registry.source_metadata(principal, revision_id)
        self._require_approved(source)
        if source["index_state"] != "READY":
            return None
        row = self.database.connection.execute(
            "SELECT * FROM index_generations WHERE tenant_id = ? AND revision_id = ? "
            "AND generation = ? AND state = 'READY'",
            (principal.tenant_id, revision_id, source["index_generation"]),
        ).fetchone()
        if row is None:
            return None
        return _generation_record(row)

    def graph_manifest_for_generation(self, principal: Principal, revision_id: str,
                                     generation: str) -> dict[str,str]:
        self.registry.source_metadata(principal,revision_id)
        return {r[0]:r[1] for r in self.database.connection.execute(
            "SELECT item_id,sha256 FROM index_graph_expectations WHERE tenant_id=? AND revision_id=? AND generation=?",
            (principal.tenant_id,revision_id,generation))}

    def add_aliases(
        self, principal: Principal, revision_id: str, pairs: Sequence[tuple[str, str]]
    ) -> None:
        """Register exact aliases of one revision's chunks all together or not at all, retry-safely."""
        normalized = [(_normalize_alias(alias), alias, chunk_id) for alias, chunk_id in pairs]
        with self.database.transaction() as connection:
            source = self.registry.source_metadata(principal, revision_id)
            names = {_normalize_alias(str(source["family_id"])), _normalize_alias(revision_id)}
            self._require_approved(source)
            self.registry.access.authorize(
                principal,
                tenant_id=principal.tenant_id,
                case_id=str(source["case_id"]),
                grant="document:approve",
                role="admin",
            )
            known = {row[0] for row in connection.execute(
                "SELECT chunk_id FROM p02_chunks WHERE tenant_id = ? AND revision_id = ?",
                (principal.tenant_id, revision_id))}
            if any(chunk_id not in known for _, _, chunk_id in normalized):
                raise ValidationFailure
            connection.executemany(
                "INSERT OR IGNORE INTO exact_aliases "
                "(tenant_id, case_id, normalized_alias, alias, revision_id, chunk_id, defining) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [(principal.tenant_id, source["case_id"], key, alias, revision_id, chunk_id, int(key in names))
                 for key, alias, chunk_id in normalized],
            )

    def alias_hits(self, principal: Principal, case_id: str, alias: str, *, limit: int | None = None,
                   generations: Collection[str] | None = None) -> tuple[AliasHit, ...]:
        """Resolve only exact normalized aliases within the caller's case scope, defining chunks first.

        Order is stable and meaningful: chunks of a revision the alias names (its family or revision ID) before chunks
        that merely mention it, then revision, then position in the document. The alias row records which it is.
        Given `generations` (the prefilter's answer), a hit whose revision is served from another generation is
        left out before `limit` counts, so a superseded version cannot crowd out the one that applies.
        """
        self.registry.access.authorize(
            principal,
            tenant_id=principal.tenant_id,
            case_id=case_id,
            grant="source:read",
        )
        if limit is not None and not 1 <= limit <= 101:
            raise ValidationFailure
        rows = self.database.connection.execute(
            "SELECT aliases.chunk_id, aliases.revision_id, aliases.defining, revisions.index_generation "
            "FROM exact_aliases AS aliases "
            "JOIN document_revisions AS revisions "
            "ON revisions.tenant_id = aliases.tenant_id AND revisions.revision_id = aliases.revision_id "
            "JOIN p02_chunks AS chunks ON chunks.tenant_id = aliases.tenant_id AND chunks.chunk_id = aliases.chunk_id "
            "WHERE aliases.tenant_id = ? AND aliases.case_id = ? AND aliases.normalized_alias = ? "
            "AND revisions.approval_status = 'APPROVED' AND revisions.index_state = 'READY' "
            "AND (COALESCE(json_array_length(json_extract(revisions.acl_json,'$.allowed_principal_ids')), 0)=0 "
            "OR EXISTS(SELECT 1 FROM json_each(revisions.acl_json,'$.allowed_principal_ids') WHERE value=?)) "
            "ORDER BY aliases.defining DESC, aliases.revision_id, chunks.start_byte, aliases.chunk_id LIMIT ?",
            (principal.tenant_id, case_id, _normalize_alias(alias), principal.principal_id, MAX_ALIAS_ROWS),
        ).fetchall()
        result: list[AliasHit] = []
        for row in rows:
            if generations is not None and row["index_generation"] not in generations:
                continue
            hit = AliasHit(row["chunk_id"], row["revision_id"], bool(row["defining"]))
            if limit is not None and len(result) >= limit:
                break
            try:
                self.registry.source_metadata(principal, hit.revision_id)
            except PermissionDenied:
                continue
            result.append(hit)
        return tuple(result)

    def effective_supersessions(self, tenant_id: str, case_id: str, fingerprint: str,
                                revision_id: str | None = None) -> dict[str, list[str]]:
        """When each predecessor in the case stops applying, by predecessor revision.

        An edge counts once its successor can be served under the serving representation `fingerprint`: while the
        successor is approved but still indexing, failed, or indexed under another representation, the predecessor
        keeps answering, and a revoked successor still retires it (ADR-0108). One revision's edges when
        `revision_id` is given.
        """
        effective: dict[str, list[str]] = {}
        for edge in self.database.connection.execute(
            "SELECT edges.predecessor_revision_id, edges.applicability_scope_json, edges.valid_from "
            "FROM supersession_edges AS edges "
            "JOIN document_revisions AS predecessors ON predecessors.tenant_id = edges.tenant_id "
            "AND predecessors.revision_id = edges.predecessor_revision_id "
            "JOIN document_revisions AS successor ON successor.tenant_id = edges.tenant_id "
            "AND successor.revision_id = edges.successor_revision_id "
            "WHERE edges.tenant_id = ? AND predecessors.case_id = ? "
            "AND (? IS NULL OR edges.predecessor_revision_id = ?) "
            "AND NOT (successor.approval_status = 'APPROVED' AND NOT (successor.index_state = 'READY' AND EXISTS("
            "SELECT 1 FROM index_generations AS generations WHERE generations.tenant_id = successor.tenant_id "
            "AND generations.revision_id = successor.revision_id "
            "AND generations.generation = successor.index_generation AND generations.state = 'READY' "
            "AND generations.fingerprint = ?)))",
            (tenant_id, case_id, revision_id, revision_id, fingerprint)):
            if json.loads(edge[1]).get("case_id") == case_id:
                effective.setdefault(edge[0], []).append(edge[2])
        return effective

    def eligible_generations(self, principal: Principal, case_id: str, applicability: Applicability, *,
                             fingerprint: str) -> tuple[str, ...] | None:
        """Index generations of the case's revisions the caller may read that the applicability admits.

        Returns None past the bound. A generation names exactly one revision, so this also leaves out the points of
        the earlier generations of a revision that was indexed again. It uses the predicates the evidence resolver
        enforces (approved record, READY revision and generation of the serving fingerprint, window, supersession,
        ACL). The resolver still decides every returned passage, so this only decides what the index may offer.
        """
        self.registry.access.authorize(principal, tenant_id=principal.tenant_id, case_id=case_id, grant="source:read")
        rows = self.database.connection.execute(
            "SELECT revisions.revision_id, revisions.index_generation, revisions.valid_from, revisions.valid_to, "
            "revisions.acl_json "
            "FROM document_revisions AS revisions "
            "JOIN approval_records AS approvals ON approvals.approval_record_id = revisions.approval_record_id "
            "AND approvals.tenant_id = revisions.tenant_id AND approvals.revision_id = revisions.revision_id "
            "JOIN index_generations AS generations ON generations.tenant_id = revisions.tenant_id "
            "AND generations.revision_id = revisions.revision_id AND generations.generation = revisions.index_generation "
            "WHERE revisions.tenant_id = ? AND revisions.case_id = ? AND revisions.approval_status = 'APPROVED' "
            "AND revisions.index_state = 'READY' AND approvals.status = 'APPROVED' "
            "AND generations.state = 'READY' AND generations.fingerprint = ? LIMIT ?",
            (principal.tenant_id, case_id, fingerprint, MAX_ELIGIBLE_REVISIONS + 1),
        ).fetchall()
        if len(rows) > MAX_ELIGIBLE_REVISIONS:
            return None
        superseded = self.effective_supersessions(principal.tenant_id, case_id, fingerprint)
        return tuple(
            row["index_generation"] for row in rows
            if acl_allows(row["acl_json"], principal.principal_id)
            and applicability.admits(row["valid_from"], row["valid_to"], superseded.get(row["revision_id"], ()))
        )

    def add_context_link(
        self,
        actor: Principal,
        from_chunk_id: str,
        to_chunk_id: str,
        relation: str = "EXCEPTION_TO",
    ) -> None:
        """Persist an authenticated, source-linked structural exception relation."""
        if relation != "EXCEPTION_TO":
            raise ValidationFailure
        from_chunk = self.database.connection.execute(
            "SELECT revision_id, case_id FROM p02_chunks WHERE tenant_id = ? AND chunk_id = ?",
            (actor.tenant_id, from_chunk_id),
        ).fetchone()
        to_chunk = self.database.connection.execute(
            "SELECT revision_id, case_id FROM p02_chunks WHERE tenant_id = ? AND chunk_id = ?",
            (actor.tenant_id, to_chunk_id),
        ).fetchone()
        if from_chunk is None or to_chunk is None or from_chunk["case_id"] != to_chunk["case_id"]:
            raise PermissionDenied
        self.registry.access.authorize(
            actor,
            tenant_id=actor.tenant_id,
            case_id=from_chunk["case_id"],
            grant="document:approve",
            role="admin",
        )
        for revision in {from_chunk["revision_id"], to_chunk["revision_id"]}:
            source = self.registry.source_metadata(actor, revision)
            self._require_approved(source)
        with self.database.transaction() as connection:
            self.registry.access.authorize(
                actor,
                tenant_id=actor.tenant_id,
                case_id=from_chunk["case_id"],
                grant="document:approve",
                role="admin",
            )
            connection.execute(
                "INSERT OR IGNORE INTO context_links "
                "(tenant_id, case_id, from_chunk_id, to_chunk_id, relation, actor_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    actor.tenant_id, from_chunk["case_id"], from_chunk_id, to_chunk_id,
                    relation, actor.principal_id, utc_now(),
                ),
            )

    def context_links(self, principal: Principal, chunk_id: str) -> tuple[str, ...]:
        """Return directly linked targets after read authorization on both sources."""
        source_chunk = self.get_chunk(principal, chunk_id)
        rows = self.database.connection.execute(
            "SELECT links.to_chunk_id FROM context_links AS links "
            "WHERE links.tenant_id = ? AND links.case_id = ? AND links.from_chunk_id = ? "
            "AND links.relation = 'EXCEPTION_TO' ORDER BY links.to_chunk_id",
            (principal.tenant_id, source_chunk.case_id, chunk_id),
        ).fetchall()
        visible: list[str] = []
        for row in rows:
            try:
                self.get_chunk(principal, row["to_chunk_id"])
            except PermissionDenied:
                continue
            visible.append(row["to_chunk_id"])
        return tuple(visible)

    @staticmethod
    def _require_approved(source: Mapping[str, object]) -> None:
        if (
            source["approval_status"] != "APPROVED"
            or source["approval_record_status"] != "APPROVED"
        ):
            raise PermissionDenied


def _normalize_alias(alias: str) -> str:
    if not isinstance(alias, str) or not alias.strip() or len(alias) > MAX_ALIAS_LENGTH:
        raise ValidationFailure
    return alias.strip().casefold()


def _manifest_hash(chunks: Mapping[str, str]) -> str:
    canonical = json.dumps(dict(sorted(chunks.items())), separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _chunk_values(chunk: Chunk, parser_version: str) -> tuple[object, ...]:
    return (
        chunk.tenant_id,
        chunk.revision_id,
        chunk.case_id,
        chunk.section_id,
        chunk.start_byte,
        chunk.end_byte,
        chunk.line_start,
        chunk.line_end,
        chunk.text,
        chunk.content_sha256,
        chunk.source_sha256,
        chunk.parent_id,
        json.dumps(chunk.neighbor_ids, separators=(",", ":")),
        parser_version,
        json.dumps(chunk.heading_path, separators=(",", ":"), ensure_ascii=False),
    )


def _to_chunk(row: sqlite3.Row) -> Chunk:
    return Chunk(
        chunk_id=row["chunk_id"],
        tenant_id=row["tenant_id"],
        case_id=row["case_id"],
        revision_id=row["revision_id"],
        section_id=row["section_id"],
        start_byte=row["start_byte"],
        end_byte=row["end_byte"],
        line_start=row["line_start"],
        line_end=row["line_end"],
        text=row["text"],
        content_sha256=row["content_sha256"],
        source_sha256=row["source_sha256"],
        parent_id=row["parent_id"],
        neighbor_ids=tuple(json.loads(row["neighbor_ids_json"])),
        heading_path=tuple(json.loads(row["heading_path_json"])),
    )


def _generation_record(row: sqlite3.Row) -> dict[str, object]:
    return {
        "tenant_id": row["tenant_id"],
        "revision_id": row["revision_id"],
        "generation": row["generation"],
        "fingerprint": row["fingerprint"],
        "parser_version": row["parser_version"],
        "graph_enabled": bool(row["graph_enabled"]),
        "required_backends": tuple(json.loads(row["required_backends_json"])),
        "state": row["state"],
        "expected_count": row["expected_count"],
        "expected_manifest_sha256": row["expected_manifest_sha256"],
        "created_at": row["created_at"],
        "ready_at": row["ready_at"],
    }
