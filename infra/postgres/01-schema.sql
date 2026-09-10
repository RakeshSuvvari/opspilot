-- OpsPilot Phase 4 knowledge/RAG schema.
-- Run this while connected to the "opspilot" database.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS knowledge;

CREATE TABLE IF NOT EXISTS knowledge.documents (
    id BIGSERIAL PRIMARY KEY,
    source_path TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    document_type TEXT NOT NULL CHECK (
        document_type IN ('runbook', 'postmortem', 'architecture', 'incident', 'other')
    ),
    service TEXT,
    content_sha256 CHAR(64) NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding_dimensions INTEGER NOT NULL CHECK (embedding_dimensions > 0),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS knowledge.chunks (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES knowledge.documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL CHECK (chunk_index >= 0),
    heading TEXT,
    content TEXT NOT NULL,
    embedding VECTOR(1536) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    search_vector TSVECTOR GENERATED ALWAYS AS (
        to_tsvector(
            'english',
            coalesce(heading, '') || ' ' || content
        )
    ) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_documents_type
    ON knowledge.documents(document_type);

CREATE INDEX IF NOT EXISTS idx_knowledge_documents_service
    ON knowledge.documents(service);

CREATE INDEX IF NOT EXISTS idx_knowledge_documents_metadata
    ON knowledge.documents USING GIN(metadata);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_search_vector
    ON knowledge.chunks USING GIN(search_vector);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_embedding_hnsw
    ON knowledge.chunks USING hnsw (embedding vector_cosine_ops);

CREATE OR REPLACE VIEW knowledge.document_stats AS
SELECT
    d.id,
    d.source_path,
    d.title,
    d.document_type,
    d.service,
    d.embedding_model,
    d.embedding_dimensions,
    COUNT(c.id) AS chunk_count,
    d.updated_at
FROM knowledge.documents d
LEFT JOIN knowledge.chunks c ON c.document_id = d.id
GROUP BY d.id;

-- Phase 9 operational persistence.
CREATE SCHEMA IF NOT EXISTS operations;

CREATE TABLE IF NOT EXISTS operations.investigations (
    investigation_id TEXT PRIMARY KEY,
    job_id TEXT,
    query TEXT NOT NULL,
    namespace TEXT NOT NULL,
    run_mode TEXT NOT NULL CHECK (run_mode IN ('investigate', 'remediate')),
    status TEXT NOT NULL,
    confidence TEXT NOT NULL,
    summary TEXT NOT NULL,
    root_cause TEXT NOT NULL,
    evidence_score INTEGER NOT NULL CHECK (evidence_score BETWEEN 0 AND 100),
    confidence_score INTEGER NOT NULL CHECK (confidence_score BETWEEN 0 AND 100),
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ NOT NULL,
    elapsed_ms INTEGER NOT NULL CHECK (elapsed_ms >= 0),
    total_tokens INTEGER NOT NULL CHECK (total_tokens >= 0),
    tool_call_count INTEGER NOT NULL CHECK (tool_call_count >= 0),
    report JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_operations_investigations_job_id
    ON operations.investigations(job_id)
    WHERE job_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_operations_investigations_completed_at
    ON operations.investigations(completed_at DESC);

CREATE INDEX IF NOT EXISTS idx_operations_investigations_namespace
    ON operations.investigations(namespace, completed_at DESC);

CREATE INDEX IF NOT EXISTS idx_operations_investigations_status
    ON operations.investigations(status, completed_at DESC);

CREATE TABLE IF NOT EXISTS operations.tool_calls (
    id BIGSERIAL PRIMARY KEY,
    investigation_id TEXT NOT NULL REFERENCES operations.investigations(investigation_id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    tool_name TEXT NOT NULL,
    call_id TEXT,
    arguments JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (investigation_id, ordinal)
);

CREATE INDEX IF NOT EXISTS idx_operations_tool_calls_investigation
    ON operations.tool_calls(investigation_id, ordinal);

CREATE INDEX IF NOT EXISTS idx_operations_tool_calls_name
    ON operations.tool_calls(tool_name);

CREATE TABLE IF NOT EXISTS operations.remediation_actions (
    id BIGSERIAL PRIMARY KEY,
    investigation_id TEXT NOT NULL REFERENCES operations.investigations(investigation_id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    tool_name TEXT NOT NULL,
    resource TEXT NOT NULL,
    approved BOOLEAN NOT NULL,
    status TEXT NOT NULL,
    arguments JSONB NOT NULL DEFAULT '{}'::jsonb,
    result JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (investigation_id, ordinal)
);

CREATE INDEX IF NOT EXISTS idx_operations_remediation_actions_investigation
    ON operations.remediation_actions(investigation_id, ordinal);
