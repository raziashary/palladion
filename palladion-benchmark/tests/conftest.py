"""Session-wide fixtures: the S-tier world, corpus and pilot questions are built once and shared read-only."""

from __future__ import annotations

from pathlib import Path

import pytest

from benchmark.config import FixturesConfig, load_fixtures_config
from benchmark.fixtures.artifacts import build_corpus, plan_from_config
from benchmark.fixtures.documents import Document
from benchmark.fixtures.knowledge import DocumentState
from benchmark.fixtures.manifest import Split, build_records, snapshot_id
from benchmark.fixtures.question_gen import build_questions
from benchmark.fixtures.questions import GoldRecord
from benchmark.fixtures.world import World, build_world

CONFIGS = Path(__file__).resolve().parents[1] / "configs"
SEED = 7


@pytest.fixture(scope="session")
def s_config() -> FixturesConfig:
    return load_fixtures_config(CONFIGS / "fixtures.yaml")


@pytest.fixture(scope="session")
def s_world() -> World:
    return build_world(SEED)


@pytest.fixture(scope="session")
def s_corpus(s_world: World, s_config: FixturesConfig) -> tuple[Document, ...]:
    drafts = sum(v.state is DocumentState.DRAFT for v in s_world.knowledge.versions)
    return build_corpus(s_world, plan_from_config(s_config, 10, authoritative_drafts=drafts))


@pytest.fixture(scope="session")
def s_snapshot(s_world: World, s_corpus: tuple[Document, ...]) -> str:
    return snapshot_id(build_records(s_world, s_corpus, SEED))


@pytest.fixture(scope="session")
def s_questions(s_world: World, s_corpus: tuple[Document, ...], s_snapshot: str) -> tuple[GoldRecord, ...]:
    return build_questions(s_world, s_corpus, s_snapshot, SEED, "S", {Split.SMOKE: 10})
