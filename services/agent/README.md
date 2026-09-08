# OpsPilot Agent Service (Phases 3–4)

The Python service orchestrates the OpenAI incident agent, the read-only Go Kubernetes MCP server,
and the PostgreSQL/pgvector knowledge base.

## Responsibilities

- Connect to the Go Kubernetes MCP server with Streamable HTTP.
- Let the OpenAI agent autonomously select Kubernetes diagnostic tools.
- Expose `search_knowledge` for RAG over runbooks, incidents, postmortems, and architecture docs.
- Return the typed `IncidentReport` schema through the CLI and FastAPI API.
- Keep current-cluster diagnosis read-only and evidence-backed.

## Setup

From the repository root:

```bash
make agent-setup
make agent-test
```

Phase 4 database setup:

```bash
make db-create
make db-init
make rag-ingest
make rag-search RAG_QUERY="crashloop missing database configuration"
```

With the Go MCP server port-forward running:

```bash
make agent-tools
make investigate-1
```

`agent-tools` now lists the five Kubernetes MCP tools plus `search_knowledge` when RAG is enabled.
