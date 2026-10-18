"""Idempotent synthetic seed into explicit local stores; never resets persistent data."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from evidence_agent.core.bootstrap import seed
from evidence_agent.settings import load_settings
from evidence_agent.storage.qdrant import QdrantIndex


def main() -> None:
    settings = load_settings(Path(__file__).resolve().parents[1] / "config/settings.yaml")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("runtime/demo"))
    parser.add_argument("--url", default=settings.qdrant_url)
    parser.add_argument("--collection", default=settings.qdrant_collection)
    parser.add_argument("--bm25-profile", choices=["english", "no_stemming"], default=settings.bm25_profile)
    args = parser.parse_args()
    index = QdrantIndex(url=args.url, collection_name=args.collection, bm25_profile=args.bm25_profile)
    try:
        revisions = seed(args.root, Path(__file__).resolve().parents[1], index)
        print(json.dumps({"revisions": revisions, "synthetic_auth_file": str(args.root / "demo_auth.json"),
                          "representation": index.representation_manifest}, indent=2))
    finally:
        index.close()


if __name__ == "__main__":
    main()
