"""Application-owned model, scoped gateway limits and SQLite lifecycle."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from evidence_agent.agent.llm import LanguageModel
from evidence_agent.agent.loop import AgentRuntime, new_trace
from evidence_agent.agent.tools import Tools
from evidence_agent.core.fixtures import load_fixtures
from evidence_agent.core.retrieval import SearchIndex
from evidence_agent.live.contracts import AdapterConfig, Snapshot
from evidence_agent.live.gateway import LiveGateway
from evidence_agent.live.mock import MockAdapter, ReadAdapter
from evidence_agent.memory.hotcache import HotCache
from evidence_agent.memory.store import CaseStore
from evidence_agent.retrieval.evidence import RequestLedger
from evidence_agent.retrieval.graph_expand import GraphExpansion
from evidence_agent.retrieval.hybrid import HybridSearch, Ranker
from evidence_agent.settings import Settings
from evidence_agent.storage.catalog import Catalog
from evidence_agent.storage.originals import OriginalStore
from evidence_agent.storage.registry import Registry
from evidence_agent.storage.sqlite import Database


class AgentServices:
    def __init__(self, root: Path, index: SearchIndex, model: LanguageModel | None,
                 adapter: ReadAdapter, config: AdapterConfig, settings: Settings,
                 ranker: Ranker | None = None, graph: GraphExpansion | None = None) -> None:
        self.root, self.index, self.model = root, index, model
        self.adapter, self.config, self.settings, self.ranker = adapter, config, settings, ranker
        self.hotcache = HotCache()
        self.graph = graph
        self.database: Database | None = None
        self.registry: Registry | None = None
        self.gateway: LiveGateway | None = None

    def begin(self, principal_id: str, case_id: str, session_id: str | None = None) -> AgentRuntime:
        if self.database is None:
            # Created on the serving event loop; never share a sqlite connection across threads.
            self.database = Database(self.root / "registry.sqlite").open()
            self.registry = Registry(self.database, OriginalStore(self.root / "originals"))
            self.gateway = LiveGateway(self.registry, self.adapter, self.config)
        assert self.registry is not None and self.gateway is not None
        principal = self.registry.access.authenticate(principal_id)
        from evidence_agent.memory.sessions import Sessions
        session_id = Sessions(self.registry,principal,case_id).resolve(session_id)
        store = CaseStore(self.registry, principal, case_id,session_id)
        store.authorize()
        ledger = RequestLedger(HybridSearch(Catalog(self.registry), self.index, self.ranker, self.graph),
            principal, case_id, new_trace(), {k: v.max_age_seconds for k, v in self.config.operations.items()}, hotcache=self.hotcache)
        tools = Tools(ledger,self.gateway,store)
        tools.graph_required = self.settings.graph_required
        return AgentRuntime(self.model, tools, store, self.settings)

    def close(self) -> None:
        self.hotcache.clear()
        if self.database is not None:
            self.database.close()
            self.database = None
            self.registry = self.gateway = None


def configure_agent(app: FastAPI, *, model: LanguageModel | None, adapter: ReadAdapter,
                    config: AdapterConfig, settings: Settings) -> None:
    """Explicit wiring; model credentials merely existing never enable runtime calls."""
    if settings.graph_enabled != (app.state.graph is not None):
        raise ValueError("Graph treatment and explicit application wiring disagree")
    app.state.graph_required = settings.graph_required
    app.state.agent_services = AgentServices(app.state.runtime_root, app.state.index,
        model, adapter, config, settings, app.state.ranker, app.state.graph)


def fixture_adapter(app_root: Path) -> MockAdapter:
    """Explicit synthetic history projection; never connects to an operational service."""
    bundle = load_fixtures(app_root)
    cases = {c.case_id: c for c in bundle.cases}
    snapshots: dict[tuple[str, str], list[Snapshot]] = {}
    for observation in sorted(bundle.observations, key=lambda o: o.sequence):
        if observation.operation == "user_report" or observation.status == "REPORTED":
            continue
        suffix = cases[observation.case_id].transaction_id.removeprefix("TX-")
        data = dict(observation.data)
        if observation.operation == "get_transaction_status":
            target = "TX-" + suffix
        elif observation.operation == "get_settlement_status":
            target = "SET-" + suffix
            if observation.status == "OK":
                data["settlement_id"] = target
        else:
            target = "MERCHANT-" + suffix
            data = {"merchant_id": target, "result": observation.data["result"]}
        snapshot = Snapshot(status=observation.status, data=data,
            source_event_at=observation.source_event_at, data_as_of=observation.data_as_of)
        snapshots.setdefault((observation.operation, target), []).append(snapshot)
    return MockAdapter({key: tuple(value) for key, value in snapshots.items()})
