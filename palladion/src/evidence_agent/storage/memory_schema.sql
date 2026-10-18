-- P05 additive v4: old memory rows remain untouched and unowned (fail closed).
CREATE TABLE memory_provenance (
    memory_id TEXT PRIMARY KEY REFERENCES memory_entries(memory_id),
    owner_id TEXT NOT NULL REFERENCES principals(principal_id),
    origin_case_id TEXT,
    set_by TEXT NOT NULL REFERENCES principals(principal_id),
    set_at TEXT NOT NULL,
    valid_from TEXT NOT NULL,
    supersedes_id TEXT UNIQUE REFERENCES memory_entries(memory_id),
    claim_kind TEXT NOT NULL CHECK (claim_kind IN ('REPORTED','HYPOTHESIS','PROCEDURE')),
    source_ref_json TEXT
);
CREATE TABLE memory_teams (
    tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
    team_id TEXT NOT NULL,
    PRIMARY KEY(tenant_id,team_id)
);
CREATE TABLE memory_team_memberships (
    tenant_id TEXT NOT NULL,
    team_id TEXT NOT NULL,
    principal_id TEXT NOT NULL REFERENCES principals(principal_id),
    set_by TEXT NOT NULL REFERENCES principals(principal_id),
    set_at TEXT NOT NULL,
    revoked_at TEXT,
    PRIMARY KEY(tenant_id,team_id,principal_id),
    FOREIGN KEY(tenant_id,team_id) REFERENCES memory_teams(tenant_id,team_id)
);
CREATE VIRTUAL TABLE memory_fts USING fts5(memory_id UNINDEXED,content);
INSERT INTO memory_fts(memory_id,content) SELECT memory_id,content FROM memory_entries;
CREATE TRIGGER memory_fts_insert AFTER INSERT ON memory_entries BEGIN
    INSERT INTO memory_fts(memory_id,content) VALUES(NEW.memory_id,NEW.content);
END;
CREATE TRIGGER memory_entries_no_update BEFORE UPDATE ON memory_entries BEGIN
    SELECT RAISE(ABORT,'memory entries are immutable');
END;
CREATE TRIGGER memory_entries_no_delete BEFORE DELETE ON memory_entries BEGIN
    SELECT RAISE(ABORT,'memory entries are immutable');
END;
CREATE TRIGGER memory_provenance_no_update BEFORE UPDATE ON memory_provenance BEGIN
    SELECT RAISE(ABORT,'memory provenance is immutable');
END;
CREATE TRIGGER memory_provenance_no_delete BEFORE DELETE ON memory_provenance BEGIN
    SELECT RAISE(ABORT,'memory provenance is immutable');
END;
CREATE INDEX memory_scope_idx ON memory_entries(tenant_id,scope_kind,scope_id,created_at);
