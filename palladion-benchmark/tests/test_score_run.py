"""The score-run driver, run through the real Runner with control arms and an injected registry (B03-T07.01)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from benchmark.config import RetryPolicy, load_evaluation_config
from benchmark.contracts import ArmUnavailable, CacheCondition, ContractError, RetrievalRequest, RunStatus, Track
from benchmark.eval.evidence_sets import citable_slots
from benchmark.eval.normalize import PublishedCorpus
from benchmark.eval.retrieval import RETRIEVAL_METRICS
from benchmark.eval.score_run import (
    CONTROL_EMPTY,
    CONTROL_IDS,
    CONTROL_PERFECT,
    CONTROL_SHUFFLED,
    HARM_METRICS,
    INVALID_PAYLOAD,
    ControlArm,
    PairScore,
    RunScore,
    ScoreRunError,
    Separation,
    control_arms,
    control_registry,
    control_separation,
    gold_digest,
    retrieval_request,
    score_run,
)
from benchmark.fixtures.manifest import Split, manifest_digest, write_annotations
from benchmark.fixtures.questions import GoldRecord
from benchmark.fixtures.world import World
from benchmark.registry import default_registry
from benchmark.run_manifest import RunManifest, TreeState, read_verified
from benchmark.runner import (
    ArmBinding,
    LedgerRecord,
    PlanRegistry,
    RunLedger,
    Runner,
    RunnerCase,
    RunnerError,
    RunnerSettings,
)

CONFIGS = Path(__file__).resolve().parents[1] / "configs"
RUN_ID = "run-0001"
K = 10
SETTINGS = RunnerSettings(
    order_seed=11,
    case_deadline_seconds=5.0,
    run_deadline_seconds=None,
    retry=RetryPolicy(max_attempts=2, base_backoff_seconds=1.0),
)
REASONS = {
    k: "not applicable in this test"
    for k in (
        "system_under_test",
        "container_image_digest",
        "method_version",
        "prompt_digest",
        "pricing_snapshot",
        "generator_assignment_sha256",
    )
}


class DownArm(ControlArm):
    """A control that cannot be reached, to give the ledger a non-completed state."""

    def retrieve(self, request: RetrievalRequest) -> list[Any]:
        raise ArmUnavailable("the service is down")


def write_manifest(
    path: Path, arm: str, gold_sha256: str, source_sha256: str, retrieval_config: dict[str, int] | None = None
) -> None:
    RunManifest(
        run_id=RUN_ID,
        track=Track.RETRIEVAL_ONLY,
        arm=arm,
        split="pilot",
        source_manifest_sha256=source_sha256,
        question_manifest_sha256="b" * 64,
        gold_manifest_sha256=gold_sha256,
        benchmark=TreeState("benchmark", "1" * 40, "d" * 64, ()),
        system_under_test=None,
        container_image_digest=None,
        method_version=None,
        model_versions={},
        retrieval_config={"k": K} if retrieval_config is None else retrieval_config,
        prompt_digest=None,
        hardware={},
        pricing_snapshot=None,
        seed=1,
        order_seed=SETTINGS.order_seed,
        cache_condition=CacheCondition.COLD,
        started_at_utc="2026-10-18T03:00:00Z",
        retry_policy=SETTINGS.retry_policy_dict(),
        generator_assignment_sha256=None,
        confirmatory=False,
        null_reasons=REASONS,
    ).write(path)


class Run:
    """A finished control run on disk, and everything needed to score it."""

    def __init__(
        self, tmp: Path, questions: tuple[GoldRecord, ...], corpus: PublishedCorpus, published: Path, world: World
    ) -> None:
        self.tmp = tmp
        self.questions = questions
        self.published = published
        self.gold_path = write_annotations(tmp / "gold", Split.SMOKE, [q.to_dict() for q in questions])
        self.gold_sha = gold_digest(self.gold_path)
        self.source_sha = manifest_digest(published)
        self.roles = {p.principal_id: p.role_id for p in world.entities.principals}
        self.kinds = load_evaluation_config(CONFIGS / "evaluation.yaml").slot_kinds
        self.ledger_path = tmp / "ledger.jsonl"
        self.manifests = {arm: tmp / f"manifest-{arm}.json" for arm in CONTROL_IDS}
        self.arms: dict[str, ControlArm] = dict(control_arms(questions, corpus))

    def execute(self, arms: dict[str, ControlArm] | None = None) -> None:
        chosen = arms or self.arms
        for arm in chosen:
            write_manifest(self.manifests[arm], arm, self.gold_sha, self.source_sha)
        runner = Runner(
            RUN_ID,
            SETTINGS,
            [ArmBinding(arm, adapter, self.manifests[arm]) for arm, adapter in chosen.items()],
            RunLedger(self.ledger_path),
            PlanRegistry(self.tmp / "plans.jsonl"),
            control_registry(),
            sleep=lambda _seconds: None,
        )
        cases = [RunnerCase(retrieval_request(q, limit=K, max_evidence_tokens=4000)) for q in self.questions]
        runner.run(cases, split="pilot")

    def score(self, manifests: dict[str, Path] | None = None, withdrawn: dict[str, str] | None = None) -> RunScore:
        used = manifests or {arm: self.manifests[arm] for arm in {r.arm for r in RunLedger(self.ledger_path).records}}
        return score_run(
            ledger_path=self.ledger_path,
            manifests=used,
            gold_path=self.gold_path,
            published_dir=self.published,
            roles=self.roles,
            kinds=self.kinds,
            k=K,
            withdrawn=withdrawn,
        )


@pytest.fixture
def run(
    tmp_path: Path,
    s_questions: tuple[GoldRecord, ...],
    s_published_corpus: PublishedCorpus,
    s_published: Path,
    s_world: World,
) -> Run:
    return Run(tmp_path, s_questions, s_published_corpus, s_published, s_world)


def by_arm(score: RunScore, arm: str) -> dict[str, PairScore]:
    return {p.question_id: p for p in score.arm_pairs(arm)}


# --------------------------------------------------------------------------- controls


def test_the_three_controls_separate_where_evidence_exists(run: Run) -> None:
    run.execute()
    score = run.score()
    assert score.arms == sorted(CONTROL_IDS)
    perfect, empty, shuffled = (by_arm(score, a) for a in (CONTROL_PERFECT, CONTROL_EMPTY, CONTROL_SHUFFLED))
    with_evidence = {q.question_id for q in run.questions if citable_slots(q)}
    assert len(with_evidence) >= 5
    for q in with_evidence:
        assert perfect[q].metrics["complete_set_at_k"] == 1.0
        assert perfect[q].metrics["slot_coverage_at_k"] == 1.0
        assert empty[q].metrics["complete_set_at_k"] == 0.0
        assert empty[q].metrics["slot_coverage_at_k"] == 0.0
        assert perfect[q].metrics["mrr"] == 1.0 and empty[q].metrics["mrr"] == 0.0

    def mean(arm: dict[str, PairScore], metric: str) -> float:
        return sum(arm[q].metrics[metric] for q in with_evidence) / len(with_evidence)

    assert mean(shuffled, "complete_set_at_k") < mean(perfect, "complete_set_at_k")
    assert mean(shuffled, "slot_coverage_at_k") < mean(perfect, "slot_coverage_at_k")
    assert mean(shuffled, "slot_coverage_at_k") >= mean(empty, "slot_coverage_at_k")


def test_controls_coincide_where_no_evidence_exists(run: Run) -> None:
    run.execute()
    score = run.score()
    perfect, empty = by_arm(score, CONTROL_PERFECT), by_arm(score, CONTROL_EMPTY)
    without = {q.question_id for q in run.questions if not citable_slots(q)}
    assert without, "the fixture should contain questions with no citable evidence"
    for q in without:
        assert perfect[q].metrics == empty[q].metrics, "perfect and empty are not distinguishable without evidence"
        assert "complete_set_at_k" not in perfect[q].applicable


def test_every_ledger_final_becomes_a_pair_with_a_state_or_a_score(run: Run) -> None:
    run.execute()
    score = run.score()
    finals = [r for r in score.ledger_records if r.is_final]
    assert len(score.pairs) == len(finals) == len(CONTROL_IDS) * len(run.questions)
    assert all(p.status is RunStatus.OK and p.metrics for p in score.pairs)
    assert set(score.pairs[0].metrics) <= set(RETRIEVAL_METRICS)
    assert set(RETRIEVAL_METRICS) >= HARM_METRICS


def test_a_withdrawn_question_leaves_the_scored_pairs_but_stays_on_the_result(run: Run) -> None:
    run.execute()
    gone = run.questions[0].question_id
    score = run.score(withdrawn={gone: "gold defect"})
    assert len(score.pairs) == len(CONTROL_IDS) * (len(run.questions) - 1)
    assert gone not in {p.question_id for p in score.pairs}
    assert score.withdrawn == {gone: "gold defect"}
    assert gone in {r.question_id for r in score.ledger_records}, "it still ran; only the scoring leaves it out"
    assert run.score().withdrawn == {} and len(run.score().pairs) == len(CONTROL_IDS) * len(run.questions)


def test_a_withdrawn_id_that_is_not_in_the_gold_stops_the_scorer(run: Run) -> None:
    run.execute()
    with pytest.raises(ScoreRunError, match="not in the gold"):
        run.score(withdrawn={"q-0000000000000000": "typo"})


def test_a_non_completed_pair_is_a_state_with_no_values(run: Run) -> None:
    arms: dict[str, ControlArm] = {CONTROL_PERFECT: run.arms[CONTROL_PERFECT], CONTROL_EMPTY: DownArm({})}
    run.execute(arms)
    score = run.score()
    down = score.arm_pairs(CONTROL_EMPTY)
    assert len(down) == len(run.questions)
    for pair in down:
        assert pair.status is RunStatus.NOT_RUN and pair.metrics == {} and pair.code == "ARM_UNAVAILABLE"
    target = next(p for p in down if "complete_set_at_k" in p.applicable)
    assert target.metrics == {}, "the pair still shows what it owed through `applicable`, not through a zero"


def test_the_controls_never_enter_the_production_registry() -> None:
    assert set(control_registry().ids()) == set(CONTROL_IDS)
    assert not set(default_registry().ids()) & set(CONTROL_IDS)


def test_a_runner_given_the_production_registry_refuses_the_controls(run: Run) -> None:
    write_manifest(run.manifests[CONTROL_PERFECT], CONTROL_PERFECT, run.gold_sha, run.source_sha)
    runner = Runner(
        RUN_ID,
        SETTINGS,
        [ArmBinding(CONTROL_PERFECT, run.arms[CONTROL_PERFECT], run.manifests[CONTROL_PERFECT])],
        RunLedger(run.ledger_path),
        PlanRegistry(run.tmp / "plans.jsonl"),
        default_registry(),
    )
    with pytest.raises(RunnerError, match="not in the registry"):
        runner.run(
            [RunnerCase(retrieval_request(q, limit=K, max_evidence_tokens=4000)) for q in run.questions], split="pilot"
        )


# --------------------------------------------------------------------------- the scorer stops on inconsistent runs


def test_a_ledger_hole_stops_the_scorer(run: Run) -> None:
    run.execute()
    lines = run.ledger_path.read_text(encoding="utf-8").splitlines()
    run.ledger_path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    with pytest.raises(RunnerError, match="ledger is not complete"):
        run.score()


def test_a_gold_digest_mismatch_stops_the_scorer(run: Run) -> None:
    run.execute()
    first, *rest = run.gold_path.read_text(encoding="utf-8").splitlines()
    record = json.loads(first)
    record["query"] = record["query"] + " (edited)"
    run.gold_path.write_text("\n".join([json.dumps(record, sort_keys=True), *rest]) + "\n", encoding="utf-8")
    with pytest.raises(ScoreRunError, match="different gold file"):
        run.score()


def test_a_manifest_for_another_arm_stops_the_scorer(run: Run) -> None:
    run.execute()
    swapped = {
        **run.manifests,
        CONTROL_PERFECT: run.manifests[CONTROL_EMPTY],
        CONTROL_EMPTY: run.manifests[CONTROL_PERFECT],
    }
    with pytest.raises(ScoreRunError, match="different arm"):
        run.score(swapped)


def test_arms_without_a_manifest_stop_the_scorer(run: Run) -> None:
    run.execute()
    with pytest.raises(ScoreRunError, match="do not match the ledger's arms"):
        run.score({CONTROL_PERFECT: run.manifests[CONTROL_PERFECT]})


def test_a_ledger_that_does_not_match_the_manifest_stops_the_scorer(run: Run) -> None:
    run.execute()
    lines = run.ledger_path.read_text(encoding="utf-8").splitlines()
    rewritten = []
    for line in lines:
        data = json.loads(line)
        if data["arm"] == CONTROL_PERFECT:
            data["manifest_sha256"] = "9" * 64
        rewritten.append(json.dumps(data, sort_keys=True))
    run.ledger_path.write_text("\n".join(rewritten) + "\n", encoding="utf-8")
    with pytest.raises(ScoreRunError, match="do not match its manifest"):
        run.score()


def test_an_unreadable_payload_is_an_invalid_pair_not_a_dropped_one(run: Run) -> None:
    write_manifest(run.manifests[CONTROL_PERFECT], CONTROL_PERFECT, run.gold_sha, run.source_sha)
    digest = read_verified(run.manifests[CONTROL_PERFECT]).digest()
    ledger = RunLedger(run.ledger_path)
    for q in run.questions:
        ledger.append(
            LedgerRecord(
                RUN_ID, digest, CONTROL_PERFECT, q.question_id, 1, True, RunStatus.OK, None, None,
                "2026-10-18T03:00:00Z", 12.0, RunStatus.OK, 1, {"not": "a candidate list"},
            )
        )  # fmt: skip
    score = run.score()
    assert {p.status for p in score.pairs} == {RunStatus.INVALID_RUN}
    assert {p.code for p in score.pairs} == {INVALID_PAYLOAD}
    assert len(score.pairs) == len(run.questions)


def test_the_shuffled_control_needs_two_questions(
    s_questions: tuple[GoldRecord, ...], s_published_corpus: PublishedCorpus
) -> None:
    with pytest.raises(ScoreRunError):
        control_arms(s_questions[:1], s_published_corpus)


def test_a_principal_without_a_role_stops_the_scorer(run: Run) -> None:
    run.execute()
    run.roles.pop(run.questions[0].principal_id)
    with pytest.raises(ScoreRunError, match="no role"):
        run.score()


def test_the_controls_are_not_given_gold_through_the_request(run: Run) -> None:
    request = retrieval_request(run.questions[0], limit=K, max_evidence_tokens=4000)
    names = set(request.__dataclass_fields__)
    assert not names & {"answerability", "slots", "minimal_sets", "citation_gold_spans", "split"}
    with pytest.raises(ContractError):
        RetrievalRequest(**{**request.__dict__, "filters": {"slots": ["x"]}})


def test_controls_are_reported_separated_or_not_per_stratum(run: Run) -> None:
    run.execute()
    rows = control_separation(run.score())
    assert all(isinstance(r, Separation) for r in rows)
    by_stratum = {r.stratum: r for r in rows}
    with_evidence = {q.stratum.value for q in run.questions if citable_slots(q)}
    assert with_evidence
    for stratum in with_evidence:
        row = by_stratum[stratum]
        assert row.questions > 0 and row.perfect_vs_empty, "perfect and empty must differ where evidence exists"
    for row in rows:
        if row.questions == 0:
            assert not row.perfect_vs_empty and not row.perfect_vs_shuffled


def test_a_published_document_edited_after_the_run_stops_the_scorer(run: Run, tmp_path: Path) -> None:
    run.execute()
    copy = tmp_path / "published-copy"
    shutil.copytree(run.published, copy)
    victim = next(copy.glob("**/*.md"))
    victim.write_text(victim.read_text(encoding="utf-8") + "\nEdited after indexing.\n", encoding="utf-8")
    run.published = copy
    with pytest.raises(ScoreRunError, match="does not match its manifest"):
        run.score()


def test_a_manifest_written_against_another_corpus_stops_the_scorer(run: Run) -> None:
    run.execute()
    other = run.tmp / "manifest-other-corpus.json"
    write_manifest(other, CONTROL_EMPTY, run.gold_sha, "e" * 64)
    with pytest.raises(ScoreRunError, match="different published corpus"):
        run.score({**run.manifests, CONTROL_EMPTY: other})


def test_a_run_scored_at_another_k_stops_the_scorer(run: Run) -> None:
    run.execute()
    with pytest.raises(ScoreRunError, match="scored at K=5"):
        score_run(
            ledger_path=run.ledger_path,
            manifests=run.manifests,
            gold_path=run.gold_path,
            published_dir=run.published,
            roles=run.roles,
            kinds=run.kinds,
            k=5,
        )


def test_a_manifest_that_does_not_record_k_stops_the_scorer(run: Run) -> None:
    run.execute()
    bare = run.tmp / "manifest-no-k.json"
    write_manifest(bare, CONTROL_EMPTY, run.gold_sha, run.source_sha, retrieval_config={})
    with pytest.raises(ScoreRunError, match="records K=None"):
        run.score({**run.manifests, CONTROL_EMPTY: bare})
