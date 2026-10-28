"""Wording variants of the questions and the check that keeps them equivalent (B08-T01.02, BADR-0047)."""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest

from benchmark.generator import GenerationError
from benchmark.paraphrase import (
    SYSTEM_PROMPT,
    Outcome,
    OutcomeLog,
    ParaphraseError,
    Paraphraser,
    QuestionText,
    Verdict,
    collect,
    findings,
    judge,
)

Q1, Q2, Q3 = "q-0000000000000001", "q-0000000000000002", "q-0000000000000003"
ORIGINAL = "According to POL-004@v1, within how many hours must a request be raised?"
CODE = "What HTTP status does the gateway return for error MS-1019?"


# -- the equivalence check: a violating and a valid case for each rule -----------------------------------------------


def test_a_reworded_question_with_everything_kept_passes() -> None:
    assert findings(ORIGINAL, "In POL-004@v1, how many hours do you have to raise a request?") == ()


def test_a_lost_identifier_is_found() -> None:
    assert findings(ORIGINAL, "How many hours must a request be raised within?") == ("IDENTIFIER_LOST:pol-004@v1",)


def test_an_added_identifier_is_found() -> None:
    assert "IDENTIFIER_ADDED:pol-005" in findings(
        ORIGINAL, "Per POL-004@v1 and POL-005, how many hours to raise a request?"
    )


def test_a_changed_version_suffix_is_a_changed_identifier() -> None:
    problems = findings(ORIGINAL, "According to POL-004@v2, within how many hours must a request be raised?")
    assert "IDENTIFIER_LOST:pol-004@v1" in problems and "IDENTIFIER_ADDED:pol-004@v2" in problems


def test_a_changed_number_is_found_and_the_digits_of_an_identifier_are_not_counted_as_numbers() -> None:
    assert "NUMBER_CHANGED" in findings(
        "Is a refund over 500 allowed under MS-1019?", "Is a refund over 5000 allowed under MS-1019?"
    )
    assert (
        findings("Is a refund over 500 allowed under MS-1019?", "Under MS-1019, can a refund above 500 be given?") == ()
    )


def test_a_number_written_as_a_word_is_a_changed_number() -> None:
    assert "NUMBER_CHANGED" in findings(
        "Can it be raised within 24 hours?", "Can it be raised within twenty-four hours?"
    )


def test_a_dropped_negation_is_found() -> None:
    assert "NEGATION_CHANGED" in findings(
        "Which refunds are not allowed after 30 days?", "Which refunds are allowed after 30 days?"
    )


def test_an_added_negation_is_found() -> None:
    assert "NEGATION_CHANGED" in findings(
        "Which refunds are allowed after 30 days?", "Which refunds are not allowed after 30 days?"
    )


def test_a_negation_in_indonesian_and_a_contraction_are_read() -> None:
    assert "NEGATION_CHANGED" in findings("Apa yang tidak boleh dilakukan?", "Apa yang boleh dilakukan?")
    assert "NEGATION_CHANGED" in findings("What can't be refunded?", "What can be refunded?")
    assert findings("What can't be refunded?", "What cannot be refunded?") == ()


def test_an_empty_a_multiline_and_an_oversized_rewrite_are_refused() -> None:
    assert findings(ORIGINAL, "  ") == ("EMPTY",)
    assert "MULTILINE" in findings(ORIGINAL, "In POL-004@v1,\nhow many hours?")
    assert "TOO_LONG" in findings(ORIGINAL, "POL-004@v1 " + "how many hours " * 80)


def test_a_rewrite_that_changes_nothing_is_unchanged_not_accepted() -> None:
    assert judge(ORIGINAL, ORIGINAL) == (Verdict.UNCHANGED, ())
    assert judge(ORIGINAL, "  " + ORIGINAL.replace("According to", "ACCORDING TO") + " ")[0] is Verdict.UNCHANGED


def test_no_rewrite_at_all_is_rejected() -> None:
    assert judge(ORIGINAL, None) == (Verdict.REJECTED, ("NO_REWRITE",))


# -- the paraphraser over a scripted pool -----------------------------------------------------------------------------


@dataclass
class Reply:
    text: str | None


class ScriptedPool:
    """Answers each question id with the next scripted reply; an exception in the script is raised."""

    def __init__(self, replies: Mapping[str, object]) -> None:
        self.replies = dict(replies)
        self.calls: list[tuple[str, list[dict[str, str]], bool, int | None]] = []

    def complete(
        self,
        question_id: str,
        messages: Sequence[Mapping[str, str]],
        *,
        json_output: bool = False,
        max_completion_tokens: int | None = None,
    ) -> Reply:
        self.calls.append((question_id, [dict(m) for m in messages], json_output, max_completion_tokens))
        reply = self.replies[question_id]
        if isinstance(reply, Exception):
            raise reply
        return Reply(str(reply) if reply is not None else None)


def question(question_id: str, text: str, language: str = "en") -> QuestionText:
    return QuestionText(question_id, text, language)


def as_json(text: str) -> str:
    return json.dumps({"question": text})


def test_an_accepted_rewrite_is_recorded_with_its_model_and_the_call_asks_for_json_without_any_gold() -> None:
    pool = ScriptedPool({Q1: as_json("In POL-004@v1, how many hours do you have to raise a request?")})
    outcome = Paraphraser(pool, {Q1: "openai/gpt-oss-120b"}).rewrite(question(Q1, ORIGINAL))
    assert outcome.verdict is Verdict.ACCEPTED and outcome.model == "openai/gpt-oss-120b" and outcome.findings == ()
    asked_id, messages, json_output, cap = pool.calls[0]
    assert asked_id == Q1 and json_output is True and cap is not None and cap <= 400
    assert messages[0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert json.loads(messages[1]["content"]) == {"language": "en", "question": ORIGINAL}, "only the words and language"


def test_a_rewrite_that_loses_the_code_is_rejected_and_keeps_no_variant() -> None:
    pool = ScriptedPool({Q1: as_json("What HTTP status comes back for that gateway error?")})
    outcome = Paraphraser(pool, {}).rewrite(question(Q1, CODE))
    assert outcome.verdict is Verdict.REJECTED and outcome.findings == ("IDENTIFIER_LOST:ms-1019",)


@pytest.mark.parametrize("reply", ["not json", "[1, 2]", '{"question": 5}', '{"other": "x"}', None])
def test_a_reply_that_is_not_the_one_object_asked_for_is_rejected_not_an_error(reply: str | None) -> None:
    outcome = Paraphraser(ScriptedPool({Q1: reply}), {}).rewrite(question(Q1, CODE))
    assert outcome.verdict is Verdict.REJECTED and outcome.findings == ("NO_REWRITE",) and outcome.rewrite is None


def test_a_failed_call_is_a_failed_outcome_with_its_code() -> None:
    outcome = Paraphraser(ScriptedPool({Q1: GenerationError("PROVIDER_HTTP_500")}), {}).rewrite(question(Q1, CODE))
    assert outcome.verdict is Verdict.FAILED and outcome.findings == ("PROVIDER_HTTP_500",)


def test_a_run_logs_each_outcome_resumes_without_asking_again_and_stops_at_a_quota_stop(tmp_path: Path) -> None:
    log = OutcomeLog(tmp_path / "paraphrases.jsonl")
    good = as_json("In POL-004@v1, how many hours do you have to raise a request?")
    pool = ScriptedPool({Q1: good, Q2: GenerationError("QUOTA_BLOCKED"), Q3: good})
    questions = [question(Q1, ORIGINAL), question(Q2, ORIGINAL), question(Q3, ORIGINAL)]
    made = Paraphraser(pool, {}).run(questions, log)
    assert [o.question_id for o in made] == [Q1], "the quota stop ends the run and is not logged as an outcome"
    assert [c[0] for c in pool.calls] == [Q1, Q2], "nothing is asked after the stop"
    pool2 = ScriptedPool({Q2: good, Q3: good})
    Paraphraser(pool2, {}).run(questions, log)
    assert [c[0] for c in pool2.calls] == [Q2, Q3], "the next day asks only what the log lacks"
    assert set(log.read()) == {Q1, Q2, Q3}


def test_the_set_holds_only_accepted_rewrites_with_counts_and_a_digest_that_follows_them(tmp_path: Path) -> None:
    log = OutcomeLog(tmp_path / "p.jsonl")
    good = as_json("In POL-004@v1, how many hours do you have to raise a request?")
    pool = ScriptedPool({Q1: good, Q2: as_json(ORIGINAL), Q3: as_json("How many hours to raise a request?")})
    Paraphraser(pool, {}).run([question(q, ORIGINAL) for q in (Q1, Q2, Q3)], log)
    result = collect(log)
    assert set(result.queries) == {Q1}
    assert result.counts == {"ACCEPTED": 1, "UNCHANGED": 1, "REJECTED": 1, "FAILED": 0}
    other = OutcomeLog(tmp_path / "q.jsonl")
    Paraphraser(ScriptedPool({Q1: as_json("Under POL-004@v1, within how many hours is a request raised?")}), {}).run(
        [question(Q1, ORIGINAL)], other
    )
    assert collect(other).digest != result.digest, "a different accepted wording is a different set"


def test_a_log_line_that_is_not_an_outcome_is_refused_with_its_line_number(tmp_path: Path) -> None:
    path = tmp_path / "p.jsonl"
    OutcomeLog(path).append(Outcome(Q1, ORIGINAL, None, Verdict.REJECTED, ("NO_REWRITE",), None))
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"question_id": "oops"}\n')
    with pytest.raises(ParaphraseError, match="line 2"):
        OutcomeLog(path).read()


def test_a_question_must_have_a_pseudonymous_id_and_bounded_text() -> None:
    with pytest.raises(Exception, match="pseudonymous"):
        QuestionText("not-an-id", "text?", "en")
    with pytest.raises(ParaphraseError):
        QuestionText(Q1, "  ", "en")
    with pytest.raises(ParaphraseError):
        QuestionText(Q1, "x" * 601, "en")


# -- the command line -------------------------------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "paraphrase_questions.py"), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )


def test_the_command_line_plans_without_a_model_and_counts_what_the_log_already_holds(
    s_root: Path, tmp_path: Path
) -> None:
    first = run_script("--root", str(s_root), "--out", str(tmp_path))
    assert first.returncode == 0, first.stderr
    plan = json.loads(first.stdout)
    assert plan["questions"] == plan["to_do"] > 0 and plan["estimated_tokens"] == plan["to_do"] * 450
    known = sorted(
        json.loads(line)["question_id"]
        for line in (s_root / "annotations_dev" / "questions_smoke.jsonl").read_text(encoding="utf-8").splitlines()
    )[0]
    OutcomeLog(tmp_path / "paraphrases.jsonl").append(
        Outcome(known, ORIGINAL, None, Verdict.REJECTED, ("NO_REWRITE",), None)
    )
    assert json.loads(run_script("--root", str(s_root), "--out", str(tmp_path)).stdout)["to_do"] == plan["to_do"] - 1


def test_a_live_run_without_enablement_a_budget_and_a_cap_is_refused_and_asks_nothing(
    s_root: Path, tmp_path: Path
) -> None:
    refused = run_script("--root", str(s_root), "--out", str(tmp_path), "--generator", "live")
    assert (
        refused.returncode == 2
        and "--enable-live" in refused.stderr
        and not (tmp_path / "generation_records.jsonl").exists()
    )


def test_only_the_words_and_the_language_of_a_question_leave_the_gold_file(s_root: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    import paraphrase_questions

    found = paraphrase_questions.questions_of(s_root, "smoke")
    assert found and all(isinstance(q, QuestionText) for q in found)
    assert [q.question_id for q in found] == sorted(q.question_id for q in found)
    assert set(QuestionText.__dataclass_fields__) == {"question_id", "text", "language"}
