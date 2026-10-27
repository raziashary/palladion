"""The comparison report: provenance, run states beside scores, cost beside quality, no winner (B08-T06.01)."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from test_runner import settings as runner_settings
from test_runner import write_manifest
from test_tables import STATS, binary_pairs

from benchmark.analysis.reports import (
    LIMITS,
    ArmCost,
    ComparisonInputs,
    Provenance,
    ReportError,
    TrackARun,
    TrackBRun,
    arm_costs,
    figures,
    findings,
    load_track_c,
    main,
    render,
    write_report,
)
from benchmark.analysis.tables import build_scorecard
from benchmark.contracts import RunStatus
from benchmark.eval.score_run import RunScore
from benchmark.runner import LedgerRecord

COMMIT = "d" * 40
METRICS = (
    "complete_set_at_k", "valid_source_recall", "mrr",
    "forbidden_source_exposure", "authority_confusion", "wrong_vintage_intrusion",
)  # fmt: skip


def provenance(label: str = "Track A C2", commit: str | None = COMMIT) -> Provenance:
    return Provenance(label, "run-dir", "run-0001", commit, "a" * 64)


def ledger_row(arm: str, index: int, millis: float) -> LedgerRecord:
    return LedgerRecord(
        "run-0001", "m" * 64, arm, f"q-{index:08x}", 1, True, RunStatus.OK, None, None, "2026-10-27T10:00:00Z",
        millis, RunStatus.OK, 1, [], (),
    )  # fmt: skip


def track_a(commit: str | None = COMMIT) -> TrackARun:
    """Three arms on 20 questions: R7a beats R3 on the metric but is slower; R0 is both worse and slower than R3."""
    pairs = binary_pairs("R3", set(range(4)), 20) + binary_pairs("R7a", set(range(10)), 20)
    pairs += binary_pairs("R0", {0, 1}, 20)
    rows = [ledger_row("R3", i, 10.0) for i in range(20)]
    rows += [ledger_row("R7a", i, 30.0) for i in range(20)] + [ledger_row("R0", i, 50.0) for i in range(20)]
    score = RunScore("run-0001", 10, "0" * 64, tuple(sorted(pairs, key=lambda p: (p.arm, p.question_id))), tuple(rows))
    card = build_scorecard(score, metrics=METRICS, stats=STATS, reference="R3", primary="R7a")
    builds: list[Mapping[str, Any]] = [
        {"arm": "R3", "status": "BUILT", "seconds": 1.5},
        {"arm": "R7a", "status": "BUILT"},
    ]
    return TrackARun("C2", provenance(commit=commit), score, card, builds, "R3", "R7a")


def inputs(**over: Any) -> ComparisonInputs:
    base: dict[str, Any] = {
        "track_a": [track_a()], "track_b": None, "track_c": [], "graph": [], "matched_digests": {"A": "b" * 64}
    }  # fmt: skip
    return ComparisonInputs(**{**base, **over})


# --------------------------------------------------------------------------- what the report says it is


def test_the_report_says_what_it_is_lists_its_runs_and_every_limit() -> None:
    text = render(inputs())
    assert "Status: exploratory. Not sealed. No composite score, no ranking" in text
    assert f"`{COMMIT}`" in text and "A `bbbbbbbbbbbb`" in text
    assert "| Track A C2 | run-dir | run-0001 | dddddddddddd | aaaaaaaaaaaa |" in text
    for limit in LIMITS:
        assert limit in text
    assert "single run" in text and "capability" in text


def test_a_harm_is_shown_as_bounds_and_an_unmeasured_cell_says_so() -> None:
    text = render(inputs())
    assert "NOT_OBSERVABLE (the load happens inside Palladion; no time was recorded)" in text
    assert "| R3 | 20 |" in text and "1.5 s" in text
    assert "Harm over every eligible pair" in text


def test_latency_comes_from_the_ledger_of_each_arm() -> None:
    text = render(inputs())
    assert "p50 10 ms" in text and "p50 30 ms" in text and "p50 50 ms" in text


def test_no_system_is_called_the_winner_and_no_composite_appears() -> None:
    text = render(inputs()).lower()
    for word in ("winner", "best system", "overall score", "composite score:"):
        assert word not in text.replace("no composite score", "")


# --------------------------------------------------------------------------- pooling, findings and figures


def test_runs_at_two_palladion_commits_may_not_share_a_report() -> None:
    other = TrackARun(**{**track_a().__dict__, "provenance": provenance("Track A C1", "e" * 40)})
    with pytest.raises(ReportError, match="2 different Palladion commits"):
        render(inputs(track_a=[track_a(), other]))


def test_primary_pairings_are_sorted_into_adverse_favourable_and_inconclusive_from_their_intervals() -> None:
    text = "\n".join(findings(inputs()))
    assert "- Adverse to the system under test: none" in text
    assert "- Inconclusive (the interval includes zero): none" in text
    favourable = text.split("- Favourable to it:")[1]
    assert "R7a against R3 on complete_set_at_k: 0.300 [0.150, 0.450]" in favourable


def test_an_adverse_primary_interval_is_listed_as_adverse_not_hidden() -> None:
    pairs = binary_pairs("R3", set(range(15)), 20) + binary_pairs("R7a", set(), 20)
    score = RunScore("run-0001", 10, "0" * 64, tuple(pairs), ())
    card = build_scorecard(score, metrics=METRICS, stats=STATS, reference="R3", primary="R7a")
    run = TrackARun("C2", provenance(), score, card, [], "R3", "R7a")
    adverse = "\n".join(findings(inputs(track_a=[run]))).split("Favourable to it:")[0]
    assert "R7a against R3 on complete_set_at_k" in adverse


def test_a_dominated_system_is_marked_in_the_figure_and_the_others_are_not() -> None:
    svg = figures(inputs())["track_a_C2_quality_latency.svg"]
    root = ET.fromstring(svg)
    labels = [t.text for t in root.iter("{http://www.w3.org/2000/svg}text")]
    assert "R0 (dominated)" in labels, "R0 is slower and finds less than R3"
    assert "R3" in labels and "R7a" in labels, "R7a finds more but is slower, so nothing beats it"
    assert "track_a_C2_by_stratum.svg" in figures(inputs())


def test_the_report_and_its_figures_are_written_together(tmp_path: Path) -> None:
    path = write_report(tmp_path, inputs())
    assert path.read_text(encoding="utf-8").startswith("# Palladion beside the other systems")
    names = sorted(p.name for p in (tmp_path / "figures").iterdir())
    assert "track_a_C2_quality_latency.svg" in names
    assert "![track_a_C2_quality_latency.svg](figures/track_a_C2_quality_latency.svg)" in path.read_text(
        encoding="utf-8"
    )


def test_nothing_is_written_when_the_report_cannot_be_assembled(tmp_path: Path) -> None:
    other = TrackARun(**{**track_a().__dict__, "provenance": provenance("Track A C1", "e" * 40)})
    with pytest.raises(ReportError):
        write_report(tmp_path / "out", inputs(track_a=[track_a(), other]))
    assert not (tmp_path / "out").exists()


# --------------------------------------------------------------------------- reading the books


def test_cost_per_arm_sums_the_generators_records_and_leaves_an_unknown_unknown(tmp_path: Path) -> None:
    rows = [
        {"arm_id": "R3", "status": "OK", "prompt_tokens": 100, "completion_tokens": 10, "latency_ms": 900.0},
        {"arm_id": "R3", "status": "OK", "prompt_tokens": 200, "completion_tokens": 20, "latency_ms": 1100.0},
        {"arm_id": "R3", "status": "RATE_LIMITED", "prompt_tokens": None, "completion_tokens": None, "latency_ms": 5.0},
        {"arm_id": "R0", "status": "ERROR", "prompt_tokens": None, "completion_tokens": None, "latency_ms": None},
    ]
    path = tmp_path / "generation_records.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    costs = arm_costs(path)
    assert costs["R3"] == ArmCost(3, 300, 30, 1000.0) and costs["R3"].tokens == 330
    assert costs["R0"] == ArmCost(1, 0, 0, None), "no answered call, so no latency"
    assert arm_costs(tmp_path / "missing.jsonl") == {}


def test_a_track_c_run_counts_its_turns_per_system_and_a_stopped_turn_apart(tmp_path: Path) -> None:
    write_manifest(tmp_path / "manifest.json", "track-c", runner_settings(), run_id="run-0001")
    (tmp_path / "summary.json").write_text(
        json.dumps({"spend": {"E0": {"calls": 3}, "E1": {"calls": 9}}}), encoding="utf-8"
    )

    def row(arm: str, status: str, code: str | None) -> str:
        return json.dumps({"arm": arm, "status": status, "code": code})

    rows = [
        row("E0|none.cold.matched", "OK", None),
        row("E0|none.cold.matched", "OK", None),
        row("E1|none.cold.matched", "OK", None),
        row("E1|none.cold.matched", "NOT_RUN", "QUOTA_BLOCKED"),
        row("E1|none.cold.matched", "NOT_RUN", "ARM_UNAVAILABLE"),
        row("E1|mutation|M01", "NOT_RUN", "QUOTA_BLOCKED"),
    ]
    (tmp_path / "ledger.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")
    run = load_track_c(tmp_path)
    assert run.turn_states == {"E0": {"OK": 2}, "E1": {"OK": 1, "QUOTA_BLOCKED": 1, "NOT_RUN": 1}}
    assert run.case_states == {"E1": {"QUOTA_BLOCKED": 1}}
    text = render(inputs(track_c=[run]))
    assert "| E1 | NOT_RUN=1, OK=1, QUOTA_BLOCKED=1 | QUOTA_BLOCKED=1 | 9 |" in text
    assert "| E0 | OK=2 | NOT_RUN | 3 |" in text, "an arm with no mutation case recorded shows NOT_RUN, not a zero"


def test_a_track_b_cost_table_marks_an_arm_with_no_records_as_not_observable() -> None:
    b = TrackBRun(provenance("Track B C2"), None, [], [], {}, 0)  # type: ignore[arg-type]
    assert b.costs == {} and b.planned_pairs == 0


def test_the_command_line_refuses_a_missing_run_and_says_why(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["--root", str(tmp_path), "--out", str(tmp_path / "out"), "--track-b", str(tmp_path / "nowhere")])
    assert code == 2 and "refused" in capsys.readouterr().err and not (tmp_path / "out").exists()
