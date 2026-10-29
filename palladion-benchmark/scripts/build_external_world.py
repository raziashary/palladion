"""Turn a BEIR-format retrieval dataset into a benchmark world, to run the unchanged harness on public data.

    uv run python scripts/build_external_world.py --beir artifacts/external/scifact-raw/scifact \
        --name SciFact --license "CC BY-NC 2.0" --out artifacts/external/scifact-world

BEIR holds a corpus of passages, queries and relevance judgements. Each passage becomes one published document whose
text is a single numbered clause (``1.1 <text>``), so a returned chunk of the passage credits the passage, which is
all a document-level judgement can say. Each judged query becomes one question with one evidence slot per relevant
passage. Every document is approved, unrestricted and unversioned: this tests ordinary search, not the approval,
version or access rules the synthetic worlds test, and the report says so. The converter reads files and writes
files; it never runs anything from the dataset.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from benchmark.contracts import EvidenceStatus
from benchmark.fixtures import canonical_json, sha256_hex
from benchmark.fixtures.entities import Principal
from benchmark.fixtures.manifest import (
    IdentityManifest,
    Layout,
    ManifestRecord,
    Namespace,
    Split,
    snapshot_id,
    verify_published,
    write_annotations,
)
from benchmark.fixtures.questions import (
    Answerability,
    Citation,
    EvidenceSlot,
    GoldRecord,
    Severity,
    SlotState,
    Stratum,
)

TENANT, ROLE, PRINCIPAL = "T-EXT", "reader", "external.reader.01"
EVALUATION_TIME = "2026-10-18T03:00:00Z"
MAX_QUERIES = 10_000


class ExternalWorldError(ValueError):
    """The dataset cannot be turned into a world."""


def passages(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            yield json.loads(line)


def one_line(text: str) -> str:
    return " ".join(str(text).split())


def render(name: str, license_name: str, title: str, text: str) -> str:
    """The published text of one passage: a banner, the title, and the passage as clause 1.1."""
    return (
        f"> EXTERNAL: a passage of the public dataset {name} ({license_name}); not part of the fictional corpus.\n\n"
        f"# {one_line(title) or 'Untitled'}\n\n"
        "- Document type: passage\n\n"
        f"1.1 {one_line(text)}\n"
    )


def build(beir: Path, name: str, license_name: str, out: Path, *, qrels_name: str = "test") -> dict[str, Any]:
    corpus_file, queries_file, qrels_file = (
        beir / "corpus.jsonl",
        beir / "queries.jsonl",
        beir / "qrels" / f"{qrels_name}.tsv",
    )
    for required in (corpus_file, queries_file, qrels_file):
        if not required.is_file():
            raise ExternalWorldError(f"{required.name} is missing from {beir}")
    layout = Layout(out)
    if out.exists() and any(out.iterdir()):
        raise ExternalWorldError("the output folder is not empty; a world is never overwritten")
    published = layout.path(Namespace.PUBLISHED)
    (published / "docs").mkdir(parents=True)

    records: list[ManifestRecord] = []
    texts: dict[str, str] = {}
    for item in passages(corpus_file):
        doc_id = f"SF-{item['_id']}"
        text = render(name, license_name, item.get("title", ""), item.get("text", ""))
        sha = sha256_hex(text)
        path = f"docs/{sha256_hex(doc_id + chr(58) + sha)[:16]}.md"
        (published / path).write_bytes(text.encode("utf-8"))
        texts[doc_id] = text
        records.append(
            ManifestRecord(
                doc_id, path, sha, one_line(item.get("title", "")) or "Untitled", "passage", "approved",
                None, None, None, None, None, None, None, (), (), len(text.split()),
            )
        )  # fmt: skip
    if len({r.doc_id for r in records}) != len(records):
        raise ExternalWorldError("the corpus holds a repeated id")
    records.sort(key=lambda r: sha256_hex(f"{name}:order:{r.doc_id}"))
    (published / "corpus_manifest.jsonl").write_bytes(
        "".join(canonical_json(r) + "\n" for r in records).encode("utf-8")
    )
    identity = IdentityManifest(
        ({"tenant_id": TENANT, "name": f"{name} reader", "internal": False},),
        ({"role_id": ROLE, "name": "Reader", "internal_only": False},),
        (Principal(PRINCIPAL, TENANT, ROLE, "External reader"),),
    )
    (published / "identity_manifest.json").write_bytes((canonical_json(identity) + "\n").encode("utf-8"))
    snapshot = snapshot_id(records)
    (published / "snapshot.json").write_bytes(
        (
            canonical_json({"corpus_snapshot_id": snapshot, "notice": f"A public dataset, {name} ({license_name})."})
            + "\n"
        ).encode("utf-8")
    )

    queries = {q["_id"]: one_line(q["text"]) for q in passages(queries_file)}
    relevant: dict[str, list[str]] = {}
    with qrels_file.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if int(row["score"]) >= 1 and f"SF-{row['corpus-id']}" in texts and row["query-id"] in queries:
                relevant.setdefault(row["query-id"], []).append(f"SF-{row['corpus-id']}")
    if not relevant or len(relevant) > MAX_QUERIES:
        raise ExternalWorldError("no judged query, or too many")
    gold: list[dict[str, Any]] = []
    for query_id in sorted(relevant):
        docs = sorted(set(relevant[query_id]))
        citations = []
        for doc_id in docs:
            text = texts[doc_id]
            start = text.index("1.1 ")
            end = text.index("\n", start)
            citations.append(Citation(doc_id, "1.1", start, end, sha256_hex(text[start:end])))
        slots = tuple(
            EvidenceSlot(f"passage_{i}", SlotState.SATISFIABLE, None, (c,)) for i, c in enumerate(citations, start=1)
        )
        record = GoldRecord(
            question_id="q-" + sha256_hex(f"{name}:{query_id}")[:16], split=Split.SMOKE,
            stratum=Stratum.Q3 if len(docs) > 1 else Stratum.Q2, difficulty=1, language="en",
            scenario_family=f"{name}-{query_id}", corpus_snapshot_id=snapshot, principal_id=PRINCIPAL, tenant_id=TENANT,
            authorized_partitions=(TENANT,), evaluation_time=EVALUATION_TIME, event_time=None, case_open_time=None,
            query=queries[query_id], answerability=Answerability.ANSWERABLE, missing_reasons=(),
            required_claims=("The cited passages are judged relevant to the query.",),
            forbidden_claims=(), slots=slots, minimal_sets=(tuple(citations),), gold_as_of_basis=None,
            gold_applicable_version_ids=(), policy_outcome=None, required_policy_inputs=(), expected_live_snapshot=None,
            allowed_statuses=(EvidenceStatus.SUPPORTED,), preferred_action="answer from the cited clauses",
            abstention_note=None, citation_gold_spans=tuple(citations), harm_severity=Severity.LOW, allowed_actions=(),
            inaccessible_sources=(), track_eligibility=("retrieval_only",), twin_of=None,
        )  # fmt: skip
        gold.append(record.to_dict() | {"split": Split.SMOKE.value})
    write_annotations(out, Split.SMOKE, gold)
    problems = verify_published(published)
    if problems:
        raise ExternalWorldError(f"the written corpus failed its readback: {problems[:3]}")
    return {
        "name": name,
        "license": license_name,
        "documents": len(records),
        "questions": len(gold),
        "questions_with_several_relevant_documents": sum(1 for q in gold if len(q["slots"]) > 1),
        "snapshot_id": snapshot,
        "dataset_sha256": sha256_hex(corpus_file.read_text(encoding="utf-8")),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--beir", type=Path, required=True, help="the unzipped BEIR folder (corpus.jsonl, queries.jsonl)"
    )
    parser.add_argument("--name", required=True)
    parser.add_argument("--license", dest="license_name", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--qrels", default="test")
    options = parser.parse_args(argv)
    try:
        summary = build(options.beir, options.name, options.license_name, options.out, qrels_name=options.qrels)
    except (ExternalWorldError, OSError, KeyError, ValueError) as error:
        print(f"refused: {str(error)[:300]}", file=sys.stderr)
        return 2
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
