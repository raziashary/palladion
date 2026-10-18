"""Bounded exact-passage cache; canonical validation precedes every hit."""
from __future__ import annotations

import copy
import hashlib
import json
import time
from collections import OrderedDict
from typing import Any, Callable

from evidence_agent.core.models import Principal


class HotCache:
    def __init__(self, *, capacity: int = 32, ttl_seconds: float = 120,
                 clock: Callable[[], float] = time.monotonic) -> None:
        if not 1 <= capacity <= 128 or not 0 < ttl_seconds <= 600:
            raise ValueError("Cache bounds exceeded")
        self.capacity, self.ttl, self.clock = capacity, ttl_seconds, clock
        self.entries: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()
        self.hits = self.misses = 0
        self.contexts: dict[tuple[str, str], str] = {}

    def clear(self) -> None:
        self.entries.clear()
        self.contexts.clear()

    def read(self, loader: Callable[[], dict[str, Any]], *, principal: Principal,
             case_id: str, epoch: str, temporal_key: str = "current") -> dict[str, Any]:
        context = (principal.principal_id, case_id)
        if self.contexts.get(context) != epoch:
            self.clear()
            self.contexts[context] = epoch
        try:
            current = loader()  # ACL, generation, validity, bytes and revocation checked even on a hit.
        except BaseException:
            self.clear()
            raise
        if current["kind"] != "DOCUMENT" or len(str(current.get("text", "")).encode()) > 4096:
            return current
        now = self.clock()
        for old in list(self.entries):
            if now - self.entries[old][0] >= self.ttl:
                del self.entries[old]
        material = [principal.model_dump(mode="json"), case_id, epoch, temporal_key,
            current["content_sha256"], current["evidence_id"], current["generation"]]
        key = hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()
        cached = self.entries.pop(key, None)
        if cached and cached[1] == current:
            self.hits += 1
            self.entries[key] = cached  # Hits do not extend TTL.
            return copy.deepcopy(cached[1])
        self.misses += 1
        self.entries[key] = (now, copy.deepcopy(current))
        while len(self.entries) > self.capacity:
            self.entries.popitem(last=False)
        return current
