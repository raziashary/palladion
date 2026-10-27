"""Configuration loaders: strict schemas, no floating pins, deterministic loading."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from benchmark.config import (
    ConfigError,
    Pin,
    config_digest,
    load_all,
    load_benchmark_config,
    load_comparators_config,
    read_yaml,
)
from benchmark.contracts import Track

CONFIGS = Path(__file__).resolve().parents[1] / "configs"
COMMIT = "0123456789abcdef0123456789abcdef01234567"


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    target = tmp_path / "configs"
    shutil.copytree(CONFIGS, target)
    return target


def edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"anchor not found: {old!r}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def test_real_configs_load_and_have_the_documented_shape() -> None:
    bundle = load_all(CONFIGS)
    assert bundle.benchmark.k_values == (5, 10, 20)
    assert bundle.benchmark.token_budgets == (4000, 8000)
    assert (bundle.benchmark.splits.smoke, bundle.benchmark.splits.dev, bundle.benchmark.splits.test) == (10, 30, 60)
    assert bundle.benchmark.main_max_calls == 5 and bundle.benchmark.critic_max_calls == 3
    assert [a.arm_id for a in bundle.comparators.arms][:3] == ["R0", "R1", "R2"]
    assert len(bundle.comparators.arms) == 15
    assert bundle.evaluation.sealed is False
    assert bundle.benchmark.generator.models[0] == "qwen/qwen3.8-27b"
    assert bundle.benchmark.generator.allow_automatic_failover is False
    assert Track.NATIVE_END_TO_END in next(a for a in bundle.comparators.arms if a.arm_id == "E3").tracks


def test_the_same_files_load_to_identical_objects_and_digests() -> None:
    first, second = load_all(CONFIGS), load_all(CONFIGS)
    assert first == second
    assert config_digest(first) == config_digest(second)


def test_digest_changes_when_a_value_changes(config_dir: Path) -> None:
    before = config_digest(load_all(config_dir))
    edit(config_dir / "benchmark.yaml", "default: 7", "default: 8")
    assert config_digest(load_all(config_dir)) != before


def test_unknown_key_is_rejected(config_dir: Path) -> None:
    edit(config_dir / "benchmark.yaml", "seeds:\n  default: 7", "seeds:\n  default: 7\n  gold_seed: 1")
    with pytest.raises(ConfigError, match="unknown key"):
        load_benchmark_config(config_dir / "benchmark.yaml")


def test_missing_required_key_is_rejected(config_dir: Path) -> None:
    edit(config_dir / "benchmark.yaml", "seeds:\n  default: 7\n", "seeds: {}\n")
    with pytest.raises(ConfigError, match="required"):
        load_benchmark_config(config_dir / "benchmark.yaml")


def test_duplicate_yaml_key_is_rejected(config_dir: Path) -> None:
    edit(config_dir / "benchmark.yaml", "seeds:\n  default: 7", "seeds:\n  default: 7\n  default: 9")
    with pytest.raises(ConfigError, match="duplicate YAML key"):
        read_yaml(config_dir / "benchmark.yaml")


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("default: 7", "default: true"),
        ("default: 7", "default: 7.5"),
        ("k_values: [5, 10, 20]", "k_values: [5, 5]"),
        ("main_max_calls: 5", "main_max_calls: 6"),
        ("critic_max_calls: 3", "critic_max_calls: 4"),
        ("max_attempts: 2", "max_attempts: 4"),
        ("temperature: 0.0", "temperature: .nan"),
        ('schema_version: "1.0"', 'schema_version: "2.0"'),
    ],
)
def test_out_of_range_or_mistyped_values_are_rejected(config_dir: Path, old: str, new: str) -> None:
    edit(config_dir / "benchmark.yaml", old, new)
    with pytest.raises(ConfigError):
        load_benchmark_config(config_dir / "benchmark.yaml")


def test_split_sizes_must_add_up_to_the_m_tier(config_dir: Path) -> None:
    edit(config_dir / "benchmark.yaml", "test_per_stratum: 60", "test_per_stratum: 61")
    with pytest.raises(ConfigError, match="M-tier"):
        load_benchmark_config(config_dir / "benchmark.yaml")


def test_unapproved_or_misordered_models_are_rejected(config_dir: Path) -> None:
    edit(
        config_dir / "benchmark.yaml", '    - "openai/gpt-oss-20b"\n  temperature', '    - "other/model"\n  temperature'
    )
    with pytest.raises(ConfigError, match="approved"):
        load_benchmark_config(config_dir / "benchmark.yaml")


def test_cross_file_composition_must_match_the_m_tier(config_dir: Path) -> None:
    edit(config_dir / "fixtures.yaml", "sop_versions: 2600", "sop_versions: 2601")
    with pytest.raises(ConfigError, match="m_tier_composition"):
        load_all(config_dir)


def test_language_profile_must_sum_to_one_hundred(config_dir: Path) -> None:
    edit(config_dir / "fixtures.yaml", "mixed: 15", "mixed: 16")
    with pytest.raises(ConfigError, match="sum to 100"):
        load_all(config_dir)


# ----------------------------------------------------------------------------- pins


def test_unpinned_entries_load_in_exploratory_mode_and_fail_in_confirmatory_mode() -> None:
    config = load_comparators_config(CONFIGS / "comparators.yaml")
    assert config.system_under_test.is_pinned is True, (
        "Palladion is pinned to the commit the isolated runtime checks out"
    )
    assert next(a for a in config.arms if a.arm_id == "R7").pin.is_pinned is False
    assert all(next(a for a in config.arms if a.arm_id == r).pin.is_pinned for r in ("R4", "R5", "R6"))
    with pytest.raises(ConfigError, match="confirmatory mode refuses unpinned"):
        load_comparators_config(CONFIGS / "comparators.yaml", confirmatory=True)


@pytest.mark.parametrize(
    ("kind", "value"),
    [
        ("version", "latest"),
        ("version", "LATEST"),
        ("commit", "main"),
        ("commit", "HEAD"),
        ("commit", "v1"),
        ("commit", COMMIT[:39]),
        ("commit", COMMIT.upper()),
        ("version", ">=1.0"),
        ("version", "^1.2"),
        ("version", "1.*"),
        ("version", "1"),
        ("model", "latest"),
        ("model", "stable"),
        ("image_tag", "qdrant/qdrant:latest"),
        ("image_tag", "qdrant/qdrant"),
        ("unpinned", "main"),
        ("bogus", "1.0"),
    ],
)
def test_floating_or_malformed_pins_are_rejected(kind: str, value: str) -> None:
    with pytest.raises(ConfigError):
        Pin(kind, value)


@pytest.mark.parametrize(
    ("kind", "value"),
    [
        ("commit", COMMIT),
        ("version", "0.28.1"),
        ("version", "3.10.1"),
        ("model", "qwen/qwen3.8-27b"),
        ("image_tag", "qdrant/qdrant:v1.19.2"),
        ("unpinned", "UNPINNED"),
    ],
)
def test_exact_pins_are_accepted(kind: str, value: str) -> None:
    assert Pin(kind, value).value == value


def test_unquoted_version_like_pin_is_rejected_because_yaml_turns_it_into_a_float(config_dir: Path) -> None:
    path = config_dir / "comparators.yaml"
    edit(
        path,
        'system_under_test: {kind: commit, value: "dd70c0eb4c8949bea858a51deef8868e589b0edf"}',
        "system_under_test: {kind: version, value: 3.10}",
    )
    with pytest.raises(ConfigError, match="quoted string"):
        load_comparators_config(path)


def test_duplicate_arm_ids_are_rejected(config_dir: Path) -> None:
    edit(config_dir / "comparators.yaml", "{id: R1,", "{id: R0,")
    with pytest.raises(ConfigError, match="duplicate ids"):
        load_comparators_config(config_dir / "comparators.yaml")


def test_unknown_track_is_rejected(config_dir: Path) -> None:
    edit(
        config_dir / "comparators.yaml",
        "tracks: [retrieval_only], pin",
        "tracks: [mystery], pin",
    )
    with pytest.raises(ConfigError, match="unknown track"):
        load_comparators_config(config_dir / "comparators.yaml")


def test_fully_pinned_comparators_pass_confirmatory_mode(config_dir: Path) -> None:
    path = config_dir / "comparators.yaml"
    text = path.read_text(encoding="utf-8").replace(
        'pin: {kind: unpinned, value: "UNPINNED"}', f'pin: {{kind: commit, value: "{COMMIT}"}}'
    )
    text = text.replace('{kind: unpinned, value: "UNPINNED"}', f'{{kind: commit, value: "{COMMIT}"}}')
    path.write_text(text, encoding="utf-8")
    assert load_comparators_config(path, confirmatory=True).system_under_test.is_pinned


def test_one_floating_pin_among_pinned_ones_still_fails_confirmatory_mode(config_dir: Path) -> None:
    path = config_dir / "comparators.yaml"
    text = path.read_text(encoding="utf-8").replace(
        '{kind: unpinned, value: "UNPINNED"}', f'{{kind: commit, value: "{COMMIT}"}}'
    )
    floated = re.sub(
        r'(id: R7,.*?pin: )\{kind: commit, value: "' + COMMIT + r'"\}',
        r'\1{kind: unpinned, value: "UNPINNED"}',
        text,
        count=1,
    )
    assert floated != text
    path.write_text(floated, encoding="utf-8")
    with pytest.raises(ConfigError, match="R7"):
        load_comparators_config(path, confirmatory=True)


def test_oversized_config_file_is_refused(tmp_path: Path) -> None:
    big = tmp_path / "big.yaml"
    big.write_text("a: " + "x" * (300 * 1024), encoding="utf-8")
    with pytest.raises(ConfigError, match="exceeds"):
        read_yaml(big)


def test_non_mapping_top_level_is_refused(tmp_path: Path) -> None:
    bad = tmp_path / "list.yaml"
    bad.write_text("- 1\n- 2\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="mapping"):
        read_yaml(bad)


def test_a_malformed_strata_key_is_a_config_error_not_a_crash(config_dir: Path) -> None:
    edit(config_dir / "evaluation.yaml", 'Q10: "Global synthesis and long-document structure"', 'Qten: "x"')
    with pytest.raises(ConfigError, match="Q1 through Q10"):
        load_all(config_dir)
