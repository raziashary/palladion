"""Small correlated retrieval audit; payloads never contain queries or source text."""
from __future__ import annotations

import json
import re
import uuid
from typing import Any

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
        """Internal diagnostic reader; no API exposure (P04 owns that authorization)."""
        return tuple(json.loads(row[0]) for row in self.registry.database.connection.execute(
            "SELECT safe_payload_json FROM audit_events WHERE trace_id=? "
            "AND event_kind='RETRIEVAL_COMPLETED' ORDER BY occurred_at,audit_id", (trace_id,)))
