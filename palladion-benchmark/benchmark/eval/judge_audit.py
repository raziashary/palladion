"""Blinded labelling, a label store with fixed precedence, and a judge audit (B05-T04.02, protocol 14.5, BADR-0028).

Labels about answers (does this cited span support this claim?) come from three sources with a fixed order: a
deterministic check, then a human, then a language-model judge. Every label is kept, but the standing label is the
highest source's, so a lower source can never overwrite a higher one; a judge label counts for scoring only when the
caller opts in after its agreement with the human labels has been reported with its denominators. Judges are
secondary checks: at least two judges, each a different model from the one that wrote the answer, with any family
overlap disclosed (the approved pool has only two families).

Sampling for human labelling hides the arm and the generator model behind seeded item ids; the key that maps ids back is
a separate file. Judge prompts and outputs belong in an evaluator-only folder, never in a run directory, so they cannot
reach an arm. Judge calls need the owner's authorization; every function here takes an injected ``complete`` callable.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path

from benchmark.fixtures.audit import cohens_kappa

Key = tuple[str, str, str, str]  # (question id, arm, claim id, citation)
Complete = Callable[[str, Sequence[Mapping[str, str]]], str | None]  # (judge model, messages) -> text


class LabelError(ValueError):
    """A sampling or judge setup the audit refuses."""


class Source(IntEnum):
    """Higher beats lower; a label never replaces one from a higher source."""

    JUDGE = 1
    HUMAN = 2
    DETERMINISTIC = 3


@dataclass(frozen=True)
class Label:
    key: Key
    supported: bool
    source: Source
    by: str


class LabelStore:
    """Entailment labels with their source, every write kept in the history."""

    def __init__(self) -> None:
        self._history: dict[Key, list[Label]] = {}

    def set(self, key: Key, supported: bool, source: Source, by: str) -> Label:
        """Record a label. A label from a lower source is kept in the history but never becomes the standing label."""
        label = Label(key, supported, source, by)
        self._history.setdefault(key, []).append(label)
        return label

    def history(self, key: Key) -> tuple[Label, ...]:
        return tuple(self._history.get(key, ()))

    def current(self, key: Key) -> Label | None:
        """The standing label: the highest source, the latest write among equals."""
        history = self._history.get(key)
        return max(history[::-1], key=lambda h: h.source) if history else None  # the latest among equals

    def labels(self, *, include_judge: bool = False) -> dict[Key, bool]:
        """The labels a scorer may use. A judge label is left out unless the caller opts in."""
        out: dict[Key, bool] = {}
        for key in self._history:
            standing = self.reference(key) if not include_judge else self.current(key)
            if standing is not None:
                out[key] = standing.supported
        return out

    def reference(self, key: Key) -> Label | None:
        """The standing label that is not a judge's: what judges are measured against."""
        pool = [h for h in self._history.get(key, ()) if h.source is not Source.JUDGE]
        return max(pool[::-1], key=lambda h: h.source) if pool else None

    def all_keys(self) -> list[Key]:
        return sorted(self._history)

    def judges(self) -> list[str]:
        return sorted({h.by for hist in self._history.values() for h in hist if h.source is Source.JUDGE})

    def judge_label(self, key: Key, judge: str) -> Label | None:
        mine = [h for h in self._history.get(key, ()) if h.source is Source.JUDGE and h.by == judge]
        return mine[-1] if mine else None

    def disagreements(self) -> list[Key]:
        """Keys where two sources, or two writes of one source, disagree."""
        return sorted(k for k, h in self._history.items() if len({x.supported for x in h}) > 1)


# --------------------------------------------------------------------------- blinded sampling


@dataclass(frozen=True)
class BlindItem:
    item_id: str
    stratum: str
    claim_id: str
    citation: str


def blind_id(seed: int, question_id: str, arm: str, claim_id: str, citation: str) -> str:
    digest = hashlib.sha256(f"{seed}|{question_id}|{arm}|{claim_id}|{citation}".encode()).hexdigest()
    return f"item-{digest[:12]}"


def sample_for_labelling(
    candidates: Sequence[tuple[str, str, str, str, str]], per_stratum: int, seed: int
) -> tuple[list[BlindItem], dict[str, tuple[str, str]]]:
    """Seeded, stratified sample of ``(question_id, arm, stratum, claim_id, citation)`` pairs for human labels.

    The packet holds an item id, the stratum, the claim and the citation, and nothing that names the arm or the model.
    The key maps each item id back to ``(question_id, arm)``; keep it apart from the packet.
    """
    if per_stratum < 1:
        raise LabelError("a sample takes at least one item per stratum")
    by_stratum: dict[str, list[tuple[str, str, str, str, str]]] = {}
    for candidate in candidates:
        by_stratum.setdefault(candidate[2], []).append(candidate)
    items: list[BlindItem] = []
    key: dict[str, tuple[str, str]] = {}
    for stratum in sorted(by_stratum):
        ranked = sorted(by_stratum[stratum], key=lambda c: blind_id(seed, c[0], c[1], c[3], c[4]))
        for question, arm, _, claim, citation in ranked[:per_stratum]:
            item_id = blind_id(seed, question, arm, claim, citation)
            items.append(BlindItem(item_id, stratum, claim, citation))
            key[item_id] = (question, arm)
    return items, key


# --------------------------------------------------------------------------- the judge


def family(model: str) -> str:
    """The provider family of an approved model id: the part before the slash."""
    return model.split("/", 1)[0]


@dataclass(frozen=True)
class JudgePlan:
    judges: tuple[str, ...]
    generator_model: str
    family_overlap: tuple[str, ...]  # judges from the generator's own family: disclosed, not hidden


def plan_judges(pool_models: Sequence[str], generator_model: str, *, minimum: int = 2) -> JudgePlan:
    """At least ``minimum`` judges, none the model that wrote the answer; judges of its family are named."""
    judges = tuple(dict.fromkeys(m for m in pool_models if m != generator_model))
    if len(judges) < minimum:
        raise LabelError(f"fewer than {minimum} judge models other than the generator are available")
    return JudgePlan(judges, generator_model, tuple(m for m in judges if family(m) == family(generator_model)))


def judge_messages(claim_text: str, span_text: str) -> list[dict[str, str]]:
    """The exposed judge prompt: the claim and the cited span, and nothing about the question's answer."""
    return [
        {"role": "system", "content": "You check whether a quoted passage supports a statement. Reply with YES or NO."},
        {
            "role": "user",
            "content": f"Statement: {claim_text}\n\nPassage: {span_text}\n\nDoes the passage support the statement?",
        },
    ]


def _verdict(text: str | None) -> bool | None:
    words = (text or "").strip().split()
    word = words[0].strip(".,!:;").upper() if words else ""
    return True if word == "YES" else False if word == "NO" else None


def run_judges(
    store: LabelStore,
    plan: JudgePlan,
    items: Sequence[tuple[Key, str, str]],
    complete: Complete,
    log_path: Path,
    *,
    run_dir: Path | None = None,
) -> int:
    """Ask every judge about every ``(key, claim text, span text)``; labels go to the store as judge labels.

    Prompts and outputs are written to ``log_path``, which must not lie inside a run directory. A reply that is neither
    YES nor NO is logged and produces no label. Returns the number of labels written.
    """
    if run_dir is not None and run_dir.resolve() in log_path.resolve().parents:
        raise LabelError("judge prompts must be kept outside the run directory")
    written = 0
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8", newline="\n") as log:
        for key, claim_text, span_text in items:
            messages = judge_messages(claim_text, span_text)
            for judge in plan.judges:
                reply = complete(judge, messages)
                verdict = _verdict(reply)
                log.write(json.dumps({"key": list(key), "judge": judge, "messages": messages, "reply": reply}) + "\n")
                if verdict is not None:
                    store.set(key, verdict, Source.JUDGE, judge)
                    written += 1
    return written


@dataclass(frozen=True)
class JudgeAgreement:
    judge: str
    compared: int  # keys with a human or deterministic label and this judge's label
    agreed: int
    kappa: float | None


def judge_agreement(store: LabelStore) -> list[JudgeAgreement]:
    """Each judge against the standing human or deterministic label, with the number of pairs compared."""
    report = []
    for judge in store.judges():
        theirs: list[str] = []
        ours: list[str] = []
        for key in store.all_keys():
            mine, standing = store.judge_label(key, judge), store.reference(key)
            if mine is not None and standing is not None:
                theirs.append(str(mine.supported))
                ours.append(str(standing.supported))
        agreed = sum(1 for a, b in zip(theirs, ours, strict=True) if a == b)
        report.append(JudgeAgreement(judge, len(theirs), agreed, cohens_kappa(theirs, ours) if theirs else None))
    return report


def disagreement_summary(store: LabelStore) -> dict[str, int]:
    """How many keys carry labels that disagree, by the pair of sources involved."""
    counts: Counter[str] = Counter()
    for key in store.disagreements():
        sources = sorted({h.source.name.lower() for h in store.history(key)})
        counts["/".join(sources)] += 1
    return dict(counts)
