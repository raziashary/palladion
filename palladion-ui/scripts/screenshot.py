"""Capture the UI as a PNG with headless Chrome, for documentation.

    uv run python -m scripts.screenshot --session sess_... --open chunk_... --out docs/screenshots/answer.png
    uv run python -m scripts.screenshot --route ingest --query "as=uploader-a" --out docs/screenshots/ingestion.png

The UI must be running. A saved conversation opens at #/chat/<session>; ?open=<evidence id> shows that evidence;
?as=<identity> signs in as a demo identity; on the Policies screen ?example=1&step=4 opens the example
at its review step.
"""
from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

CHROME = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session")
    parser.add_argument("--route", default="", help="screen to open: chat, search, ingest or policies")
    parser.add_argument("--query", default="", help="query string without the question mark, for example as=admin-a")
    parser.add_argument("--open", help="evidence id to show in the side panel")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--size", default="1500,1020")
    args = parser.parse_args()
    query = args.query + (("&" if args.query else "") + f"open={args.open}" if args.open else "")
    route = f"#/{args.route}" if args.route else (f"#/chat/{args.session}" if args.session else "")
    url = f"http://127.0.0.1:{args.port}/" + (f"?{query}" if query else "") + route
    print(url)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="palladion-ui-shot-") as profile:
        command = [str(CHROME), "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={profile}",
                   f"--window-size={args.size}", "--virtual-time-budget=25000",
                   "--run-all-compositor-stages-before-draw", f"--screenshot={args.out.resolve()}", url]
        subprocess.run(command, check=True, timeout=90, capture_output=True)
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
