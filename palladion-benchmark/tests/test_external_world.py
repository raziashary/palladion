"""The BEIR-to-world converter: a public retrieval set becomes a world the unchanged harness can score (B09-T03.01)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from benchmark.eval.normalize import PublishedCorpus
from benchmark.fixtures.manifest import Layout, Namespace, read_identity, read_records, verify_published
from benchmark.fixtures.questions import read_gold

ROOT = Path(__file__).resolve().parents[1]


def load_script() -> ModuleType:
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("build_external_world", ROOT / "scripts" / "build_external_world.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


converter = load_script()


def beir(tmp_path: Path, qrels: str = "q1\td1\t1\nq1\td2\t1\nq2\td3\t1\nq2\td1\t0\nq3\tdX\t1\n") -> Path:
    folder = tmp_path / "beir"
    (folder / "qrels").mkdir(parents=True)
    corpus = [
        {"_id": "d1", "title": "On cats", "text": "Cats purr.\nThey sleep a lot."},
        {"_id": "d2", "title": "On dogs", "text": "Dogs bark."},
        {"_id": "d3", "title": "", "text": "Fish swim."},
    ]
    (folder / "corpus.jsonl").write_text("".join(json.dumps(c) + "\n" for c in corpus), encoding="utf-8")
    queries = [{"_id": "q1", "text": "pets"}, {"_id": "q2", "text": "fish?"}, {"_id": "q3", "text": "missing doc"}]
    (folder / "queries.jsonl").write_text("".join(json.dumps(q) + "\n" for q in queries), encoding="utf-8")
    (folder / "qrels" / "test.tsv").write_text("query-id\tcorpus-id\tscore\n" + qrels, encoding="utf-8")
    return folder


def test_a_world_is_written_that_the_harness_reads_back_and_verifies(tmp_path: Path) -> None:
    out = tmp_path / "world"
    summary = converter.build(beir(tmp_path), "Mini", "CC0", out)
    published = Layout(out).path(Namespace.PUBLISHED)
    assert verify_published(published) == []
    assert summary["documents"] == 3 and summary["questions"] == 2, "q3 judges a document the corpus lacks"
    records = read_records(published)
    assert {r.doc_id for r in records} == {"SF-d1", "SF-d2", "SF-d3"}
    assert all(r.registry_state == "approved" and not r.acl_tenants and not r.acl_roles for r in records)
    assert len(read_identity(published).principals) == 1


def test_each_passage_is_one_clause_so_a_returned_chunk_of_it_credits_it(tmp_path: Path) -> None:
    out = tmp_path / "world"
    converter.build(beir(tmp_path), "Mini", "CC0", out)
    corpus = PublishedCorpus.load(Layout(out).path(Namespace.PUBLISHED))
    cats = corpus.docs["SF-d1"]
    assert list(cats.clauses) == ["1.1"] and "Cats purr. They sleep a lot." in cats.text, (
        "newlines are folded into one line"
    )
    start, end = cats.clauses["1.1"]
    assert cats.text[start:end].startswith("1.1 Cats purr.")


def test_questions_have_one_slot_per_relevant_passage_and_zero_judgements_are_ignored(tmp_path: Path) -> None:
    out = tmp_path / "world"
    converter.build(beir(tmp_path), "Mini", "CC0", out)
    gold = read_gold(Layout(out).path(Namespace.DEV_ANNOTATIONS) / "questions_smoke.jsonl")
    by_query = {g.query: g for g in gold}
    assert [len(by_query["pets"].slots), len(by_query["fish?"].slots)] == [2, 1], "q2's score-0 judgement is not a slot"
    assert {c.doc_id for c in by_query["pets"].citation_gold_spans} == {"SF-d1", "SF-d2"}
    assert by_query["pets"].stratum.value == "Q3" and by_query["fish?"].stratum.value == "Q2"
    assert by_query["pets"].track_eligibility == ("retrieval_only",)


def test_the_gold_span_is_the_clause_text_by_hash(tmp_path: Path) -> None:
    from benchmark.fixtures import sha256_hex

    out = tmp_path / "world"
    converter.build(beir(tmp_path), "Mini", "CC0", out)
    published = Layout(out).path(Namespace.PUBLISHED)
    gold = read_gold(Layout(out).path(Namespace.DEV_ANNOTATIONS) / "questions_smoke.jsonl")
    record = next(g for g in gold if g.query == "fish?")
    citation = record.citation_gold_spans[0]
    corpus = PublishedCorpus.load(published)
    assert sha256_hex(corpus.docs[citation.doc_id].text[citation.start : citation.end]) == citation.span_sha256
    assert (citation.start, citation.end) == corpus.docs[citation.doc_id].clauses[citation.clause_id]


def test_a_world_is_never_overwritten_and_missing_files_or_no_judgements_are_refused(tmp_path: Path) -> None:
    out = tmp_path / "world"
    converter.build(beir(tmp_path), "Mini", "CC0", out)
    with pytest.raises(converter.ExternalWorldError, match="never overwritten"):
        converter.build(beir(tmp_path / "again"), "Mini", "CC0", out)
    empty = beir(tmp_path / "empty", qrels="q3\tdX\t1\n")
    with pytest.raises(converter.ExternalWorldError, match="no judged query"):
        converter.build(empty, "Mini", "CC0", tmp_path / "none")
    (empty / "queries.jsonl").unlink()
    with pytest.raises(converter.ExternalWorldError, match="missing"):
        converter.build(empty, "Mini", "CC0", tmp_path / "gone")
