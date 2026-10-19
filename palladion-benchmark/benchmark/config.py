"""Typed, strict loaders for the four YAML configuration files.

Loading never reads credentials and never contacts a provider. Unknown keys, duplicate keys,
floating pins and out-of-range values are refused. Numbers marked provisional follow BADR-0012:
they are defaults until the B08-T03.01 seal.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

from benchmark.contracts import ContractError, Track

MAX_CONFIG_BYTES = 256 * 1024
APPROVED_MODELS = ("qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b")

_FLOATING_WORDS = frozenset({"latest", "main", "master", "head", "stable", "nightly", "dev", "current"})
_COMMIT = re.compile(r"[0-9a-f]{40}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_VERSION = re.compile(r"\d+(?:\.\d+){1,3}(?:[A-Za-z0-9.+_-]*)")
_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,100}")
_IMAGE = re.compile(r"[a-z0-9][a-z0-9./_-]*:v?\d[A-Za-z0-9._-]*")
UNPINNED = "UNPINNED"


class ConfigError(ContractError):
    """A configuration file violates its schema."""


# --------------------------------------------------------------------------- YAML loading


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader that refuses duplicate mapping keys instead of silently keeping the last."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        seen: set[Any] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise ConfigError(f"duplicate YAML key: {key!r}")
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


def read_yaml(path: Path) -> Mapping[str, Any]:
    if path.stat().st_size > MAX_CONFIG_BYTES:
        raise ConfigError(f"{path.name} exceeds {MAX_CONFIG_BYTES} bytes")
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=_StrictLoader)
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path.name} is not valid YAML ({type(exc).__name__})") from exc
    if not isinstance(data, Mapping):
        raise ConfigError(f"{path.name} must hold a mapping at the top level")
    return data


class _Reader:
    """Typed field access that records which keys were consumed so unknown keys can be refused."""

    def __init__(self, where: str, data: object) -> None:
        if not isinstance(data, Mapping):
            raise ConfigError(f"{where} must be a mapping")
        self.where = where
        self.data = data
        self.used: set[str] = set()

    def _get(self, key: str) -> Any:
        if key not in self.data:
            raise ConfigError(f"{self.where}.{key} is required")
        self.used.add(key)
        return self.data[key]

    def text(self, key: str, *, allowed: tuple[str, ...] | None = None) -> str:
        value = self._get(key)
        if not isinstance(value, str) or not value.strip():
            raise ConfigError(f"{self.where}.{key} must be a non-empty string")
        if allowed is not None and value not in allowed:
            raise ConfigError(f"{self.where}.{key} must be one of {', '.join(allowed)}")
        return value

    def integer(self, key: str, *, minimum: int = 0, maximum: int | None = None) -> int:
        value = self._get(key)
        if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
            raise ConfigError(f"{self.where}.{key} must be an integer in range")
        return value

    def optional_integer(self, key: str, *, minimum: int = 0) -> int | None:
        value = self._get(key)
        if value is None:
            return None
        if type(value) is not int or value < minimum:
            raise ConfigError(f"{self.where}.{key} must be an integer in range or null")
        return value

    def number(self, key: str, *, minimum: float = 0.0, maximum: float | None = None) -> float:
        value = self._get(key)
        if isinstance(value, bool) or not isinstance(value, int | float) or value != value:
            raise ConfigError(f"{self.where}.{key} must be a number")
        if value < minimum or (maximum is not None and value > maximum) or value in (float("inf"), float("-inf")):
            raise ConfigError(f"{self.where}.{key} out of range")
        return float(value)

    def boolean(self, key: str) -> bool:
        value = self._get(key)
        if type(value) is not bool:
            raise ConfigError(f"{self.where}.{key} must be a boolean")
        return value

    def sub(self, key: str) -> _Reader:
        return _Reader(f"{self.where}.{key}", self._get(key))

    def items(self, key: str) -> list[Any]:
        value = self._get(key)
        if not isinstance(value, list) or not value:
            raise ConfigError(f"{self.where}.{key} must be a non-empty list")
        return value

    def ints(self, key: str, *, minimum: int = 1) -> tuple[int, ...]:
        values = self.items(key)
        if not all(type(v) is int and v >= minimum for v in values) or len(set(values)) != len(values):
            raise ConfigError(f"{self.where}.{key} must hold distinct integers of at least {minimum}")
        return tuple(values)

    def texts(self, key: str) -> tuple[str, ...]:
        values = self.items(key)
        if not all(isinstance(v, str) and v.strip() for v in values) or len(set(values)) != len(values):
            raise ConfigError(f"{self.where}.{key} must hold distinct non-empty strings")
        return tuple(values)

    def finish(self) -> None:
        extra = sorted(set(self.data) - self.used)
        if extra:
            raise ConfigError(f"{self.where} has unknown key(s): {', '.join(str(k) for k in extra)}")


def _schema_version(reader: _Reader) -> str:
    return reader.text("schema_version", allowed=("1.0",))


# --------------------------------------------------------------------------- pins


@dataclass(frozen=True)
class Pin:
    """A reference to an exact external version. Floating references are refused."""

    kind: str
    value: str
    revision: str | None = None  # a model's 40-character commit in its repository
    digests: Mapping[str, str] = field(default_factory=dict)  # SHA-256 of each file the arm loads

    def __post_init__(self) -> None:
        if self.kind not in ("commit", "version", "model", "image_tag", "unpinned"):
            raise ConfigError("pin kind is not recognised")
        if self.revision is not None and not _COMMIT.fullmatch(self.revision):
            raise ConfigError("a pin revision is a 40-character lower-case commit")
        if not all(_SHA256.fullmatch(d) for d in self.digests.values()):
            raise ConfigError("a pin digest is a 64-character lower-case SHA-256")
        if self.kind == "unpinned" and (self.revision or self.digests):
            raise ConfigError("an unpinned entry carries no revision or digests")
        if not isinstance(self.value, str):
            raise ConfigError("pin value must be a quoted string (an unquoted 3.10 would load as the float 3.1)")
        if self.kind == "unpinned":
            if self.value != UNPINNED:
                raise ConfigError("an unpinned entry must use the value UNPINNED")
            return
        if self.value.lower() in _FLOATING_WORDS or any(ch in self.value for ch in "*^~<>=! "):
            raise ConfigError("pin is a floating or range reference")
        pattern = {"commit": _COMMIT, "version": _VERSION, "model": _MODEL, "image_tag": _IMAGE}[self.kind]
        if not pattern.fullmatch(self.value):
            raise ConfigError(f"pin value does not match the {self.kind} form")
        if self.kind == "image_tag" and self.value.endswith(":latest"):
            raise ConfigError("pin is a floating or range reference")

    @property
    def is_pinned(self) -> bool:
        return self.kind != "unpinned"

    @property
    def is_verifiable(self) -> bool:
        """A pin the loader can check: a model needs its revision and file digests, a binary its digests."""
        if not self.is_pinned:
            return False
        if self.kind == "model":
            return self.revision is not None and bool(self.digests)
        return True


def _pin(reader: _Reader) -> Pin:
    kind = reader.text("kind")
    value = reader._get("value")
    revision = reader.text("revision") if "revision" in reader.data else None
    digests: dict[str, str] = {}
    if "digests" in reader.data:
        digest_reader = reader.sub("digests")
        digests = {name: digest_reader.text(name) for name in sorted(digest_reader.data)}
        digest_reader.finish()
    reader.finish()
    return Pin(kind, value, revision, digests)


# --------------------------------------------------------------------------- benchmark.yaml


@dataclass(frozen=True)
class TierConfig:
    documents: int
    single_turn_questions: int
    episodes: int


@dataclass(frozen=True)
class SplitSizes:
    smoke: int
    dev: int
    test: int


@dataclass(frozen=True)
class RetryPolicy:
    """Predeclared retry rule: only classified transient infrastructure faults, never result quality or timeouts."""

    max_attempts: int
    base_backoff_seconds: float


@dataclass(frozen=True)
class GeneratorSettings:
    models: tuple[str, ...]
    temperature: float
    max_completion_tokens: int
    reasoning_effort: Mapping[str, str]
    rate_limit_max_wait_seconds: float
    request_timeout_seconds: float
    call_budget_per_run: int | None
    token_budgets: Mapping[str, int | None]
    allow_automatic_failover: bool


@dataclass(frozen=True)
class BenchmarkConfig:
    schema_version: str
    tiers: Mapping[str, TierConfig]
    default_seed: int
    k_values: tuple[int, ...]
    token_budgets: tuple[int, ...]
    strata_count: int
    splits: SplitSizes
    case_deadline_seconds: float
    run_deadline_seconds: float | None
    retry: RetryPolicy
    main_max_calls: int
    critic_max_calls: int
    generator: GeneratorSettings

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> BenchmarkConfig:
        r = _Reader("benchmark", data)
        version = _schema_version(r)
        tiers_r = r.sub("tiers")
        tiers = {}
        for name in ("S", "M", "L"):
            t = tiers_r.sub(name)
            tiers[name] = TierConfig(
                documents=t.integer("documents", minimum=1),
                single_turn_questions=t.integer("single_turn_questions", minimum=1),
                episodes=t.integer("episodes"),
            )
            t.finish()
        tiers_r.finish()
        seeds = r.sub("seeds")
        default_seed = seeds.integer("default")
        seeds.finish()
        evidence = r.sub("evidence")
        k_values, token_budgets = evidence.ints("k_values"), evidence.ints("token_budgets")
        evidence.finish()
        splits_r = r.sub("splits")
        splits = SplitSizes(
            smoke=splits_r.integer("smoke_per_stratum", minimum=1),
            dev=splits_r.integer("dev_per_stratum", minimum=1),
            test=splits_r.integer("test_per_stratum", minimum=1),
        )
        strata_count = splits_r.integer("strata_count", minimum=1)
        splits_r.finish()
        runner = r.sub("runner")
        retry_r = runner.sub("retry")
        retry = RetryPolicy(
            max_attempts=retry_r.integer("max_attempts", minimum=1, maximum=3),
            base_backoff_seconds=retry_r.number("base_backoff_seconds", maximum=60.0),
        )
        retry_r.finish()
        case_deadline = runner.number("case_deadline_seconds", minimum=0.001, maximum=3600.0)
        run_deadline_raw = runner._get("run_deadline_seconds")
        if run_deadline_raw is not None and (
            isinstance(run_deadline_raw, bool) or not isinstance(run_deadline_raw, int | float) or run_deadline_raw <= 0
        ):
            raise ConfigError("benchmark.runner.run_deadline_seconds must be positive or null")
        runner.finish()
        budgets = r.sub("budgets")
        main_calls = budgets.integer("main_max_calls", minimum=1, maximum=5)
        critic_calls = budgets.integer("critic_max_calls", minimum=1, maximum=3)
        budgets.finish()
        g = r.sub("generator")
        models = g.texts("models")
        if any(m not in APPROVED_MODELS for m in models) or models[0] != APPROVED_MODELS[0]:
            raise ConfigError("benchmark.generator.models must be approved models with qwen first")
        effort_r = g.sub("reasoning_effort")
        effort = {m: effort_r.text(m) for m in models}
        effort_r.finish()
        budget_r = g.sub("token_budgets")
        token_budgets_by_model = {m: budget_r.optional_integer(m, minimum=1) for m in models}
        budget_r.finish()
        generator = GeneratorSettings(
            models=models,
            temperature=g.number("temperature", maximum=2.0),
            max_completion_tokens=g.integer("max_completion_tokens", minimum=1, maximum=8192),
            reasoning_effort=effort,
            rate_limit_max_wait_seconds=g.number("rate_limit_max_wait_seconds", maximum=600.0),
            request_timeout_seconds=g.number("request_timeout_seconds", minimum=1.0, maximum=300.0),
            call_budget_per_run=g.optional_integer("call_budget_per_run", minimum=1),
            token_budgets=token_budgets_by_model,
            allow_automatic_failover=g.boolean("allow_automatic_failover"),
        )
        g.finish()
        r.finish()
        config = cls(
            schema_version=version,
            tiers=tiers,
            default_seed=default_seed,
            k_values=k_values,
            token_budgets=token_budgets,
            strata_count=strata_count,
            splits=splits,
            case_deadline_seconds=case_deadline,
            run_deadline_seconds=None if run_deadline_raw is None else float(run_deadline_raw),
            retry=retry,
            main_max_calls=main_calls,
            critic_max_calls=critic_calls,
            generator=generator,
        )
        config.validate()
        return config

    def validate(self) -> None:
        pilot_total = (self.splits.smoke + self.splits.dev + self.splits.test) * self.strata_count
        if pilot_total != self.tiers["M"].single_turn_questions:
            raise ConfigError("split sizes times strata must equal the M-tier question count")
        if (
            self.tiers["S"].documents >= self.tiers["M"].documents
            or self.tiers["M"].documents >= self.tiers["L"].documents
        ):
            raise ConfigError("tier document counts must increase from S to L")


# --------------------------------------------------------------------------- comparators.yaml


@dataclass(frozen=True)
class ArmConfig:
    arm_id: str
    name: str
    family: str
    tracks: tuple[Track, ...]
    pin: Pin
    eligibility: str


@dataclass(frozen=True)
class ComparatorsConfig:
    schema_version: str
    arms: tuple[ArmConfig, ...]
    shared_models: Mapping[str, Pin]
    system_under_test: Pin

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any], *, confirmatory: bool = False) -> ComparatorsConfig:
        r = _Reader("comparators", data)
        version = _schema_version(r)
        arms = []
        for index, raw in enumerate(r.items("arms")):
            a = _Reader(f"comparators.arms[{index}]", raw)
            arm = ArmConfig(
                arm_id=a.text("id"),
                name=a.text("name"),
                family=a.text("family"),
                tracks=tuple(_track(t) for t in a.texts("tracks")),
                pin=_pin(a.sub("pin")),
                eligibility=a.text("eligibility"),
            )
            a.finish()
            arms.append(arm)
        ids = [a.arm_id for a in arms]
        if len(ids) != len(set(ids)):
            raise ConfigError("comparators.arms has duplicate ids")
        models_r = r.sub("shared_models")
        shared = {name: _pin(models_r.sub(name)) for name in sorted(models_r.data)}
        models_r.finish()
        sut = _pin(r.sub("system_under_test"))
        r.finish()
        config = cls(version, tuple(arms), shared, sut)
        if confirmatory:
            config.require_confirmatory()
        return config

    def require_confirmatory(self) -> None:
        """Confirmatory runs must name an exact version for every arm, model and the system under test."""
        pins = [(arm.arm_id, arm.pin) for arm in self.arms]
        pins += [(name, pin) for name, pin in self.shared_models.items()]
        pins.append(("system_under_test", self.system_under_test))
        floating = [name for name, pin in pins if not pin.is_pinned]
        if floating:
            raise ConfigError(f"confirmatory mode refuses unpinned entries: {', '.join(floating)}")
        unverifiable = [name for name, pin in self.shared_models.items() if not pin.is_verifiable]
        if unverifiable:
            raise ConfigError(f"confirmatory mode needs a revision and file digests for: {', '.join(unverifiable)}")


def _track(value: str) -> Track:
    try:
        return Track(value)
    except ValueError as exc:
        raise ConfigError(f"unknown track: {value}") from exc


# --------------------------------------------------------------------------- evaluation.yaml


@dataclass(frozen=True)
class StatisticsSettings:
    bootstrap_resamples: int
    confidence: float
    multiplicity: str
    cluster_by: str
    zero_failure_bound_numerator: int
    bootstrap_seed: int
    min_clusters: int


@dataclass(frozen=True)
class EvaluationConfig:
    schema_version: str
    strata: Mapping[str, str]
    metric_groups: Mapping[str, tuple[str, ...]]
    statistics: StatisticsSettings
    quantile_method: str
    slot_kinds: Mapping[str, str]
    loss_matrix: Mapping[str, float]
    provisional_gates: Mapping[str, str]
    sealed: bool

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> EvaluationConfig:
        r = _Reader("evaluation", data)
        version = _schema_version(r)
        strata_r = r.sub("strata")
        keys = sorted(strata_r.data, key=lambda k: (len(str(k)), str(k)))
        strata = {key: strata_r.text(key) for key in keys}
        strata_r.finish()
        if list(strata) != [f"Q{i}" for i in range(1, 11)]:
            raise ConfigError("evaluation.strata must define Q1 through Q10")
        groups_r = r.sub("metric_groups")
        groups = {name: groups_r.texts(name) for name in sorted(groups_r.data)}
        groups_r.finish()
        s = r.sub("statistics")
        statistics = StatisticsSettings(
            bootstrap_resamples=s.integer("bootstrap_resamples", minimum=100),
            confidence=s.number("confidence", minimum=0.5, maximum=0.999),
            multiplicity=s.text("multiplicity", allowed=("holm",)),
            cluster_by=s.text("cluster_by", allowed=("scenario_family",)),
            zero_failure_bound_numerator=s.integer("zero_failure_bound_numerator", minimum=1),
            bootstrap_seed=s.integer("bootstrap_seed", minimum=0),
            min_clusters=s.integer("min_clusters", minimum=2),
        )
        s.finish()
        quantile_method = r.text("quantile_method", allowed=("linear",))
        kinds_r = r.sub("slot_kinds")
        slot_kinds = {name: kinds_r.text(name) for name in sorted(kinds_r.data)}
        kinds_r.finish()
        loss_r = r.sub("loss_matrix")
        loss = {name: loss_r.number(name) for name in sorted(loss_r.data)}
        loss_r.finish()
        gates_r = r.sub("provisional_gates")
        gates = {name: gates_r.text(name) for name in sorted(gates_r.data)}
        gates_r.finish()
        sealed = r.boolean("sealed")
        r.finish()
        return cls(version, strata, groups, statistics, quantile_method, slot_kinds, loss, gates, sealed)


# --------------------------------------------------------------------------- fixtures.yaml


@dataclass(frozen=True)
class FixturesConfig:
    schema_version: str
    world_name: str
    m_tier_composition: Mapping[str, int]
    language_profile_percent: Mapping[str, int]
    noise_percent_ranges: Mapping[str, tuple[float, float]]
    episodes_turns: tuple[int, int]
    update_events: int

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> FixturesConfig:
        r = _Reader("fixtures", data)
        version = _schema_version(r)
        world = r.text("world_name")
        comp_r = r.sub("m_tier_composition")
        composition = {name: comp_r.integer(name, minimum=1) for name in sorted(comp_r.data)}
        comp_r.finish()
        lang_r = r.sub("language_profile_percent")
        language = {name: lang_r.integer(name, minimum=0, maximum=100) for name in sorted(lang_r.data)}
        lang_r.finish()
        if sum(language.values()) != 100:
            raise ConfigError("fixtures.language_profile_percent must sum to 100")
        noise_r = r.sub("noise_percent_ranges")
        noise: dict[str, tuple[float, float]] = {}
        for name in sorted(noise_r.data):
            pair = noise_r._get(name)
            if (
                not isinstance(pair, list)
                or len(pair) != 2
                or not all(isinstance(v, int | float) and not isinstance(v, bool) for v in pair)
                or not 0 <= pair[0] <= pair[1] <= 100
            ):
                raise ConfigError(f"fixtures.noise_percent_ranges.{name} must be [low, high] within 0..100")
            noise[name] = (float(pair[0]), float(pair[1]))
        noise_r.finish()
        turns_r = r.sub("episode_turns")
        low, high = turns_r.integer("min", minimum=1), turns_r.integer("max", minimum=1)
        turns_r.finish()
        if low > high:
            raise ConfigError("fixtures.episode_turns.min exceeds max")
        events = r.integer("update_events", minimum=1)
        r.finish()
        config = cls(version, world, composition, language, noise, (low, high), events)
        return config


# --------------------------------------------------------------------------- bundle and digest


@dataclass(frozen=True)
class ConfigBundle:
    benchmark: BenchmarkConfig
    comparators: ComparatorsConfig
    evaluation: EvaluationConfig
    fixtures: FixturesConfig


def load_benchmark_config(path: Path) -> BenchmarkConfig:
    return BenchmarkConfig.from_mapping(read_yaml(path))


def load_comparators_config(path: Path, *, confirmatory: bool = False) -> ComparatorsConfig:
    return ComparatorsConfig.from_mapping(read_yaml(path), confirmatory=confirmatory)


def load_evaluation_config(path: Path) -> EvaluationConfig:
    return EvaluationConfig.from_mapping(read_yaml(path))


def load_fixtures_config(path: Path) -> FixturesConfig:
    return FixturesConfig.from_mapping(read_yaml(path))


def load_all(config_dir: Path, *, confirmatory: bool = False) -> ConfigBundle:
    bundle = ConfigBundle(
        benchmark=load_benchmark_config(config_dir / "benchmark.yaml"),
        comparators=load_comparators_config(config_dir / "comparators.yaml", confirmatory=confirmatory),
        evaluation=load_evaluation_config(config_dir / "evaluation.yaml"),
        fixtures=load_fixtures_config(config_dir / "fixtures.yaml"),
    )
    if sum(bundle.fixtures.m_tier_composition.values()) != bundle.benchmark.tiers["M"].documents:
        raise ConfigError("fixtures.m_tier_composition must sum to the M-tier document count in benchmark.tiers")
    if set(bundle.evaluation.strata) != {f"Q{i}" for i in range(1, bundle.benchmark.strata_count + 1)}:
        raise ConfigError("evaluation.strata must match benchmark.splits.strata_count")
    return bundle


def to_plain(value: Any) -> Any:
    """Convert a config object into JSON-ready containers for hashing and display."""
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_plain(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(k): to_plain(v) for k, v in value.items()}
    if isinstance(value, tuple | list):
        return [to_plain(v) for v in value]
    return value


def config_digest(value: Any) -> str:
    """SHA-256 of the canonical JSON form; equal configs always give equal digests."""
    canonical = json.dumps(to_plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
