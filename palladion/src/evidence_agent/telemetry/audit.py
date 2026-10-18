"""Small correlated retrieval audit; payloads never contain queries or source text."""
from __future__ import annotations

import json
import re
import uuid
from typing import Any

from evidence_agent.core.errors import PermissionDenied
from evidence_agent.core.models import Principal
from evidence_agent.storage.registry import Registry
from evidence_agent.storage.sqlite import utc_now

_FIELDS = {"mode", "generation", "generations", "fingerprint", "candidate_count", "returned_count", "elapsed_ms",
           "excluded_count", "failure", "stage_counts", "index_coverage"}


class AuditLog:
    def __init__(self, registry: Registry) -> None:
        self.registry = registry

    def append(self, principal: Principal, trace_id: str, payload: dict[str, Any]) -> None:
        if set(payload) - _FIELDS or not trace_id or len(trace_id) > 100:
            raise ValueError("Unsafe audit fields")
        # Only enumerated labels/numbers are admitted; arbitrary source strings cannot be logged.
        for key, value in payload.items():
            if key == "mode" and value not in {"lexical", "dense", "hybrid", "reranked"}:
                raise ValueError("Unknown audit mode")
            if key == "failure" and value not in {"NONE", "INDEX_UNAVAILABLE", "RERANK_UNAVAILABLE"}:
                raise ValueError("Unknown failure label")
            if key == "generation" and (not isinstance(value, str) or len(value) > 100):
                raise ValueError("Invalid generation")
            if key == "generations" and (not isinstance(value, tuple) or len(value) > 12 or
                    any(not isinstance(item, str) or not re.fullmatch(r"gen_[0-9a-f]{64}", item)
                        for item in value)):
                raise ValueError("Invalid generations")
            if key == "fingerprint" and (not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)):
                raise ValueError("Invalid representation fingerprint")
            if key == "stage_counts" and (not isinstance(value, dict) or
                    any(k not in {"discovered", "resolved", "reranked", "expanded"} or
                        type(v) is not int or v < 0 for k, v in value.items())):
                raise ValueError("Invalid stage counts")
            if key not in {"mode", "failure", "generation", "generations", "fingerprint", "stage_counts"} and (
                    not isinstance(value, (int, float, bool)) or value < 0):
                raise ValueError("Invalid audit measurement")
        with self.registry.database.transaction() as connection:
            self.registry.access.authorize(principal, tenant_id=principal.tenant_id)
            connection.execute(
                "INSERT INTO audit_events(audit_id,trace_id,principal_id,tenant_id,event_kind,"
                "safe_payload_json,occurred_at) VALUES(?,?,?,?,?,?,?)",
                (f"audit_{uuid.uuid4().hex}", trace_id, principal.principal_id,
                 principal.tenant_id, "RETRIEVAL_COMPLETED", json.dumps(payload), utc_now()),
            )

    def read(self, trace_id: str) -> tuple[dict[str, Any], ...]:
        """Internal legacy reader; HTTP uses the separately authorized case reader."""
        return tuple(json.loads(row[0]) for row in self.registry.database.connection.execute(
            "SELECT safe_payload_json FROM audit_events WHERE trace_id=? "
            "AND event_kind='RETRIEVAL_COMPLETED' ORDER BY occurred_at,audit_id", (trace_id,)))

    def read_case_trace(self, principal: Principal, case_id: str, trace_id: str) -> dict[str, Any]:
        """Current admin AND case membership; metadata only, never runtime prose."""
        self.registry.access.authorize(principal, tenant_id=principal.tenant_id,
                                       case_id=case_id, grant="case:read", role="admin")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", trace_id):
            raise PermissionDenied
        rows = self.registry.database.connection.execute(
            "SELECT event_id,event_kind,payload_json,occurred_at FROM case_events "
            "WHERE tenant_id=? AND case_id=? AND event_kind LIKE 'RUNTIME_%' "
            "AND (json_extract(payload_json,'$.trace_id')=? OR "
            "json_extract(payload_json,'$.retrieval_trace_id')=?) ORDER BY occurred_at,event_id LIMIT 101",
            (principal.tenant_id, case_id, trace_id, trace_id)).fetchall()
        if not rows:
            raise PermissionDenied
        labels = {"status": {"STARTED", "RECEIVED", "FAILED", "CANCELLED", "SCHEMA_INVALID", "SUCCEEDED"},
            "role": {"main", "critic"}, "tool": {"search_knowledge", "evaluate_policy", "lookup_live_data", "recall_memory", "unknown"},
            "disposition": {"SUPPORTED", "PARTIALLY_SUPPORTED", "CONFLICT", "NOT_ESTABLISHED", "VERIFICATION_UNAVAILABLE"}}
        events = []
        for row in rows[:100]:
            payload = json.loads(row["payload_json"])
            metadata: dict[str, Any] = {}
            for key, allowed in labels.items():
                value = payload.get(key)
                if isinstance(value, str) and value in allowed:
                    metadata[key] = value
            for key in ("attempt", "main_used", "tool_used"):
                value = payload.get(key)
                if type(value) is int and 0 <= value <= 100:
                    metadata[key] = value
            events.append({"event_id": row["event_id"], "kind": row["event_kind"],
                "at": row["occurred_at"], "metadata": metadata})
        linked = {trace_id}
        for row in rows[:100]:
            value = json.loads(row["payload_json"]).get("retrieval_trace_id")
            if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value):
                linked.add(value)
        retrieval = []
        for identifier in sorted(linked):
            for row in self.registry.database.connection.execute(
                    "SELECT safe_payload_json FROM audit_events WHERE tenant_id=? AND trace_id=? "
                    "AND event_kind='RETRIEVAL_COMPLETED' ORDER BY occurred_at,audit_id LIMIT 8",
                    (principal.tenant_id, identifier)):
                payload = json.loads(row[0])
                metadata = {key: value for key, value in payload.items()
                    if key in {"candidate_count", "returned_count", "elapsed_ms", "excluded_count"}
                    and type(value) in (int, float) and 0 <= value < 1e12}
                if payload.get("mode") in {"lexical", "dense", "hybrid", "reranked"}:
                    metadata["mode"] = payload["mode"]
                if payload.get("failure") in {"NONE", "INDEX_UNAVAILABLE", "RERANK_UNAVAILABLE"}:
                    metadata["failure"] = payload["failure"]
                retrieval.append({"trace_id": identifier, "metadata": metadata})
        return {"trace_id": trace_id, "events": events, "retrieval": retrieval, "truncated": len(rows) > 100}
