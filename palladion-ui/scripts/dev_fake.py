"""Run the UI against the fake Palladion: no model, no Qdrant, no quota. For looking at screens and for browser tests.

    uv run python -m scripts.dev_fake          # UI on http://127.0.0.1:8766, fake Palladion on 18481
"""
from __future__ import annotations

import json
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

import uvicorn

from palladion_ui.app import create_app
from palladion_ui.settings import MODELS, Settings
from tests.fake_palladion import create_fake

ROOT = Path(__file__).resolve().parents[1]
UI_PORT, FAKE_PORT = 8766, 18481
PRINCIPALS = ("admin-a", "uploader-a", "reader-a", "reader-a-limited", "admin-b", "uploader-b", "reader-b")


class DemoStack:
    """Pretends to start models, so the model menu can be tried without starting anything."""

    def __init__(self) -> None:
        self.state, self.model, self._since = "ready", MODELS[0][0], time.time()

    async def status(self) -> dict[str, Any]:
        if self.state == "starting" and time.time() - self._since > 2:
            self.state = "ready"
        return {"state": self.state, "model": self.model, "mode": "agent" if self.model else "search", "error": None,
                "api": True, "managed": True, "qdrant": True, "since": self._since}

    def begin(self, model: str | None) -> None:
        self.state, self.model, self._since = "starting", model, time.time()

    async def shutdown(self) -> None:
        return None


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="palladion-ui-fake-"))
    (tmp / "data").mkdir()
    (tmp / "data" / "demo_auth.json").write_text(json.dumps({f"tok-{p}": p for p in PRINCIPALS}))
    fixtures = tmp / "palladion-src" / "palladion" / "data" / "demo"
    fixtures.mkdir(parents=True)
    shutil.copy(ROOT / "tests" / "fixtures" / "sample_cases.json", fixtures / "sample_cases.json")
    fake = create_fake(tmp / "data", step_delay=0.6)
    threading.Thread(target=lambda: uvicorn.run(fake, host="127.0.0.1", port=FAKE_PORT, log_level="warning"),
                     daemon=True).start()
    settings = Settings(runtime_dir=tmp, upstream_port=FAKE_PORT, port=UI_PORT, managed=False, stream_delay=0.02)
    app = create_app(settings, stack=DemoStack(), autostart=False)  # type: ignore[arg-type]
    print(f"UI http://127.0.0.1:{UI_PORT}  (fake Palladion on {FAKE_PORT}, data in {tmp})", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=UI_PORT, log_level="warning")


if __name__ == "__main__":
    main()
