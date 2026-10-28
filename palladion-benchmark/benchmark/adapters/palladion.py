"""R7a: Palladion's retrieval over its HTTP API (B04-T03.01, B04-T03.02, BADR-0002, BADR-0025).

Nothing here imports Palladion. The arm sends authenticated requests to a running Palladion (the isolated runtime of
``scripts/palladion_runtime.py``) and maps what comes back onto the published corpus.

What the arm declares rather than hides:

* Under condition C2 every benchmark principal is a Palladion reader of its own (``PrincipalMap``; Palladion's PF05
  routes) and each restricted document is uploaded with the readers allowed to see it, so Palladion's own access control
  works before ranking, as the neutral filter does for R0 to R3. The arm does not mask Palladion's output: a returned
  document the neutral filter would have refused is kept and counted (``acl_leaked``), so a difference between the two
  rules shows as exposure and is not hidden. Under C1 every reader sees every document.
* Palladion's search answers at most 12 results (its schema says 40, E-B08-007) and has no word budget. K above 12
  is refused as unsupported and the evidence budget is applied on the harness side. The request carries the case's
  evaluation time as ``as_of`` (PF01) and, when the case has one, its event time as a further applicability instant
  (ADR-0102), so a policy version that governed the event and has since been superseded is still reachable. Both are
  fields every arm receives in the retrieval request; the gold's own time basis is never sent.
* A response is a run state when it is not a usable answer: an unreachable server, an index that cannot be read, or a
  reranked request on a server without the reranker is ``NOT_RUN``; a partial index is a transient fault. An empty
  list is returned only when Palladion itself reports an unknown identifier or finds nothing.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import httpx

from benchmark.adapters.common import (
    AccessFilter,
    AdapterError,
    Condition,
    PublishedView,
    count_words,
    enforce_budget,
    flags_from_notes,
)
from benchmark.contracts import (
    ArmUnavailable,
    CapabilityUnsupported,
    ContractError,
    EvidenceCandidate,
    RetrievalRequest,
    TransientInfrastructureError,
)
from benchmark.fixtures.manifest import ManifestRecord

Mode = Literal["lexical", "dense", "hybrid", "reranked"]
# Observed at dd70c0e (E-B08-007): lexical and hybrid search answer HTTP 400 above 12 results although the request
# schema allows 40, and reranked search refuses 40. K is 10, so the bound the arm relies on is the one that works.
MAX_PALLADION_LIMIT = 12
MAX_UPLOAD_CHARACTERS = 65536
READER = "reader-a"
UPLOADER = "uploader-a"
APPROVER = "admin-a"
CASE = "case-42"
UNAVAILABLE_WARNINGS = frozenset({"INDEX_UNAVAILABLE", "INDEX_MANIFEST_MISMATCH", "INTEGRITY_CONFLICT"})
RETRYABLE_WARNINGS = frozenset({"ACCEPTED_BUT_UNINDEXED"})
# Warnings that describe a normal answer: a truncated coverage report at scale, an identifier Palladion lacks,
# candidates that its canonical checks all refused, a case with nothing that could apply, a bounded prefilter or lane.
NOTE_WARNINGS = frozenset(
    {
        "COVERAGE_SCOPE_TRUNCATED",
        "EXACT_IDENTIFIER_NOT_FOUND",
        "EXACT_CANDIDATES_TRUNCATED",
        "ALL_CANDIDATES_EXCLUDED",
        "NO_ELIGIBLE_SOURCES",
        "ELIGIBILITY_PREFILTER_BOUNDED",
    }
)
APPROVE_STATES = frozenset({"approved", "retired", "non_normative", "withdrawn"})
REVOKE_STATES = frozenset({"withdrawn"})
TIMEOUT_SECONDS = 60.0
TABLE_FILE = "palladion_revisions.json"
ALIASES_FILE = "palladion_aliases.json"  # written next to the table by scripts/palladion_aliases.py
# What Palladion reads as an identifier in a query (copied from its documented behaviour, not imported).
IDENTIFIER_SHAPE = re.compile(r"(?<![A-Za-z0-9])(?:[A-Z][A-Z0-9_.]*[-.][A-Z0-9_.-]+)(?![A-Za-z0-9])")


@dataclass(frozen=True)
class PrincipalMap:
    """Which Palladion principal and case answer for a benchmark principal. Default: one reader in one case."""

    reader: str = READER
    case_id: str = CASE
    overrides: Mapping[str, tuple[str, str]] = field(default_factory=dict)

    def resolve(self, benchmark_principal: str) -> tuple[str, str]:
        return self.overrides.get(benchmark_principal, (self.reader, self.case_id))

    def covers(self, benchmark_principals: Sequence[str]) -> bool:
        """Whether every benchmark principal has a reader of its own."""
        return all(p in self.overrides for p in benchmark_principals)


@dataclass(frozen=True)
class LoadReport:
    uploaded: int
    approved: int
    revoked: int
    left_as_draft: int
    revisions: Mapping[str, str]  # published document id -> Palladion revision id
    states: Mapping[str, str]  # published document id -> state it was given in Palladion
    superseded: int = 0  # approvals that named the version they replace


def utf8_to_character_offsets(text: str, start_byte: int, end_byte: int) -> tuple[int, int]:
    """Palladion reports byte offsets into the uploaded UTF-8; the locator grammar counts characters."""
    raw = text.encode("utf-8")
    if not 0 <= start_byte <= end_byte <= len(raw):
        raise ContractError("a Palladion passage lies outside the document it names")
    try:
        return len(raw[:start_byte].decode("utf-8")), len(raw[:end_byte].decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ContractError("a Palladion passage boundary falls inside a character") from exc


class PalladionArm:
    """The R7a arm over a running Palladion. ``tokens`` maps Palladion principal ids to bearer tokens."""

    arm_id = "R7a"

    def __init__(
        self,
        view: PublishedView,
        base_url: str,
        tokens: Mapping[str, str],
        *,
        mode: Mode = "hybrid",
        condition: Condition = Condition.C2,
        principals: PrincipalMap | None = None,
        client: httpx.Client | None = None,
        timeout: float = TIMEOUT_SECONDS,
    ) -> None:
        if mode not in ("lexical", "dense", "hybrid", "reranked"):
            raise AdapterError("unknown Palladion search mode")
        self.view = view
        self.base_url = base_url.rstrip("/")
        self._tokens = dict(tokens)
        self.mode: Mode = mode
        self.condition = condition
        self.principals = principals or PrincipalMap()
        self.access = AccessFilter(view, condition)
        if condition is Condition.C2 and not self.principals.covers([p.principal_id for p in view.identity.principals]):
            raise AdapterError("condition C2 needs one Palladion reader for every benchmark principal")
        self._client = client or httpx.Client(timeout=timeout)
        self._owns_client = client is None
        self._revisions: dict[str, str] = {}  # Palladion revision id -> published document id
        self._table_states: dict[str, str] = {}  # published document id -> state it was given in Palladion
        self._aliases: dict[str, Any] | None = None  # what the alias setup step recorded; None when it was not run
        self._stats: dict[str, Any] = {}
        self.last_notes: dict[str, Any] = {}

    # -- plumbing --------------------------------------------------------------------------------

    def call(self, method: str, path: str, principal: str, body: dict[str, Any] | None = None) -> httpx.Response:
        if principal not in self._tokens:
            raise AdapterError(f"no token for Palladion principal {principal}")
        try:
            return self._client.request(
                method, self.base_url + path, json=body, headers={"Authorization": f"Bearer {self._tokens[principal]}"}
            )
        except httpx.TimeoutException as exc:
            raise TimeoutError("Palladion did not answer in time") from exc
        except httpx.TransportError as exc:
            raise ArmUnavailable("Palladion is not reachable") from exc

    def document_for(self, revision_id: str) -> str | None:
        """The published document a Palladion revision holds; None for a revision this corpus does not know."""
        return self._revisions.get(revision_id)

    def call_flags(self) -> tuple[str, ...]:
        return flags_from_notes(self.last_notes)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def describe(self) -> dict[str, Any]:
        return {
            "arm": self.arm_id,
            "mode": self.mode,
            "condition": self.condition.value,
            "principal_map": {"reader": self.principals.reader, "case": self.principals.case_id},
            "max_limit": MAX_PALLADION_LIMIT,
            "acl": "Palladion's own per-document access list before ranking (C2: one reader per benchmark principal, "
            "output not masked, disagreement with the neutral filter counted as acl_leaked); none under C1",
            "clock": "the case's evaluation time, sent as as_of (PF01), and its event time as an extra applicability "
            "instant when it has one (ADR-0102)",
            "ingestion": "native: each document uploaded whole and chunked by Palladion",
            "corpus": "approved, retired, non_normative and withdrawn-then-revoked documents are approved in Palladion",
            "unapproved": "drafts and unapproved proposals are uploaded, never approved, and so not retrievable by R7a",
            "states": "approval in Palladion means retrievable, not authoritative; a version is approved naming the "
            "one it supersedes and validity windows are sent; drafts and unapproved proposals stay unapproved",
            "aliases": self._aliases
            if self._aliases is not None
            else "registered by Palladion's own approval (family, revision and identifiers found in each chunk)",
        }

    # -- loading (B04-T03.02) --------------------------------------------------------------------

    def load_corpus(self, table_path: Path) -> LoadReport:
        """Upload every published document as the uploader and approve it as the distinct admin where its state allows.

        draft and unapproved_proposal stay unapproved; a version is approved after the one it supersedes and names it;
        withdrawn documents are approved and revoked once every approval is done. The
        revision table is written next to the index so a later run maps passages back to documents.
        """
        if table_path.exists():
            raise AdapterError("the corpus is already loaded; verify it or use a fresh runtime")
        revisions: dict[str, str] = {}
        records: dict[str, ManifestRecord] = {}
        for document in self.view.documents():
            record = document.record
            if len(document.text) > MAX_UPLOAD_CHARACTERS:
                raise AdapterError(f"{record.doc_id} exceeds Palladion's upload limit; split it and record how")
            revisions[record.doc_id] = self._upload(record, document.text)
            records[record.doc_id] = record
        states = {doc_id: "DRAFT" for doc_id in revisions}
        superseded = 0

        def approve(doc_id: str) -> None:
            """Approve a document after the version it supersedes, naming that version when Palladion can accept it."""
            nonlocal superseded
            if states[doc_id] != "DRAFT" or records[doc_id].registry_state not in APPROVE_STATES:
                return
            predecessor = records[doc_id].supersedes
            if predecessor in records:
                approve(str(predecessor))
            named = predecessor is not None and states.get(predecessor) == "APPROVED"
            body = {"supersedes_revision_id": revisions[str(predecessor)]} if named else None
            self._expect(
                self.call("POST", f"/sources/{revisions[doc_id]}/approve", APPROVER, body), 200, "approve", doc_id
            )
            states[doc_id] = "APPROVED"
            superseded += int(named)

        for doc_id in revisions:
            approve(doc_id)
        approved = sum(1 for state in states.values() if state == "APPROVED")
        revoked = 0
        for doc_id, record in records.items():
            # Revoked last, so a withdrawn version is still approved when a later version supersedes it.
            if record.registry_state in REVOKE_STATES and states[doc_id] == "APPROVED":
                self._expect(self.call("POST", f"/sources/{revisions[doc_id]}/revoke", APPROVER), 200, "revoke", doc_id)
                states[doc_id] = "REVOKED"
                revoked += 1
        table_path.write_text(json.dumps({"revisions": revisions, "states": states}, sort_keys=True), encoding="utf-8")
        self._revisions = {revision: doc for doc, revision in revisions.items()}
        self._table_states = states
        return LoadReport(len(revisions), approved, revoked, len(revisions) - approved, revisions, states, superseded)

    def publish(self, record: ManifestRecord, text: str, *, supersedes: str | None = None) -> str:
        """Upload one more document after the load, approve it where its state allows and name the document it
        supersedes when that one is approved. The arm's own view and map learn the document; the revision table on
        disk and any other view are not changed."""
        if record.doc_id in self._table_states:
            raise AdapterError(f"{record.doc_id} is already in Palladion; a change is a new document or a revoke")
        extended = self.view.with_document(record, text)  # a passage of it must map back to a document
        access = AccessFilter(extended, self.condition)
        revision = self._upload(record, text, access)
        self._revisions[revision] = record.doc_id
        self._table_states[record.doc_id] = "DRAFT"
        self.view, self.access = extended, access
        if record.registry_state in APPROVE_STATES:
            named = supersedes is not None and self._table_states.get(supersedes) == "APPROVED"
            body = {"supersedes_revision_id": self._revision_of(str(supersedes))} if named else None
            self._expect(
                self.call("POST", f"/sources/{revision}/approve", APPROVER, body), 200, "approve", record.doc_id
            )
            self._table_states[record.doc_id] = "APPROVED"
        if record.registry_state in REVOKE_STATES:
            self.revoke(record.doc_id)
        return revision

    def revoke(self, doc_id: str) -> None:
        """Revoke an approved document so Palladion stops serving it. Palladion has no route that undoes this."""
        if self._table_states.get(doc_id) != "APPROVED":
            raise AdapterError(f"{doc_id} is not approved in Palladion, so it cannot be revoked")
        self._expect(self.call("POST", f"/sources/{self._revision_of(doc_id)}/revoke", APPROVER), 200, "revoke", doc_id)
        self._table_states[doc_id] = "REVOKED"

    def held_states(self) -> dict[str, str]:
        """The state each document was given in Palladion (DRAFT, APPROVED or REVOKED), as this arm recorded it."""
        return dict(self._table_states)

    def _revision_of(self, doc_id: str) -> str:
        for revision, document in self._revisions.items():
            if document == doc_id:
                return revision
        raise AdapterError(f"{doc_id} has no Palladion revision")

    def map_revisions(self, revision_to_document: Mapping[str, str]) -> None:
        """Tell the arm which Palladion revision holds which published document."""
        self._revisions = dict(revision_to_document)

    def read_table(self, table_path: Path) -> None:
        data = json.loads(table_path.read_text(encoding="utf-8"))
        self.map_revisions({revision: doc for doc, revision in data["revisions"].items()})
        self._table_states = dict(data["states"])
        marker = table_path.with_name(ALIASES_FILE)
        self._aliases = json.loads(marker.read_text(encoding="utf-8")) if marker.exists() else None

    def _allowed_readers(self, record: ManifestRecord, access: AccessFilter) -> list[str]:
        """The Palladion principals that may read ``record``; empty means every member of the case.

        A restricted document also lists the uploader and the approver, who must still reach it to approve it.
        """
        if self.condition is Condition.C1:
            return []
        everyone = [p.principal_id for p in self.view.identity.principals]
        allowed = [p for p in everyone if access.allows(p, record.doc_id)]
        if len(allowed) == len(everyone):
            return []
        readers = {self.principals.resolve(p)[0] for p in allowed}
        return sorted(readers | {UPLOADER, APPROVER})

    def _upload(self, record: ManifestRecord, text: str, access: AccessFilter | None = None) -> str:
        body = {
            "case_id": self.principals.case_id,
            "family_id": record.family_id or record.doc_id,
            "filename": f"{record.doc_id}.md",
            "mime_type": "text/markdown",
            "content": text,
            "owner_id": UPLOADER,
            "allowed_principal_ids": self._allowed_readers(record, access or self.access),
            "valid_from": record.valid_from,
            "valid_to": record.valid_to,
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        }
        response = self.call("POST", "/sources", UPLOADER, body)
        self._expect(response, 201, "upload", record.doc_id)
        revision = str(response.json()["revision_id"])
        return revision

    @staticmethod
    def _expect(response: httpx.Response, status: int, action: str, doc_id: str) -> None:
        if response.status_code != status:
            raise AdapterError(f"Palladion refused to {action} {doc_id} (HTTP {response.status_code})")

    def verify_load(self, sample: int = 25) -> dict[str, Any]:
        """Check the load by reading it back: table completeness, index coverage warnings, passage integrity.

        Integrity means a returned passage's text and hash equal the published bytes at the offsets it reports.
        Reachability of a sampled document by its own title is measured and reported, not required (ranking is not
        loading). Any mismatch of counts or bytes raises.
        """
        if not self._revisions:
            raise AdapterError("no revision table: load the corpus first")
        documents = {r.doc_id for r in self.view.records}
        if set(self._revisions.values()) != documents:
            raise AdapterError("the revision table does not cover exactly the published corpus")
        health = self.call("GET", f"/index-health?case_id={self.principals.case_id}", self.principals.reader)
        self._expect(health, 200, "read index health for", self.principals.case_id)
        coverage = health.json()
        blocking = sorted(set(coverage["warnings"]) & (UNAVAILABLE_WARNINGS | RETRYABLE_WARNINGS))
        if blocking:
            raise AdapterError(f"Palladion's index reports {blocking}")
        step = max(1, len(self.view.records) // sample)
        probes = list(self.view.records)[::step][:sample]
        reached = checked = 0
        for record in probes:
            if self._table_state(record.doc_id) != "APPROVED":
                continue
            principal = self.view.identity.principals[0].principal_id
            probe = " ".join(
                IDENTIFIER_SHAPE.sub(" ", record.title).split()
            )  # Palladion refuses a query naming an unknown code
            if not probe:
                continue
            checked += 1
            reached += record.doc_id in self._found_by_title(probe, principal)
        if checked and not reached:
            raise AdapterError(
                "none of the sampled documents can be found in Palladion; the revision table does not describe it"
            )
        return {
            "documents": len(documents),
            "index_warnings": coverage["warnings"],
            "sampled": checked,
            "reachable_by_title": reached,
        }

    def verify_acl(self, sample: int = 12) -> dict[str, Any]:
        """Read the access lists back through Palladion: who can and who cannot find a restricted document.

        For restricted approved documents, a principal the neutral filter allows must find the document by its title
        (the positive control, so a silent search cannot pass), and principals it forbids are asked the same query. A
        forbidden principal that finds the document is a leak: it is counted and reported, not raised, because it is a
        finding about Palladion's access control, not a failure to load. Without any reachable document nothing was
        checked, which raises.
        """
        if self.condition is Condition.C1:
            return {"condition": "C1", "restricted_checked": 0, "note": "C1 has no access list"}
        everyone = [p.principal_id for p in self.view.identity.principals]
        restricted = [
            r
            for r in self.view.records
            if self._table_state(r.doc_id) == "APPROVED" and not all(self.access.allows(p, r.doc_id) for p in everyone)
        ]
        step = max(1, len(restricted) // sample)
        reachable = probes = leaks = 0
        for record in restricted[::step][:sample]:
            allowed = [p for p in everyone if self.access.allows(p, record.doc_id)]
            forbidden = [p for p in everyone if not self.access.allows(p, record.doc_id)]
            title = " ".join(IDENTIFIER_SHAPE.sub(" ", record.title).split())
            if not title or not allowed:
                continue
            if record.doc_id not in self._found_by_title(title, allowed[0]):
                continue
            reachable += 1
            for who in forbidden[:3]:
                probes += 1
                leaks += record.doc_id in self._found_by_title(title, who)
        if restricted and not reachable:
            raise AdapterError("no restricted document could be found by a principal allowed to see it")
        return {
            "condition": "C2",
            "restricted_checked": len(restricted[::step][:sample]),
            "reachable_by_allowed": reachable,
            "forbidden_probes": probes,
            "leaks": leaks,
        }

    def _found_by_title(self, title: str, principal: str) -> set[str]:
        """The published documents a lexical search for ``title`` returns to a benchmark principal."""
        request = RetrievalRequest(
            "q-0000000000000000", title, principal, "load-check", "2026-10-18T03:00:00Z", None, {},
            MAX_PALLADION_LIMIT, 100000,
        )  # fmt: skip
        return {h.source_document_id for h in self._search(request, "lexical") if h.source_document_id}

    def _table_state(self, doc_id: str) -> str:
        return self._table_states.get(doc_id, "APPROVED")

    # -- retrieval (B04-T03.01) ------------------------------------------------------------------

    def build_index(self, source_manifest_uri: str, index_namespace: str) -> None:
        """Palladion indexes at upload and approval; this records the namespace and refuses a different corpus."""
        if Path(source_manifest_uri).resolve() != self.view.root.resolve():
            raise AdapterError("the index is built from the published directory this arm was created with")
        started = time.perf_counter()
        self._stats = {
            "arm": self.arm_id,
            "namespace": index_namespace,
            "documents": len(self.view.records),
            "mapped_revisions": len(self._revisions),
            "mode": self.mode,
            "condition": self.condition.value,
            "build_ms": (time.perf_counter() - started) * 1000,
            "note": "indexing happened at load time inside Palladion; build_ms is the check only",
        }

    def index_stats(self) -> dict[str, Any]:
        return dict(self._stats)

    def retrieve(self, request: RetrievalRequest) -> list[EvidenceCandidate]:
        if request.limit > MAX_PALLADION_LIMIT:
            raise CapabilityUnsupported(f"Palladion returns at most {MAX_PALLADION_LIMIT} passages; K={request.limit}")
        if not self._revisions:
            raise AdapterError("no revision table: load the corpus first")
        found = self._search(request, self.mode)
        shown = [c for c in found if self._in_corpus(c)]
        leaked = sum(1 for c in shown if not self._visible(c, request.principal_id))
        renumbered = [EvidenceCandidate.from_dict({**c.to_dict(), "rank": i}) for i, c in enumerate(shown, start=1)]
        bundle = enforce_budget(renumbered, request.max_evidence_tokens)
        self.last_notes = {
            **self.last_notes,
            "foreign_dropped": len(found) - len(shown),
            "acl_leaked": leaked,
            "truncated": bundle.truncated,
            "dropped": bundle.dropped,
            "cut_words": bundle.cut_words,
            "words": bundle.words,
        }
        return list(bundle.kept)

    def _in_corpus(self, candidate: EvidenceCandidate) -> bool:
        """A passage of a revision this corpus does not hold cannot be cited or scored; it is left out of C2 only."""
        return candidate.source_document_id is not None or self.condition is Condition.C1

    def _visible(self, candidate: EvidenceCandidate, principal_id: str) -> bool:
        """What the neutral filter would say; under C1 it says yes to everything, so nothing is ever leaked."""
        return candidate.source_document_id is None or self.access.allows(principal_id, candidate.source_document_id)

    def _search(self, request: RetrievalRequest, mode: Mode) -> list[EvidenceCandidate]:
        principal, case_id = self.principals.resolve(request.principal_id)
        response = self.call(
            "POST",
            "/search",
            principal,
            {
                "case_id": case_id,
                "query": request.query,
                "mode": mode,
                "limit": request.limit,
                "as_of": request.evaluation_time,
                "applicability_instants": [request.event_time] if request.event_time else [],
            },
        )
        if response.status_code >= 500:
            raise TransientInfrastructureError(f"Palladion answered HTTP {response.status_code}")
        if response.status_code != 200:
            raise ContractError(f"Palladion refused the search (HTTP {response.status_code})")
        body = response.json()
        warnings = set(body.get("warnings", ()))
        if warnings & UNAVAILABLE_WARNINGS or body.get("status") == "UNAVAILABLE":
            raise ArmUnavailable("Palladion's index is unavailable")
        if mode == "reranked" and "RERANK_UNAVAILABLE" in warnings:
            raise ArmUnavailable("Palladion was asked to rerank but its reranker is unavailable")
        if warnings & RETRYABLE_WARNINGS:
            raise TransientInfrastructureError("Palladion reports accepted sources that are not indexed")
        unexpected = sorted(warnings - NOTE_WARNINGS)
        if (
            unexpected
            or body.get("status") not in ("OK", "DEGRADED")
            or (body.get("status") == "DEGRADED" and not warnings)
        ):
            raise TransientInfrastructureError(
                f"Palladion answered with an unknown status or warning: {unexpected or body.get('status')}"
            )
        self.last_notes = {
            "palladion_status": body.get("status"),
            "palladion_warnings": sorted(warnings),
            "palladion_stage_ms": body.get("stage_ms") or {},
        }
        return [self._candidate(passage, rank) for rank, passage in enumerate(body["passages"], start=1)]

    def _candidate(self, passage: Mapping[str, Any], rank: int) -> EvidenceCandidate:
        doc_id = self._revisions.get(str(passage["revision_id"]))
        meta: dict[str, Any] = {
            "citation_id": passage["citation_id"],
            "revision_id": passage["revision_id"],
            "section_id": passage["section_id"],
            "words": count_words(str(passage["text"])),
        }
        if doc_id is None:
            return EvidenceCandidate(
                None,
                None,
                str(passage["text"]),
                rank,
                None,
                f"palladion_{self.mode}",
                (),
                False,  # without a published id there is nothing a native citation could point to
                {**meta, "foreign": True},
            )
        document = self.view.document(doc_id)
        start, end = utf8_to_character_offsets(document.text, int(passage["start_byte"]), int(passage["end_byte"]))
        if (
            document.text[start:end] != passage["text"]
            or hashlib.sha256(str(passage["text"]).encode()).hexdigest() != passage["sha256"]
        ):
            raise ContractError(f"a Palladion passage differs from the published bytes of {doc_id}")
        return EvidenceCandidate(
            source_version_id=document.record.version_id,
            locator=f"chars:{start}-{end}",
            content=str(passage["text"]),
            rank=rank,
            native_score=None,
            retrieval_channel=f"palladion_{self.mode}",
            evidence_path=(),
            native_citation_supported=True,
            additional_metadata=meta,
            source_document_id=doc_id,
            source_sha256=document.record.sha256,
        )
