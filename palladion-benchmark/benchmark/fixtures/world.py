"""The hidden world: vocabulary, knowledge base and operations built from one seed (protocol section 4.4).

The world is evaluator-side state. Rendering (documents.py) and gold building (questions.py) read it; no arm ever does.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from benchmark.fixtures import digest_of, sha256_hex
from benchmark.fixtures.entities import WorldEntities, build_entities
from benchmark.fixtures.knowledge import KnowledgeBase, build_knowledge
from benchmark.fixtures.operations import Operations, build_operations


@dataclass(frozen=True)
class WorldScale:
    """How much of the world to generate. The S tier is the M composition divided by ten (protocol 4.2)."""

    sop_versions: int
    policy_documents: int
    conflict_pairs: int
    transactions: int
    cases: int


S_SCALE = WorldScale(sop_versions=260, policy_documents=140, conflict_pairs=4, transactions=240, cases=180)


def tier_seed(base: int, tier: str) -> int:
    """A tier's own world seed. Tiers must not share a prefix of generated families (adv-11)."""
    return int(sha256_hex(f"{base}:tier:{tier}")[:8], 16)


@dataclass(frozen=True)
class World:
    seed: int
    entities: WorldEntities
    knowledge: KnowledgeBase
    operations: Operations

    def records(self) -> Iterator[dict[str, Any]]:
        yield from self.entities.records()
        yield from self.knowledge.records()
        yield from self.operations.records()

    def digest(self) -> str:
        return digest_of({"seed": self.seed, "records": list(self.records())})


def build_world(seed: int, scale: WorldScale = S_SCALE) -> World:
    entities = build_entities(seed)
    return World(
        seed=seed,
        entities=entities,
        knowledge=build_knowledge(
            entities,
            seed,
            sop_versions=scale.sop_versions,
            policy_documents=scale.policy_documents,
            conflict_pairs=scale.conflict_pairs,
        ),
        operations=build_operations(entities, seed, transactions=scale.transactions, cases=scale.cases),
    )
