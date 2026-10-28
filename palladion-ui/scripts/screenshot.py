"""Capture the UI as a PNG with headless Chrome, for documentation.

    uv run python -m scripts.screenshot --session sess_... --open chunk_... --out docs/screenshots/answer.png

The UI must be running. A saved conversation opens at #/chat/<session>; ?open=<evidence id> shows that evidence.
"""
from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

CHROME = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True)
    parser.add_argument("--open", help="evidence id to show in the side panel")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--size", default="1500,1020")
    args = parser.parse_args()
    query = f"?open={args.open}" if args.open else ""
    url = f"http://127.0.0.1:{args.port}/{query}#/chat/{args.session}"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="palladion-ui-shot-") as profile:
        command = [str(CHROME), "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={profile}",
                   f"--window-size={args.size}", "--virtual-time-budget=12000",
                   f"--screenshot={args.out.resolve()}", url]
        subprocess.run(command, check=True, timeout=90, capture_output=True)
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
