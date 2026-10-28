"""The UI's own small memory: past conversations and the documents it uploaded. Palladion stays the authority.

Nothing here is evidence. A stored answer is a record of what was shown, and its citations are re-read from
Palladion whenever someone opens them.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

MAX_MESSAGES = 200


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.RLock()
        self._data: dict[str, Any] = {"sessions": {}, "sources": {}}
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self._data = {"sessions": loaded.get("sessions", {}), "sources": loaded.get("sources", {})}
            except (OSError, ValueError):
                # A damaged file must not stop the UI; it is kept aside for inspection and a fresh one starts.
                os.replace(path, path.with_suffix(f".damaged-{int(time.time())}"))

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self._data, indent=1), encoding="utf-8")
        os.replace(temporary, self.path)

    # Sessions -------------------------------------------------------------------------------------------------

    def add_session(self, persona: str, case_id: str, session_id: str, title: str = "New session") -> dict[str, Any]:
        with self._lock:
            record = {"id": session_id, "persona": persona, "case_id": case_id, "title": title,
                      "created_at": now(), "updated_at": now(), "closed": False, "messages": []}
            self._data["sessions"][session_id] = record
            self._save()
            return record

    def session(self, persona: str, session_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._data["sessions"].get(session_id)
            return record if record and record["persona"] == persona else None

    def sessions(self, persona: str, case_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            found = [s for s in self._data["sessions"].values()
                     if s["persona"] == persona and (case_id is None or s["case_id"] == case_id)]
            found.sort(key=lambda s: s["updated_at"], reverse=True)
            return [{k: v for k, v in s.items() if k != "messages"} | {"message_count": len(s["messages"])}
                    for s in found]

    def append_message(self, persona: str, session_id: str, message: dict[str, Any]) -> None:
        with self._lock:
            record = self.session(persona, session_id)
            if record is None:
                return
            message = {"id": uuid.uuid4().hex[:12], "at": now(), **message}
            record["messages"] = (record["messages"] + [message])[-MAX_MESSAGES:]
            record["updated_at"] = now()
            if record["title"] == "New session" and message.get("role") == "user":
                text = " ".join(str(message.get("text", "")).split())
                record["title"] = (text[:48] + "…") if len(text) > 48 else text or record["title"]
            self._save()

    def close_session(self, persona: str, session_id: str) -> None:
        with self._lock:
            record = self.session(persona, session_id)
            if record is not None:
                record["closed"] = True
                self._save()

    # Documents uploaded through the UI -------------------------------------------------------------------------

    def remember_source(self, entry: dict[str, Any]) -> None:
        with self._lock:
            self._data["sources"][entry["revision_id"]] = {**self._data["sources"].get(entry["revision_id"], {}),
                                                         **entry}
            self._save()

    def source(self, revision_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._data["sources"].get(revision_id)

    def sources_for_case(self, case_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(e) for e in self._data["sources"].values() if e.get("case_id") == case_id]

    def family_owner(self, case_id: str, family_id: str) -> str | None:
        """Palladion binds a document family to the owner of its first revision; later revisions must match."""
        with self._lock:
            for entry in self._data["sources"].values():
                if entry.get("case_id") == case_id and entry.get("family_id") == family_id:
                    return entry.get("owner_id")
            return None
