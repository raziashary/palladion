"""Bounded synthetic source/search HTTP inputs; identity is server supplied."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Upload(RequestModel):
    case_id: str = Field(min_length=1, max_length=100)
    family_id: str = Field(min_length=1, max_length=200)
    filename: str = Field(min_length=1, max_length=200)
    mime_type: Literal["text/markdown", "text/plain"]
    content: str = Field(min_length=1, max_length=65536)
    owner_id: str = Field(min_length=1, max_length=100)
    allowed_principal_ids: list[str] = Field(default_factory=list, max_length=100)
    valid_from: str | None = None
    valid_to: str | None = None
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class Search(RequestModel):
    case_id: str = Field(min_length=1, max_length=100)
    query: str = Field(min_length=1, max_length=2048)
    mode: Literal["lexical", "dense", "hybrid", "reranked"] = "hybrid"
    limit: int = Field(default=12, ge=1, le=12)


class Approval(RequestModel):
    supersedes_revision_id: str | None = Field(default=None, max_length=100)
