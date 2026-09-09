# OpsPilot

**Agentic Kubernetes Incident Response Platform**

OpsPilot investigates Kubernetes incidents by combining live cluster diagnostics with operational knowledge. The project deliberately uses **Go** for Kubernetes/MCP infrastructure and **Python** for OpenAI agent orchestration, RAG, evaluation, and observability.

## Current milestone: Phase 5

The end-to-end system now includes:

```text
Engineer
   |
   v
OpenAI Incident Agent (Python)
   |                         \
   | MCP                      \ local RAG tool
   v                           v
Kubernetes MCP Server (Go)   PostgreSQL + pgvector
   |                           |
   v                           v
Kubernetes API               Runbooks / incidents / postmortems
   \                           /
    \                         /
     +---- evidence-backed RCA ----+
                    |
                    v
       Phase 5 deterministic trust layer
       - actual tools used
       - incident timeline
       - evidence/confidence score
       - token/latency metrics
       - evaluation score
       - local run artifacts
```

### Phase 5 trust model

The LLM still performs the semantic root-cause analysis, but it no longer self-reports its tool usage or constructs the authoritative timeline.

After `Runner.run(...)` completes, OpsPilot reads the actual SDK run items and:

1. extracts real MCP/function tool calls,
2. derives `tools_used`,
3. builds a timestamp-sorted timeline from Kubernetes tool outputs,
4. calculates deterministic evidence/confidence coverage,
5. records model request/token/tool-call/latency metrics,
6. saves a local investigation artifact,
7. optionally scores the run against a known incident evaluation case.

This separates **model judgment** from **system-observed facts**.

## Main stack

- Go 1.27.1
- Kubernetes + kind
- Docker
- Model Context Protocol (MCP)
- Python 3.11+
- OpenAI Agents SDK / Responses API
- PostgreSQL + pgvector
- OpenAI embeddings
- FastAPI

## Phase 5 configuration

Add these to `.env` (the defaults are also in `.env.example`):

```bash
OPSPILOT_SAVE_RUN_ARTIFACTS=true
OPSPILOT_RUN_ARTIFACT_DIR=.opspilot/runs
OPSPILOT_EVAL_ARTIFACT_DIR=.opspilot/evals
OPSPILOT_TIMELINE_MAX_EVENTS=20
```

Raw Kubernetes tool outputs are **not** persisted in the local run artifact. The artifact stores the final report plus tool names/arguments; secret-like environment values are already redacted by the Go MCP server.

## Run an investigation

Keep the MCP port-forward open:

```bash
make port-forward-k8s-mcp
```

Inject INC-001 in another terminal:

```bash
make incident-1
```

Then investigate:

```bash
make investigate-1
```

The Phase 5 CLI now adds sections similar to:

```text
Confidence:    high (100/100)
Evidence:      100/100

Deterministic timeline
- ...

Evidence assessment
- Live sources: 5
- Corroborated: yes
- RAG used: yes

Run metrics
- Elapsed: ... ms
- Model requests: ...
- Tokens: ...
- Tool calls: ...
```

The corresponding JSON artifact is written to:

```text
.opspilot/runs/inv-xxxxxxxxxxxx.json
```

## Evaluation framework

The four deterministic incident definitions live in:

```text
evals/cases/incidents.jsonl
```

Evaluate the currently injected incident:

```bash
make eval-case EVAL_CASE=INC-001
```

Convenience targets:

```bash
make eval-1
make eval-2
make eval-3
make eval-4
```

These targets run the evaluation only; inject the matching incident first. For example:

```bash
make incident-2
make eval-2
```

A successful evaluation prints a 0-100 breakdown and writes the full result under:

```text
.opspilot/evals/
```

For INC-004, inject it and generate one failing request before evaluating so checkout has live timeout log evidence:

```bash
make incident-4
kubectl port-forward -n opspilot-demo service/checkout 8081:8080
curl -i http://localhost:8081/checkout
make eval-4
```

## Evaluation dimensions

The deterministic score currently uses:

| Dimension | Weight |
|---|---:|
| Incident status | 15 |
| Root-cause signal coverage | 40 |
| Required tool coverage | 20 |
| Affected resource | 10 |
| Confidence | 5 |
| RAG expectation | 5 |
| Timeline | 5 |
| **Total** | **100** |

The root-cause text is evaluated using incident-specific signal groups rather than exact string equality, so wording can vary while the underlying diagnosis remains measurable.

## Evidence/confidence scoring

Phase 5 separately calculates evidence coverage from the actual tools called:

| Tool | Evidence weight |
|---|---:|
| `k8s_list_pods` | 20 |
| `k8s_get_pod` | 20 |
| `k8s_get_pod_logs` | 20 |
| `k8s_get_events` | 15 |
| `k8s_get_deployment` | 20 |
| `search_knowledge` | 5 |

An additional corroboration bonus is applied when multiple independent live Kubernetes sources are used, capped at 100. Incident/degraded reports cannot receive high deterministic confidence if fewer than two live sources were collected.

The model's own confidence is retained as `assessment.model_confidence` for comparison, while the report's top-level `confidence` is the deterministic Phase 5 confidence.

## OpenAI tracing

OpenAI Agents SDK tracing remains enabled unless:

```bash
OPSPILOT_AGENT_DISABLE_TRACING=true
```

Every investigation adds `investigation_id`, namespace, model, RAG state, component, and phase metadata to the trace. Sensitive trace data remains disabled by default:

```bash
OPSPILOT_AGENT_TRACE_SENSITIVE_DATA=false
```

The same `investigation_id` appears in the CLI output and local run artifact, making it easier to correlate a local investigation with the OpenAI trace.

## Phase 5 checks

```bash
make phase5-check
```

This runs the Python unit suite and source validation. Phase 5 adds tests for deterministic timeline generation, evidence/confidence scoring, evaluation scoring, and observability helpers.

## Security model

The Kubernetes MCP service remains read-only. It can inspect pods, logs, events, and deployments but cannot create, patch, update, or delete workloads. Phase 5 does not add remediation actions.

## Next milestone

A later phase can add the Go Incident API, GitHub/deployment-change correlation, richer benchmark reporting, and eventually human-approved remediation tools.
