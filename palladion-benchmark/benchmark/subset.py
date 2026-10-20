"""A matched subset of the S tier for the graph comparators' cold-state pilot (B06-T06.01, BADR-0031).

Running a graph comparator's LLM extraction over all 1,200 documents does not fit the free tier (an estimate of 4
million tokens and about 8 hours each), so the pilot runs on a smaller snapshot that every arm, graph or not, is run on.

The rule is fixed and recorded: a seeded, stratum-balanced set of Track A questions; every document those questions
need (the evidence they cite, the sources they must not reveal, and the supersession chain of each); then seeded decoys
drawn from the rest until the document total is reached. Choosing documents from the gold is an evaluator-side act: no
arm sees the gold or the rule. It does make the subset easier than the full corpus (fewer distractors), so its results
are a matched pilot and say nothing about the full tier.

The subset is a new snapshot root with the same layout as the parent: ``published/`` with only the chosen documents,
``annotations_dev/`` with only the chosen questions (their records unchanged, line for line), and ``subset.json`` with
the rule, the seed and the digests.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from benchmark.fixtures.manifest import (
    Layout,
    ManifestRecord,
    Namespace,
    Split,
    manifest_digest,
    read_records,
    verify_published,
)
from benchmark.fixtures.questions import LIVE_PREFIX, GoldRecord, read_gold
from benchmark.runner import derived_rng
from benchmark.track_b import pick_subset

RETRIEVAL_ONLY = "retrieval_only"


class SubsetError(ValueError):
    """A subset cannot be built as asked. The message holds no gold."""


def needed_documents(record: GoldRecord) -> set[str]:
    """Every document the question's gold refers to: cited evidence, withheld sources and the version chain."""
    docs: set[str] = set(record.inaccessible_sources)
    for slot in record.slots:
        docs.update(a.doc_id for a in slot.alternatives)
    for group in record.minimal_sets:
        docs.update(c.doc_id for c in group)
    docs.update(c.doc_id for c in record.citation_gold_spans)
    return {d for d in docs if not d.startswith(LIVE_PREFIX)}


def with_version_chain(doc_ids: set[str], records: Mapping[str, ManifestRecord]) -> set[str]:
    """Add the documents each chosen document supersedes, and the ones that supersede it (its whole chain)."""
    successors: dict[str, set[str]] = {}
    for record in records.values():
        if record.supersedes:
            successors.setdefault(record.supersedes, set()).add(record.doc_id)
    chain = set(doc_ids)
    pending = list(doc_ids)
    while pending:
        current = pending.pop()
        found = records.get(current)
        earlier = {found.supersedes} if found is not None and found.supersedes else set()
        linked = earlier | successors.get(current, set())
        for other in linked:
            if other in records and other not in chain:
                chain.add(other)
                pending.append(other)
    return chain


@dataclass(frozen=True)
class SubsetPlan:
    questions: tuple[str, ...]
    documents: tuple[str, ...]
    needed: int  # documents the questions need before decoys
    decoys: int


def plan_subset(
    questions: Sequence[GoldRecord],
    records: Mapping[str, ManifestRecord],
    *,
    question_count: int,
    document_total: int,
    seed: int,
    withdrawn: Mapping[str, str] | None = None,
) -> SubsetPlan:
    """Choose the questions, then the documents. Refuses a document total smaller than the questions need."""
    skip = set(withdrawn or ())
    eligible = [q for q in questions if RETRIEVAL_ONLY in q.track_eligibility and q.question_id not in skip]
    chosen = pick_subset(eligible, question_count, seed)
    by_id = {q.question_id: q for q in eligible}
    needed: set[str] = set()
    for question_id in chosen:
        needed |= needed_documents(by_id[question_id])
    unknown = sorted(needed - set(records))
    if unknown:
        raise SubsetError(f"the chosen questions refer to {len(unknown)} document(s) the corpus does not hold")
    needed = with_version_chain(needed, records)
    if document_total < len(needed):
        raise SubsetError(f"the chosen questions need {len(needed)} documents; the total {document_total} is smaller")
    rest = sorted(set(records) - needed)
    decoys = derived_rng(seed, "subset:decoys").sample(rest, min(document_total - len(needed), len(rest)))
    documents = tuple(sorted(needed | set(decoys)))
    return SubsetPlan(tuple(chosen), documents, len(needed), len(documents) - len(needed))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_subset(
    root: Path,
    out: Path,
    *,
    question_count: int,
    document_total: int,
    seed: int,
    withdrawn: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Write the subset snapshot under ``out`` (which must not exist) and return its provenance record."""
    if out.exists():
        raise SubsetError("the output directory exists; a subset is written once")
    parent = Layout(root)
    published = parent.path(Namespace.PUBLISHED)
    problems = verify_published(published)
    if problems:
        raise SubsetError(f"the parent published tree does not verify: {problems[:3]}")
    annotations = parent.path(Namespace.DEV_ANNOTATIONS) / f"questions_{Split.SMOKE.value}.jsonl"
    gold = read_gold(annotations, expected_sha256=_sha(annotations))
    records = {r.doc_id: r for r in read_records(published)}
    plan = plan_subset(
        gold, records, question_count=question_count, document_total=document_total, seed=seed, withdrawn=withdrawn
    )
    layout = Layout(out)
    target = layout.path(Namespace.PUBLISHED)
    (target / "docs").mkdir(parents=True)
    kept = set(plan.documents)
    manifest_lines = [
        line
        for line in (published / "corpus_manifest.jsonl").read_text(encoding="utf-8").splitlines()
        if json.loads(line)["doc_id"] in kept
    ]
    for line in manifest_lines:
        relative = json.loads(line)["path"]
        shutil.copyfile(published / relative, target / relative)
    (target / "corpus_manifest.jsonl").write_bytes(("".join(line + "\n" for line in manifest_lines)).encode("utf-8"))
    for name in ("identity_manifest.json", "snapshot.json"):
        shutil.copyfile(published / name, target / name)
    chosen = set(plan.questions)
    question_lines = [
        line
        for line in annotations.read_text(encoding="utf-8").splitlines()
        if json.loads(line)["question_id"] in chosen
    ]
    dev = layout.path(Namespace.DEV_ANNOTATIONS)
    dev.mkdir(parents=True)
    (dev / annotations.name).write_bytes(("".join(line + "\n" for line in question_lines)).encode("utf-8"))
    layout.path(Namespace.TEST_ANNOTATIONS).mkdir(parents=True)
    layout.path(Namespace.GENERATOR).mkdir(parents=True)
    problems = verify_published(target)
    if problems:
        raise SubsetError(f"the subset's published tree does not verify: {problems[:3]}")
    provenance: dict[str, object] = {
        "rule": (
            "seeded stratum-balanced Track A questions; their cited, withheld and version-chain documents; "
            "seeded decoys"
        ),
        "seed": seed,
        "questions": len(plan.questions),
        "documents": len(plan.documents),
        "needed_documents": plan.needed,
        "decoys": plan.decoys,
        "parent_published_manifest_sha256": manifest_digest(published),
        "published_manifest_sha256": manifest_digest(target),
        "questions_sha256": _sha(dev / annotations.name),
        "document_ids_sha256": hashlib.sha256("\n".join(plan.documents).encode("utf-8")).hexdigest(),
        "notice": (
            "A matched pilot subset: easier than the full tier because the gold chose its documents (evaluator side)."
        ),
    }
    (out / "subset.json").write_text(json.dumps(provenance, indent=2, sort_keys=True), encoding="utf-8")
    return provenance
