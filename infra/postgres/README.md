# OpsPilot PostgreSQL / pgvector

Phase 4 stores operational knowledge in a local PostgreSQL database named `opspilot`.

## PgAdmin setup

1. Connect to your local PostgreSQL server in PgAdmin.
2. Open the Query Tool on the default `postgres` database and run `00-create-database.sql` once.
3. Switch the Query Tool connection to the new `opspilot` database.
4. Ensure pgvector is installed on the PostgreSQL server, then run `01-schema.sql`.

The same operations are available through `make db-create` and `make db-init` once the connection URLs in `.env` are configured.

## pgvector on macOS

PgAdmin is a database client; the PostgreSQL server itself must have the `vector` extension installed. Check availability with:

```sql
SELECT version();
SELECT name, default_version, installed_version
FROM pg_available_extensions
WHERE name = 'vector';
```

Then validate the active database with:

```sql
SELECT extversion FROM pg_extension WHERE extname = 'vector';
```

## Schema

- `knowledge.documents`: source metadata and content versioning.
- `knowledge.chunks`: Markdown chunks and 1536-dimensional embeddings.
- `idx_knowledge_chunks_embedding_hnsw`: HNSW cosine index.
- `idx_knowledge_chunks_search_vector`: PostgreSQL full-text GIN index reserved for hybrid retrieval.


## Runtime role model

`OPSPILOT_POSTGRES_ADMIN_URL` is used only for database/schema administration.
`OPSPILOT_DATABASE_URL` is the least-privilege runtime role used by ingestion and retrieval.
`make db-init` creates/updates the schema with the admin connection and grants the runtime role:

- CONNECT on the `opspilot` database
- USAGE on the `knowledge` schema
- SELECT/INSERT/UPDATE/DELETE on knowledge tables
- USAGE/SELECT on knowledge sequences

The runtime role does not need CREATE or database ownership.
