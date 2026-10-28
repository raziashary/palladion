"""R0x: R0 plus the rule that a section named by its code comes first (BADR-0047).

Palladion puts the chunk whose heading names a code in the question ahead of every other hit, because an article titled
with its code is the answer to a question about that code, while a table that merely lists the code is a mention. Plain
keyword search scores the two alike. R0x adds that one rule to R0 so the benchmark can tell how much of Palladion's
exact-code result is the rule and how much is the rest of its design.

Only the defining-first rule is mirrored. Palladion's labels for a code the corpus does not hold or the question's time
excludes, and the order of mentions after the defining chunks, are not; the arm's description says so.
"""

from __future__ import annotations

import re
from typing import Any

from benchmark.adapters.bm25 import Bm25Arm, Scored, identifiers
from benchmark.adapters.common import Chunk

_HEADING = re.compile(r"^#{1,6}[ \t].*$", re.MULTILINE)


def defines(chunk: Chunk, codes: list[str]) -> bool:
    """True when a heading line in the chunk names one of the codes as a whole identifier (as the index tokens are)."""
    named = {token for heading in _HEADING.findall(chunk.text) for token in identifiers(heading)}
    return any(code in named for code in codes)


class ExactLaneArm(Bm25Arm):
    """R0 with the chunks whose heading names a code of the query ranked first, each group by its BM25 score."""

    arm_id = "R0x"

    def rank(self, query: str, principal_id: str, eligible: frozenset[str] | None = None) -> list[Scored]:
        ranked = super().rank(query, principal_id, eligible)
        codes = identifiers(query)
        first = [s for s in ranked if codes and defines(s.chunk, codes)]
        if not first:
            return ranked
        named = {s.chunk.chunk_id for s in first}
        return first + [s for s in ranked if s.chunk.chunk_id not in named]

    def describe(self) -> dict[str, Any]:
        return {
            **super().describe(),
            "exact_lane": "a chunk whose heading names a code of the query comes first; Palladion's labels for unknown "
            "or inapplicable codes and its order of mentions are not mirrored",
        }
