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
