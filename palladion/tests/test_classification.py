"""Frozen synthetic lexical controls, including near misses and profile provenance."""

import json
from pathlib import Path

import pytest

from evidence_agent.core.evaluation import score_categories
from evidence_agent.memory.classification import deterministic, deterministic_profile

CONTROLS = json.loads((Path(__file__).parents[1] / "data/demo/p10_classification_controls.json")
                      .read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("text,expected", CONTROLS)
def test_frozen_lexical_controls(text, expected):
    result = deterministic(text, field_name="query")
    assert result.category == expected
    if expected == "EPISODIC" and result.rule_id != "AMBIGUOUS_PERSONAL_PREFERENCE":
        assert not result.semantic_eligible


def test_category_measurement_preserves_false_positives_and_negatives():
    measured = score_categories(["SEMANTIC", "EPISODIC", "PROCEDURAL"],
                                ["EPISODIC", "SEMANTIC", "PROCEDURAL"])
    assert measured["SEMANTIC"] == {"tp": 0, "fp": 1, "fn": 1, "precision": 0, "recall": 0}
    assert measured["PROCEDURAL"]["recall"] == 1
    with pytest.raises(ValueError):
        score_categories(["SEMANTIC"], [])


def test_profile_contains_executable_rules_and_weights():
    profile = deterministic_profile()
    assert profile["version"] == "lexical-2"
    assert profile["scores_are_probabilities"] is False
    assert profile["patterns"] and profile["weights"]
    profile["weights"]["explicit"] = 0
    assert deterministic_profile()["weights"]["explicit"] == 0.7


@pytest.mark.parametrize("text", ["English", "Indonesian",
    "I prefer short passwords.", "I prefer concise answers; my API keys are private.",
    "I like brief credential summaries with secrets."])
def test_additional_ambiguous_and_plural_privacy_near_misses(text):
    result = deterministic(text, field_name="query")
    assert result.category == "EPISODIC" and not result.semantic_eligible
