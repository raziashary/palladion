PRAGMA foreign_keys = ON;

CREATE TABLE schema_versions (
    version INTEGER PRIMARY KEY CHECK (version > 0),
    applied_at TEXT NOT NULL
);

CREATE TABLE tenants (
    tenant_id TEXT PRIMARY KEY
);

CREATE TABLE principals (
    principal_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
    profile_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE principal_roles (
    principal_id TEXT NOT NULL REFERENCES principals(principal_id),
    role TEXT NOT NULL,
    PRIMARY KEY (principal_id, role)
);

CREATE TABLE principal_grants (
    principal_id TEXT NOT NULL REFERENCES principals(principal_id),
    grant_name TEXT NOT NULL CHECK (
        grant_name IN ('document:upload', 'document:approve', 'source:read', 'case:read')
    ),
    PRIMARY KEY (principal_id, grant_name)
);

CREATE TABLE cases (
    tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
    case_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, case_id)
);

CREATE TABLE case_memberships (
    tenant_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    principal_id TEXT NOT NULL REFERENCES principals(principal_id),
    granted_at TEXT NOT NULL,
    revoked_at TEXT,
    PRIMARY KEY (tenant_id, case_id, principal_id),
    FOREIGN KEY (tenant_id, case_id) REFERENCES cases(tenant_id, case_id),
    CHECK (revoked_at IS NULL OR revoked_at >= granted_at)
);

CREATE TABLE document_families (
    tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
    family_id TEXT NOT NULL,
    owner_id TEXT NOT NULL REFERENCES principals(principal_id),
    created_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, family_id)
);

CREATE TABLE approval_records (
    approval_record_id TEXT PRIMARY KEY,
    revision_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    approver_id TEXT NOT NULL REFERENCES principals(principal_id),
    status TEXT NOT NULL CHECK (status IN ('APPROVED', 'REVOKED')),
    approval_scope_json TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    UNIQUE (tenant_id, revision_id, approval_record_id),
    FOREIGN KEY (tenant_id, revision_id)
        REFERENCES document_revisions(tenant_id, revision_id)
        DEFERRABLE INITIALLY DEFERRED
);

CREATE TABLE document_revisions (
    revision_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    family_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    content_sha256 TEXT NOT NULL CHECK (
        length(content_sha256) = 64 AND content_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    source_path TEXT NOT NULL,
    approval_status TEXT NOT NULL CHECK (
        approval_status IN ('DRAFT', 'REVIEW', 'APPROVED', 'REVOKED')
    ),
    approval_record_id TEXT REFERENCES approval_records(approval_record_id)
        DEFERRABLE INITIALLY DEFERRED,
    uploader_id TEXT NOT NULL REFERENCES principals(principal_id),
    owner_id TEXT NOT NULL REFERENCES principals(principal_id),
    valid_from TEXT,
    valid_to TEXT,
    registered_at TEXT NOT NULL,
    index_state TEXT NOT NULL CHECK (
        index_state IN ('RECEIVED', 'VALIDATED', 'STORED', 'PARSED', 'INDEXING',
                        'RECONCILED', 'READY', 'FAILED')
    ),
    index_generation TEXT NOT NULL,
    acl_json TEXT NOT NULL,
    PRIMARY KEY (tenant_id, revision_id),
    FOREIGN KEY (tenant_id, family_id)
        REFERENCES document_families(tenant_id, family_id),
    FOREIGN KEY (tenant_id, case_id) REFERENCES cases(tenant_id, case_id),
    FOREIGN KEY (tenant_id, revision_id, approval_record_id)
        REFERENCES approval_records(tenant_id, revision_id, approval_record_id)
        DEFERRABLE INITIALLY DEFERRED,
    CHECK (valid_to IS NULL OR (valid_from IS NOT NULL AND valid_from < valid_to)),
    CHECK (approval_status <> 'APPROVED' OR approval_record_id IS NOT NULL)
);

CREATE INDEX document_revisions_family_idx
    ON document_revisions(tenant_id, family_id, registered_at);
CREATE INDEX document_revisions_case_idx
    ON document_revisions(tenant_id, case_id, approval_status, index_state);

CREATE TABLE supersession_edges (
    edge_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    predecessor_revision_id TEXT NOT NULL,
    successor_revision_id TEXT NOT NULL,
    applicability_scope_json TEXT NOT NULL,
    valid_from TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    approved_by TEXT NOT NULL REFERENCES principals(principal_id),
    FOREIGN KEY (tenant_id, predecessor_revision_id)
        REFERENCES document_revisions(tenant_id, revision_id),
    FOREIGN KEY (tenant_id, successor_revision_id)
        REFERENCES document_revisions(tenant_id, revision_id),
    CHECK (predecessor_revision_id <> successor_revision_id)
);

CREATE TABLE chunks (
    chunk_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    revision_id TEXT NOT NULL,
    section_id TEXT NOT NULL,
    original_text TEXT NOT NULL,
    source_line_start INTEGER,
    source_line_end INTEGER,
    original_sha256 TEXT NOT NULL CHECK (
        length(original_sha256) = 64 AND original_sha256 NOT GLOB '*[^0-9a-f]*'
    ),
    parser_version TEXT NOT NULL,
    FOREIGN KEY (tenant_id, revision_id)
        REFERENCES document_revisions(tenant_id, revision_id),
    CHECK (source_line_start IS NULL OR source_line_start > 0),
    CHECK (source_line_end IS NULL OR source_line_end >= source_line_start)
);

CREATE TABLE policy_versions (
    version_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
    family_id TEXT NOT NULL,
    approval_record_id TEXT NOT NULL REFERENCES approval_records(approval_record_id),
    time_basis TEXT NOT NULL,
    timestamp_source TEXT NOT NULL,
    valid_from TEXT NOT NULL,
    valid_to TEXT,
    registered_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('DRAFT', 'APPROVED', 'REVOKED')),
    applicability_json TEXT NOT NULL,
    decision_table_json TEXT NOT NULL,
    FOREIGN KEY (tenant_id, family_id)
        REFERENCES document_families(tenant_id, family_id),
    CHECK (valid_to IS NULL OR valid_from < valid_to)
);

CREATE TABLE policy_source_clauses (
    tenant_id TEXT NOT NULL,
    version_id TEXT NOT NULL REFERENCES policy_versions(version_id),
    revision_id TEXT NOT NULL,
    section_id TEXT NOT NULL,
    PRIMARY KEY (version_id, revision_id, section_id),
    FOREIGN KEY (tenant_id, revision_id)
        REFERENCES document_revisions(tenant_id, revision_id)
);

CREATE TABLE case_events (
    event_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    actor_id TEXT NOT NULL REFERENCES principals(principal_id),
    event_kind TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    FOREIGN KEY (tenant_id, case_id) REFERENCES cases(tenant_id, case_id)
);

CREATE TABLE memory_entries (
    memory_id TEXT PRIMARY KEY,
    memory_kind TEXT NOT NULL CHECK (
        memory_kind IN ('EPISODIC', 'SEMANTIC', 'PROCEDURAL')
    ),
    tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
    scope_kind TEXT NOT NULL,
    scope_id TEXT NOT NULL,
    source_event_id TEXT REFERENCES case_events(event_id),
    source_evidence_id TEXT,
    verification_status TEXT NOT NULL,
    content TEXT NOT NULL,
    validity_policy_id TEXT,
    user_valid_until TEXT,
    observed_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE index_manifest (
    tenant_id TEXT NOT NULL,
    revision_id TEXT NOT NULL,
    index_generation TEXT NOT NULL,
    backend TEXT NOT NULL,
    expected_count INTEGER NOT NULL CHECK (expected_count >= 0),
    confirmed_count INTEGER NOT NULL CHECK (confirmed_count >= 0),
    source_hash TEXT NOT NULL CHECK (
        length(source_hash) = 64 AND source_hash NOT GLOB '*[^0-9a-f]*'
    ),
    verified_at TEXT,
    PRIMARY KEY (tenant_id, revision_id, index_generation, backend),
    FOREIGN KEY (tenant_id, revision_id)
        REFERENCES document_revisions(tenant_id, revision_id)
);

CREATE TABLE audit_events (
    audit_id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    principal_id TEXT NOT NULL REFERENCES principals(principal_id),
    tenant_id TEXT NOT NULL REFERENCES tenants(tenant_id),
    event_kind TEXT NOT NULL,
    safe_payload_json TEXT NOT NULL,
    occurred_at TEXT NOT NULL
);

CREATE TRIGGER approval_records_no_update
BEFORE UPDATE ON approval_records BEGIN
    SELECT RAISE(ABORT, 'approval records are immutable');
END;
CREATE TRIGGER approval_records_no_delete
BEFORE DELETE ON approval_records BEGIN
    SELECT RAISE(ABORT, 'approval records are immutable');
END;
