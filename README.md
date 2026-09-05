# OpsPilot

**Agentic Kubernetes Incident Response Platform**

OpsPilot is a production-style AI/backend project that investigates Kubernetes incidents by combining live cluster evidence with operational knowledge. The final system will use Go for Kubernetes/MCP/backend components and Python for OpenAI agent orchestration, RAG, and evaluation.

## Current milestone: Phase 1

Phase 1 provides a real local Kubernetes environment with three small Go services and four deterministic failure scenarios. This gives later agents real pods, logs, events, probes, resource states, and deployment configuration to inspect.

### Demo services

```text
checkout ──────> inventory
payment
```

- `checkout`: calls `inventory` and exposes a configurable downstream timeout; it can also intentionally allocate memory for OOM testing.
- `inventory`: returns inventory data after a configurable delay.
- `payment`: refuses to start when `DATABASE_URL` is missing.

## Prerequisites

- Docker
- kubectl
- kind
- Go (only needed for local source builds/tests; Docker builds are self-contained)

The kind project recommends tagged stable releases for local/CI usage. On macOS with Homebrew:

```bash
brew install kind kubectl
```

Docker Desktop must also be running.

## Run the healthy baseline

```bash
make verify
make cluster-up
make build-images
make load-images
make deploy-base
make status
```

### Test the services

In separate terminals:

```bash
kubectl port-forward -n opspilot-demo service/checkout 8080:8080
curl http://localhost:8080/checkout
```

```bash
kubectl port-forward -n opspilot-demo service/inventory 8081:8080
curl http://localhost:8081/inventory
```

## Reproducible incidents

Each incident command recreates the `opspilot-demo` namespace so scenarios do not leak state into one another.

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

Expected root cause: a deployment configuration regression removed the required database connection environment variable.

### INC-002 — `OOMKilled`

```bash
make incident-2
make status
kubectl describe pod -n opspilot-demo -l app=checkout
```

Expected evidence:

- checkout is configured with a 64Mi memory limit
- process deliberately touches about 192Mi of memory
- container terminates with reason `OOMKilled` / exit code 137

Expected root cause: checkout exceeded its Kubernetes container memory limit.

### INC-003 — Broken readiness probe

```bash
make incident-3
make status
kubectl describe pod -n opspilot-demo -l app=inventory
```

Expected evidence:

- inventory process is running
- pod remains `Ready=False`
- readiness probe attempts port `8081`
- application listens on port `8080`

Expected root cause: readiness probe configuration points at the wrong container port.

### INC-004 — Downstream timeout

```bash
make incident-4
kubectl port-forward -n opspilot-demo service/checkout 8080:8080
curl -i http://localhost:8080/checkout
```

Expected evidence:

- inventory response delay is 180ms
- checkout timeout is 50ms
- checkout logs report `context deadline exceeded`
- client receives HTTP 503

Expected root cause: a timeout configuration regression makes checkout's downstream deadline shorter than normal inventory response latency.

## Planned architecture

```text
Engineer
   |
   v
Incident API (Go)
   |
   v
Agent Orchestrator (Python / OpenAI)
   |
   +--> Kubernetes MCP Server (Go) --> Kubernetes API
   |
   +--> RAG (Python) --> PostgreSQL + pgvector
   |
   +--> GitHub MCP Server (Go) --> GitHub
   |
   v
Evidence-backed RCA + timeline + remediation
```

## Next milestone

Phase 2 adds a read-only Kubernetes integration in Go and exposes diagnostic capabilities as MCP tools:

- `k8s_list_pods`
- `k8s_get_pod`
- `k8s_get_pod_logs`
- `k8s_get_events`
- `k8s_get_deployment`

The first OpenAI agent will consume those tools only after the Kubernetes diagnostics work independently.
