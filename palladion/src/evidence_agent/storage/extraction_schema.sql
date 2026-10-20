CREATE TABLE source_extractions (
    tenant_id TEXT NOT NULL,
    revision_id TEXT NOT NULL,
    original_sha256 TEXT NOT NULL CHECK(length(original_sha256)=64),
    original_filename TEXT NOT NULL,
    extracted_sha256 TEXT NOT NULL CHECK(length(extracted_sha256)=64),
    parser_version TEXT NOT NULL,
    pages_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(tenant_id, revision_id),
    FOREIGN KEY(tenant_id, revision_id) REFERENCES document_revisions(tenant_id, revision_id)
);
CREATE TRIGGER source_extractions_no_update BEFORE UPDATE ON source_extractions
BEGIN SELECT RAISE(ABORT, 'immutable extraction provenance'); END;
CREATE TRIGGER source_extractions_no_delete BEFORE DELETE ON source_extractions
BEGIN SELECT RAISE(ABORT, 'immutable extraction provenance'); END;
