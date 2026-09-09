# OpsPilot Agent Service (Phases 3–5)

The Python service orchestrates the OpenAI incident agent, the read-only Go Kubernetes MCP server,
the PostgreSQL/pgvector knowledge base, and the Phase 5 trust/evaluation layer.

## Responsibilities

- Connect to the Go Kubernetes MCP server with Streamable HTTP.
- Let the OpenAI agent autonomously select Kubernetes diagnostic tools.
- Expose `search_knowledge` for RAG over runbooks, incidents, postmortems, and architecture docs.
- Return a typed incident analysis from the LLM.
- Derive actual `tools_used` from SDK run items instead of model self-reporting.
- Build deterministic timelines from timestamped Kubernetes tool outputs.
- Calculate evidence/confidence coverage separately from the model's confidence.
- Record request/token/tool-call/latency metrics and local run artifacts.
- Score known incident runs with deterministic evaluation cases.

## Setup

From the repository root:

```bash
make agent-setup
make agent-test
```

Database/RAG setup:

```bash
make db-create
make db-init
make rag-ingest
make rag-search RAG_QUERY="crashloop missing database configuration"
```

With the Go MCP server port-forward running:

```bash
make agent-tools
make incident-1
make investigate-1
make eval-1
```

Run artifacts are stored in `.opspilot/runs/`; evaluation artifacts are stored in `.opspilot/evals/` by default.
