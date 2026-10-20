"""Session-wide fixtures: the S-tier world, corpus and pilot questions are built once and shared read-only."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from benchmark.config import FixturesConfig, load_fixtures_config
from benchmark.eval.normalize import PublishedCorpus
from benchmark.fixtures.answer_gold import AnswerGold, derive_all, write_answer_gold
from benchmark.fixtures.artifacts import build_corpus, plan_from_config
from benchmark.fixtures.documents import Document
from benchmark.fixtures.knowledge import DocumentState
from benchmark.fixtures.manifest import Split, build_records, snapshot_id, write_annotations, write_namespaces
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


@pytest.fixture(scope="session")
def s_golds(s_questions: tuple[GoldRecord, ...]) -> tuple[AnswerGold, ...]:
    return derive_all(s_questions)


@pytest.fixture(scope="session")
def s_roles(s_world: World) -> dict[str, str]:
    """Principal id to role id, the way the scorers receive it."""
    return {p.principal_id: p.role_id for p in s_world.entities.principals}


@pytest.fixture(scope="session")
def s_published(tmp_path_factory: pytest.TempPathFactory, s_world: World, s_corpus: tuple[Document, ...]) -> Path:
    """The S-tier published namespace written once to disk, the way a scorer finds it."""
    root = tmp_path_factory.mktemp("published") / "S"
    write_namespaces(root, s_world, s_corpus, SEED)
    return root / "published"


@pytest.fixture(scope="session")
def s_root(s_published: Path, s_questions: tuple[GoldRecord, ...], s_golds: tuple[AnswerGold, ...]) -> Path:
    """The snapshot root of the S-tier fixture with the smoke annotation and answer-gold files written."""
    root = s_published.parent
    write_annotations(root, Split.SMOKE, [q.to_dict() for q in s_questions])
    write_answer_gold(root, Split.SMOKE, s_golds)
    return root


@pytest.fixture(scope="session")
def s_published_corpus(s_published: Path) -> PublishedCorpus:
    return PublishedCorpus.load(s_published)


QDRANT_URL = "http://127.0.0.1:17333"


def _wsl_ubuntu() -> bool:
    if shutil.which("wsl") is None:
        return False
    listing = subprocess.run(["wsl", "-l", "-q"], capture_output=True, text=True, check=False).stdout
    return "Ubuntu" in listing.replace("\x00", "")


@pytest.fixture(scope="module")
def qdrant_server() -> Iterator[str]:
    """The benchmark's own Qdrant under WSL for the tests of one module; stopped when the module ends."""
    if not _wsl_ubuntu():
        pytest.skip("WSL Ubuntu is not available")
    script = str(Path(__file__).resolve().parents[1] / "scripts" / "qdrant_server.py")

    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["python", script, *args], capture_output=True, text=True, check=False, timeout=180)

    run("stop")
    started = run("start", "--detach")
    assert started.returncode == 0, started.stderr
    try:
        yield QDRANT_URL
    finally:
        run("stop")
