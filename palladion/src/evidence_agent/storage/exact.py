"""Exact aliases are a separate union channel, never fuzzy identifier substitutions."""
from __future__ import annotations

import re

from evidence_agent.core.models import Principal
from evidence_agent.storage.catalog import Catalog

_CODE = re.compile(r"(?<![A-Za-z0-9])(?:[A-Z][A-Z0-9_.]*[-.][A-Z0-9_.-]+)(?![A-Za-z0-9])")


class ExactIndex:
    def __init__(self, catalog: Catalog) -> None:
        self.catalog = catalog

    def lookup(self, principal: Principal, case_id: str, query: str) -> tuple[str, ...]:
        identifiers = dict.fromkeys(_CODE.findall(query))
        result: list[str] = []
        for identifier in identifiers:
            for chunk in self.catalog.lookup_alias(principal, case_id, identifier):
                chunk_id = chunk if isinstance(chunk, str) else chunk.chunk_id
                if chunk_id not in result:
                    result.append(chunk_id)
        return tuple(result)

    def identifiers(self, query: str) -> tuple[str, ...]:
        return tuple(dict.fromkeys(_CODE.findall(query)))
