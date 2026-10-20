"""Backend-only event promotion with atomic, replayable original-span provenance."""

from __future__ import annotations

import json
import uuid
from typing import Any

from evidence_agent.core.errors import PermissionDenied
from evidence_agent.core.ids import digest_bytes
from evidence_agent.memory.classification import (
    Classification,
    SimilaritySupplement,
    deterministic,
    deterministic_profile,
)
from evidence_agent.memory.store import CaseStore, MemorySpec
from evidence_agent.storage.sqlite import utc_now

TOOLS = {"search_knowledge", "evaluate_policy", "lookup_live_data", "recall_memory"}


def event_view(kind: str, payload: dict[str, Any]) -> tuple[str, str, str | None]:
    """Whitelist projections: never copy tool payloads, prompts or model reasoning."""
    if kind == "RUNTIME_REQUEST" and isinstance(payload.get("query"), str):
        return "query", payload["query"], None
    tool, status = payload.get("tool"), payload.get("status")
    if (
        kind == "RUNTIME_TOOL_RESULT"
        and tool in TOOLS
        and status in {"SUCCEEDED", "FAILED", "CANCELLED"}
    ):
        return "tool_summary", f"Observed tool experience: {tool} returned {status}.", tool
    if kind == "RUNTIME_RELEASE" and payload.get("disposition") in {
        "SUPPORTED",
        "PARTIALLY_SUPPORTED",
        "CONFLICT",
        "NOT_ESTABLISHED",
        "VERIFICATION_UNAVAILABLE",
    }:
        return "release_summary", "Session answer disposition: " + payload["disposition"], None
    return "", "", None


def source_chunk(
    case: CaseStore, chunk_id: str, *, owner_id: str | None = None
) -> tuple[dict[str, Any], str]:
    """Re-read the original event and verify UTF-8 offsets and immutable digest."""
    case.authorize()
    owner_id = owner_id or case.principal.principal_id
    if owner_id != case.principal.principal_id:
        case.registry.access.authorize(
            case.principal,
            tenant_id=case.principal.tenant_id,
            case_id=case.case_id,
            role="admin",
            grant="document:approve",
        )
    row = case.registry.database.connection.execute(
        "SELECT c.*, e.event_kind,e.payload_json,e.actor_id,e.tenant_id,e.case_id "
        "FROM memory_event_chunks c JOIN case_events e USING(event_id) "
        "JOIN memory_event_sessions s ON s.event_id=c.event_id AND s.session_id=c.session_id "
        "WHERE c.chunk_id=? AND e.tenant_id=? AND e.actor_id=?",
        (chunk_id, case.principal.tenant_id, owner_id),
    ).fetchone()
    if row is None:
        raise PermissionDenied
    case.registry.access.authorize(
        case.principal, tenant_id=row["tenant_id"], case_id=row["case_id"], grant="case:read"
    )
    field, text, _ = event_view(row["event_kind"], json.loads(row["payload_json"]))
    encoded = text.encode()
    if field != row["field_name"] or not 0 <= row["start_byte"] < row["end_byte"] <= len(encoded):
        raise PermissionDenied
    span = encoded[row["start_byte"] : row["end_byte"]]
    if digest_bytes(span) != row["text_sha256"]:
        raise PermissionDenied
    try:
        return dict(row), span.decode()
    except UnicodeDecodeError as error:
        raise PermissionDenied from error


class PromotionEngine:
    """Path A is automatic; Path B is supplied only by an explicitly enabled job."""

    def __init__(self, case: CaseStore, supplement: SimilaritySupplement | None = None) -> None:
        self.case, self.supplement = case, supplement

    def process(self, event_id: str) -> dict[str, int]:
        self.case.authorize()
        db = self.case.registry.database.connection
        row = db.execute(
            "SELECT e.*,s.session_id FROM case_events e JOIN memory_event_sessions s "
            "USING(event_id) WHERE e.event_id=? AND e.tenant_id=? AND e.case_id=? AND e.actor_id=?",
            (
                event_id,
                self.case.principal.tenant_id,
                self.case.case_id,
                self.case.principal.principal_id,
            ),
        ).fetchone()
        if row is None or row["session_id"] != self.case.session_id:
            raise PermissionDenied
        field, text, tool = event_view(row["event_kind"], json.loads(row["payload_json"]))
        if not text:
            return {"processed": 0, "promoted": 0, "omitted_bytes": 0}
        # Splitting must never turn an attributed/blocked complete request into a preference.
        whole = (
            deterministic(text, field_name=field, tool=tool) if len(text.encode()) <= 4096 else None
        )
        chunks = [text[i : i + 512] for i in range(0, min(len(text), 4096), 512)]
        classified: list[tuple[str, Classification]] = []
        for chunk in chunks:
            primary = deterministic(chunk, field_name=field, tool=tool)
            if field == "query" and (
                len(chunks) > 1 or whole is None or whole.rule_id == "HARD_EPISODIC_BOUNDARY"
            ):
                primary = Classification("EPISODIC", "WHOLE_EVENT_BOUNDARY", {"path_a": 1.0})
            classified.append(
                (chunk, self.supplement.classify(chunk, primary) if self.supplement else primary)
            )
        profile = {
            "version": "promotion-2",
            "deterministic": deterministic_profile(),
            "chunk_chars": 512,
            "max_chunks": 8,
            "supplement": self.supplement.profile
            if self.supplement and any(item.model_fingerprint for _, item in classified)
            else None,
        }
        fingerprint = digest_bytes(json.dumps(profile, sort_keys=True).encode())
        processed = promoted = offset = 0
        with self.case.registry.database.transaction() as connection:
            self.case.authorize()
            for text_chunk, decision in classified:
                end = offset + len(text_chunk.encode())
                chunk_id = "mchunk_" + digest_bytes(f"{event_id}:{field}:{offset}:{end}".encode())
                connection.execute(
                    "INSERT OR IGNORE INTO memory_event_chunks VALUES(?,?,?,?,?,?,?,?)",
                    (
                        chunk_id,
                        event_id,
                        self.case.session_id,
                        field,
                        offset,
                        end,
                        digest_bytes(text_chunk.encode()),
                        utc_now(),
                    ),
                )
                _, verified = source_chunk(self.case, chunk_id)
                if verified != text_chunk:
                    raise PermissionDenied
                offset = end
                if connection.execute(
                    "SELECT 1 FROM memory_promotion_decisions WHERE chunk_id=? "
                    "AND profile_sha256=?",
                    (chunk_id, fingerprint),
                ).fetchone():
                    continue
                previous = connection.execute(
                    "SELECT l.memory_id,d.category FROM memory_promotion_links l "
                    "JOIN memory_promotion_decisions d USING(decision_id) WHERE l.chunk_id=?",
                    (chunk_id,),
                ).fetchone()
                if previous is not None:
                    # Explicit correction/revocation wins over later automatic jobs.
                    existing = self.case.memory().read(previous["memory_id"])
                    audit = connection.execute(
                        "SELECT payload_json FROM case_events WHERE event_id=?",
                        (existing["source_event_id"],),
                    ).fetchone()
                    if audit is None or not json.loads(audit[0]).get("automatic_promotion", False):
                        continue
                decision_id = "mpd_" + uuid.uuid4().hex
                connection.execute(
                    "INSERT INTO memory_promotion_decisions VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        decision_id,
                        chunk_id,
                        fingerprint,
                        decision.category,
                        decision.rule_id,
                        json.dumps({**decision.scores, "_profile": profile}, sort_keys=True),
                        decision.loss,
                        "DECIDED",
                        utc_now(),
                    ),
                )
                # Preserve immutable history while replacing only the derived current link.
                if previous is None or previous["category"] != decision.category:
                    identifier = self.case.memory().write(
                        MemorySpec(
                            memory_kind=decision.category,
                            scope_id=self.case.principal.principal_id,
                            content=text_chunk,
                            validity_policy_id="UNSPECIFIED",
                        ),
                        supersedes_id=previous["memory_id"] if previous else None,
                        _connection=connection,
                    )
                    connection.execute(
                        "INSERT INTO memory_promotion_links VALUES(?,?,?) "
                        "ON CONFLICT(chunk_id) DO UPDATE SET memory_id=excluded.memory_id,decision_id=excluded.decision_id",
                        (chunk_id, identifier, decision_id),
                    )
                    promoted += 1
                else:
                    connection.execute(
                        "UPDATE memory_promotion_links SET decision_id=? WHERE chunk_id=?",
                        (decision_id, chunk_id),
                    )
                processed += 1
        return {
            "processed": processed,
            "promoted": promoted,
            "omitted_bytes": len(text.encode()) - offset,
        }
