"""The matched subset for the graph comparators' pilot: a smaller snapshot every arm can be run on (B06-T06.01)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from benchmark.adapters.common import Condition, PublishedView
from benchmark.fixtures.manifest import (
    Layout,
    ManifestRecord,
    Namespace,
    read_records,
    scan_published,
    verify_published,
)
from benchmark.fixtures.questions import LIVE_PREFIX, GoldRecord, read_gold
from benchmark.results_check import validate_run
from benchmark.subset import (
    SubsetError,
    build_subset,
    needed_documents,
    plan_subset,
    with_version_chain,
)
from benchmark.track_a import RunSpec, build_local_arms, execute, read_annotations

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS, DOCUMENTS = 10, 100


@pytest.fixture(scope="module")
def records(s_root: Path) -> dict[str, ManifestRecord]:
    return {r.doc_id: r for r in read_records(Layout(s_root).path(Namespace.PUBLISHED))}


def plan(questions: tuple[GoldRecord, ...], records: dict[str, ManifestRecord], **over: object) -> object:
    base: dict[str, object] = {"question_count": QUESTIONS, "document_total": DOCUMENTS, "seed": 7}
    return plan_subset(questions, records, **{**base, **over})  # type: ignore[arg-type]


# --------------------------------------------------------------------------- which documents a question needs


def test_a_question_needs_the_documents_its_gold_cites_and_withholds_and_never_a_live_read(
    s_questions: tuple[GoldRecord, ...],
) -> None:
    cited = next(
        q for q in s_questions if any(not a.doc_id.startswith(LIVE_PREFIX) for s in q.slots for a in s.alternatives)
    )
    docs = needed_documents(cited)
    assert docs and not any(d.startswith(LIVE_PREFIX) for d in docs)
    assert {a.doc_id for s in cited.slots for a in s.alternatives if not a.doc_id.startswith(LIVE_PREFIX)} <= docs
    blocked = next((q for q in s_questions if q.inaccessible_sources), None)
    assert blocked is not None and set(blocked.inaccessible_sources) <= needed_documents(blocked)


def test_the_version_chain_adds_what_a_document_supersedes_and_what_supersedes_it(
    records: dict[str, ManifestRecord],
) -> None:
    chained = [r for r in records.values() if r.supersedes and r.supersedes in records]
    assert chained, "the S tier has version chains"
    newer = chained[0]
    assert with_version_chain({newer.doc_id}, records) >= {newer.doc_id, newer.supersedes}
    assert newer.supersedes is not None
    older = records[newer.supersedes]
    assert newer.doc_id in with_version_chain({older.doc_id}, records)
    assert with_version_chain(set(), records) == set()


# --------------------------------------------------------------------------- the plan


def test_the_plan_is_deterministic_stratum_balanced_and_exactly_the_requested_size(
    s_questions: tuple[GoldRecord, ...], records: dict[str, ManifestRecord]
) -> None:
    first = plan_subset(s_questions, records, question_count=QUESTIONS, document_total=DOCUMENTS, seed=7)
    again = plan_subset(s_questions, records, question_count=QUESTIONS, document_total=DOCUMENTS, seed=7)
    other = plan_subset(s_questions, records, question_count=QUESTIONS, document_total=DOCUMENTS, seed=8)
    assert first == again and first.documents != other.documents
    assert len(first.questions) == QUESTIONS and len(first.documents) == DOCUMENTS
    assert first.needed + first.decoys == DOCUMENTS and first.decoys > 0
    strata = {next(q.stratum for q in s_questions if q.question_id == i) for i in first.questions}
    available = {q.stratum for q in s_questions if "retrieval_only" in q.track_eligibility}
    assert strata == available and len(first.questions) >= len(available), "every Track A stratum is represented"


def test_every_document_a_chosen_question_needs_is_in_the_plan(
    s_questions: tuple[GoldRecord, ...], records: dict[str, ManifestRecord]
) -> None:
    chosen = plan_subset(s_questions, records, question_count=QUESTIONS, document_total=DOCUMENTS, seed=7)
    by_id = {q.question_id: q for q in s_questions}
    for question_id in chosen.questions:
        assert needed_documents(by_id[question_id]) <= set(chosen.documents), question_id


def test_a_withdrawn_question_is_never_chosen(
    s_questions: tuple[GoldRecord, ...], records: dict[str, ManifestRecord]
) -> None:
    base = plan_subset(s_questions, records, question_count=QUESTIONS, document_total=DOCUMENTS, seed=7)
    gone = base.questions[0]
    after = plan_subset(
        s_questions, records, question_count=QUESTIONS, document_total=DOCUMENTS, seed=7, withdrawn={gone: "defect"}
    )
    assert gone not in after.questions and len(after.questions) == QUESTIONS


def test_a_document_total_smaller_than_the_questions_need_is_refused(
    s_questions: tuple[GoldRecord, ...], records: dict[str, ManifestRecord]
) -> None:
    with pytest.raises(SubsetError, match="smaller"):
        plan_subset(s_questions, records, question_count=QUESTIONS, document_total=2, seed=7)


def test_a_question_that_names_a_missing_document_is_refused(
    s_questions: tuple[GoldRecord, ...], records: dict[str, ManifestRecord]
) -> None:
    trimmed = {k: v for k, v in records.items() if k != next(iter(needed_documents(s_questions[0])), "")}
    with pytest.raises(SubsetError, match="does not hold"):
        plan_subset(s_questions, trimmed, question_count=len(s_questions), document_total=1200, seed=7)


# --------------------------------------------------------------------------- the written snapshot


@pytest.fixture(scope="module")
def subset(s_root: Path, tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, object]]:
    out = tmp_path_factory.mktemp("subset") / "S"
    return out, build_subset(s_root, out, question_count=QUESTIONS, document_total=DOCUMENTS, seed=7)


def test_the_subset_is_a_verified_snapshot_with_the_requested_counts(
    subset: tuple[Path, dict[str, object]],
) -> None:
    out, provenance = subset
    published = Layout(out).path(Namespace.PUBLISHED)
    assert verify_published(published) == [] and scan_published(published) == []
    assert len(read_records(published)) == DOCUMENTS == provenance["documents"]
    assert provenance["questions"] == QUESTIONS and provenance["needed_documents"] + provenance["decoys"] == DOCUMENTS  # type: ignore[operator]
    assert PublishedView.load(published).document(read_records(published)[0].doc_id).text


def test_the_chosen_questions_are_copied_unchanged_line_for_line(
    s_root: Path, subset: tuple[Path, dict[str, object]]
) -> None:
    out, _ = subset
    parent = {
        json.loads(line)["question_id"]: line
        for line in (Layout(s_root).path(Namespace.DEV_ANNOTATIONS) / "questions_smoke.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    }
    written = (
        (Layout(out).path(Namespace.DEV_ANNOTATIONS) / "questions_smoke.jsonl").read_text(encoding="utf-8").splitlines()
    )
    assert len(written) == QUESTIONS and all(line == parent[json.loads(line)["question_id"]] for line in written)


def test_the_subset_holds_no_generator_material_and_no_answer_sidecar(subset: tuple[Path, dict[str, object]]) -> None:
    out, _ = subset
    assert list(Layout(out).path(Namespace.GENERATOR).iterdir()) == []
    assert not list(Layout(out).path(Namespace.DEV_ANNOTATIONS).glob("answers_*"))
    assert not list(Layout(out).path(Namespace.TEST_ANNOTATIONS).iterdir())


def test_the_provenance_records_the_rule_the_seed_and_digests_that_match_the_files(
    subset: tuple[Path, dict[str, object]],
) -> None:
    out, provenance = subset
    assert json.loads((out / "subset.json").read_text(encoding="utf-8")) == provenance
    assert (
        provenance["seed"] == 7
        and "stratum-balanced" in str(provenance["rule"])
        and "easier" in str(provenance["notice"])
    )
    assert provenance["parent_published_manifest_sha256"] != provenance["published_manifest_sha256"]


def test_a_subset_is_written_once(s_root: Path, subset: tuple[Path, dict[str, object]]) -> None:
    out, _ = subset
    with pytest.raises(SubsetError, match="written once"):
        build_subset(s_root, out, question_count=QUESTIONS, document_total=DOCUMENTS, seed=7)


def test_every_arm_can_run_on_the_subset_and_the_run_validates(
    subset: tuple[Path, dict[str, object]], tmp_path: Path
) -> None:
    out, _ = subset
    records, _ = read_annotations(out, "smoke")
    assert len(records) == QUESTIONS
    view = PublishedView.load(Layout(out).path(Namespace.PUBLISHED))
    arms, builds = build_local_arms(view, ["R0"], condition=Condition.C2, index_dir=tmp_path / "index")
    execute(RunSpec("run-s-0001", "smoke", Condition.C2, 10, 4000, out, tmp_path / "run"), arms, builds=builds)
    assert validate_run(tmp_path / "run", root=out) == []
    gold = read_gold(Layout(out).path(Namespace.DEV_ANNOTATIONS) / "questions_smoke.jsonl")
    assert len(gold) == QUESTIONS


def test_the_command_line_writes_a_subset_and_refuses_an_impossible_one(s_root: Path, tmp_path: Path) -> None:
    script = str(ROOT / "scripts" / "build_subset.py")
    ok = subprocess.run(
        [sys.executable, script, "--root", str(s_root), "--out", str(tmp_path / "ok"), "-q", "5", "-d", "40"],
        capture_output=True, text=True, check=False, timeout=600,
    )  # fmt: skip
    assert ok.returncode == 0, ok.stderr
    assert json.loads(ok.stdout)["documents"] == 40
    bad = subprocess.run(
        [sys.executable, script, "--root", str(s_root), "--out", str(tmp_path / "bad"), "-q", "5", "-d", "1"],
        capture_output=True, text=True, check=False, timeout=600,
    )  # fmt: skip
    assert bad.returncode == 2 and bad.stderr.startswith("refused:") and not (tmp_path / "bad").exists()
