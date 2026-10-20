"""Exact aliases are a separate union channel, never fuzzy identifier substitutions."""
from __future__ import annotations

import re

from evidence_agent.core.models import Principal
from evidence_agent.storage.catalog import Catalog

_CODE = re.compile(r"(?<![A-Za-z0-9])(?:[A-Z][A-Z0-9_.]*[-.][A-Z0-9_.-]+)(?![A-Za-z0-9])")


class ExactIndex:
    def __init__(self, catalog: Catalog) -> None:
        self.catalog = catalog
        self.truncated = False

    def lookup(self, principal: Principal, case_id: str, query: str) -> tuple[str, ...]:
        identifiers = dict.fromkeys((query.strip(), *_CODE.findall(query)))
        result: list[str] = []
        self.truncated = False
        for identifier in identifiers:
            if len(result) >= 100:
                self.truncated = True  # Remaining identifiers were not exhausted.
                break
            if not identifier or len(identifier) > 256:
                continue
            hits = self.catalog.lookup_alias(principal, case_id, identifier, limit=101)
            self.truncated |= len(hits) > 100
            for chunk in hits:
                chunk_id = chunk if isinstance(chunk, str) else chunk.chunk_id
                if chunk_id not in result:
                    result.append(chunk_id)
                if len(result) > 100:
                    self.truncated = True
                    return tuple(result[:100])
        return tuple(result)

    def identifiers(self, query: str) -> tuple[str, ...]:
        return tuple(dict.fromkeys(_CODE.findall(query)))

    def register_approved(self, actor: Principal, revision_id: str) -> int:
        """Register bounded canonical identifiers under the existing alias authority.

        Called by source approval after publication, not the general uploader pipeline.
        Aliases are discovery hints only: every hit still passes the canonical resolver.
        """
        source = self.catalog.registry.source_metadata(actor, revision_id)
        self.catalog.registry.access.authorize(actor, tenant_id=actor.tenant_id,
            case_id=str(source["case_id"]), role="admin", grant="document:approve")
        rows = self.catalog.database.connection.execute(
            "SELECT chunk_id,text FROM p02_chunks WHERE tenant_id=? AND revision_id=? "
            "ORDER BY start_byte LIMIT 1001", (actor.tenant_id, revision_id)).fetchall()
        if len(rows) > 1000:
            raise ValueError("Automatic alias chunk bound exceeded")
        planned: list[tuple[str, str]] = []
        for row in rows:
            aliases = dict.fromkeys((str(source["family_id"]), revision_id,
                *self.identifiers(str(row["text"]))))
            if len(aliases) > 64:
                raise ValueError("Automatic alias identifier bound exceeded")
            for alias in aliases:
                if len(alias) <= 256:
                    planned.append((alias, row["chunk_id"]))
        for alias, chunk_id in planned:
            self.catalog.add_alias(actor, alias, revision_id, chunk_id=chunk_id)
        return len(planned)
