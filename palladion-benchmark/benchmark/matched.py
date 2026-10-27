"""Matched lists, frozen before the first spend (BADR-0044, B08-T08.09).

A comparison is only a comparison if every system answers the same questions and episodes. The lists are chosen once,
written with their digest, and never rewritten; each run then checks the ids it is about to ask against the frozen
list and records the list's digest, so a run that drifted from the list is refused before it spends anything.

The file holds ids and, for Track B, the model each question is assigned to (one model per question across all arms,
BADR-0008). It holds no gold.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from benchmark.contracts import ContractError, require_question_id

MAX_LIST = 10_000


class MatchedListError(ContractError):
    """The frozen lists cannot be written, read or trusted."""


def _digest(body: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class MatchedLists:
    seed: int
    lists: Mapping[str, tuple[str, ...]]  # name -> sorted ids (question ids, episode ids or mutation ids)
    assignment: Mapping[str, str]  # question id -> the model every arm uses for it (Track B)

    def __post_init__(self) -> None:
        for name, ids in self.lists.items():
            if not name or len(ids) > MAX_LIST or list(ids) != sorted(set(ids)):
                raise MatchedListError(f"list {name!r} must hold sorted, distinct ids")
        for question, model in self.assignment.items():
            require_question_id("assigned question", question)
            if not model:
                raise MatchedListError("an assignment names a model")

    def body(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "lists": {name: list(ids) for name, ids in sorted(self.lists.items())},
            "assignment": dict(sorted(self.assignment.items())),
        }

    @property
    def digest(self) -> str:
        return _digest(self.body())

    def require(self, name: str, ids: Sequence[str]) -> None:
        """Refuse a run whose ids are not exactly the frozen list's."""
        if name not in self.lists:
            raise MatchedListError(f"the frozen lists have no list {name!r}")
        asked, frozen = sorted(set(ids)), list(self.lists[name])
        if asked != frozen:
            missing, extra = sorted(set(frozen) - set(asked)), sorted(set(asked) - set(frozen))
            raise MatchedListError(
                f"the run's {name} list is not the frozen one: {len(missing)} missing, {len(extra)} not on the list"
            )


def freeze(path: Path, lists: MatchedLists) -> str:
    """Write the lists once; a second write, even of the same lists, is refused. Returns the digest."""
    document = {"matched": lists.body(), "sha256": lists.digest}
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(document, sort_keys=True, indent=2) + "\n")
    except FileExistsError:
        raise MatchedListError(f"{path.name} already exists; frozen lists are never rewritten") from None
    return lists.digest


def load(path: Path) -> MatchedLists:
    """Read frozen lists and verify the digest written with them."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        body = document["matched"]
        lists = MatchedLists(
            int(body["seed"]),
            {name: tuple(ids) for name, ids in body["lists"].items()},
            dict(body["assignment"]),
        )
        recorded = document["sha256"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise MatchedListError(f"{path.name} is not a readable frozen list") from exc
    if recorded != lists.digest:
        raise MatchedListError(f"{path.name} was changed after it was frozen")
    return lists
