# Kubernetes MCP Server

Phase 2 of OpsPilot exposes read-only Kubernetes diagnostics over Model Context Protocol (MCP) using Go.

## Tools

- `k8s_list_pods` — concise pod health, readiness, restart count, and container state
- `k8s_get_pod` — detailed pod/container diagnostics, resources, probes, and last termination evidence
- `k8s_get_pod_logs` — recent pod logs, capped at 1000 lines
- `k8s_get_events` — recent namespace/object events
- `k8s_get_deployment` — deployment state, images, resources, non-secret environment values, and probes

The server uses Streamable HTTP at `/mcp` and a process health endpoint at `/healthz`.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `OPSPILOT_MCP_ADDR` | `:8080` | HTTP listen address |
| `OPSPILOT_DEFAULT_NAMESPACE` | `opspilot-demo` | Namespace used when a tool call omits one |
| `KUBECONFIG` | empty | Explicit kubeconfig path for local execution |

When running inside Kubernetes, the client automatically uses in-cluster credentials. Outside the cluster it uses `KUBECONFIG`, or falls back to `~/.kube/config`.

## Run locally

The current MCP Go SDK requires Go 1.25+.

```bash
go mod tidy
go test ./...
go run ./cmd/server
```

Then verify the process endpoint:

```bash
curl http://localhost:8080/healthz
```

For the local kind demo, the in-cluster deployment is preferred because it exercises the same ServiceAccount/RBAC model we want in production.

## Security boundary

The Kubernetes manifest grants the server only `get`, `list`, and `watch` access to pods/events/deployments plus `get` access to pod logs in `opspilot-demo`. It cannot create, patch, update, or delete workloads.

Environment values with secret-like names are redacted before they are returned to an MCP client. Secret-backed env vars return only their source reference, never the secret value.
