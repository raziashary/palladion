"""The single dev suite: lint, server tests, front-end tests. No model, no Qdrant, no quota.

    uv run python -m scripts.check
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = [
    ("ruff", [sys.executable, "-m", "ruff", "check", "palladion_ui", "tests", "scripts"], ROOT),
    ("server tests", [sys.executable, "-m", "pytest", "-q"], ROOT),
    ("front-end syntax", ["node", "--check", "js/app.js"], ROOT / "web"),
    ("front-end tests", ["node", "--test"], ROOT / "web"),
]


def main() -> int:
    failed = []
    for name, command, cwd in STEPS:
        print(f"\n== {name}", flush=True)
        if subprocess.run(command, cwd=cwd).returncode != 0:
            failed.append(name)
    print("\nFAILED: " + ", ".join(failed) if failed else "\nAll checks passed.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
