-- P07 additive v5. Canonical source-backed attestations; Neo4j remains derived.
CREATE TABLE index_graph_expectations (
    tenant_id TEXT NOT NULL,
    revision_id TEXT NOT NULL,
    generation TEXT NOT NULL,
    item_id TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    PRIMARY KEY(tenant_id,revision_id,generation,item_id),
    FOREIGN KEY(tenant_id,revision_id,generation)
        REFERENCES index_generations(tenant_id,revision_id,generation)
);
CREATE TABLE graph_entity_attestations (
    attestation_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    entity_key TEXT NOT NULL,
    source_system TEXT NOT NULL,
    entity_kind TEXT NOT NULL,
    external_id TEXT,
    identity_state TEXT NOT NULL CHECK(identity_state IN ('VERIFIED','PROVISIONAL')),
    display_name TEXT NOT NULL,
    evidence_chunk_id TEXT NOT NULL REFERENCES p02_chunks(chunk_id),
    actor_id TEXT NOT NULL REFERENCES principals(principal_id),
    occurred_at TEXT NOT NULL,
    FOREIGN KEY(tenant_id,case_id) REFERENCES cases(tenant_id,case_id),
    UNIQUE(tenant_id,case_id,entity_key,evidence_chunk_id)
);
CREATE INDEX graph_entity_scope ON graph_entity_attestations(tenant_id,case_id,entity_key);
CREATE TABLE graph_relations (
    edge_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    from_key TEXT NOT NULL,
    to_key TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    evidence_chunk_id TEXT NOT NULL REFERENCES p02_chunks(chunk_id),
    evidence_kind TEXT NOT NULL CHECK(evidence_kind IN ('EXPLICIT_SOURCE','EXTRACTED_UNREVIEWED')),
    actor_id TEXT NOT NULL REFERENCES principals(principal_id),
    occurred_at TEXT NOT NULL,
    FOREIGN KEY(tenant_id,case_id) REFERENCES cases(tenant_id,case_id)
);
CREATE INDEX graph_relation_scope ON graph_relations(tenant_id,case_id,evidence_chunk_id);
CREATE TABLE graph_relation_reviews (
    review_id TEXT PRIMARY KEY,
    edge_id TEXT NOT NULL REFERENCES graph_relations(edge_id),
    decision TEXT NOT NULL CHECK(decision IN ('HUMAN_VERIFIED','REJECTED')),
    reviewer_id TEXT NOT NULL REFERENCES principals(principal_id),
    reason TEXT NOT NULL,
    occurred_at TEXT NOT NULL
);
CREATE TABLE graph_merge_decisions (
    decision_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    from_key TEXT NOT NULL,
    to_key TEXT NOT NULL,
    decision TEXT NOT NULL CHECK(decision IN ('ACCEPTED','REJECTED')),
    evidence_chunk_id TEXT NOT NULL REFERENCES p02_chunks(chunk_id),
    reviewer_id TEXT NOT NULL REFERENCES principals(principal_id),
    reason TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    FOREIGN KEY(tenant_id,case_id) REFERENCES cases(tenant_id,case_id)
);
