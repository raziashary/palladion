"""R7b is unsupported at the pinned Palladion commit; R4 to R6 declare what they cannot do (B06-T04.01)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from benchmark.adapters.common import Condition, PublishedView
from benchmark.config import load_comparators_config
from benchmark.contracts import CapabilityUnsupported, RunStatus, classify_exception
from benchmark.registry import R7B_REASON, Capability, Support, default_registry
from benchmark.runner import RunLedger
from benchmark.track_a import RunSpec, UnavailableArm, build_local_arms, execute

ROOT = Path(__file__).resolve().parents[1]


def test_r7b_is_a_feature_not_supported_with_the_reason_and_the_fix_named() -> None:
    spec = default_registry().get("R7b")
    assert spec.forced_status is RunStatus.FEATURE_NOT_SUPPORTED and spec.forced_reason == R7B_REASON
    assert "PF07" in R7B_REASON and "BR34" in R7B_REASON
    with pytest.raises(CapabilityUnsupported) as caught:
        default_registry().require_runnable("R7b")
    assert classify_exception(caught.value)[0] is RunStatus.FEATURE_NOT_SUPPORTED


def test_the_registry_and_the_comparator_file_agree_about_r7b() -> None:
    registry = default_registry()
    config = load_comparators_config(ROOT / "configs" / "comparators.yaml")
    registry.check_against_config(config)
    eligibility = next(a for a in config.arms if a.arm_id == "R7b").eligibility
    assert "FEATURE_NOT_SUPPORTED" in eligibility and "PF07" in eligibility


@pytest.mark.parametrize("arm", ["R4", "R5", "R6"])
def test_the_comparators_declare_what_their_outputs_cannot_support(arm: str) -> None:
    spec = default_registry().get(arm)
    assert spec.forced_status is None, "they are built, not forced off"
    caps = spec.capabilities
    assert caps[Capability.ACL_FILTER].support is Support.UNSUPPORTED and "BR35" in caps[Capability.ACL_FILTER].source
    assert caps[Capability.TEMPORAL_FILTER].support is Support.UNSUPPORTED
    assert caps[Capability.NATIVE_CITATION].support is Support.UNSUPPORTED
    assert caps[Capability.OFFLINE_COST].support is Support.SUPPORTED
    assert caps[Capability.GRAPH].support is Support.SUPPORTED


def test_the_matrix_prints_a_word_for_every_graph_arm_cell() -> None:
    matrix = default_registry().render_matrix(["R4", "R5", "R6", "R7b"])
    rows = [line for line in matrix.splitlines()[2:]]
    assert len(rows) == 4 and all("  " not in row.replace("| ", "|") and "||" not in row for row in rows)
    assert rows[-1].rstrip().endswith("FEATURE_NOT_SUPPORTED |")


def test_a_run_that_names_r7b_records_unsupported_for_every_pair_and_scores_no_zero(
    s_root: Path, tmp_path: Path
) -> None:
    view = PublishedView.load(s_root / "published")
    arms, builds = build_local_arms(view, ["R0"], condition=Condition.C2, index_dir=tmp_path / "index")
    adapters = {**arms, "R7b": UnavailableArm("R7b", R7B_REASON)}
    out = tmp_path / "run"
    execute(RunSpec("run-r7b-0001", "smoke", Condition.C2, 10, 4000, s_root, out), adapters, builds=builds)
    finals = [r for r in RunLedger(out / "ledger.jsonl").records if r.is_final]
    r7b = [r for r in finals if r.arm == "R7b"]
    assert r7b and {(r.status, r.code) for r in r7b} == {(RunStatus.FEATURE_NOT_SUPPORTED, "CAPABILITY_UNSUPPORTED")}
    assert all(r.payload is None for r in r7b), "no candidates, so nothing a metric could turn into a zero"
    none = tmp_path / "none.json"
    none.write_text(json.dumps({"questions": {}}), encoding="utf-8")
    scored = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "score_track_a.py"), "--run-dir", str(out), "--root", str(s_root),
         "--k", "10", "--withdrawn", str(none)],
        capture_output=True, text=True, check=False, timeout=900,
    )  # fmt: skip
    assert scored.returncode == 0, scored.stderr
    pairs = json.loads((out / "scores.json").read_text(encoding="utf-8"))["pairs"]
    mine = [p for p in pairs if p["arm"] == "R7b"]
    assert mine and all(p["status"] == "FEATURE_NOT_SUPPORTED" and p["metrics"] == {} for p in mine)
    card = (out / "scorecard.md").read_text(encoding="utf-8")
    assert "FEATURE_NOT_SUPPORTED" in card
