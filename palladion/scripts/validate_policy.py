"""Run the real P03 domain path on isolated fictional stores; no provider or network."""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from evidence_agent.core.clock import utc_clock
from evidence_agent.core.models import PolicyDecision, PolicyDecisionStatus
from evidence_agent.live.contracts import LookupRequest, Snapshot
from evidence_agent.live.gateway import LiveGateway, load_config
from evidence_agent.live.mock import MockAdapter
from evidence_agent.policy.bootstrap import seed_policy_fixture
from evidence_agent.policy.engine import PolicyEngine
from evidence_agent.policy.registry import PolicyRegistry
from evidence_agent.storage.originals import OriginalStore
from evidence_agent.storage.registry import Registry
from evidence_agent.storage.sqlite import Database


def run(root: Path, app: Path) -> dict[str, object]:
    with Database(root / "registry.sqlite") as database:
        registry = Registry(database, OriginalStore(root / "originals"))
        seed_policy_fixture(registry, app)
        principal = registry.access.authenticate("reader-a")
        adapter = MockAdapter({
            ("get_transaction_status", "TX-DEMO-102"): (Snapshot(status="OK", data={
                "transaction_id": "TX-DEMO-102", "state": "FAILED",
                "transaction_occurred_at": "2025-06-20T11:30:00Z"}),),
            ("get_settlement_status", "SET-DEMO-102"): (Snapshot(status="OK", data={
                "settlement_id": "SET-DEMO-102", "settlement_state": "UNSETTLED"}),)})
        gateway = LiveGateway(registry, adapter, load_config(app / "config/adapters.yaml"))
        policies = PolicyRegistry(registry)
        engine = PolicyEngine(policies)

        async def reads() -> tuple[PolicyDecision, PolicyDecision, PolicyDecision]:
            transaction = await gateway.lookup(principal, LookupRequest(operation="get_transaction_status",
                case_id="case-42", target_id="TX-DEMO-102"))
            partial = engine.evaluate(principal, "case-42", "DEMO.REVERSAL.CHECK", (transaction.lookup_id,))
            assert partial.status is PolicyDecisionStatus.INCOMPLETE_INPUT
            settlement = await gateway.lookup(principal, LookupRequest(operation="get_settlement_status",
                case_id="case-42", target_id="SET-DEMO-102"))
            determined = engine.evaluate(principal, "case-42", "DEMO.REVERSAL.CHECK",
                                         (transaction.lookup_id, settlement.lookup_id))
            assert determined.status is PolicyDecisionStatus.DETERMINED
            handling = engine.evaluate(principal, "case-42", "DEMO.HANDLING")
            assert determined.version_id == "demo-reversal-2025-a"
            assert handling.version_id == "demo-handling-2026-a"
            assert engine.replay(principal, "case-42", determined.audit_id) == determined
            return partial, determined, handling
        partial, determined, handling = asyncio.run(reads())
    # Real persisted consumer after closing the producer's connection.
    with Database(root / "registry.sqlite") as database:
        registry = Registry(database, OriginalStore(root / "originals"))
        engine = PolicyEngine(PolicyRegistry(registry))
        replayed = engine.replay(registry.access.authenticate("reader-a"), "case-42", determined.audit_id)
        assert replayed == determined
    return {"status": "PASS", "missing_settlement": partial.status.value,
            "event_policy": determined.version_id, "current_handling_policy": handling.version_id,
            "outcome": determined.outcome, "reopened_trace": replayed.audit_id,
            "provider_calls": 0, "operational_writes": 0, "completed_at": utc_clock().isoformat()}


def main() -> None:
    app = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="palladion-policy-") as temporary:
        print(json.dumps(run(Path(temporary), app), indent=2))


if __name__ == "__main__":
    main()
