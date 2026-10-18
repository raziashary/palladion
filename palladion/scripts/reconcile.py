"""Inspect exact canonical/index manifests without deleting or silently repairing data."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from evidence_agent.settings import load_settings
from evidence_agent.storage.catalog import Catalog
from evidence_agent.storage.originals import OriginalStore
from evidence_agent.storage.qdrant import QdrantIndex
from evidence_agent.storage.registry import Registry
from evidence_agent.storage.sqlite import Database


def main() -> None:
    settings = load_settings(Path(__file__).resolve().parents[1] / "config/settings.yaml")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("runtime/demo"))
    parser.add_argument("--url", default=settings.qdrant_url)
    parser.add_argument("--collection", default=settings.qdrant_collection)
    parser.add_argument("--principal", default="admin-a")
    args = parser.parse_args()
    index = QdrantIndex(url=args.url, collection_name=args.collection, bm25_profile=settings.bm25_profile)
    reports: list[dict[str, object]] = []
    try:
        with Database(args.root / "registry.sqlite") as database:
            registry = Registry(database, OriginalStore(args.root / "originals"))
            principal = registry.access.authenticate(args.principal)
            registry.access.authorize(principal, tenant_id=principal.tenant_id,
                                       role="admin", grant="document:approve")
            catalog = Catalog(registry)
            revisions = [row[0] for row in database.connection.execute(
                "SELECT revision_id FROM document_revisions WHERE tenant_id=? AND approval_status='APPROVED'",
                (principal.tenant_id,))]
            for revision in revisions:
                metadata = catalog.eligible_generation_metadata(principal, revision)
                if metadata is None:
                    reports.append({"revision": revision, "match": False, "reason": "UNINDEXED"})
                    continue
                generation = str(metadata["generation"])
                expected = catalog.manifest_for_generation(principal, revision, generation)
                actual = index.readback(principal.tenant_id, revision, generation)
                reports.append({"revision": revision, "generation": generation,
                                "match": expected == actual and metadata["fingerprint"] == index.fingerprint,
                                "expected_count": len(expected), "actual_count": len(actual)})
        print(json.dumps({"reports": reports, "all_match": all(r["match"] for r in reports)}, indent=2))
        if not reports or not all(r["match"] for r in reports):
            raise SystemExit(1)
    finally:
        index.close()


if __name__ == "__main__":
    main()
