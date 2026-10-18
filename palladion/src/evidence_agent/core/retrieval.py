"""Shared P02 ingestion/index contracts; canonical text is resolved before exposure."""
from __future__ import annotations

from typing import Literal, Protocol, Sequence

from pydantic import Field

from evidence_agent.core.models import Principal, VersionedModel


class Chunk(VersionedModel):
    chunk_id: str
    tenant_id: str
    case_id: str
    revision_id: str
    section_id: str
    start_byte: int = Field(ge=0)
    end_byte: int = Field(gt=0)
    line_start: int = Field(gt=0)
    line_end: int = Field(gt=0)
    text: str
    content_sha256: str
    source_sha256: str
    parent_id: str | None = None
    neighbor_ids: tuple[str, ...] = ()


class Candidate(VersionedModel):
    chunk_id: str
    generation: str
    score: float
    channel: str


class SearchIndex(Protocol):
    """Structural interface implemented by storage.qdrant.QdrantIndex.

    Ellipsis bodies declare required signatures; this is not a runnable index.
    """

    @property
    def fingerprint(self) -> str: ...
    def ensure_collection(self) -> None: ...
    def upsert(self, chunks: Sequence[Chunk], generation: str,
               allowed_principal_ids: tuple[str, ...]) -> None: ...
    def readback(self, tenant_id: str, revision_id: str,
                 generation: str) -> dict[str, str]: ...
    def query(self, query: str, principal: Principal, case_id: str,
              mode: Literal["lexical", "dense", "hybrid"] = "hybrid",
              limit: int = 20, exact: bool = False) -> tuple[Candidate, ...]: ...
