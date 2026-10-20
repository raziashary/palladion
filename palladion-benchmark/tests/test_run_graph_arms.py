"""The graph-arm runner: a comparator indexes from cold behind the counting proxy and nothing spends past the caps."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from support import HashingEncoder

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_graph_arms

from benchmark.adapters.common import Condition, PublishedView
from benchmark.adapters.worker import WorkerArm, launch_arm
from benchmark.contracts import ArmUnavailable, RunStatus
from benchmark.generator import TransportResponse
from benchmark.llm_proxy import ProxyLimits
from benchmark.results_check import validate_run
from benchmark.run_manifest import ComparatorPin, read_verified
from benchmark.runner import RunLedger
from benchmark.track_a import TrackAError

ROOT = Path(__file__).resolve().parents[1]
STUB = Path(__file__).resolve().parent / "comparator_stub.py"
MODEL = "qwen/qwen3.8-27b"
PIN = ComparatorPin.from_dict(
    {"repository": "https://github.com/example/stub", "commit": "c" * 40, "lock_sha256": "d" * 64,
     "interpreter": "3.12.5", "native_config": {"mode": "stub"}, "deviations": []}
)  # fmt: skip


class Provider:
    def __init__(self) -> None:
        self.calls = 0

    def post(self, payload: Any) -> TransportResponse:
        self.calls += 1
        body = {"model": MODEL, "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60}}  # fmt: skip
        return TransportResponse(200, {}, json.dumps(body).encode())


def stub_factory(build_calls: int = 0) -> Any:
    def make(**kwargs: Any) -> WorkerArm:
        extra = {"STUB_BUILD_CALLS": str(build_calls), "STUB_MODEL": MODEL}
        return launch_arm(
            "R4", script=STUB, unsupported=["acl_filter"], extra_env=extra,
            **{k: v for k, v in kwargs.items() if k in {"interpreter", "server", "pin", "view", "work_dir", "llm_model",
                                                         "embedding_model", "condition", "build_timeout"}},
        )  # fmt: skip

    return make


def limits(**over: Any) -> ProxyLimits:
    base: dict[str, Any] = {"max_calls": 100, "max_tokens": 1_000_000, "max_completion_tokens": 700,
                            "pace_seconds": 0.0, "models": (MODEL,)}  # fmt: skip
    return ProxyLimits(**{**base, **over})


def run(s_root: Path, out: Path, provider: Provider, **over: Any) -> dict[str, Any]:
    factory = over.pop("factory", stub_factory())
    return run_graph_arms.run_arm(
        "R4", root=s_root, out=out, run_id="run-g-0100", transport=provider, encoder=HashingEncoder(),
        limits=over.pop("limits", limits()), embedding_model="stub-embed@1", token="t" * 24, factory=factory,
        interpreter=Path(sys.executable), pin=PIN, **over,
    )  # fmt: skip


def test_a_graph_arm_indexes_from_cold_answers_every_question_and_validates(s_root: Path, tmp_path: Path) -> None:
    out = tmp_path / "run"
    provider = Provider()
    spend = run(s_root, out, provider, factory=stub_factory(build_calls=3))
    assert spend["usage"]["calls"] == 3 == provider.calls and spend["usage"]["prompt_tokens"] == 150
    assert spend["build"]["status"] == "BUILT" and spend["build"]["stats"]["extraction_calls"] == 3
    finals = [r for r in RunLedger(out / "ledger.jsonl").records if r.is_final]
    assert finals and {r.status for r in finals} == {RunStatus.OK}
    assert validate_run(out, root=s_root) == []
    manifest = read_verified(out / "manifest-R4.json")
    assert manifest.retrieval_config["comparator"]["commit"] == "c" * 40
    assert manifest.cache_condition.value == "cold"


def test_the_run_keeps_its_books_as_numbers_and_codes_only(s_root: Path, tmp_path: Path) -> None:
    out = tmp_path / "run"
    run(s_root, out, Provider(), factory=stub_factory(build_calls=2))
    rows = [json.loads(line) for line in (out / "proxy.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["outcome"] for r in rows if r["outcome"] != "EMBEDDING"] == ["OK", "OK"]
    assert set(rows[0]) <= {"sequence", "at", "outcome", "model", "http_status", "prompt_tokens", "completion_tokens",
                            "latency_ms", "code", "inputs"}  # fmt: skip
    spend = json.loads((out / "spend.json").read_text(encoding="utf-8"))
    assert spend["limits"] == {"calls": 100, "tokens": 1_000_000, "pace_seconds": 0.0}
    assert "t" * 24 not in (out / "spend.json").read_text(encoding="utf-8"), "the run token is never written"


def test_a_comparator_that_asks_for_more_than_the_cap_is_stopped_at_the_cap(s_root: Path, tmp_path: Path) -> None:
    out = tmp_path / "run"
    provider = Provider()
    spend = run(s_root, out, provider, factory=stub_factory(build_calls=20), limits=limits(max_calls=5))
    assert provider.calls == 5 == spend["usage"]["calls"] and spend["usage"]["refused"] == 15


def test_a_build_that_fails_is_recorded_and_every_pair_is_not_run_never_a_zero(s_root: Path, tmp_path: Path) -> None:
    class Failing:
        def __init__(self, arm: WorkerArm) -> None:
            self.arm = arm

        def __getattr__(self, name: str) -> Any:
            return getattr(self.arm, name)

        def build_index(self, uri: str, namespace: str) -> None:
            raise ArmUnavailable("R4 could not build its index: TIMEOUT")

    def factory(**kwargs: Any) -> Any:
        failing: Any = Failing(stub_factory()(**kwargs))
        return failing

    out = tmp_path / "run"
    spend = run(s_root, out, Provider(), factory=factory)
    assert spend["build"]["status"] == "FAILED" and spend["build"]["error"] == "ArmUnavailable"
    finals = [r for r in RunLedger(out / "ledger.jsonl").records if r.is_final]
    assert finals and {(r.status, r.code) for r in finals} == {(RunStatus.NOT_RUN, "ARM_UNAVAILABLE")}


def test_only_the_three_comparators_run_here_and_an_existing_directory_is_never_reused(
    s_root: Path, tmp_path: Path
) -> None:
    with pytest.raises(TrackAError, match="not a graph comparator"):
        run_graph_arms.run_arm(
            "R0", root=s_root, out=tmp_path / "x", run_id="run-g-0101", transport=Provider(),
            encoder=HashingEncoder(), limits=limits(), embedding_model="e", token="t" * 24,
        )  # fmt: skip
    existing = tmp_path / "there"
    existing.mkdir()
    with pytest.raises(FileExistsError):
        run(s_root, existing, Provider())


def test_the_worker_is_always_stopped_even_when_the_run_fails(s_root: Path, tmp_path: Path) -> None:
    started: list[WorkerArm] = []

    def factory(**kwargs: Any) -> WorkerArm:
        arm: WorkerArm = stub_factory()(**kwargs)
        started.append(arm)
        return arm

    with pytest.raises(Exception):  # noqa: B017 (any failure inside the run)
        run(s_root, tmp_path / "run", Provider(), factory=factory, k=0)
    assert started and not started[0]._worker.alive


def test_a_run_can_finish_an_earlier_runs_work_and_leaves_that_run_as_it_was(s_root: Path, tmp_path: Path) -> None:
    earlier = tmp_path / "earlier"
    (earlier / "work" / "native").mkdir(parents=True)
    (earlier / "work" / "native" / "state.json").write_text('{"done": 35}', encoding="utf-8")
    out = tmp_path / "run"
    spend = run(s_root, out, Provider(), resume_from=earlier)
    assert (out / "work" / "native" / "state.json").read_text(encoding="utf-8") == '{"done": 35}'
    assert spend["resumed_from"] == str(earlier)
    assert sorted(p.name for p in earlier.iterdir()) == ["work"], "the earlier run is untouched"
    cold = run(s_root, tmp_path / "cold", Provider())
    assert cold["resumed_from"] is None


def test_a_failed_build_carries_what_it_spent_before_failing(s_root: Path, tmp_path: Path) -> None:
    class Spending:
        def __init__(self, arm: WorkerArm) -> None:
            self.arm = arm

        def __getattr__(self, name: str) -> Any:
            return getattr(self.arm, name)

        def build_index(self, uri: str, namespace: str) -> None:
            self.arm.build_index(uri, namespace)
            raise ArmUnavailable("R4 could not build its index: TIMEOUT")

    def factory(**kwargs: Any) -> Any:
        spending: Any = Spending(stub_factory(build_calls=3)(**kwargs))
        return spending

    out = tmp_path / "run"
    spend = run(s_root, out, Provider(), factory=factory)
    assert spend["build"]["status"] == "FAILED" and spend["build"]["spend_before_failure"]["calls"] == 3
    assert validate_run(out, root=s_root) == [], "a failed build that names its error is a recorded result"


def test_a_run_that_is_interrupted_still_records_what_it_spent(
    s_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def interrupted(*args: Any, **kwargs: Any) -> Any:
        raise KeyboardInterrupt

    monkeypatch.setattr(run_graph_arms, "execute", interrupted)
    out = tmp_path / "run"
    with pytest.raises(KeyboardInterrupt):
        run(s_root, out, Provider(), factory=stub_factory(build_calls=2))
    spend = json.loads((out / "spend.json").read_text(encoding="utf-8"))
    assert spend["status"] == "INTERRUPTED" and spend["usage"]["calls"] == 2 and spend["build"]["status"] == "BUILT"


def test_a_run_stopped_from_outside_gets_a_spend_record_rebuilt_from_its_book(tmp_path: Path) -> None:
    run_dir = tmp_path / "g-r6-x"
    run_dir.mkdir()
    rows = [
        {"sequence": 1, "outcome": "EMBEDDING", "inputs": 4, "http_status": 200},
        {"sequence": 2, "outcome": "OK", "prompt_tokens": 100, "completion_tokens": 20, "http_status": 200},
        {"sequence": 3, "outcome": "RATE_LIMITED", "http_status": 429},
        {"sequence": 4, "outcome": "REFUSED", "code": "BUDGET_EXHAUSTED", "http_status": 403},
    ]
    (run_dir / "proxy.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    spend = run_graph_arms.reconstruct_spend(run_dir, "R6", MODEL, limits(), None)
    assert spend["reconstructed_from_book"] is True and spend["status"] == "STOPPED_BY_OPERATOR"
    assert spend["usage"]["calls"] == 2 and spend["usage"]["rate_limited"] == 1 and spend["usage"]["refused"] == 1
    assert spend["usage"]["prompt_tokens"] == 100 and spend["usage"]["embedding_inputs"] == 4
    assert json.loads((run_dir / "spend.json").read_text(encoding="utf-8")) == spend


# --------------------------------------------------------------------------- the command line


def cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_graph_arms.py"), *args],
        capture_output=True, text=True, check=False, timeout=600,
    )  # fmt: skip


def test_the_command_line_refuses_to_spend_without_the_enable_flag(s_root: Path, tmp_path: Path) -> None:
    done = cli("--root", str(s_root), "--arm", "R6", "--out", str(tmp_path / "o"), "--run-id", "run-g-0102",
               "--call-cap", "10", "--token-cap", "1000", "--pace-seconds", "0")  # fmt: skip
    assert done.returncode == 2 and "--enable-live" in done.stderr and not (tmp_path / "o").exists()


def test_the_command_line_with_the_flag_but_no_key_refuses_without_naming_one(s_root: Path, tmp_path: Path) -> None:
    done = cli("--root", str(s_root), "--arm", "R6", "--out", str(tmp_path / "o"), "--run-id", "run-g-0103",
               "--call-cap", "10", "--token-cap", "1000", "--pace-seconds", "0", "--enable-live",
               "--env-file", str(tmp_path / "missing.env"))  # fmt: skip
    assert done.returncode == 2 and "NO_CREDENTIAL" in done.stderr and not (tmp_path / "o").exists()


def test_the_comparator_environments_and_view_are_what_the_runner_uses(s_root: Path) -> None:
    for arm, folder in (("R4", "env-HippoRAG"), ("R5", "env-graphrag"), ("R6", "env-LightRAG")):
        assert run_graph_arms.interpreter_of(arm).parts[-3] == folder
    assert PublishedView.load(s_root / "published").root == s_root / "published"
    assert Condition.C2.value == "C2"
