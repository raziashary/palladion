"""Family-grouped partitions and the language profile (B02-T04.02)."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

import pytest

from benchmark.fixtures.documents import Document
from benchmark.fixtures.entities import rng_for
from benchmark.fixtures.manifest import Split
from benchmark.fixtures.question_gen import build_questions
from benchmark.fixtures.questions import (
    GoldError,
    GoldRecord,
    Stratum,
    check_partition,
    language_labels,
    split_for_family,
)
from benchmark.fixtures.world import World

SMOKE_ONLY = {Split.SMOKE: 10}
M_WEIGHTS = {Split.SMOKE: 10, Split.DEV: 30, Split.TEST: 60}


def families(count: int) -> list[str]:
    return [f"POL-{n:04d}" for n in range(count)]


# --------------------------------------------------------------------------- the split function


def test_a_family_always_lands_in_the_same_split() -> None:
    first = [split_for_family(7, "M", f, M_WEIGHTS) for f in families(200)]
    assert first == [split_for_family(7, "M", f, M_WEIGHTS) for f in families(200)]


def test_splits_follow_the_weights() -> None:
    counts = Counter(split_for_family(7, "M", f, M_WEIGHTS) for f in families(6000))
    for split, weight in M_WEIGHTS.items():
        assert abs(counts[split] / 6000 - weight / 100) < 0.03, split


def test_a_single_weight_sends_everything_to_that_split() -> None:
    assert {split_for_family(7, "S", f, SMOKE_ONLY) for f in families(100)} == {Split.SMOKE}


def test_tiers_and_seeds_assign_families_independently() -> None:
    by_tier = [split_for_family(7, "S", f, M_WEIGHTS) != split_for_family(7, "M", f, M_WEIGHTS) for f in families(300)]
    by_seed = [split_for_family(7, "M", f, M_WEIGHTS) != split_for_family(8, "M", f, M_WEIGHTS) for f in families(300)]
    assert sum(by_tier) > 100 and sum(by_seed) > 100  # not prefix-stable across tiers or seeds


# --------------------------------------------------------------------------- the partition check


def test_the_generated_pilot_passes_the_partition_check(s_questions: tuple[GoldRecord, ...]) -> None:
    check_partition(s_questions, SMOKE_ONLY)
    assert all(r.split is Split.SMOKE for r in s_questions)  # nothing in the pilot is a test question


def test_a_family_shared_across_strata_stays_in_one_split(s_questions: tuple[GoldRecord, ...]) -> None:
    strata_by_family: dict[str, set[Stratum]] = {}
    for r in s_questions:
        strata_by_family.setdefault(r.scenario_family, set()).add(r.stratum)
    assert any(len(strata) > 1 for strata in strata_by_family.values())  # the policy worlds overlap across strata
    check_partition(s_questions, SMOKE_ONLY)


def test_a_planted_cross_split_family_is_rejected(s_questions: tuple[GoldRecord, ...]) -> None:
    twin = replace(s_questions[1], scenario_family=s_questions[0].scenario_family, split=Split.TEST)
    planted = [s_questions[0], twin, *s_questions[2:]]
    with pytest.raises(GoldError, match="spans two splits"):
        check_partition(planted, {Split.SMOKE: 10, Split.TEST: 1})


def test_a_planted_cross_stratum_family_in_two_splits_is_rejected(s_questions: tuple[GoldRecord, ...]) -> None:
    other = next(r for r in s_questions if r.stratum is not s_questions[0].stratum)
    shifted = replace(other, scenario_family=s_questions[0].scenario_family, split=Split.DEV)
    with pytest.raises(GoldError, match="spans two splits"):
        check_partition([s_questions[0], shifted], {Split.SMOKE: 1, Split.DEV: 1})


def test_wrong_counts_and_stray_splits_are_rejected(s_questions: tuple[GoldRecord, ...]) -> None:
    with pytest.raises(GoldError, match="has 9 questions in smoke, expected 10"):
        check_partition(s_questions[1:], SMOKE_ONLY)
    stray = [*s_questions, replace(s_questions[0], scenario_family="POL-UNIQUE", split=Split.TEST)]
    with pytest.raises(GoldError, match="outside the targets"):
        check_partition(stray, SMOKE_ONLY)


def test_a_pilot_that_needs_more_splits_than_the_world_has_families_for_is_refused(
    s_world: World, s_corpus: tuple[Document, ...], s_snapshot: str
) -> None:
    with pytest.raises(GoldError, match=r"scenario family|cannot reach"):
        build_questions(s_world, s_corpus, s_snapshot, 7, "S", {Split.SMOKE: 1, Split.DEV: 1, Split.TEST: 1})


# --------------------------------------------------------------------------- language profile


@pytest.mark.parametrize("total", [100, 1000, 7, 1, 0])
def test_language_labels_sum_to_the_total_and_follow_the_profile(total: int) -> None:
    labels = language_labels(total, rng_for(7, "labels"))
    assert len(labels) == total
    counts = Counter(labels)
    for lang, share in (("en", 0.55), ("id", 0.30), ("mixed", 0.15)):
        assert abs(counts[lang] - total * share) < 1  # largest remainder keeps every share within one question


def test_the_hundred_question_profile_is_exact() -> None:
    assert Counter(language_labels(100, rng_for(7, "labels"))) == {"en": 55, "id": 30, "mixed": 15}


def test_language_labels_are_shuffled_but_reproducible() -> None:
    a, b = language_labels(100, rng_for(7, "labels")), language_labels(100, rng_for(7, "labels"))
    assert a == b and a != sorted(a)
    assert language_labels(100, rng_for(8, "labels")) != a
