"""The result validator: a clean run passes, and each planted defect is rejected for its own reason (B04-T04.03)."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from benchmark.adapters.common import Condition, PublishedView
from benchmark.fixtures.questions import GoldRecord
from benchmark.results_check import Finding, gold_texts, validate_run
from benchmark.track_a import RunSpec, build_local_arms, execute

K, BUDGET = 10, 4000
PLANTED = "-".join(["planted", "value", "0123456789abcdef"])


@pytest.fixture(scope="module")
def clean_run(s_root: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("clean") / "run"
    view = PublishedView.load(s_root / "published")
    arms, builds = build_local_arms(view, ["R0"], condition=Condition.C2, index_dir=out / "index")
    execute(RunSpec("run-v-0001", "smoke", Condition.C2, K, BUDGET, s_root, out), arms, builds=builds)
    return out


def planted(clean_run: Path, tmp_path: Path, edit: Callable[[Path], None]) -> Path:
    copy = tmp_path / "run"
    shutil.copytree(clean_run, copy)
    edit(copy)
    return copy


def rules(findings: list[Finding]) -> str:
    return " | ".join(f.render() for f in findings)


def edit_ledger(run: Path, change: Callable[[list[dict[str, object]]], list[dict[str, object]]]) -> None:
    lines = (run / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
    rows = change([json.loads(line) for line in lines])
    (run / "ledger.jsonl").write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n", encoding="utf-8")


def edit_json(path: Path, change: Callable[[dict[str, object]], None]) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def first_ok_payload(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    for row in rows:
        payload = row["payload"]
        if row["is_final"] and row["status"] == "OK" and isinstance(payload, list) and payload:
            return payload
    raise AssertionError("the clean run has no OK record with candidates")


# --------------------------------------------------------------------------- the control


def test_a_clean_run_passes(clean_run: Path, s_root: Path) -> None:
    assert validate_run(clean_run, root=s_root, secret_values=[PLANTED]) == []


# --------------------------------------------------------------------------- planted defects


def test_planted_gold_text_is_rejected(
    clean_run: Path, s_root: Path, tmp_path: Path, s_questions: tuple[GoldRecord, ...]
) -> None:
    claim = gold_texts(s_questions)[0]

    def plant(run: Path) -> None:
        def change(rows: list[dict[str, object]]) -> list[dict[str, object]]:
            first_ok_payload(rows)[0]["content"] = f"{first_ok_payload(rows)[0]['content']} {claim}"
            return rows

        edit_ledger(run, change)

    found = rules(validate_run(planted(clean_run, tmp_path, plant), root=s_root))
    assert "gold text appears in an artifact" in found


def test_a_planted_gold_key_is_rejected(clean_run: Path, s_root: Path, tmp_path: Path) -> None:
    def plant(run: Path) -> None:
        edit_json(run / "run_config.json", lambda data: data.update({"expected_answer": "x"}))

    assert "a JSON key names gold" in rules(validate_run(planted(clean_run, tmp_path, plant), root=s_root))


def test_a_gold_key_inside_a_candidates_metadata_is_rejected(clean_run: Path, s_root: Path, tmp_path: Path) -> None:
    def plant(run: Path) -> None:
        def change(rows: list[dict[str, object]]) -> list[dict[str, object]]:
            meta = first_ok_payload(rows)[0]["additional_metadata"]
            assert isinstance(meta, dict)
            meta["required_evidence"] = ["POL-001#4.1"]
            return rows

        edit_ledger(run, change)

    assert "a JSON key names gold" in rules(validate_run(planted(clean_run, tmp_path, plant), root=s_root))


def test_a_planted_answer_gold_key_is_rejected(clean_run: Path, s_root: Path, tmp_path: Path) -> None:
    def plant(run: Path) -> None:
        edit_json(run / "run_config.json", lambda data: data.update({"allowed_actions": ["ANSWER"]}))

    assert "a JSON key names gold" in rules(validate_run(planted(clean_run, tmp_path, plant), root=s_root))

    def plant_inputs(run: Path) -> None:
        edit_json(run / "run_config.json", lambda data: data.update({"required_policy_inputs": ["amount"]}))

    other = tmp_path / "second"
    other.mkdir()
    assert "a JSON key names gold" in rules(validate_run(planted(clean_run, other, plant_inputs), root=s_root))


def test_a_recorded_read_of_the_locked_test_namespace_is_rejected(
    clean_run: Path, s_root: Path, tmp_path: Path
) -> None:
    def plant(run: Path) -> None:
        edit_json(
            run / "read_log.json",
            lambda data: data.update({"annotation_namespace": "annotations_test", "test_namespace_read": True}),
        )

    found = rules(validate_run(planted(clean_run, tmp_path, plant), root=s_root))
    assert "the run read the locked test namespace" in found


def test_a_run_that_read_another_splits_file_is_rejected(clean_run: Path, s_root: Path, tmp_path: Path) -> None:
    def plant(run: Path) -> None:
        edit_json(run / "read_log.json", lambda data: data.update({"annotation_file": "questions_dev.jsonl"}))

    assert "other than its own split's" in rules(validate_run(planted(clean_run, tmp_path, plant), root=s_root))


def test_the_test_split_in_the_configuration_is_rejected(clean_run: Path, s_root: Path, tmp_path: Path) -> None:
    def plant(run: Path) -> None:
        edit_json(run / "run_config.json", lambda data: data.update({"split": "test"}))

    assert "not runnable by Track A" in rules(validate_run(planted(clean_run, tmp_path, plant), root=s_root))


def test_a_planted_secret_value_and_a_planted_credential_pattern_are_rejected(
    clean_run: Path, s_root: Path, tmp_path: Path
) -> None:
    def plant_value(run: Path) -> None:
        with (run / "summary.json").open("a", encoding="utf-8") as stream:
            stream.write(f"\n{PLANTED}\n")

    found = rules(validate_run(planted(clean_run, tmp_path, plant_value), root=s_root, secret_values=[PLANTED]))
    assert "exact-env-value" in found
    assert PLANTED not in found, "a finding names the rule and the file, never the matched text"

    def plant_pattern(run: Path) -> None:
        with (run / "summary.json").open("a", encoding="utf-8") as stream:
            stream.write("\ngsk_" + "a" * 30 + "\n")

    other = tmp_path / "second"
    other.mkdir()
    assert "groq-key" in rules(validate_run(planted(clean_run, other, plant_pattern), root=s_root))


def test_a_bundle_over_k_and_a_bundle_over_the_budget_are_rejected(
    clean_run: Path, s_root: Path, tmp_path: Path
) -> None:
    def over_k(run: Path) -> None:
        def change(rows: list[dict[str, object]]) -> list[dict[str, object]]:
            payload = first_ok_payload(rows)
            payload.extend({**payload[0], "rank": len(payload) + i} for i in range(1, K + 2))
            return rows

        edit_ledger(run, change)

    assert "exceeds K or the evidence budget" in rules(validate_run(planted(clean_run, tmp_path, over_k), root=s_root))

    def over_budget(run: Path) -> None:
        def change(rows: list[dict[str, object]]) -> list[dict[str, object]]:
            first_ok_payload(rows)[0]["content"] = "word " * (BUDGET + 5)
            return rows

        edit_ledger(run, change)

    other = tmp_path / "second"
    other.mkdir()
    assert "exceeds K or the evidence budget" in rules(
        validate_run(planted(clean_run, other, over_budget), root=s_root)
    )


def test_ranks_out_of_order_are_rejected(clean_run: Path, s_root: Path, tmp_path: Path) -> None:
    def plant(run: Path) -> None:
        def change(rows: list[dict[str, object]]) -> list[dict[str, object]]:
            first_ok_payload(rows)[0]["rank"] = 7
            return rows

        edit_ledger(run, change)

    assert "ranks are not 1..n" in rules(validate_run(planted(clean_run, tmp_path, plant), root=s_root))


def test_a_ledger_hole_is_rejected(clean_run: Path, s_root: Path, tmp_path: Path) -> None:
    def plant(run: Path) -> None:
        edit_ledger(run, lambda rows: rows[:-1])

    assert "not a complete record of the run" in rules(validate_run(planted(clean_run, tmp_path, plant), root=s_root))


def test_a_run_a_daily_limit_stopped_is_reported_as_paused_not_as_a_hole(
    clean_run: Path, s_root: Path, tmp_path: Path
) -> None:
    def plant(run: Path) -> None:
        def change(rows: list[dict[str, object]]) -> list[dict[str, object]]:
            last = dict(rows[-1])
            last.update(is_final=False, status="NOT_RUN", origin="HARNESS", code="QUOTA_BLOCKED", payload=None)
            last.update(initial_status=None, attempts=None, duration_ms=None)
            return [*rows[:-1], last]

        edit_ledger(run, change)

    reported = rules(validate_run(planted(clean_run, tmp_path, plant), root=s_root))
    assert "the run is paused" in reported and "not a complete record" not in reported


def test_a_record_that_does_not_match_its_manifest_is_rejected(clean_run: Path, s_root: Path, tmp_path: Path) -> None:
    def plant(run: Path) -> None:
        def change(rows: list[dict[str, object]]) -> list[dict[str, object]]:
            rows[0]["manifest_sha256"] = "9" * 64
            return rows

        edit_ledger(run, change)

    assert "does not match its arm's manifest" in rules(validate_run(planted(clean_run, tmp_path, plant), root=s_root))


def test_a_missing_or_altered_manifest_is_rejected(clean_run: Path, s_root: Path, tmp_path: Path) -> None:
    def remove(run: Path) -> None:
        (run / "manifest-R0.json").unlink()

    assert "manifest is missing or does not verify" in rules(
        validate_run(planted(clean_run, tmp_path, remove), root=s_root)
    )

    def alter(run: Path) -> None:
        path = run / "manifest-R0.json"
        path.write_text(path.read_text(encoding="utf-8").replace('"k": 10', '"k": 99'), encoding="utf-8")

    other = tmp_path / "second"
    other.mkdir()
    assert "manifest is missing or does not verify" in rules(
        validate_run(planted(clean_run, other, alter), root=s_root)
    )


def test_a_changed_k_in_the_configuration_is_rejected(clean_run: Path, s_root: Path, tmp_path: Path) -> None:
    def plant(run: Path) -> None:
        edit_json(run / "run_config.json", lambda data: data.update({"k": 5}))

    assert "the manifest's k differs from the run configuration" in rules(
        validate_run(planted(clean_run, tmp_path, plant), root=s_root)
    )


def test_a_run_state_without_a_reason_is_rejected(clean_run: Path, s_root: Path, tmp_path: Path) -> None:
    def plant(run: Path) -> None:
        def change(rows: list[dict[str, object]]) -> list[dict[str, object]]:
            for row in rows:
                if row["is_final"]:
                    row.update({"status": "NOT_RUN", "code": None, "payload": None, "duration_ms": None})
                    break
            return rows

        edit_ledger(run, change)

    assert "a run state without a reason code" in rules(validate_run(planted(clean_run, tmp_path, plant), root=s_root))


def test_a_published_corpus_that_changed_since_the_run_is_rejected(
    clean_run: Path, s_root: Path, tmp_path: Path
) -> None:
    def plant(run: Path) -> None:
        edit_json(run / "read_log.json", lambda data: data.update({"published_manifest_sha256": "1" * 64}))

    assert "the published corpus changed" in rules(validate_run(planted(clean_run, tmp_path, plant), root=s_root))


def test_missing_required_files_are_reported_by_name(clean_run: Path, s_root: Path, tmp_path: Path) -> None:
    def plant(run: Path) -> None:
        (run / "summary.json").unlink()
        (run / "read_log.json").unlink()

    found = rules(validate_run(planted(clean_run, tmp_path, plant), root=s_root))
    assert "summary.json: required file is missing" in found and "read_log.json: required file is missing" in found


def test_the_manifests_digest_of_the_gold_file_is_the_one_gold_named_key_a_run_may_hold(
    clean_run: Path, s_root: Path, tmp_path: Path
) -> None:
    assert "gold_manifest_sha256" in (clean_run / "manifest-R0.json").read_text(encoding="utf-8")
    assert validate_run(clean_run, root=s_root) == []

    def plant(run: Path) -> None:
        path = run / "manifest-R0.json"
        path.write_text(
            path.read_text(encoding="utf-8").replace('"seed"', '"expected_outcome": 1, "seed"'), encoding="utf-8"
        )

    assert "a JSON key names gold" in rules(validate_run(planted(clean_run, tmp_path, plant), root=s_root))


def test_gold_text_is_also_looked_for_as_it_reads_inside_a_json_file(s_questions: tuple[GoldRecord, ...]) -> None:
    from dataclasses import replace

    awkward = 'He said "refunds" within 72 hours - café rule'
    record = replace(s_questions[0], required_claims=(awkward,))
    texts = gold_texts([record])
    assert awkward in texts and json.dumps(awkward)[1:-1] in texts
    assert json.dumps({"content": awkward}).count(json.dumps(awkward)[1:-1]) == 1
