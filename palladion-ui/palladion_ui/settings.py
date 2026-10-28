"""Where everything lives, and the few knobs that change. Environment variables use the PALLADION_UI_ prefix."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

UI_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = UI_ROOT.parent

# The only models the Palladion API accepts (scripts/serve.py --model). The UI never adds to this list.
MODELS: tuple[tuple[str, str], ...] = (
    ("openai/gpt-oss-20b", "GPT-OSS 20B"),
    ("openai/gpt-oss-120b", "GPT-OSS 120B"),
    ("qwen/qwen3.8-27b", "Qwen3.8 27B"),
)


def _env(name: str, default: str) -> str:
    return os.environ.get(f"PALLADION_UI_{name}", default)


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8765
    runtime_dir: Path = UI_ROOT / ".runtime"
    upstream_port: int = 18480
    qdrant_port: int = 17533
    collection: str = "palladion_ui_dev"
    # True when this server starts and stops Palladion and Qdrant itself (the normal dev stack).
    managed: bool = True
    # Seconds between reveals of released text; 0 sends it at once (tests).
    stream_delay: float = 0.012
    poll_interval: float = 0.8
    request_timeout: int = 120  # seconds Palladion may spend on one message; the UI waits a little longer
    models: tuple[tuple[str, str], ...] = field(default=MODELS)
    env_file: Path = REPO_ROOT / ".env"  # read only when a model is explicitly started

    @property
    def upstream_url(self) -> str:
        return f"http://127.0.0.1:{self.upstream_port}"

    @property
    def qdrant_url(self) -> str:
        return f"http://127.0.0.1:{self.qdrant_port}"

    @property
    def app_dir(self) -> Path:
        return self.runtime_dir / "palladion-src" / "palladion"

    @property
    def data_root(self) -> Path:
        return self.runtime_dir / "data"

    @property
    def fixtures_root(self) -> Path:
        return self.app_dir / "data" / "demo"

    @property
    def state_file(self) -> Path:
        return self.runtime_dir / "ui-state.json"

    @property
    def log_dir(self) -> Path:
        return self.runtime_dir / "logs"

    @property
    def model_ids(self) -> tuple[str, ...]:
        return tuple(model for model, _ in self.models)

    @classmethod
    def from_env(cls) -> Settings:
        runtime = Path(_env("RUNTIME_DIR", str(UI_ROOT / ".runtime")))
        return cls(
            host=_env("HOST", "127.0.0.1"),
            port=int(_env("PORT", "8765")),
            runtime_dir=runtime,
            upstream_port=int(_env("UPSTREAM_PORT", "18480")),
            qdrant_port=int(_env("QDRANT_PORT", "17533")),
            collection=_env("COLLECTION", "palladion_ui_dev"),
            managed=_env("MANAGED", "1") != "0",
        )
