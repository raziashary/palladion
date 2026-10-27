"""The registry owns one evaluation clock (ADR-0101): every layer reads it, and the default is the wall clock."""
import asyncio
import importlib.util
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from evidence_agent.agent.draft import Draft
from evidence_agent.agent.gate import release
from evidence_agent.agent.preflight import preflight
from evidence_agent.agent.services import configure_agent
from evidence_agent.core.clock import utc_clock
from evidence_agent.core.errors import PermissionDenied
from evidence_agent.live.gateway import LiveGateway
from evidence_agent.live.mock import MockAdapter
from evidence_agent.main import create_app
from evidence_agent.memory.packet import build_packet
from evidence_agent.memory.store import CaseStore, MemorySpec
from evidence_agent.policy.engine import PolicyEngine
from evidence_agent.policy.registry import PolicyRegistry
from evidence_agent.settings import Settings
from evidence_agent.storage.registry import Registry
from evidence_agent.storage.sqlite import Database

from .test_agent_budget import ScriptedModel, UnavailableIndex
from .test_gate import live_fixture

FROZEN = datetime(2040, 1, 1, 12, tzinfo=timezone.utc)


def freeze(monkeypatch, p03, instant=FROZEN):
    monkeypatch.setattr(p03.registry, "clock", lambda: instant)


def test_a_registry_reads_the_wall_clock_unless_it_is_given_another(p03):
    with Database(p03.registry.database.path) as database:
        registry = Registry(database, p03.registry.originals)
        assert registry.clock is utc_clock
        assert abs((registry.clock() - datetime.now(timezone.utc)).total_seconds()) < 5
        fixed = Registry(database, p03.registry.originals, lambda: FROZEN)
        assert fixed.clock() == FROZEN


def test_the_continuity_packet_and_preflight_carry_the_registry_time(p03, monkeypatch):
    freeze(monkeypatch, p03)
    store = CaseStore(p03.registry, p03.reader, "case-42")
    assert build_packet(store, "follow up").generated_at == FROZEN
    for include_memory in (True, False):
        stamped = datetime.fromisoformat(preflight("follow up", store, include_memory=include_memory)["packet"]["generated_at"])
        assert stamped == FROZEN


def test_memory_validity_is_judged_against_the_registry_time(p03, monkeypatch):
    memory = CaseStore(p03.registry, p03.reader, "case-42").memory()
    soon = datetime.now(timezone.utc) + timedelta(days=30)
    kept = memory.write(MemorySpec(scope_id="reader-a", content="debit reported", valid_until=soon))
    assert memory.read(kept)["content"] == "debit reported"
    freeze(monkeypatch, p03)  # the year 2040: the validity ended long ago
    with pytest.raises(PermissionDenied):
        memory.read(kept)
    with pytest.raises(ValueError):
        memory.write(MemorySpec(scope_id="reader-a", content="late", valid_until=soon))


def test_memory_recall_selects_by_the_registry_time_not_the_wall_clock(p03, monkeypatch):
    memory = CaseStore(p03.registry, p03.reader, "case-42").memory()
    freeze(monkeypatch, p03)  # the year 2040, later than the real date
    start = FROZEN - timedelta(days=1)  # valid from a day before the registry instant, long after the wall clock
    later = memory.write(MemorySpec(scope_id="reader-a", content="debit reported", valid_from=start))
    assert later in [item["memory_id"] for item in memory.recall()]


def test_live_evidence_is_fresh_or_stale_by_the_registry_time_not_the_wall_clock(p03, monkeypatch):
    freeze(monkeypatch, p03)
    fixture, identifier, claim = live_fixture(p03)
    assert fixture.ledger.envelopes[identifier].occurred_at == FROZEN
    assert len(release(Draft(claims=(claim,)), fixture.ledger)["verified_claims"]) == 1
    freeze(monkeypatch, p03, FROZEN + timedelta(days=1))
    assert release(Draft(claims=(claim,)), fixture.ledger)["verified_claims"] == []


def test_the_gateway_and_the_policy_engine_default_to_the_registry_clock_and_honour_an_explicit_one(p03, monkeypatch):
    freeze(monkeypatch, p03)
    assert LiveGateway(p03.registry, MockAdapter({}), p03.config).clock() == FROZEN
    assert PolicyEngine(PolicyRegistry(p03.registry)).clock() == FROZEN
    other = FROZEN + timedelta(hours=1)
    assert LiveGateway(p03.registry, MockAdapter({}), p03.config, clock=lambda: other).clock() == other
    assert PolicyEngine(PolicyRegistry(p03.registry, clock=lambda: other)).clock() == other


def test_an_application_given_a_clock_builds_its_registry_with_it(p03):
    root = Path(p03.registry.database.path).parent
    app = create_app(root, UnavailableIndex(), {"reader-test": "reader-a"}, clock=lambda: FROZEN)
    configure_agent(app, model=ScriptedModel([]), adapter=MockAdapter({}), config=p03.config, settings=Settings())
    with TestClient(app) as client:
        response = client.post("/v1/cases/case-42/messages", headers={"Authorization": "Bearer reader-test"},
                               json={"query": "hello"})
        assert response.status_code == 200, response.text
        assert app.state.agent_services.registry.clock() == FROZEN


# --------------------------------------------------------------------------- the launcher option


def load_serve():
    spec = importlib.util.spec_from_file_location("serve_script_clock", Path(__file__).parents[1] / "scripts/serve.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BASE = ["--enable-live-llm", "--acknowledge-not-serving", "--evaluator-arm", "B6"]


def test_the_launcher_fixes_the_time_only_for_an_evaluator_run():
    serve = load_serve()
    args, _ = serve.parse_args([*BASE, "--evaluation-time", "2026-10-18T03:00:00Z"])
    assert serve.evaluation_clock(args)() == datetime(2026, 10, 18, 3, tzinfo=timezone.utc)
    assert serve.evaluation_clock(serve.parse_args([])[0]) is utc_clock


@pytest.mark.parametrize("argv", [
    ["--evaluation-time", "2026-10-18T03:00:00Z"],
    [*BASE, "--evaluation-time", "2026-10-18T03:00:00"],
    [*BASE, "--evaluation-time", "yesterday"],
])
def test_the_launcher_refuses_a_fixed_time_without_an_evaluator_arm_or_without_an_offset(argv):
    with pytest.raises(SystemExit) as caught:
        load_serve().parse_args(argv)
    assert caught.value.code == 2


def test_two_requests_at_different_real_times_see_the_same_instant(p03):
    """The frozen clock does not move: the same evaluation time at two moments of real time."""
    serve = load_serve()
    args, _ = serve.parse_args([*BASE, "--evaluation-time", "2026-10-18T03:00:00Z"])
    clock = serve.evaluation_clock(args)
    first = clock()
    asyncio.run(asyncio.sleep(0.02))
    assert clock() == first == datetime(2026, 10, 18, 3, tzinfo=timezone.utc)
    assert json.dumps(first.isoformat()) == '"2026-10-18T03:00:00+00:00"'


@pytest.mark.skipif(not os.environ.get("PALLADION_TEST_QDRANT_URL"),
                    reason="Explicit local Qdrant integration enablement required")
def test_the_search_subprocess_is_told_the_registry_instant(p03, monkeypatch):
    from evidence_agent.agent.search_worker import worker_payload
    from evidence_agent.retrieval.hybrid import HybridSearch
    from evidence_agent.storage.applicability import Applicability
    from evidence_agent.storage.catalog import Catalog
    from evidence_agent.storage.qdrant import QdrantIndex

    index = QdrantIndex(url=os.environ["PALLADION_TEST_QDRANT_URL"], collection_name="clock_" + uuid.uuid4().hex)
    try:
        owner = HybridSearch(Catalog(p03.registry), index)
        freeze(monkeypatch, p03)
        earlier = FROZEN - timedelta(days=30)
        payload = worker_payload(owner, "reader-a", "case-42", "query", "hybrid", 3, False,
                                 Applicability.at(FROZEN, [earlier]))
        assert datetime.fromisoformat(payload["as_of"]) == FROZEN and payload["also_at"] == [earlier.isoformat()]
    finally:
        index.close()
