"""Deterministic fictional snapshots; injected failure sequences never call a network."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Protocol

from evidence_agent.live.contracts import LookupRequest, Snapshot


class ReadAdapter(Protocol):
    async def read(self, request: LookupRequest) -> Snapshot: ...


class MockAdapter:
    def __init__(self, snapshots: dict[tuple[str, str], tuple[Snapshot, ...]], *,
                 delay_seconds: float = 0) -> None:
        self.snapshots = dict(snapshots)
        self.delay_seconds = delay_seconds
        self.calls: dict[tuple[str, str], int] = defaultdict(int)
        self.cancelled = 0

    async def read(self, request: LookupRequest) -> Snapshot:
        key = (request.operation, request.target_id)
        sequence = self.snapshots.get(key, (Snapshot(status="NOT_FOUND"),))
        position = self.calls[key]
        self.calls[key] += 1
        try:
            await asyncio.sleep(self.delay_seconds)
        except asyncio.CancelledError:
            self.cancelled += 1
            raise
        return sequence[min(position, len(sequence) - 1)].model_copy(deep=True)
