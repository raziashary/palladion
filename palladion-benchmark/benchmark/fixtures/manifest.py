"""Corpus and identity manifests, ACL visibility and the four physically separate namespaces (B02-T03.01).

Protocol 4.4 and 7.3 require an information barrier: the generator and gold builder read the hidden world, an arm
reads only the published corpus. Four directories enforce that physically: ``generator`` (hidden world and generator
tags), ``published`` (documents and manifests an arm may index), ``annotations_dev`` (smoke and dev gold) and
``annotations_test`` (locked test gold). Nothing under ``published`` may name gold, a split, a scenario family or a
question; :func:`scan_published` checks the written tree rather than trusting the writer.
"""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from benchmark.contracts import QUESTION_ID
from benchmark.fixtures import FICTIONAL_NOTICE, canonical_json, digest_of, sha256_hex
from benchmark.fixtures.documents import Document
from benchmark.fixtures.entities import Principal, WorldEntities, WorldError
from benchmark.fixtures.world import World

PUBLISHED_FILES = frozenset({"corpus_manifest.jsonl", "identity_manifest.json", "snapshot.json"})
_GOLD_MARKERS = re.compile(
    r"(?i)(?<![a-z])gold(?![a-z])|answerability|required[ _-]?evidence|forbidden[ _-]?claim|minimal[ _-]?evidence|"
    r"expected[ _-]?answer|outcome[ _-]?label|scenario[ _-]?family|\bstratum\b|citation[ _-]?span|harm[ _-]?severity"
)
_SPLIT_WORDS = re.compile(r"(?i)(?<![a-z])(smoke|locked)(?![a-z])")
_DOC_TYPE = re.compile(r"^- Document type: (.+)$", re.MULTILINE)


class Namespace(StrEnum):
    GENERATOR = "generator"
    PUBLISHED = "published"
    DEV_ANNOTATIONS = "annotations_dev"
    TEST_ANNOTATIONS = "annotations_test"


class Split(StrEnum):
    SMOKE = "smoke"
    DEV = "dev"
    TEST = "test"


@dataclass(frozen=True)
class ManifestRecord:
    """One published document: identity, content hash, authority metadata and access list. No gold, no tags."""

    doc_id: str
    path: str
    sha256: str
    title: str
    source_type: str
    registry_state: str
    version_id: str | None
    family_id: str | None
    approved_by: str | None
    valid_from: str | None
    valid_to: str | None
    supersedes: str | None
    acl_tenants: tuple[str, ...]
    acl_roles: tuple[str, ...]
    tokens: int


@dataclass(frozen=True)
class IdentityManifest:
    tenants: tuple[Mapping[str, Any], ...]
    roles: tuple[Mapping[str, Any], ...]
    principals: tuple[Principal, ...]


def source_type_of(world: World, doc: Document) -> str:
    """A coarse source type that is safe to publish: the family kind, or the header's own document type."""
    if doc.source_version_id is not None:
        return world.knowledge.family(world.knowledge.version(doc.source_version_id).family_id).kind.value
    found = _DOC_TYPE.search(doc.text)
    if not found:
        raise WorldError(f"{doc.doc_id} has no document type in its header")
    return re.sub(r"[^a-z]+", "_", found.group(1).lower()).strip("_")


def doc_path(doc: Document) -> str:
    """Opaque file name from the id and content hash: listing order says nothing about family or category.

    The id is part of the key because two documents may legitimately have identical text.
    """
    return f"docs/{sha256_hex(doc.doc_id + chr(58) + doc.sha256)[:16]}.md"


def build_records(world: World, corpus: Sequence[Document], seed: int) -> list[ManifestRecord]:
    """Manifest records in an order shuffled by a keyed hash that is independent of generation order."""
    kb = world.knowledge
    records: list[ManifestRecord] = []
    for doc in corpus:
        version = kb.version(doc.source_version_id) if doc.source_version_id else None
        records.append(
            ManifestRecord(
                doc_id=doc.doc_id,
                path=doc_path(doc),
                sha256=doc.sha256,
                title=doc.title,
                source_type=source_type_of(world, doc),
                registry_state=doc.registry_state,
                version_id=doc.source_version_id,
                family_id=version.family_id if version else None,
                approved_by=version.approved_by if version else None,
                valid_from=version.valid.start if version else None,
                valid_to=version.valid.end if version else None,
                supersedes=version.supersedes if version else None,
                acl_tenants=doc.acl_tenants,
                acl_roles=doc.acl_roles,
                tokens=len(doc.text.split()),
            )
        )
    if len({r.path for r in records}) != len(records) or len({r.doc_id for r in records}) != len(records):
        raise WorldError("manifest ids and paths must be unique")
    return sorted(records, key=lambda r: sha256_hex(f"{seed}:manifest-order:{r.doc_id}"))


def identity_manifest(entities: WorldEntities) -> IdentityManifest:
    tenants = tuple({"tenant_id": t.tenant_id, "name": t.name, "internal": t.internal} for t in entities.tenants)
    roles = tuple({"role_id": r.role_id, "name": r.name, "internal_only": r.internal_only} for r in entities.roles)
    return IdentityManifest(tenants, roles, entities.principals)


def visible_records(records: Iterable[ManifestRecord], principal: Principal) -> list[ManifestRecord]:
    """Records the principal may see: empty ACL lists are unrestricted, otherwise tenant and role must both match."""
    return [
        r
        for r in records
        if (not r.acl_tenants or principal.tenant_id in r.acl_tenants)
        and (not r.acl_roles or principal.role_id in r.acl_roles)
    ]


def snapshot_id(records: Sequence[ManifestRecord]) -> str:
    """An opaque corpus snapshot id derived from the content hashes alone."""
    return "snap-" + digest_of(sorted((r.doc_id, r.sha256) for r in records))[:16]


# --------------------------------------------------------------------------- writing and reading the namespaces


@dataclass(frozen=True)
class Layout:
    root: Path

    def path(self, namespace: Namespace) -> Path:
        return self.root / namespace.value


def write_namespaces(
    root: Path, world: World, corpus: Sequence[Document], seed: int, *, overwrite: bool = False
) -> dict[str, str]:
    """Write the generator and published namespaces and create the two annotation namespaces. Returns digests."""
    layout = Layout(root)
    if root.exists() and any(root.iterdir()) and not overwrite:
        raise WorldError("output directory is not empty; pass overwrite to replace a previous generation")
    if overwrite:
        _clear_previous(layout)
    for namespace in Namespace:
        layout.path(namespace).mkdir(parents=True, exist_ok=True)
    records = build_records(world, corpus, seed)
    published = layout.path(Namespace.PUBLISHED)
    (published / "docs").mkdir(exist_ok=True)
    by_id = {d.doc_id: d for d in corpus}
    for record in records:
        (published / record.path).write_bytes(by_id[record.doc_id].text.encode("utf-8"))
    manifest_text = "".join(canonical_json(r) + "\n" for r in records)
    (published / "corpus_manifest.jsonl").write_bytes(manifest_text.encode("utf-8"))
    identity = canonical_json(identity_manifest(world.entities)) + "\n"
    (published / "identity_manifest.json").write_bytes(identity.encode("utf-8"))
    snapshot = canonical_json({"corpus_snapshot_id": snapshot_id(records), "notice": FICTIONAL_NOTICE}) + "\n"
    (published / "snapshot.json").write_bytes(snapshot.encode("utf-8"))
    generator = layout.path(Namespace.GENERATOR)
    (generator / "world.jsonl").write_bytes("".join(canonical_json(r) + "\n" for r in world.records()).encode("utf-8"))
    tags = [
        {"doc_id": d.doc_id, "category": d.category.value, "language": d.language, "tags": list(d.tags)} for d in corpus
    ]
    (generator / "document_tags.jsonl").write_bytes("".join(canonical_json(t) + "\n" for t in tags).encode("utf-8"))
    return {
        "corpus_manifest_sha256": sha256_hex(manifest_text),
        "identity_manifest_sha256": sha256_hex(identity),
        "snapshot_id": snapshot_id(records),
        "world_digest": world.digest(),
    }


def _clear_previous(layout: Layout) -> None:
    """Remove what a previous generation wrote. The generator's audit folder holds human labels and is kept."""
    for namespace in (Namespace.PUBLISHED, Namespace.DEV_ANNOTATIONS, Namespace.TEST_ANNOTATIONS):
        shutil.rmtree(layout.path(namespace), ignore_errors=True)
    generator = layout.path(Namespace.GENERATOR)
    if generator.exists():
        for entry in generator.iterdir():
            if entry.name != "audit":
                shutil.rmtree(entry) if entry.is_dir() else entry.unlink()


def read_records(published: Path) -> list[ManifestRecord]:
    out: list[ManifestRecord] = []
    for line in (published / "corpus_manifest.jsonl").read_text(encoding="utf-8").splitlines():
        data = json.loads(line)
        data["acl_tenants"], data["acl_roles"] = tuple(data["acl_tenants"]), tuple(data["acl_roles"])
        out.append(ManifestRecord(**data))
    return out


def read_identity(published: Path) -> IdentityManifest:
    data = json.loads((published / "identity_manifest.json").read_text(encoding="utf-8"))
    return IdentityManifest(
        tuple(data["tenants"]), tuple(data["roles"]), tuple(Principal(**p) for p in data["principals"])
    )


def verify_published(published: Path) -> list[str]:
    """Re-read the written tree: every manifest hash must match the file on disk and no file may be unlisted."""
    problems: list[str] = []
    records = read_records(published)
    listed = {r.path for r in records}
    for record in records:
        file = published / record.path
        if not file.is_file():
            problems.append(f"missing file for {record.doc_id}")
        elif sha256_hex(file.read_bytes().decode("utf-8")) != record.sha256:
            problems.append(f"hash mismatch for {record.doc_id}")
    on_disk = {p.relative_to(published).as_posix() for p in (published / "docs").glob("*") if p.is_file()}
    problems += [f"unlisted file {name}" for name in sorted(on_disk - listed)]
    return problems


def find_barrier_markers(text: str) -> list[str]:
    """Labels of the barrier markers in ``text``: gold vocabulary, a split word or a pseudonymous question id."""
    labels = (("gold marker", _GOLD_MARKERS), ("split word", _SPLIT_WORDS), ("question id", QUESTION_ID))
    return [label for label, pattern in labels if pattern.search(text)]


def scan_published(published: Path, forbidden: Iterable[str] = ()) -> list[str]:
    """Findings for anything in the published tree that names gold, a split, a family or a question.

    ``forbidden`` holds exact tokens that must not appear at all, such as the scenario family names and question ids
    of the gold being protected. File names are scanned as well as contents.
    """
    tokens = [t for t in forbidden if t]
    findings: list[str] = []
    for file in sorted(p for p in published.rglob("*") if p.is_file()):
        rel = file.relative_to(published).as_posix()
        if rel not in PUBLISHED_FILES and not re.fullmatch(r"docs/[0-9a-f]{16}\.md", rel):
            findings.append(f"unexpected file {rel}")
            continue
        text = file.read_text(encoding="utf-8")
        findings += [f"{label} in {rel}" for label in find_barrier_markers(text)]
        findings += [f"forbidden token {token!r} in {rel}" for token in tokens if token in text or token in rel]
    return findings


def annotation_namespace(split: Split) -> Namespace:
    """Smoke and dev gold live apart from the locked test gold."""
    return Namespace.TEST_ANNOTATIONS if split is Split.TEST else Namespace.DEV_ANNOTATIONS


def write_annotations(root: Path, split: Split, records: Sequence[Mapping[str, Any]]) -> Path:
    """Write one split's gold. A record naming another split is refused so the two namespaces cannot mix."""
    for record in records:
        if record.get("split") != split.value:
            raise WorldError("an annotation record does not belong to the split being written")
    target = Layout(root).path(annotation_namespace(split))
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"questions_{split.value}.jsonl"
    path.write_bytes("".join(canonical_json(r) + "\n" for r in records).encode("utf-8"))
    return path


def dev_annotation_files(root: Path) -> list[Path]:
    """The only annotation files a development command may read. The locked test directory is never listed."""
    return sorted(Layout(root).path(Namespace.DEV_ANNOTATIONS).glob("questions_*.jsonl"))


def manifest_digest(published: Path) -> str:
    return sha256_hex((published / "corpus_manifest.jsonl").read_bytes().decode("utf-8"))
