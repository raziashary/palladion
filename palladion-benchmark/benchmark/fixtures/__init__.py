"""Synthetic Meridian Switchworks world, corpus and gold (protocol sections 4 to 6).

Everything here is fictional. This package holds the canonical serialisation helpers every fixture module shares,
so a digest means the same thing wherever it is computed.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Any

FICTIONAL_NOTICE = (
    "FICTIONAL: Meridian Switchworks is an invented company. Nothing here is an actual operating procedure."
)


def to_plain(value: Any) -> Any:
    """Convert dataclasses, enums, mappings and sequences into JSON-ready containers, preserving field order."""
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_plain(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): to_plain(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [to_plain(item) for item in value]
    if isinstance(value, frozenset | set):
        return sorted(to_plain(item) for item in value)
    return value


def canonical_json(value: Any) -> str:
    """Key-sorted, compact, non-ASCII-preserving JSON: the one byte form that digests are computed over."""
    return json.dumps(to_plain(value), sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def digest_of(value: Any) -> str:
    return sha256_hex(canonical_json(value))
