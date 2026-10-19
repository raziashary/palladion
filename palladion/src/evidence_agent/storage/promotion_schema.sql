-- P07 additive v6: sessions and source-linked automatic promotion.
CREATE TABLE memory_sessions (
    session_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    owner_id TEXT NOT NULL REFERENCES principals(principal_id),
    created_at TEXT NOT NULL,
    closed_at TEXT,
    FOREIGN KEY(tenant_id,case_id) REFERENCES cases(tenant_id,case_id),
    CHECK(closed_at IS NULL OR closed_at>=created_at)
);
CREATE UNIQUE INDEX memory_active_session ON memory_sessions(tenant_id,case_id,owner_id)
    WHERE closed_at IS NULL;
CREATE TABLE memory_event_sessions (
    event_id TEXT PRIMARY KEY REFERENCES case_events(event_id),
    session_id TEXT NOT NULL REFERENCES memory_sessions(session_id)
);
CREATE INDEX memory_session_events ON memory_event_sessions(session_id,event_id);
CREATE TABLE memory_event_chunks (
    chunk_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES case_events(event_id),
    session_id TEXT NOT NULL REFERENCES memory_sessions(session_id),
    field_name TEXT NOT NULL,
    start_byte INTEGER NOT NULL CHECK(start_byte>=0),
    end_byte INTEGER NOT NULL CHECK(end_byte>start_byte),
    text_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(event_id,field_name,start_byte,end_byte)
);
CREATE TABLE memory_promotion_decisions (
    decision_id TEXT PRIMARY KEY,
    chunk_id TEXT NOT NULL REFERENCES memory_event_chunks(chunk_id),
    profile_sha256 TEXT NOT NULL,
    category TEXT NOT NULL CHECK(category IN ('EPISODIC','SEMANTIC','PROCEDURAL')),
    rule_id TEXT NOT NULL,
    scores_json TEXT NOT NULL,
    loss REAL,
    status TEXT NOT NULL CHECK(status IN ('DECIDED','FAILED')),
    occurred_at TEXT NOT NULL,
    UNIQUE(chunk_id,profile_sha256)
);
CREATE TABLE memory_promotion_links (
    chunk_id TEXT PRIMARY KEY REFERENCES memory_event_chunks(chunk_id),
    memory_id TEXT NOT NULL UNIQUE REFERENCES memory_entries(memory_id),
    decision_id TEXT NOT NULL REFERENCES memory_promotion_decisions(decision_id)
);
CREATE TRIGGER memory_chunks_no_update BEFORE UPDATE ON memory_event_chunks
BEGIN SELECT RAISE(ABORT,'promotion chunk provenance is immutable'); END;
CREATE TRIGGER memory_chunks_no_delete BEFORE DELETE ON memory_event_chunks
BEGIN SELECT RAISE(ABORT,'promotion chunk provenance is immutable'); END;
CREATE TRIGGER memory_decisions_no_update BEFORE UPDATE ON memory_promotion_decisions
BEGIN SELECT RAISE(ABORT,'promotion decisions are immutable'); END;
CREATE TRIGGER memory_decisions_no_delete BEFORE DELETE ON memory_promotion_decisions
BEGIN SELECT RAISE(ABORT,'promotion decisions are immutable'); END;
