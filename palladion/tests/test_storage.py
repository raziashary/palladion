"""Isolated P07 migration preservation/rollback, never a user registry."""

import sqlite3

import pytest

from evidence_agent.storage.sqlite import Database


def old_v4(path, *, failure=False):
    with Database(path) as database:
        database.connection.execute("INSERT INTO tenants VALUES('preserved')")
    with sqlite3.connect(path) as db:
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
