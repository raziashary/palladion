from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from palladion_ui.app import create_app
from palladion_ui.settings import Settings
from tests.fake_palladion import create_fake

HERE = Path(__file__).parent
PRINCIPALS = ("admin-a", "uploader-a", "reader-a", "reader-a-limited", "admin-b", "uploader-b", "reader-b")
MODEL = "openai/gpt-oss-20b"


class StubStack:
    """Stands in for the process manager: the server logic is under test here, not subprocesses."""

    def __init__(self, state: str = "ready", model: str | None = MODEL) -> None:
        self.state, self.model, self.began = state, model, []

    async def status(self) -> dict[str, Any]:
        return {"state": self.state, "model": self.model, "mode": "agent" if self.model else "search",
                "error": None, "api": True, "managed": True, "qdrant": True, "since": 0}

    def begin(self, model: str | None) -> None:
        self.began.append(model)
        self.state, self.model = "starting", model

    async def shutdown(self) -> None:
        return None


def read_sse(response: httpx.Response) -> list[tuple[str, Any]]:
    events: list[tuple[str, Any]] = []
    name = ""
    for line in response.iter_lines():
        if line.startswith("event: "):
            name = line[7:]
        elif line.startswith("data: "):
            events.append((name, json.loads(line[6:])))
    return events


@pytest.fixture
def env(tmp_path: Path) -> Iterator[SimpleNamespace]:
    data = tmp_path / "data"
    data.mkdir()
    (data / "demo_auth.json").write_text(json.dumps({f"tok-{p}": p for p in PRINCIPALS}))
    fixtures = tmp_path / "palladion-src" / "palladion" / "data" / "demo"
    fixtures.mkdir(parents=True)
    shutil.copy(HERE / "fixtures" / "sample_cases.json", fixtures / "sample_cases.json")
    settings = Settings(runtime_dir=tmp_path, managed=False, stream_delay=0, poll_interval=0.05)
    fake = create_fake(data)
    stack = StubStack()

    def factory() -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=fake), base_url="http://palladion")

    app = create_app(settings, upstream_factory=factory, stack=stack, autostart=False)  # type: ignore[arg-type]
    with TestClient(app, headers={"X-Palladion-UI": "1"}) as client:
        yield SimpleNamespace(client=client, fake=SimpleNamespace(state=fake.state.fake), settings=settings,
                              stack=stack, app=app, tmp=tmp_path)


def act_as(env: SimpleNamespace, persona: str) -> None:
    assert env.client.post("/api/persona", json={"persona": persona}).status_code == 200
