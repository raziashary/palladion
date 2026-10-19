"""Bounded graph records: navigation metadata, never claim authority."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import Field

from evidence_agent.core.models import VersionedModel

RelationType = Literal[
    "REQUIRES", "APPLIES_TO", "EXCEPTION_TO", "REFERENCES", "SUPERSEDES", "POSSIBLY_SAME_AS"
]


class RelationCandidate(VersionedModel):
    from_key: str = Field(min_length=1, max_length=100)
    to_key: str = Field(min_length=1, max_length=100)
    relation_type: RelationType
    evidence_chunk_id: str = Field(min_length=1, max_length=100)
    evidence_kind: Literal["EXPLICIT_SOURCE", "EXTRACTED_UNREVIEWED"] = "EXTRACTED_UNREVIEWED"


class GraphPath(VersionedModel):
    path_id: str
    edge_ids: tuple[str, ...] = Field(max_length=2)
    evidence_ids: tuple[str, ...] = Field(max_length=12)
    navigation_only: Literal[True] = True
    includes_unreviewed: bool
    target_chunk_id: str | None = None


class ProjectedRelation(VersionedModel):
    edge_id: str
    from_key: str
    to_key: str
    relation_type: RelationType
    evidence_chunk_id: str
    evidence_kind: Literal["EXPLICIT_SOURCE", "EXTRACTED_UNREVIEWED", "HUMAN_VERIFIED"]


def projection_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


class TraversalLimits(VersionedModel):
    hops: int = Field(default=2, ge=0, le=2)
    fanout: int = Field(default=8, ge=1, le=32)
    nodes: int = Field(default=24, ge=1, le=64)
    edges: int = Field(default=32, ge=1, le=128)
    timeout_seconds: float = Field(default=2.0, gt=0, le=10)
