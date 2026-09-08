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
