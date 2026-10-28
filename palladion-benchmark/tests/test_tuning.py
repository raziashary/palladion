"""The tuning budget and the choice of a setting (B08-T02.01, BADR-0047)."""

from __future__ import annotations

from pathlib import Path

import pytest

from benchmark.track_a import ArmSettings
from benchmark.tuning import BASELINE, MAX_TRIALS, METRIC, Trial, TuningError, TuningLog, choose, one_lever

WORLDS = ("D11", "D12")
LEVERS = ArmSettings().to_dict()


def trial(name: str, score: float, arm: str = "R0", worlds: tuple[str, ...] = WORLDS) -> Trial:
    return Trial(arm, name, LEVERS, worlds, 200, {METRIC: score})


# -- one lever at a time ---------------------------------------------------------------------------------------------


def test_a_trial_changes_exactly_one_lever_and_keeps_the_others() -> None:
    changed = one_lever(LEVERS, "k1", 1.5)
    assert changed["k1"] == 1.5 and {k: v for k, v in changed.items() if k != "k1"} == {
        k: v for k, v in LEVERS.items() if k != "k1"
    }


def test_an_integer_may_stand_for_a_float_lever_but_not_the_other_way_round() -> None:
    assert one_lever(LEVERS, "k1", 2)["k1"] == 2
    with pytest.raises(TuningError, match="takes a int"):
        one_lever(LEVERS, "chunk_words", 100.5)


def test_an_unknown_lever_and_the_baseline_value_are_refused() -> None:
    with pytest.raises(TuningError, match="not a lever"):
        one_lever(LEVERS, "temperature", 0.5)
    with pytest.raises(TuningError, match="baseline, not a trial"):
        one_lever(LEVERS, "k1", LEVERS["k1"])


def test_the_levers_are_those_of_the_settings_object() -> None:
    assert set(LEVERS) == {"k1", "b", "chunk_words", "rrf_k", "fusion_depth", "rerank_depth"}


# -- the log and its budget --------------------------------------------------------------------------------------------


def test_trials_read_back_as_they_were_written(tmp_path: Path) -> None:
    log = TuningLog(tmp_path / "log.jsonl")
    assert log.read() == []
    log.append(trial(BASELINE, 0.2))
    log.append(trial("k1=1.5", 0.25))
    assert [t.name for t in log.read()] == [BASELINE, "k1=1.5"] and log.read()[1].scores[METRIC] == 0.25


def test_the_budget_is_six_trials_per_arm_and_the_baseline_is_free(tmp_path: Path) -> None:
    log = TuningLog(tmp_path / "log.jsonl")
    log.append(trial(BASELINE, 0.2))
    for i in range(MAX_TRIALS):
        log.append(trial(f"k1={1 + i / 10}", 0.2))
    assert log.spent("R0") == MAX_TRIALS == 6
    with pytest.raises(TuningError, match="used its 6 trials"):
        log.append(trial("b=0.9", 0.3))
    log.append(trial(BASELINE, 0.2, arm="R0x"))
    log.append(trial("b=0.9", 0.3, arm="R0x"))  # another arm has its own budget
    assert log.spent("R0x") == 1


def test_a_baseline_on_other_worlds_is_still_allowed_after_the_budget_is_used(tmp_path: Path) -> None:
    log = TuningLog(tmp_path / "log.jsonl")
    for i in range(MAX_TRIALS):
        log.append(trial(f"k1={1 + i / 10}", 0.2))
    log.append(trial(BASELINE, 0.2, worlds=("D11",)))
    assert log.spent("R0") == MAX_TRIALS


def test_the_same_trial_on_the_same_worlds_is_not_logged_twice(tmp_path: Path) -> None:
    log = TuningLog(tmp_path / "log.jsonl")
    log.append(trial("k1=1.5", 0.2))
    with pytest.raises(TuningError, match="already in the log"):
        log.append(trial("k1=1.5", 0.9))
    log.append(trial("k1=1.5", 0.9, worlds=("D11",)))


def test_a_trial_without_the_primary_metric_and_a_corrupt_log_are_refused(tmp_path: Path) -> None:
    log = TuningLog(tmp_path / "log.jsonl")
    with pytest.raises(TuningError, match=METRIC):
        log.append(Trial("R0", BASELINE, LEVERS, WORLDS, 10, {"mrr": 0.1}))
    (tmp_path / "log.jsonl").write_text("not json\n", encoding="utf-8")
    with pytest.raises(TuningError, match="not a tuning log"):
        log.read()


# -- the choice --------------------------------------------------------------------------------------------------------


def test_the_best_trial_wins_only_when_it_beats_the_baseline_by_the_margin() -> None:
    trials = [trial(BASELINE, 0.20), trial("k1=1.5", 0.215), trial("b=0.9", 0.24)]
    assert choose(trials, "R0", min_gain=0.02).name == "b=0.9"
    assert choose(trials, "R0", min_gain=0.05).name == BASELINE, "a gain under the margin keeps the defaults"
    assert choose(trials, "R0", min_gain=0.04).name == "b=0.9", "the margin is inclusive"


def test_a_tie_between_trials_goes_to_the_earlier_one_and_a_loss_to_the_baseline() -> None:
    tied = [trial(BASELINE, 0.2), trial("k1=1.5", 0.3), trial("b=0.9", 0.3)]
    assert choose(tied, "R0", min_gain=0.0).name == "k1=1.5"
    assert choose([trial(BASELINE, 0.2), trial("k1=1.5", 0.1)], "R0", min_gain=0.0).name == BASELINE
    assert choose([trial(BASELINE, 0.2), trial("k1=1.5", 0.2)], "R0", min_gain=0.0).name == BASELINE


def test_the_choice_looks_at_one_arm_and_needs_one_baseline_on_the_same_worlds() -> None:
    trials = [trial(BASELINE, 0.2), trial("k1=1.5", 0.9, arm="R0x"), trial(BASELINE, 0.1, arm="R0x")]
    assert choose(trials, "R0", min_gain=0.0).name == BASELINE
    with pytest.raises(TuningError, match="exactly one baseline"):
        choose([trial("k1=1.5", 0.3)], "R0", min_gain=0.0)
    with pytest.raises(TuningError, match="other worlds"):
        choose([trial(BASELINE, 0.2), trial("k1=1.5", 0.3, worlds=("D11",))], "R0", min_gain=0.0)
    with pytest.raises(TuningError, match="zero or more"):
        choose([trial(BASELINE, 0.2)], "R0", min_gain=-0.1)
