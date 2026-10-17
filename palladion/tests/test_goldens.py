"""Integrity tests for the synthetic source and T01–T24 pilot catalog."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from evidence_agent.core.fixtures import FixtureValidationError, load_fixtures

APP_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = APP_ROOT.parent


def _copy_fixture_tree(tmp_path: Path) -> Path:
    app = tmp_path / "palladion"
    for relative in (
        "data/demo/sop_2025.md",
        "data/demo/sop_2026.md",
        "data/demo/exception_appendix.md",
        "data/demo/draft_memo.md",
        "data/demo/sample_cases.json",
        "data/demo/goldens.jsonl",
        "config/policies/demo_reversal_v2.json",
    ):
        destination = app / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(APP_ROOT / relative, destination)
    return app


def _read_goldens(app: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in (app / "data/demo/goldens.jsonl").read_text(encoding="utf-8").splitlines()]


def _write_goldens(app: Path, rows: list[dict[str, object]]) -> None:
    path = app / "data/demo/goldens.jsonl"
    path.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


def test_valid_corpus_has_exact_source_spans_and_all_pilot_cases() -> None:
    bundle = load_fixtures(REPOSITORY_ROOT)

    summary = bundle.summary()
    assert summary.golden_ids == tuple(f"T{i:02d}" for i in range(1, 25))
    assert summary.golden_count == 24
    assert summary.annotation_status == "PILOT"
    assert summary.source_count == 4
    assert summary.approved_source_count == 3
    assert {principal.tenant_id for principal in bundle.principals} == {"tenant-a", "tenant-b"}
    assert {role for principal in bundle.principals for role in principal.roles} >= {"admin", "uploader", "reader"}
    assert bundle.source_map()["SOP-2026-B"].clauses["S26-REVERSAL"].text.startswith("For a QR_DEMO")
    assert bundle.observations[1].status == "TIMEOUT"
    assert bundle.observations[2].data["settlement_state"] == "UNSETTLED"


def test_missing_golden_catalog_entry_fails(tmp_path: Path) -> None:
    app = _copy_fixture_tree(tmp_path)
    _write_goldens(app, _read_goldens(app)[:-1])

    with pytest.raises(FixtureValidationError, match="T01 through T24"):
        load_fixtures(app)


def test_duplicate_golden_id_fails(tmp_path: Path) -> None:
    app = _copy_fixture_tree(tmp_path)
    rows = _read_goldens(app)
    rows[-1]["query_id"] = "T23"
    _write_goldens(app, rows)

    with pytest.raises(FixtureValidationError, match="duplicate golden query ID|T01 through T24"):
        load_fixtures(app)


@pytest.mark.parametrize("mutation", ["unknown_source", "unknown_clause", "wrong_hash", "wrong_span"])
def test_invalid_gold_source_reference_fails(tmp_path: Path, mutation: str) -> None:
    app = _copy_fixture_tree(tmp_path)
    rows = _read_goldens(app)
    reference = rows[0]["source_clause_refs"][0]
    assert isinstance(reference, dict)
    if mutation == "unknown_source":
        reference["source_id"] = "MISSING-SOURCE"
    elif mutation == "unknown_clause":
        reference["clause_id"] = "MISSING-CLAUSE"
    elif mutation == "wrong_hash":
        reference["source_sha256"] = "0" * 64
    else:
        reference["span_start"] = reference["span_start"] + 1
    _write_goldens(app, rows)

    with pytest.raises(FixtureValidationError, match="unknown source reference|unknown clause reference|source hash/span mismatch"):
        load_fixtures(app)


def test_missing_required_golden_field_fails(tmp_path: Path) -> None:
    app = _copy_fixture_tree(tmp_path)
    rows = _read_goldens(app)
    del rows[0]["forbidden_actions"]
    _write_goldens(app, rows)

    with pytest.raises(FixtureValidationError, match="forbidden_actions|Field required"):
        load_fixtures(app)


def test_unknown_policy_time_source_fails(tmp_path: Path) -> None:
    app = _copy_fixture_tree(tmp_path)
    path = app / "config/policies/demo_reversal_v2.json"
    policy = json.loads(path.read_text(encoding="utf-8"))
    policy["versions"][1]["applicability"]["timestamp_source"] = "user_text.transaction_occurred_at"
    path.write_text(json.dumps(policy), encoding="utf-8")

    with pytest.raises(FixtureValidationError, match="unknown time source"):
        load_fixtures(app)


def test_unknown_policy_fact_source_fails(tmp_path: Path) -> None:
    app = _copy_fixture_tree(tmp_path)
    path = app / "config/policies/demo_reversal_v2.json"
    policy = json.loads(path.read_text(encoding="utf-8"))
    policy["versions"][1]["required_facts"][0]["source"] = "user_text.settlement_state"
    path.write_text(json.dumps(policy), encoding="utf-8")

    with pytest.raises(FixtureValidationError, match="unknown fact source"):
        load_fixtures(app)


def test_unknown_observation_time_field_fails(tmp_path: Path) -> None:
    app = _copy_fixture_tree(tmp_path)
    path = app / "data/demo/sample_cases.json"
    catalog = json.loads(path.read_text(encoding="utf-8"))
    catalog["observations"][0]["trusted_fields"].append("user_supplied_time")
    path.write_text(json.dumps(catalog), encoding="utf-8")

    with pytest.raises(FixtureValidationError, match="trusts a field it does not contain"):
        load_fixtures(app)


def test_changed_original_bytes_invalidate_frozen_source_references(tmp_path: Path) -> None:
    app = _copy_fixture_tree(tmp_path)
    source = app / "data/demo/sop_2026.md"
    source.write_text(source.read_text(encoding="utf-8") + "\nChanged after annotation.\n", encoding="utf-8")

    with pytest.raises(FixtureValidationError, match="source hash/span mismatch"):
        load_fixtures(app)


def test_impossible_missing_settlement_answer_fails(tmp_path: Path) -> None:
    app = _copy_fixture_tree(tmp_path)
    rows = _read_goldens(app)
    row = next(item for item in rows if item["query_id"] == "T09")
    row["expected_policy_decision"] = "REVERSAL_ALLOWED"
    row["expected_disposition"] = "SUPPORTED"
    _write_goldens(app, rows)

    with pytest.raises(FixtureValidationError, match="T09 missing settlement"):
        load_fixtures(app)


def test_stale_bi_observation_cannot_be_labeled_current_negative(tmp_path: Path) -> None:
    app = _copy_fixture_tree(tmp_path)
    rows = _read_goldens(app)
    row = next(item for item in rows if item["query_id"] == "T13")
    row["expected_disposition"] = "SUPPORTED"
    _write_goldens(app, rows)

    with pytest.raises(FixtureValidationError, match="T13 must preserve stale data_as_of"):
        load_fixtures(app)


def test_source_path_escape_is_rejected(tmp_path: Path) -> None:
    app = _copy_fixture_tree(tmp_path)
    path = app / "data/demo/sample_cases.json"
    catalog = json.loads(path.read_text(encoding="utf-8"))
    catalog["sources"][0]["path"] = "../../outside.md"
    path.write_text(json.dumps(catalog), encoding="utf-8")

    with pytest.raises(FixtureValidationError, match="source path is not a contained"):
        load_fixtures(app)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("disjoint", "intervals do not overlap"),
        ("event_at_end", "T03 overlap without precedence"),
        ("scope", "must share tenant, product, transaction class"),
        ("unapproved", "complete approved policy record"),
        ("unknown_version", "unknown or mismatched conflict policy version IDs"),
    ],
)
def test_conflict_fixture_requires_known_compatible_overlapping_candidates(
    tmp_path: Path, mutation: str, message: str
) -> None:
    app = _copy_fixture_tree(tmp_path)
    policy_path = app / "config/policies/demo_reversal_v2.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    candidates = policy["conflict_fixture"]["candidates"]
    if mutation == "disjoint":
        candidates[1]["applicability"]["valid_from"] = "2026-10-01T00:00:00Z"
    elif mutation == "event_at_end":
        candidates[0]["applicability"]["valid_to"] = "2026-08-15T10:20:00Z"
    elif mutation == "scope":
        candidates[1]["applicability"]["product"] = "OTHER_PRODUCT"
    elif mutation == "unapproved":
        candidates[1]["state"] = "DRAFT"
    else:
        rows = _read_goldens(app)
        row = next(item for item in rows if item["query_id"] == "T03")
        row["setup"]["candidate_policy_version_ids"][0] = "unknown-policy-version"
        _write_goldens(app, rows)
    policy_path.write_text(json.dumps(policy), encoding="utf-8")

    with pytest.raises(FixtureValidationError, match=message):
        load_fixtures(app)


def test_t03_conflict_event_must_be_backed_by_same_case_observation(tmp_path: Path) -> None:
    app = _copy_fixture_tree(tmp_path)
    path = app / "data/demo/sample_cases.json"
    catalog = json.loads(path.read_text(encoding="utf-8"))
    observation = next(item for item in catalog["observations"] if item["observation_id"] == "obs-transaction-102-v1")
    observation["case_id"] = "case-43"
    path.write_text(json.dumps(catalog), encoding="utf-8")

    with pytest.raises(FixtureValidationError, match="T03 overlap without precedence"):
        load_fixtures(app)
