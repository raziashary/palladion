"""Inspect exact canonical/index manifests without deleting or silently repairing data."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from evidence_agent.settings import load_settings
from evidence_agent.storage.catalog import Catalog
from evidence_agent.storage.neo4j import Neo4jIndex
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
    parser.add_argument("--enable-graph",action="store_true")
    parser.add_argument("--graph-partition",default=settings.graph_partition)
    parser.add_argument("--graph-timeout",type=float,default=settings.graph_timeout_seconds)
    args = parser.parse_args()
    index = QdrantIndex(url=args.url, collection_name=args.collection, bm25_profile=settings.bm25_profile)
    graph=Neo4jIndex(uri=settings.neo4j_uri,partition=args.graph_partition,
        timeout_seconds=args.graph_timeout) if args.enable_graph else None
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
                if metadata["graph_enabled"]:
                    expected_graph=catalog.graph_manifest_for_generation(principal,revision,generation)
                    actual_graph=graph.projection_readback(principal.tenant_id,revision,generation) if graph else None
                    reports.append({"revision":revision,"generation":generation,"backend":"neo4j",
                        "match":actual_graph==expected_graph,"reason":"CHECKED" if graph else "NOT_ENABLED"})
        print(json.dumps({"reports": reports, "all_match": all(r["match"] for r in reports)}, indent=2))
        if not reports or not all(r["match"] for r in reports):
            raise SystemExit(1)
    finally:
        index.close()
        if graph is not None:
            graph.close()


if __name__ == "__main__":
    main()
