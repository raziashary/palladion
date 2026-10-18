"""Strict non-secret settings; loading never reads credentials or contacts a provider."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, StrictBool


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    provider: Literal["groq"] = "groq"
    model: Literal["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"] = "qwen/qwen3.8-27b"
    enable_live_llm: StrictBool = False
    qdrant_url: str = Field(default="http://127.0.0.1:16333", pattern=r"^http://127\.0\.0\.1:[0-9]{4,5}$")
    qdrant_collection: str = Field(default="knowledge_chunks_v1", pattern=r"^[a-zA-Z0-9_]{1,100}$")
    bm25_profile: Literal["english", "no_stemming"] = "english"
    main_max_calls: int = Field(default=5, ge=1, le=5)
    critic_max_calls: int = Field(default=3, ge=1, le=3)
    tool_max_calls: int = Field(default=8, ge=1, le=8)
    critic_search_max_calls: int = Field(default=2, ge=0, le=2)
    graph_max_hops: int = Field(default=2, ge=0, le=2)
    max_draft_revisions: int = Field(default=1, ge=0, le=1)
    max_source_passages: int = Field(default=12, ge=1, le=12)
    request_timeout_seconds: int = Field(default=60, ge=1, le=300)

    def require_live_llm(self, *, api_key_present: bool) -> None:
        """Fail before dispatch unless explicitly enabled and separately credentialed."""
        if not self.enable_live_llm:
            raise PermissionError("Live model calls are explicitly disabled")
        if not api_key_present:
            raise PermissionError("Enabled model command requires credentials")


def load_settings(path: Path) -> Settings:
    """Read an explicit YAML file; credentials and ambient environment are not loaded."""
    if path.stat().st_size > 64 * 1024:
        raise ValueError("Settings file exceeds 64 KiB")
    with path.open(encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    if not isinstance(data, dict):
        raise ValueError("Settings must be a mapping")
    return Settings.model_validate(data)
