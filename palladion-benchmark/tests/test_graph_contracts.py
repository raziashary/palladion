"""Additive contract extensions for graph comparators: the pin, the cost record, the relation field (B06-T00.01)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from benchmark.adapters.bm25 import Bm25Arm
from benchmark.adapters.common import Condition, PublishedView
from benchmark.contracts import ContractError, EvidenceCandidate, RetrievalRequest
from benchmark.eval.cost_latency import OfflineCost
from benchmark.eval.statistics import StatisticsError
from benchmark.results_check import validate_run
from benchmark.run_manifest import ComparatorPin, ManifestError, read_verified
from benchmark.runner import RunLedger
from benchmark.track_a import COMPARATOR_ARMS, COST_KEYS, RunSpec, TrackAError, execute

COMMIT = "a" * 40
LOCK = "b" * 64


def pin(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "repository": "https://github.com/example/comparator",
        "commit": COMMIT,
        "lock_sha256": LOCK,
        "interpreter": "3.12.5",
        "native_config": {"mode": "local", "top_k": 10},
        "deviations": ["extraction model replaced by the approved Groq model"],
    }
    return {**base, **over}


# --------------------------------------------------------------------------- the pin


def test_a_comparator_pin_round_trips() -> None:
    value = ComparatorPin.from_dict(pin())
    assert ComparatorPin.from_dict(value.to_dict()) == value
    assert value.to_dict() == pin()


@pytest.mark.parametrize(
    "bad",
    [
        {"commit": "main"}, {"commit": "A" * 40}, {"commit": "a" * 39}, {"lock_sha256": "abc"},
        {"repository": "http://github.com/example/x"}, {"repository": "git@github.com:example/x"},
        {"interpreter": ""}, {"deviations": [""]}, {"native_config": {"x": float("nan")}},
    ],
)  # fmt: skip
def test_a_floating_or_malformed_pin_is_refused(bad: dict[str, Any]) -> None:
    with pytest.raises((ManifestError, ContractError)):
        ComparatorPin.from_dict(pin(**bad))


@pytest.mark.parametrize("drop", ["repository", "commit", "lock_sha256", "interpreter", "native_config", "deviations"])
def test_a_pin_with_a_field_missing_or_added_is_refused(drop: str) -> None:
    data = pin()
    del data[drop]
    with pytest.raises(ManifestError):
        ComparatorPin.from_dict(data)
    with pytest.raises(ManifestError):
        ComparatorPin.from_dict({**pin(), "extra": 1})


# --------------------------------------------------------------------------- the cost record


def test_the_old_two_value_cost_record_still_works() -> None:
    cost = OfflineCost(10.0, 0.5)
    assert cost.extraction_calls is None and cost.storage_bytes is None
    assert OfflineCost.from_index_stats({"build_ms": 10, "build_cost_usd": 0.5}) == cost


def test_the_cost_record_reads_extraction_calls_tokens_and_storage() -> None:
    stats = {
        "build_ms": 5, "build_cost_usd": None, "extraction_calls": 1709, "extraction_prompt_tokens": 4_100_000,
        "extraction_completion_tokens": 600_000, "storage_bytes": 123456,
    }  # fmt: skip
    cost = OfflineCost.from_index_stats(stats)
    assert (cost.extraction_calls, cost.extraction_prompt_tokens, cost.storage_bytes) == (1709.0, 4_100_000.0, 123456.0)
    assert cost.cost_usd is None, "an unknown dollar cost stays unknown"
    with pytest.raises(StatisticsError, match="extraction_calls"):
        OfflineCost.from_index_stats({**stats, "extraction_calls": "many"})


# --------------------------------------------------------------------------- the relation field


def candidate(**over: Any) -> EvidenceCandidate:
    base: dict[str, Any] = {
        "source_version_id": "POL-1@v1", "locator": "4.1", "content": "text", "rank": 1, "native_score": 1.0,
        "retrieval_channel": "graph", "evidence_path": (), "native_citation_supported": True,
        "additional_metadata": {},
    }  # fmt: skip
    return EvidenceCandidate(**{**base, **over})


def test_a_plain_passage_serializes_exactly_as_before_the_field_existed() -> None:
    data = candidate().to_dict()
    assert "relation" not in data
    assert EvidenceCandidate.from_dict(data) == candidate()


def test_a_relation_round_trips_and_is_frozen() -> None:
    edge = {"subject": "POL-1", "predicate": "SUPERSEDES", "object": "POL-0", "supporting_ids": ["POL-1@v1#4.1"]}
    value = candidate(relation=edge)
    assert value.to_dict()["relation"] == edge
    assert EvidenceCandidate.from_dict(value.to_dict()) == value
    with pytest.raises(TypeError):
        value.relation["subject"] = "x"  # type: ignore[index]


@pytest.mark.parametrize(
    "bad",
    [
        {"subject": "a", "predicate": "b", "object": "c"},
        {"subject": "a", "predicate": "b", "object": "c", "supporting_ids": [], "extra": 1},
        {"subject": "", "predicate": "b", "object": "c", "supporting_ids": []},
        {"subject": "a", "predicate": "b", "object": "c", "supporting_ids": "POL-1"},
        {"subject": "a", "predicate": "b", "object": "c", "supporting_ids": [1]},
        {"subject": "a", "predicate": "b", "object": "c", "supporting_ids": [""]},
        "SUPERSEDES",
    ],
)  # fmt: skip
def test_a_malformed_relation_is_refused(bad: Any) -> None:
    with pytest.raises(ContractError):
        candidate(relation=bad)


# --------------------------------------------------------------------------- a graph arm through the real harness


class GraphStub:
    """A graph-shaped arm over the lexical arm: it has a pin, a cost record and models, and nothing else of a graph."""

    def __init__(self, view: PublishedView, arm_id: str = "R4", *, comparator: Any = None, stats: Any = None) -> None:
        self.arm_id = arm_id
        self._inner = Bm25Arm(view, Condition.C2)
        self._comparator = pin() if comparator is None else comparator
        self._stats = {k: (None if k != "build_ms" else 1.0) for k in COST_KEYS} if stats is None else stats

    def build_index(self, source_manifest_uri: str, index_namespace: str) -> None:
        self._inner.build_index(source_manifest_uri, index_namespace)

    def retrieve(self, request: RetrievalRequest) -> list[EvidenceCandidate]:
        return self._inner.retrieve(request)

    def index_stats(self) -> dict[str, Any]:
        return dict(self._stats)

    def describe(self) -> dict[str, Any]:
        out: dict[str, Any] = {"arm": self.arm_id, "kind": "test-only graph stub", "models": {"embeddings": "stub@1"}}
        if self._comparator is not False:
            out["comparator"] = self._comparator
        return out


def run_graph(
    s_root: Path, out: Path, arm: GraphStub, *, built: bool = True, run_id: str = "run-g-0001"
) -> list[dict[str, Any]]:
    view = PublishedView.load(s_root / "published")
    arm.build_index(str(view.root), "track_a")
    builds = [{"arm": arm.arm_id, "status": "BUILT" if built else "FAILED", "stats": arm.index_stats()}]
    execute(RunSpec(run_id, "smoke", Condition.C2, 10, 4000, s_root, out), {arm.arm_id: arm}, builds=builds)
    return builds


@pytest.fixture(scope="module")
def graph_run(s_root: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("graph") / "run"
    run_graph(s_root, out, GraphStub(PublishedView.load(s_root / "published")))
    return out


def test_the_comparator_arm_ids_are_the_three_research_systems() -> None:
    assert COMPARATOR_ARMS == ("R4", "R5", "R6")


def test_a_graph_arm_runs_through_the_real_runner_and_records_its_pin(graph_run: Path, s_root: Path) -> None:
    manifest = read_verified(graph_run / "manifest-R4.json")
    assert manifest.method_version is None and manifest.model_versions == {"embeddings": "stub@1"}
    assert ComparatorPin.from_dict(manifest.retrieval_config["comparator"]).commit == COMMIT
    assert all(r.is_final for r in RunLedger(graph_run / "ledger.jsonl").records)
    assert validate_run(graph_run, root=s_root) == []


def test_a_graph_run_carries_no_gold_in_its_new_fields(graph_run: Path) -> None:
    text = "".join(f.read_text(encoding="utf-8") for f in graph_run.glob("*.json*"))
    for gold in ("citation_gold_spans", "required_claims", "minimal_sets", "gold_applicable"):
        assert gold not in text


def test_a_package_index_framework_is_pinned_by_exact_versions_and_old_pins_are_unchanged() -> None:
    framework = pin(commit="", packages={"langchain-core": "1.6.7", "langgraph": "1.2.14"})
    parsed = ComparatorPin.from_dict(framework)
    assert parsed.commit == "" and dict(parsed.packages) == {"langchain-core": "1.6.7", "langgraph": "1.2.14"}
    assert parsed.to_dict() == framework and ComparatorPin.from_dict(parsed.to_dict()) == parsed
    old = ComparatorPin.from_dict(pin())
    assert "packages" not in old.to_dict(), "a pin without packages serialises exactly as before"


@pytest.mark.parametrize(
    ("over", "reason"),
    [
        ({"commit": ""}, "40-character"),
        ({"commit": "main", "packages": {"a": "1.0"}}, "40-character"),
        ({"commit": "", "packages": {"langgraph": "latest"}}, "exact version"),
        ({"commit": "", "packages": {"langgraph": ">=1.2"}}, "exact version"),
        ({"commit": "", "packages": {"langgraph": "1.*"}}, "exact version"),
        ({"commit": "", "packages": {"": "1.0"}}, "packages"),
    ],
)
def test_a_framework_pin_without_exact_versions_or_a_commit_is_refused(over: dict[str, Any], reason: str) -> None:
    with pytest.raises(ManifestError, match=reason):
        ComparatorPin.from_dict(pin(**over))


def test_an_arm_without_a_valid_pin_cannot_start(s_root: Path, tmp_path: Path) -> None:
    view = PublishedView.load(s_root / "published")
    for bad in (False, pin(commit="main"), {}):
        with pytest.raises(TrackAError, match="comparator pin"):
            run_graph(s_root, tmp_path / f"p{abs(hash(str(bad)))}", GraphStub(view, comparator=bad))


def test_the_validator_rejects_a_graph_run_with_no_recorded_build(
    graph_run: Path, s_root: Path, tmp_path: Path
) -> None:
    copy = tmp_path / "run"
    shutil.copytree(graph_run, copy)
    config = json.loads((copy / "run_config.json").read_text(encoding="utf-8"))
    config["builds"] = []
    (copy / "run_config.json").write_text(json.dumps(config), encoding="utf-8")
    assert any("no recorded index build" in f.rule for f in validate_run(copy, root=s_root))


def test_the_validator_rejects_a_cost_record_that_omits_a_field_but_accepts_an_explicit_unknown(
    graph_run: Path, s_root: Path, tmp_path: Path
) -> None:
    copy = tmp_path / "run"
    shutil.copytree(graph_run, copy)
    config = json.loads((copy / "run_config.json").read_text(encoding="utf-8"))
    assert config["builds"][0]["stats"]["extraction_calls"] is None, "an unknown is written as null"
    assert validate_run(copy, root=s_root) == []
    del config["builds"][0]["stats"]["extraction_calls"]
    (copy / "run_config.json").write_text(json.dumps(config), encoding="utf-8")
    found = [f for f in validate_run(copy, root=s_root) if "index cost lacks extraction_calls" in f.rule]
    assert len(found) == 1


def test_a_failed_build_that_does_not_say_why_is_not_a_recorded_build(s_root: Path, tmp_path: Path) -> None:
    out = tmp_path / "failed"
    run_graph(s_root, out, GraphStub(PublishedView.load(s_root / "published")), built=False)
    assert any("no recorded index build" in f.rule for f in validate_run(out, root=s_root))


def test_a_failed_build_that_names_its_error_is_a_recorded_result(
    graph_run: Path, s_root: Path, tmp_path: Path
) -> None:
    copy = tmp_path / "run"
    shutil.copytree(graph_run, copy)
    config = json.loads((copy / "run_config.json").read_text(encoding="utf-8"))
    config["builds"] = [{"arm": config["builds"][0]["arm"], "status": "FAILED", "error": "ArmUnavailable"}]
    (copy / "run_config.json").write_text(json.dumps(config), encoding="utf-8")
    assert not any("index build" in f.rule or "index cost" in f.rule for f in validate_run(copy, root=s_root))
    config["builds"][0]["error"] = ""
    (copy / "run_config.json").write_text(json.dumps(config), encoding="utf-8")
    assert any("no recorded index build" in f.rule for f in validate_run(copy, root=s_root))


def test_a_run_without_graph_arms_is_unchanged_by_the_new_checks(s_root: Path, tmp_path: Path) -> None:
    from benchmark.track_a import build_local_arms

    view = PublishedView.load(s_root / "published")
    arms, builds = build_local_arms(view, ["R0"], condition=Condition.C2, index_dir=tmp_path / "index")
    execute(RunSpec("run-g-0002", "smoke", Condition.C2, 10, 4000, s_root, tmp_path / "r0"), arms, builds=builds)
    manifest = read_verified(tmp_path / "r0" / "manifest-R0.json")
    assert "comparator" not in manifest.retrieval_config and manifest.method_version == "1.0.0"
    assert validate_run(tmp_path / "r0", root=s_root) == []
