"""Exact aliases are a separate union channel, never fuzzy identifier substitutions."""
from __future__ import annotations

import re
from collections.abc import Collection
from dataclasses import dataclass

from evidence_agent.core.models import Principal
from evidence_agent.storage.applicability import MAX_NAMED_VERSIONS
from evidence_agent.storage.catalog import CODE_PATTERN, MAX_ALIAS_LENGTH, AliasHit, Catalog

# A code with a version number: `POL-001@v2` names the second version of POL-001 (ADR-0110).
_VERSIONED = re.compile(rf"({CODE_PATTERN.pattern})@v([1-9][0-9]{{0,2}})(?![A-Za-z0-9])")
MAX_EXACT_CANDIDATES = 100
MAX_ALIAS_CHUNKS = 1000
MAX_ALIASES_PER_CHUNK = 64
# A code cited by more chunks than this identifies none of them: those chunks rank after the semantic results.
SELECTIVE_MENTION_LIMIT = 5
WIDELY_CITED_MENTION_LIMIT = 10


@dataclass(frozen=True)
class AliasRegistration:
    registered: int
    truncated: bool  # the revision had more chunks or identifiers per chunk than the bounds; the rest are unregistered


@dataclass(frozen=True)
class ExactHits:
    """Exact-lane chunk IDs by where they belong in the ranking, plus the code-shaped tokens nothing matched."""

    leading: tuple[str, ...]  # chunks of the revision a code names, then selective mentions: ahead of semantic hits
    trailing: tuple[str, ...]  # chunks that only mention a widely cited code: after the semantic hits
    unmatched: tuple[str, ...]  # code-shaped tokens of the query with no registered alias
    inapplicable: tuple[str, ...]  # codes that are registered but whose chunks the question's time and scope exclude
    truncated: bool
    unknown_lookup: bool  # the query is only unregistered code(s): a lookup that nothing answers, not a question


@dataclass(frozen=True)
class NamedVersions:
    """The versions a query names: (family ID, revision ID or None when that family has no readable version of that
    number), and whether more references were written than are read."""

    resolved: tuple[tuple[str, str | None], ...]
    truncated: bool


class ExactIndex:
    def __init__(self, catalog: Catalog) -> None:
        self.catalog = catalog

    def _collect(self, principal: Principal, case_id: str, query: str,
                 generations: Collection[str] | None = None) -> tuple[dict[str, list[AliasHit]], bool]:
        """Alias hits per identifier in lookup order; at most MAX_EXACT_CANDIDATES distinct chunks in all."""
        identifiers = dict.fromkeys((query.strip(), *CODE_PATTERN.findall(query)))
        found: dict[str, list[AliasHit]] = {}
        seen: set[str] = set()
        truncated = False
        for identifier in identifiers:
            if len(seen) >= MAX_EXACT_CANDIDATES:
                truncated = True  # Remaining identifiers were not exhausted.
                break
            if not identifier or len(identifier) > MAX_ALIAS_LENGTH:
                continue
            hits = self.catalog.alias_hits(principal, case_id, identifier, limit=MAX_EXACT_CANDIDATES + 1,
                                           generations=generations)
            truncated |= len(hits) > MAX_EXACT_CANDIDATES
            found[identifier] = []
            for hit in hits:
                if hit.chunk_id not in seen:
                    if len(seen) >= MAX_EXACT_CANDIDATES:
                        return found, True
                    seen.add(hit.chunk_id)
                found[identifier].append(hit)
        return found, truncated

    def lookup(self, principal: Principal, case_id: str, query: str) -> tuple[str, ...]:
        """Every exact chunk ID of the query, in lookup order (defining chunks of each identifier first)."""
        found, _ = self._collect(principal, case_id, query)
        return tuple(dict.fromkeys(hit.chunk_id for hits in found.values() for hit in hits))

    def hits(self, principal: Principal, case_id: str, query: str,
             generations: Collection[str] | None = None) -> ExactHits:
        """Exact-lane chunks split into those that lead the ranking and those that trail the semantic hits.

        `generations` is the eligibility prefilter's answer (None: no restriction), so the lane offers only what the
        index may offer and its candidate bound is spent on revisions that can apply.
        """
        found, truncated = self._collect(principal, case_id, query, generations)
        leading: dict[str, None] = {}
        trailing: dict[str, None] = {}
        for hits in found.values():
            mentions = [hit for hit in hits if not hit.defining]
            for hit in hits:
                if hit.defining or len(mentions) <= SELECTIVE_MENTION_LIMIT:
                    leading[hit.chunk_id] = None
            if len(mentions) > SELECTIVE_MENTION_LIMIT:
                for hit in mentions[:WIDELY_CITED_MENTION_LIMIT]:
                    trailing[hit.chunk_id] = None
        # Only identifiers the lane looked up can be called unmatched; past the candidate bound the rest were not tried.
        empty = tuple(token for token in self.identifiers(query) if token in found and not found[token])
        known = {token for token in empty if generations is not None
                 and self.catalog.alias_hits(principal, case_id, token, limit=1)}
        unmatched = tuple(token for token in empty if token not in known)
        inapplicable = tuple(token for token in empty if token in known)
        lookup_only = not re.search(r"\w", CODE_PATTERN.sub(" ", query))
        return ExactHits(tuple(leading), tuple(c for c in trailing if c not in leading), unmatched, inapplicable,
                         truncated,
                         unknown_lookup=bool(empty) and lookup_only and not truncated and not leading and not trailing)

    def identifiers(self, query: str) -> tuple[str, ...]:
        return tuple(dict.fromkeys(CODE_PATTERN.findall(query)))

    def named_versions(self, principal: Principal, case_id: str, query: str) -> NamedVersions:
        """The versions the query names (`POL-001@v2`). A reference to a family the caller cannot read, or the case does
        not hold, names nothing and is left out; at most MAX_NAMED_VERSIONS references are read."""
        references = list(dict.fromkeys(_VERSIONED.findall(query)))
        named: list[tuple[str, str | None]] = []
        for family, number in references[:MAX_NAMED_VERSIONS]:
            found = self.catalog.family_version(principal, case_id, family, int(number))
            if found is not None:
                named.append(found)
        return NamedVersions(tuple(named), truncated=len(references) > MAX_NAMED_VERSIONS)

    def register_approved(self, actor: Principal, revision_id: str) -> AliasRegistration:
        """Register bounded canonical identifiers under the existing alias authority.

        Called by source approval after publication, not the general uploader pipeline.
        Aliases are discovery hints only: every hit still passes the canonical resolver. All of a revision's aliases
        are written in one transaction. A document past the bounds keeps the aliases inside them and says so,
        instead of failing an approval that already published it (ADR-0108).
        """
        family_id = str(self.catalog.registry.source_metadata(actor, revision_id)["family_id"])
        chunks = self.catalog.chunks_for_revision(actor, revision_id)
        truncated = len(chunks) > MAX_ALIAS_CHUNKS
        planned: list[tuple[str, str]] = []
        for chunk in chunks[:MAX_ALIAS_CHUNKS]:
            wanted = list(dict.fromkeys((family_id, revision_id, *self.identifiers(chunk.text))))
            within = [alias for alias in wanted[:MAX_ALIASES_PER_CHUNK] if len(alias) <= MAX_ALIAS_LENGTH]
            truncated |= len(within) < len(wanted)
            planned.extend((alias, chunk.chunk_id) for alias in within)
        self.catalog.add_aliases(actor, revision_id, planned)  # requires the approval authority
        return AliasRegistration(len(planned), truncated)
