"""P03 uses only isolated synthetic SQLite/originals and explicitly injected clocks."""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from evidence_agent.live.gateway import load_config
from evidence_agent.policy.bootstrap import seed_policy_fixture
from evidence_agent.policy.registry import PolicyRegistry
from evidence_agent.storage.originals import OriginalStore
from evidence_agent.storage.registry import Registry
from evidence_agent.storage.sqlite import Database


@pytest.fixture
def p03(tmp_path, monkeypatch):
    app = Path(__file__).resolve().parents[1]
    registered = datetime(2026, 10, 17, 7, tzinfo=timezone.utc)
    now = datetime(2026, 10, 18, 8, tzinfo=timezone.utc)
    monkeypatch.setattr("evidence_agent.storage.registry.utc_now", lambda: registered.isoformat())
    with Database(tmp_path / "registry.sqlite") as database:
        registry = Registry(database, OriginalStore(tmp_path / "originals"))
        revisions = seed_policy_fixture(registry, app, clock=lambda: registered)
        yield SimpleNamespace(registry=registry, policies=PolicyRegistry(registry, clock=lambda: now),
            admin=registry.access.authenticate("admin-a"), reader=registry.access.authenticate("reader-a"),
            uploader=registry.access.authenticate("uploader-a"), revisions=revisions,
            now=now, registered=registered, app=app, config=load_config(app / "config/adapters.yaml"))
