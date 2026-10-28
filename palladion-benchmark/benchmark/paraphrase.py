"""Wording variants of the questions, accepted only when nothing that matters changed (B08-T01.02, BADR-0047).

The benchmark's questions come from one generator, so a system tuned on them may be tuned to their phrasing. A model of
another family than the answering model (a gpt-oss model, not qwen) rewrites each question from its text alone; it is
never shown the gold, the corpus or a system's output. A rewrite is kept only when the identifiers and the numbers of
the original are all still there, the number of negation words is the same, and no identifier or number was added; a
rewrite that fails, or that changes nothing, is recorded and the template text stays the only version of that
question.

The check guards identifiers, numbers and negation words. It does not read meaning: a rewrite that flips a comparative
or drops a qualifier passes it. The variants are therefore a wording-sensitivity set scored beside the originals with
the originals' gold, and the acceptance counts and a hand read of the development set bound what they can say.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from benchmark.adapters.bm25 import identifiers
from benchmark.contracts import QUOTA_BLOCKED_CODE, ContractError, require_question_id
from benchmark.generator import GenerationError

MAX_QUESTION_CHARS = 600
MAX_GROWTH = 3.0
MAX_COMPLETION_TOKENS = 400
_WORD = re.compile(r"[^\W_]+(?:'[^\W_]+)?")
_NUMBER = re.compile(r"\d+(?:[.,:/-]\d+)*")
NEGATIONS = frozenset(
    {
        "no", "not", "never", "without", "none", "neither", "nor", "cannot", "cant", "dont", "doesnt", "isnt",
        "arent", "wont", "shouldnt", "mustnt", "tidak", "bukan", "tanpa", "belum", "jangan", "tak", "tiada",
    }
)  # fmt: skip
SYSTEM_PROMPT = (
    "You rewrite one question from a workplace knowledge base in different words. Keep its meaning exactly. Keep every "
    "code, identifier, number, date, name and every negation word unchanged and in the question. Add nothing. Keep the "
    "language (English, Indonesian or a mix of both as in the original). Reply with JSON only: "
    '{"question": "<the rewritten question>"}'
)


class ParaphraseError(ContractError):
    """A paraphrase file cannot be written, read or trusted."""


class Verdict(StrEnum):
    ACCEPTED = "ACCEPTED"
    UNCHANGED = "UNCHANGED"  # the model returned the question as it was: it tests nothing
    REJECTED = "REJECTED"  # an identifier, a number or a negation changed, or the rewrite is unusable
    FAILED = "FAILED"  # the call itself failed (a provider fault or a quota stop)


@dataclass(frozen=True)
class QuestionText:
    """What the model may see of a question: its id, its words and its language. No gold, no corpus."""

    question_id: str
    text: str
    language: str

    def __post_init__(self) -> None:
        require_question_id("question_id", self.question_id)
        if not self.text.strip() or len(self.text) > MAX_QUESTION_CHARS:
            raise ParaphraseError(f"a question is non-empty and at most {MAX_QUESTION_CHARS} characters")


@dataclass(frozen=True)
class Outcome:
    question_id: str
    original: str
    rewrite: str | None
    verdict: Verdict
    findings: tuple[str, ...]
    model: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "original": self.original,
            "rewrite": self.rewrite,
            "verdict": self.verdict.value,
            "findings": list(self.findings),
            "model": self.model,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Outcome:
        return cls(
            require_question_id("question_id", data.get("question_id")),
            str(data["original"]),
            None if data.get("rewrite") is None else str(data["rewrite"]),
            Verdict(data["verdict"]),
            tuple(str(f) for f in data.get("findings", ())),
            None if data.get("model") is None else str(data["model"]),
        )


def _normal(text: str) -> str:
    return " ".join(text.casefold().split())


def _numbers(text: str) -> Counter[str]:
    """Numbers outside identifiers: identifiers are compared whole, so their digits are not counted twice."""
    stripped = text
    for token in sorted(identifiers(text), key=len, reverse=True):
        stripped = re.sub(re.escape(token), " ", stripped, flags=re.IGNORECASE)
    return Counter(_NUMBER.findall(stripped))


def _negations(text: str) -> int:
    """How many negation words a question holds; a swap of one negation word for another keeps the count."""
    return sum(w.casefold().replace("'", "") in NEGATIONS for w in _WORD.findall(text))


def findings(original: str, rewrite: str) -> tuple[str, ...]:
    """Why a rewrite is not equivalent in the three ways this check reads; empty when it passes."""
    found: list[str] = []
    if not rewrite.strip():
        return ("EMPTY",)
    if "\n" in rewrite.strip():
        found.append("MULTILINE")
    if len(rewrite) > min(MAX_QUESTION_CHARS, max(120, int(len(original) * MAX_GROWTH))):
        found.append("TOO_LONG")
    before, after = identifiers(original), identifiers(rewrite)
    found.extend(f"IDENTIFIER_LOST:{token}" for token in before if token not in after)
    found.extend(f"IDENTIFIER_ADDED:{token}" for token in after if token not in before)
    if _numbers(original) != _numbers(rewrite):
        found.append("NUMBER_CHANGED")
    if _negations(original) != _negations(rewrite):
        found.append("NEGATION_CHANGED")
    return tuple(found)


def judge(original: str, rewrite: str | None) -> tuple[Verdict, tuple[str, ...]]:
    if rewrite is None:
        return Verdict.REJECTED, ("NO_REWRITE",)
    problems = findings(original, rewrite)
    if problems:
        return Verdict.REJECTED, problems
    if _normal(original) == _normal(rewrite):
        return Verdict.UNCHANGED, ()
    return Verdict.ACCEPTED, ()


class Reply(Protocol):
    @property
    def text(self) -> str | None: ...


class Completer(Protocol):
    """The part of the generator pool the paraphraser uses."""

    def complete(
        self,
        question_id: str,
        messages: Sequence[Mapping[str, str]],
        *,
        json_output: bool = False,
        max_completion_tokens: int | None = None,
    ) -> Reply: ...


def _rewrite_from(reply: str | None) -> str | None:
    """The ``question`` string of a reply, or None when the reply is not the one JSON object asked for."""
    try:
        body = json.loads(reply or "")
    except ValueError:
        return None
    value = body.get("question") if isinstance(body, dict) else None
    return value.strip() if isinstance(value, str) else None


class Paraphraser:
    """Rewrites questions one call each, from their text alone, and judges every rewrite."""

    def __init__(self, pool: Completer, models: Mapping[str, str]) -> None:
        self._pool = pool
        self._models = dict(models)  # question id -> the model the pool will use, recorded in the outcome

    def rewrite(self, question: QuestionText) -> Outcome:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps({"language": question.language, "question": question.text})},
        ]
        model = self._models.get(question.question_id)
        try:
            reply = self._pool.complete(
                question.question_id, messages, json_output=True, max_completion_tokens=MAX_COMPLETION_TOKENS
            )
        except GenerationError as error:
            return Outcome(question.question_id, question.text, None, Verdict.FAILED, (error.code,), model)
        rewrite = _rewrite_from(reply.text)
        verdict, problems = judge(question.text, rewrite)
        return Outcome(question.question_id, question.text, rewrite, verdict, problems, model)

    def run(self, questions: Sequence[QuestionText], log: OutcomeLog) -> list[Outcome]:
        """Rewrite each question the log lacks; stop at the first quota stop so nothing is spent past it."""
        done = log.read()
        made: list[Outcome] = []
        for question in questions:
            if question.question_id in done:
                continue
            outcome = self.rewrite(question)
            if QUOTA_BLOCKED_CODE in outcome.findings:
                break  # a model's daily limit: the rest waits for a later day and is not recorded as failed
            log.append(outcome)
            made.append(outcome)
        return made


class OutcomeLog:
    """An append-only file of outcomes, one JSON line each: a run a daily limit stopped resumes where it stopped."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def read(self) -> dict[str, Outcome]:
        if not self.path.exists():
            return {}
        found: dict[str, Outcome] = {}
        for number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            try:
                outcome = Outcome.from_dict(json.loads(line))
            except (ValueError, KeyError, TypeError, ContractError) as error:
                raise ParaphraseError(f"{self.path.name} line {number} is not a recorded outcome") from error
            found[outcome.question_id] = outcome
        return found

    def append(self, outcome: Outcome) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(outcome.to_dict(), sort_keys=True, ensure_ascii=False) + "\n")


@dataclass(frozen=True)
class ParaphraseSet:
    """The accepted rewrites of a run and the counts of every other outcome."""

    queries: Mapping[str, str]  # question id -> the accepted rewrite
    counts: Mapping[str, int]

    @property
    def digest(self) -> str:
        body = json.dumps(dict(sorted(self.queries.items())), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(body.encode("utf-8")).hexdigest()


def collect(log: OutcomeLog) -> ParaphraseSet:
    outcomes = log.read()
    counts = Counter(o.verdict.value for o in outcomes.values())
    queries = {o.question_id: o.rewrite for o in outcomes.values() if o.verdict is Verdict.ACCEPTED and o.rewrite}
    return ParaphraseSet(queries, {v.value: counts.get(v.value, 0) for v in Verdict})
