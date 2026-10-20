"""Isolated P07 migration preservation/rollback, never a user registry."""

import sqlite3

import pytest

from evidence_agent.storage.sqlite import Database


def old_v4(path, *, failure=False):
    with Database(path) as database:
        database.connection.execute("INSERT INTO tenants VALUES('preserved')")
    with sqlite3.connect(path) as db:
        db.execute("DROP TABLE source_extractions")
        for table in (
            "memory_promotion_links",
            "memory_promotion_decisions",
            "memory_event_chunks",
            "memory_event_sessions",
            "memory_sessions",
        ):
            db.execute(f"DROP TABLE IF EXISTS {table}")
        for table in (
            "index_graph_expectations",
            "graph_relation_reviews",
            "graph_merge_decisions",
            "graph_relations",
            "graph_entity_attestations",
        ):
            db.execute(f"DROP TABLE {table}")
        db.execute("DELETE FROM schema_versions WHERE version>=5")
        db.execute("PRAGMA user_version=4")
        if failure:
            db.execute(
                "CREATE TRIGGER fail_graph BEFORE INSERT ON schema_versions WHEN NEW.version=5 "
                "BEGIN SELECT RAISE(ABORT,'injected graph migration failure'); END"
            )


@pytest.mark.parametrize("failure", [False, True])
def test_v4_graph_upgrade_preserves_data_backup_and_rolls_back(tmp_path, failure):
    path = tmp_path / "old.sqlite"
    old_v4(path, failure=failure)
    owner = Database(path)
    if failure:
        with pytest.raises(sqlite3.IntegrityError, match="injected graph"):
            owner.open()
        with sqlite3.connect(path) as db:
            assert db.execute("PRAGMA user_version").fetchone()[0] == 4
            assert (
                db.execute("SELECT 1 FROM sqlite_master WHERE name='graph_relations'").fetchone()
                is None
            )
    else:
        with owner:
            assert (
                owner.connection.execute("PRAGMA user_version").fetchone()[0]
                == Database.SCHEMA_VERSION
            )
            assert (
                owner.connection.execute("SELECT tenant_id FROM tenants").fetchone()[0]
                == "preserved"
            )
    assert owner.backup_path is not None
    with sqlite3.connect(owner.backup_path) as backup:
        assert backup.execute("PRAGMA user_version").fetchone()[0] == 4
        assert backup.execute("SELECT tenant_id FROM tenants").fetchone()[0] == "preserved"
        assert backup.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


@pytest.mark.parametrize("failure", [False, True])
def test_v7_populated_upgrade_backup_and_rollback(tmp_path, failure):
    path = tmp_path / "v6.sqlite"
    with Database(path) as database:
        database.connection.execute("INSERT INTO tenants VALUES('v6-preserved')")
    with sqlite3.connect(path) as db:
        db.execute("DROP TABLE source_extractions")
        db.execute("DELETE FROM schema_versions WHERE version=7")
        db.execute("PRAGMA user_version=6")
        if failure:
            db.execute("CREATE TRIGGER fail_v7 BEFORE INSERT ON schema_versions WHEN NEW.version=7 "
                       "BEGIN SELECT RAISE(ABORT,'injected extraction failure'); END")
    owner = Database(path)
    if failure:
        with pytest.raises(sqlite3.IntegrityError, match="injected extraction"):
            owner.open()
        with sqlite3.connect(path) as db:
            assert db.execute("PRAGMA user_version").fetchone()[0] == 6
            assert db.execute("SELECT name FROM sqlite_master WHERE name='source_extractions'").fetchone() is None
    else:
        with owner:
            assert owner.connection.execute("PRAGMA user_version").fetchone()[0] == 7
            assert owner.connection.execute("SELECT count(*) FROM source_extractions").fetchone()[0] == 0
    assert owner.backup_path
    with sqlite3.connect(owner.backup_path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 6
        assert db.execute("SELECT tenant_id FROM tenants").fetchone()[0] == "v6-preserved"
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_v7_upgrade_preserves_populated_sessions_promotions_graph_and_sources(p03, tmp_path):
    from evidence_agent.graph.registry import GraphRegistry
    from evidence_agent.ingest.pipeline import IngestPipeline
    from evidence_agent.memory.store import CaseStore
    from evidence_agent.storage.catalog import Catalog

    from .test_pipeline import MemoryIndex

    catalog = Catalog(p03.registry)
    revision = p03.revisions["SOP-2026-B"]
    IngestPipeline(catalog, MemoryIndex()).index(p03.admin, revision)
    chunk = catalog.chunks_for_revision(p03.admin, revision)[0]
    GraphRegistry(catalog, p03.admin, "case-42").attest(chunk.chunk_id,
        kind="concept", display_name="Preserved graph")
    CaseStore(p03.registry, p03.reader, "case-42").append("REQUEST", "v7-preserve",
        {"query": "I prefer concise answers."})
    tables = ("document_revisions", "graph_entity_attestations", "case_events", "memory_sessions",
              "memory_event_sessions", "memory_event_chunks", "memory_promotion_decisions",
              "memory_promotion_links", "memory_entries", "memory_provenance")
    snapshot = {table: [tuple(row) for row in p03.registry.database.connection.execute(
        f"SELECT * FROM {table}")] for table in tables}
    assert all(snapshot.values())
    path = tmp_path / "populated-v6.sqlite"
    with sqlite3.connect(path) as target:
        p03.registry.database.connection.backup(target)
        target.execute("DROP TABLE source_extractions")
        target.execute("DELETE FROM schema_versions WHERE version=7")
        target.execute("PRAGMA user_version=6")
    with Database(path) as owner:
        assert owner.backup_path
        for table, rows in snapshot.items():
            assert [tuple(row) for row in owner.connection.execute(f"SELECT * FROM {table}")] == rows
        with sqlite3.connect(owner.backup_path) as backup:
            assert backup.execute("PRAGMA user_version").fetchone()[0] == 6
            assert backup.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            for table, rows in snapshot.items():
                assert backup.execute(f"SELECT * FROM {table}").fetchall() == rows
