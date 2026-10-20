"""The label store, blinded sampling and the judge audit: a judge never overwrites a higher source (B05-T04.02)."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest
from support import make_case, perfect_response

from benchmark.eval.citations import score_citations
from benchmark.eval.judge_audit import (
    LabelError,
    LabelStore,
    Source,
    blind_id,
    disagreement_summary,
    family,
    judge_agreement,
    judge_messages,
    plan_judges,
    run_judges,
    sample_for_labelling,
)
from benchmark.eval.normalize import PublishedCorpus
from benchmark.fixtures.answer_gold import AnswerGold
from benchmark.fixtures.questions import GoldRecord

POOL = ("qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b")
KEY = ("q-1", "R2", "c1", "POL-1@v1#4.1")


def test_a_lower_source_is_recorded_but_never_becomes_the_standing_label() -> None:
    store = LabelStore()
    store.set(KEY, True, Source.DETERMINISTIC, "check")
    store.set(KEY, False, Source.HUMAN, "owner")
    store.set(KEY, False, Source.JUDGE, "openai/gpt-oss-20b")
    standing = store.current(KEY)
    assert standing is not None and standing.supported is True and standing.source is Source.DETERMINISTIC
    assert [h.source for h in store.history(KEY)] == [Source.DETERMINISTIC, Source.HUMAN, Source.JUDGE]
    assert store.labels() == {KEY: True} and store.labels(include_judge=True) == {KEY: True}
    other = ("q-1", "R2", "c2", "POL-1@v1#4.2")
    store.set(other, True, Source.HUMAN, "owner")
    store.set(other, False, Source.JUDGE, "openai/gpt-oss-20b")
    current = store.current(other)
    assert current is not None and current.supported is True and current.by == "owner"


def test_a_higher_source_after_a_judge_stands_and_the_judge_label_stays_in_the_history() -> None:
    store = LabelStore()
    store.set(KEY, False, Source.JUDGE, "openai/gpt-oss-20b")
    store.set(KEY, True, Source.HUMAN, "owner")
    standing = store.current(KEY)
    assert standing is not None and standing.supported is True and standing.source is Source.HUMAN
    assert [h.source for h in store.history(KEY)] == [Source.JUDGE, Source.HUMAN]
    assert store.disagreements() == [KEY] and disagreement_summary(store) == {"human/judge": 1}


def test_scoring_labels_leave_judge_output_out_until_the_caller_opts_in() -> None:
    store = LabelStore()
    store.set(KEY, True, Source.JUDGE, "openai/gpt-oss-20b")
    assert store.labels() == {}
    assert store.labels(include_judge=True) == {KEY: True}
    store.set(KEY, False, Source.HUMAN, "owner")
    assert store.labels() == {KEY: False} and store.labels(include_judge=True) == {KEY: False}


def test_sampling_hides_the_arm_and_the_model_and_is_seeded_and_stratified() -> None:
    candidates = [(f"q-{i:08x}", arm, f"Q{1 + i % 3}", "c1", "POL-1@v1#4.1") for i in range(12) for arm in ("R2", "R3")]
    items, key = sample_for_labelling(candidates, per_stratum=2, seed=11)
    assert len(items) == 6 and {i.stratum for i in items} == {"Q1", "Q2", "Q3"}
    packet = json.dumps([i.__dict__ for i in items])
    assert "R2" not in packet and "R3" not in packet and "q-0000" not in packet
    assert set(key) == {i.item_id for i in items} and all(arm in ("R2", "R3") for _, arm in key.values())
    again, _ = sample_for_labelling(candidates, per_stratum=2, seed=11)
    other, _ = sample_for_labelling(candidates, per_stratum=2, seed=12)
    assert [i.item_id for i in items] == [i.item_id for i in again] != [i.item_id for i in other]
    assert blind_id(11, "q-1", "R2", "c1", "x") != blind_id(11, "q-1", "R3", "c1", "x")
    with pytest.raises(LabelError):
        sample_for_labelling(candidates, per_stratum=0, seed=1)


def test_judges_are_other_models_than_the_generator_with_family_overlap_disclosed() -> None:
    plan = plan_judges(POOL, "openai/gpt-oss-120b")
    assert plan.judges == ("qwen/qwen3.8-27b", "openai/gpt-oss-20b")
    assert plan.family_overlap == ("openai/gpt-oss-20b",)
    assert plan_judges(POOL, "qwen/qwen3.8-27b").family_overlap == ()
    with pytest.raises(LabelError, match="fewer than 2"):
        plan_judges(POOL[:2], "openai/gpt-oss-120b")
    assert family("openai/gpt-oss-20b") == "openai"


class Scripted:
    def __init__(self, replies: Mapping[str, Sequence[str | None]]) -> None:
        self.replies = {k: list(v) for k, v in replies.items()}
        self.calls: list[tuple[str, list[Mapping[str, str]]]] = []

    def __call__(self, model: str, messages: Sequence[Mapping[str, str]]) -> str | None:
        self.calls.append((model, list(messages)))
        return self.replies[model].pop(0)


def test_judges_label_through_the_injected_callable_and_the_log_keeps_prompt_and_reply(tmp_path: Path) -> None:
    store = LabelStore()
    plan = plan_judges(POOL, "openai/gpt-oss-120b")
    keys = [
        (("q-1", "R2", "c1", "A#1.1"), "claim one", "span one"),
        (("q-1", "R2", "c2", "A#1.2"), "claim two", "span two"),
    ]
    complete = Scripted({"qwen/qwen3.8-27b": ["YES", "NO"], "openai/gpt-oss-20b": ["yes, it does", "maybe"]})
    log = tmp_path / "judge" / "log.jsonl"
    written = run_judges(store, plan, keys, complete, log)
    assert written == 3, "the reply that is neither YES nor NO produces no label"
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 4 and rows[0]["messages"] == judge_messages("claim one", "span one")
    assert rows[3]["reply"] == "maybe" and store.judge_label(("q-1", "R2", "c2", "A#1.2"), "openai/gpt-oss-20b") is None
    assert all(model != "openai/gpt-oss-120b" for model, _ in complete.calls)


def test_judge_prompts_cannot_be_logged_inside_a_run_directory(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    plan = plan_judges(POOL, "openai/gpt-oss-120b")
    with pytest.raises(LabelError, match="outside the run directory"):
        run_judges(LabelStore(), plan, [(KEY, "c", "s")], Scripted({}), run_dir / "judge.jsonl", run_dir=run_dir)
    assert not (run_dir / "judge.jsonl").exists()


def test_agreement_with_the_human_labels_is_reported_per_judge_with_its_denominator() -> None:
    store = LabelStore()
    for i, human in enumerate([True, True, False, False, True]):
        store.set(("q-1", "R2", f"c{i}", "D#1.1"), human, Source.HUMAN, "owner")
    for i, verdict in enumerate([True, True, False, True, False]):
        store.set(("q-1", "R2", f"c{i}", "D#1.1"), verdict, Source.JUDGE, "judge-a")
    store.set(("q-1", "R2", "c9", "D#1.1"), True, Source.JUDGE, "judge-a")  # no human label: not compared
    report = {r.judge: r for r in judge_agreement(store)}
    assert report["judge-a"].compared == 5 and report["judge-a"].agreed == 3
    assert report["judge-a"].kappa == pytest.approx(0.1666666, abs=1e-5)


def test_labels_reach_the_citation_scorer_only_as_entailment_counts(
    s_questions: tuple[GoldRecord, ...],
    s_golds: tuple[AnswerGold, ...],
    s_published_corpus: PublishedCorpus,
    s_roles: dict[str, str],
) -> None:
    record, gold = next((q, g) for q, g in zip(s_questions, s_golds, strict=True) if q.stratum.value == "Q2")
    case = make_case(record, gold, perfect_response(record, gold), role_id=s_roles[record.principal_id])
    span = record.citation_gold_spans[0]
    key = (record.question_id, "", "c1", f"{span.doc_id}#{span.clause_id}")
    store = LabelStore()
    store.set(key, True, Source.JUDGE, "judge-a")
    without = score_citations(case, s_published_corpus, store.labels())
    assert without.entailed == 0 and without.unlabelled == len(without.checks)
    assert score_citations(case, s_published_corpus, store.labels(include_judge=True)).entailed == 1


# judge audit ---------------------------------------------------------------


def test_the_latest_write_of_the_same_source_stands() -> None:
    store = LabelStore()
    store.set(KEY, True, Source.HUMAN, "owner")
    store.set(KEY, False, Source.HUMAN, "second reader")
    standing = store.current(KEY)
    assert standing is not None and standing.supported is False and standing.by == "second reader"
    reference = store.reference(KEY)
    assert reference is not None and reference.by == "second reader" and store.labels() == {KEY: False}


@pytest.mark.parametrize("reply", ["NOT SURE", "YESTERDAY", "NOTE: unclear", "", None, "perhaps yes"])
def test_a_reply_that_is_not_exactly_yes_or_no_makes_no_label(reply: str | None, tmp_path: Path) -> None:
    store = LabelStore()
    plan = plan_judges(POOL, "openai/gpt-oss-120b")
    complete = Scripted({m: [reply] for m in plan.judges})
    assert run_judges(store, plan, [(KEY, "claim", "span")], complete, tmp_path / "log.jsonl") == 0


def test_the_same_model_listed_twice_is_one_judge() -> None:
    with pytest.raises(LabelError, match="fewer than 2"):
        plan_judges(["a/x", "a/x", "a/gen"], "a/gen")


def test_two_arms_never_share_a_label_for_the_same_claim_id_and_citation(
    s_questions: tuple[GoldRecord, ...],
    s_golds: tuple[AnswerGold, ...],
    s_published_corpus: PublishedCorpus,
    s_roles: dict[str, str],
) -> None:
    from dataclasses import replace

    record, gold = next((q, g) for q, g in zip(s_questions, s_golds, strict=True) if q.stratum.value == "Q2")
    case = replace(
        make_case(record, gold, perfect_response(record, gold), role_id=s_roles[record.principal_id]), arm="R2"
    )
    span = record.citation_gold_spans[0]
    cite = f"{span.doc_id}#{span.clause_id}"
    other_arm = score_citations(case, s_published_corpus, {(record.question_id, "R3", "c1", cite): True})
    this_arm = score_citations(case, s_published_corpus, {(record.question_id, "R2", "c1", cite): True})
    assert other_arm.entailed == 0 and this_arm.entailed == 1
