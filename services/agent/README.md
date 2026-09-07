# OpsPilot Agent Service (Phase 3)

Python/OpenAI orchestration layer for evidence-backed Kubernetes incident diagnosis.

## Responsibilities

- Connect to the Go Kubernetes MCP server over Streamable HTTP.
- Let the OpenAI agent choose diagnostic MCP tools autonomously.
- Return a typed `IncidentReport` rather than free-form chat text.
- Keep Phase 3 read-only: the agent may recommend remediation but cannot execute it.
- Keep OpenAI tracing enabled by default while excluding sensitive inputs/tool outputs from trace payloads.

## MCP tools expected

- `k8s_list_pods`
- `k8s_get_pod`
- `k8s_get_pod_logs`
- `k8s_get_events`
- `k8s_get_deployment`

The service refuses to start its runtime if any expected Phase 2 diagnostic tool is missing.

## Configuration

```bash
export OPENAI_API_KEY="..."
export OPENAI_MODEL="gpt-5.6-terra"
export OPSPILOT_K8S_MCP_URL="http://localhost:8080/mcp"
export OPSPILOT_DEFAULT_NAMESPACE="opspilot-demo"
```

Additional controls:

```bash
export OPSPILOT_AGENT_MAX_TURNS=12
export OPSPILOT_AGENT_MCP_TIMEOUT_SECONDS=10
export OPSPILOT_AGENT_MCP_RETRIES=2
export OPSPILOT_AGENT_TRACE_SENSITIVE_DATA=false
export OPSPILOT_AGENT_DISABLE_TRACING=false
```

## CLI

```bash
opspilot-agent tools

opspilot-agent investigate \
  --query "Why is the payment service failing?" \
  --namespace opspilot-demo
```

Use `--json` for an evaluation/API-friendly JSON object.

## Developer API

```bash
uvicorn opspilot_agent.api:app --host 127.0.0.1 --port 8001
```

Endpoints:

- `GET /healthz`
- `GET /v1/tools`
- `POST /v1/investigations`
