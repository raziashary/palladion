"""The wall clock, and the type of any clock a run may be given instead (ADR-0101)."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

Clock = Callable[[], datetime]


def utc_clock() -> datetime:
    """The default: the real time. An evaluator run supplies a fixed instant through the registry instead."""
    return datetime.now(timezone.utc)
