# OpsPilot

**Agentic Kubernetes Incident Response Platform**

OpsPilot is a production-style AI/backend project that investigates Kubernetes incidents by combining live cluster evidence with operational knowledge. Go is used for Kubernetes-facing/MCP/backend components; Python will be used for OpenAI agent orchestration, RAG, and evaluation.

## Current milestone: Phase 2

Phase 1 created a real local Kubernetes demo with three Go services and four deterministic incidents. Phase 2 adds a **read-only Kubernetes diagnostic service in Go** and exposes those diagnostics through the official Model Context Protocol Go SDK over Streamable HTTP.

```text
Engineer / future OpenAI agent
             |
             | MCP Streamable HTTP
             v
   k8s-mcp-server (Go)
             |
             | client-go
             v
      Kubernetes API
             |
       opspilot-demo
```

### Phase 2 MCP tools

| Tool | Purpose |
|---|---|
| `k8s_list_pods` | Find unhealthy pods, readiness state, restarts, and container state |
| `k8s_get_pod` | Inspect resources, probes, conditions, and termination evidence |
| `k8s_get_pod_logs` | Read bounded recent/current or previous container logs |
| `k8s_get_events` | Inspect recent namespace/object events |
| `k8s_get_deployment` | Inspect rollout state, images, resources, env metadata, and probes |

The tool output is intentionally normalized instead of returning full Kubernetes API objects. This keeps future LLM context smaller and surfaces evidence that matters for incident diagnosis.

## Security model

The MCP server runs as `system:serviceaccount:opspilot-system:k8s-mcp-server` and receives a namespace-scoped `Role` in `opspilot-demo`.

Allowed:

- `get`, `list`, `watch`: pods, events, deployments
- `get`: pod logs

Not allowed:

- create
- patch
- update
- delete

Secret-like environment values are redacted before tool responses are returned. Environment variables backed by Kubernetes Secrets expose the reference metadata, not the secret value.

## Prerequisites

- Docker Desktop
- kubectl
- kind
- Go **1.25+** for local Phase 2 tests/smoke client

The MCP Go SDK v1.7.0 targets the current 2026-07-28 MCP protocol and requires Go 1.25.

On macOS with Homebrew:

```bash
brew install kind kubectl go
```

## Start Phase 1 healthy baseline

```bash
make verify
make cluster-up
make build-images
make load-images
make deploy-base
make status
```

Test checkout:

```bash
kubectl port-forward -n opspilot-demo service/checkout 8080:8080
curl http://localhost:8080/checkout
```

## Start Phase 2 MCP server

With the healthy demo already running:

```bash
make phase2-up
make status-k8s-mcp
```

The RBAC check should report:

```text
yes
delete deployments: no
```

Expose the MCP server in one terminal:

```bash
make port-forward-k8s-mcp
```

Process health check:

```bash
curl http://localhost:8080/healthz
```

Expected:

```json
{"status":"ok","version":"0.2.0"}
```

In another terminal, use the included Go MCP client to verify protocol discovery and execute the first tool:

```bash
make smoke-k8s-mcp
```

It lists the five MCP tools and calls `k8s_list_pods` against `opspilot-demo`.

### Unit tests

```bash
cd services/k8s-mcp-server
go mod tidy
go test ./...
```

The initial tests verify that failure evidence such as `OOMKilled`, exit code 137, and memory limits are preserved and that secret-like environment configuration is redacted.

## Reproducible incidents

Each incident recreates `opspilot-demo`. The Makefile automatically restores the MCP server's namespace-scoped Role/RoleBinding afterward when Phase 2 is deployed.

### INC-001 — Missing `DATABASE_URL`

```bash
make incident-1
make status
make logs-payment
```

Expected evidence:

- payment pod enters `CrashLoopBackOff`
- application log contains `DATABASE_URL environment variable not configured`
- current Deployment lacks `DATABASE_URL`

### INC-002 — `OOMKilled`

```bash
make incident-2
make status
```

Expected evidence:

- checkout has a 64Mi memory limit
- process deliberately allocates beyond the limit
- previous termination reason is `OOMKilled`, exit code 137

### INC-003 — Broken readiness probe

```bash
make incident-3
make status
```

Expected evidence:

- inventory process is running
- pod remains `Ready=False`
- readiness probe targets port `8081`
- application listens on port `8080`

### INC-004 — Downstream timeout

```bash
make incident-4
kubectl port-forward -n opspilot-demo service/checkout 8081:8080
curl -i http://localhost:8081/checkout
```

Expected evidence:

- inventory response delay is 180ms
- checkout timeout is 50ms
- checkout logs report `context deadline exceeded`
- client receives HTTP 503

## Phase 2 validation against incidents

Once the MCP server is port-forwarded, the smoke client confirms connectivity. Phase 3 will replace the smoke client with the Python OpenAI agent and allow the model to decide which MCP tools to call.

The intended first automated investigation is INC-001:

```text
k8s_list_pods
      |
      v
payment pod = CrashLoopBackOff
      |
      v
k8s_get_pod
      |
      v
restart/failure state
      |
      v
k8s_get_pod_logs
      |
      v
DATABASE_URL not configured
      |
      v
k8s_get_deployment
      |
      v
DATABASE_URL absent
      |
      v
Evidence-backed root cause
```

## Repository architecture

```text
services/
  k8s-mcp-server/             Go - implemented in Phase 2
  incident-api/               Go - later phase
  agent/                      Python/OpenAI - Phase 3
  github-mcp-server/          Go - later phase

infra/kubernetes/opspilot/
  k8s-mcp-server/             ServiceAccount, RBAC, Deployment, Service

demo/
  services/                   Go demo workloads
  incidents/                  deterministic incident overlays

knowledge/                    future RAG corpus
evals/                        incident evaluation cases
```

## Next milestone: Phase 3

Phase 3 adds the Python/OpenAI incident agent and connects it to this MCP endpoint. The first success criterion is that the agent independently investigates INC-001 and returns:

- probable root cause
- supporting evidence
- recommended remediation
- confidence level

No write/remediation Kubernetes tools will be introduced yet.

# Phase 3 — OpenAI Incident Agent

Phase 3 connects a Python OpenAI agent to the read-only Go Kubernetes MCP server from Phase 2.
The model controls the diagnostic loop, while the Go service remains the only component with
Kubernetes API access.

```text
Engineer / CLI / HTTP
        |
        v
Python OpsPilot Agent
OpenAI Agents SDK + Responses API
        |
        | MCP Streamable HTTP
        v
Go Kubernetes MCP Server
        |
        v
Kubernetes API
```

The agent currently expects these MCP tools:

- `k8s_list_pods`
- `k8s_get_pod`
- `k8s_get_pod_logs`
- `k8s_get_events`
- `k8s_get_deployment`

Its final response is a structured `IncidentReport` containing status, affected resources,
root cause, confidence, evidence, timeline, recommended remediation, follow-up checks, and tools
used. No Kubernetes write/remediation tools exist in this phase.

## Phase 3 setup

The repository workspace now targets Go 1.27.1. Phase 3 requires Python 3.11+.

Create the Python environment:

```bash
make agent-setup
make agent-test
```

Create local environment configuration:

```bash
cp .env.example .env
```

Set your platform API key in `.env`:

```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.6-terra
```

`gpt-5.6-terra` is the default Phase 3 model because it balances capability and API cost. The
model can be changed entirely through `OPENAI_MODEL` without code changes.

## Run Python -> Go MCP connectivity check

The Phase 2 MCP service must already be deployed. In terminal 1:

```bash
make port-forward-k8s-mcp
```

In terminal 2:

```bash
make agent-tools
```

Expected tool list:

```text
k8s_get_deployment
k8s_get_events
k8s_get_pod
k8s_get_pod_logs
k8s_list_pods
```

This command does not call OpenAI; it only validates the Python MCP client path to the Go server.

## First end-to-end AI investigation — INC-001

Inject the deterministic payment failure:

```bash
make incident-1
```

Keep the MCP port-forward running, then execute:

```bash
make investigate-1
```

The agent should autonomously collect evidence similar to:

```text
k8s_list_pods
      |
      v
payment pod restarting / CrashLoopBackOff
      |
      +--> k8s_get_pod
      +--> k8s_get_events
      +--> k8s_get_pod_logs
      +--> k8s_get_deployment
      |
      v
DATABASE_URL required by the application but absent from Deployment
      |
      v
Structured evidence-backed RCA
```

The exact tool order is intentionally not hard-coded; deciding what evidence to collect is part of
the agent behavior.

Run any custom investigation with:

```bash
make investigate QUERY="Why is inventory not becoming Ready?"
```

## Phase 3 developer API

The Python service also exposes the same runtime through FastAPI for the later Go Incident API.
With the MCP port-forward active:

```bash
make agent-api
```

Health/tool endpoints:

```bash
curl http://localhost:8001/healthz
curl http://localhost:8001/v1/tools
```

Investigation endpoint:

```bash
curl -s http://localhost:8001/v1/investigations \
  -H 'Content-Type: application/json' \
  -d '{
    "namespace": "opspilot-demo",
    "query": "Why is the payment service failing and repeatedly restarting?"
  }'
```

## Tracing and data handling

OpenAI Agents SDK tracing is left enabled by default so agent/model/tool execution can be inspected
while developing OpsPilot. `OPSPILOT_AGENT_TRACE_SENSITIVE_DATA=false` is the project default so
potentially sensitive generation/tool payloads are not included in traces. The Phase 2 Go MCP
server also redacts likely secret environment variable values before they reach the agent.

## Phase 3 success criterion

Phase 3 is complete when, for INC-001, the agent independently calls the Kubernetes MCP tools and
returns a high-confidence root cause that the payment workload is restarting because the required
`DATABASE_URL` configuration was removed, supported by pod/log/deployment evidence.

# Phase 4 — PostgreSQL + pgvector RAG

Phase 4 adds organizational knowledge retrieval to the live Kubernetes investigation flow.
The agent still treats Kubernetes MCP evidence as the source of truth for the current incident,
but it can now search runbooks, architecture documentation, historical incidents, and
postmortems for analogous failures and safer remediation guidance.

```text
Engineer
   |
   v
Python/OpenAI Incident Agent
   |                         \
   | MCP                      \ search_knowledge
   v                           v
Go Kubernetes MCP        PostgreSQL / pgvector
   |                           |
   v                           v
Live Kubernetes          Runbooks / incidents /
evidence                 postmortems / architecture
          \               /
           \             /
            v           v
           Evidence-backed RCA
```

## Database

The local database is named `opspilot`, with a dedicated `knowledge` schema:

```text
knowledge.documents
knowledge.chunks
```

Chunks use `vector(1536)` embeddings with an HNSW cosine-distance index. The schema also creates
a PostgreSQL full-text `tsvector`/GIN index so hybrid search can be added without a database
migration in a later phase.

### Configure `.env`

Copy `.env.example` if needed and use the same local PostgreSQL credentials you use in PgAdmin:

```text
OPSPILOT_DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/opspilot
OPSPILOT_POSTGRES_ADMIN_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/postgres
OPSPILOT_RAG_ENABLED=true
OPSPILOT_EMBEDDING_MODEL=text-embedding-3-small
OPSPILOT_EMBEDDING_DIMENSIONS=1536
```

### Create and initialize the database

Using OpsPilot commands:

```bash
make agent-setup
make db-create
make db-init
make db-check
```

Or use PgAdmin directly:

1. Run `infra/postgres/00-create-database.sql` while connected to `postgres`.
2. Switch to the newly created `opspilot` database.
3. Run `infra/postgres/01-schema.sql`.

`CREATE EXTENSION vector` requires the pgvector extension to be installed in the PostgreSQL
server, not merely PgAdmin.

### Index the knowledge base

```bash
make rag-ingest
make rag-stats
```

The ingestion pipeline:

```text
knowledge/**/*.md
      |
      v
heading-aware chunking
      |
      v
OpenAI text-embedding-3-small
      |
      v
PostgreSQL knowledge.documents + knowledge.chunks
      |
      v
pgvector HNSW cosine index
```

Ingestion uses SHA-256 content hashes. Re-running `make rag-ingest` skips unchanged documents, so
we do not pay to regenerate embeddings unnecessarily.

### Test retrieval without the agent

```bash
make rag-search RAG_QUERY="payment crashloop missing database configuration"
```

A successful result should rank the payment database runbook and/or the historical payment
postmortem near the top.

### Agent + RAG

With Phase 2's MCP port-forward running, inject an incident and investigate normally:

```bash
make incident-1
make investigate-1
```

The agent can now decide to call:

```text
k8s_list_pods
k8s_get_pod
k8s_get_events
k8s_get_pod_logs
k8s_get_deployment
search_knowledge
```

For INC-001, live Kubernetes evidence should still establish that `DATABASE_URL` is missing. The
knowledge search can then retrieve the payment configuration runbook and similar historical
postmortem to strengthen remediation guidance. Historical documents must never be treated as
proof of the current cluster state.

### Phase 4 checks

```bash
make phase4-check
```

Phase 4 is complete when:

1. `make db-check` reports the `opspilot` database and an installed pgvector version.
2. `make rag-ingest` indexes the Markdown knowledge base.
3. `make rag-search` returns semantically relevant runbooks/incidents.
4. `make investigate-1` includes `search_knowledge` when useful while grounding the root cause in
   live Kubernetes evidence.
