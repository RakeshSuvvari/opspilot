#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

version_ge() {
  local have="$1" need="$2"
  [[ "$(printf '%s\n%s\n' "${need}" "${have}" | sort -V | head -n1)" == "${need}" ]]
}

GO_VERSION="$(GOWORK=off GOTOOLCHAIN=local go version | awk '{print $3}' | sed 's/^go//')"
if version_ge "${GO_VERSION}" "1.27.0"; then
  for service in checkout payment inventory; do
    echo "==> testing ${service}"
    (cd "${ROOT_DIR}/demo/services/${service}" && GOWORK=off go test ./...)
  done
  echo "All Phase 1 Go services compile successfully."

  echo "==> testing Kubernetes MCP server"
  (cd "${ROOT_DIR}/services/k8s-mcp-server" && GOWORK=off go test ./...)
  echo "==> testing GitHub MCP server"
  (cd "${ROOT_DIR}/services/github-mcp-server" && GOWORK=off go test ./...)
  echo "==> testing Phase 8 Incident API"
  (cd "${ROOT_DIR}/services/incident-api" && GOWORK=off go test ./...)
else
  echo "Go ${GO_VERSION} detected; skipping dependency-aware Go tests that require the project's Go 1.27.1 toolchain."
fi

echo "==> Kubernetes MCP source formatting"
phase2_diff="$(find "${ROOT_DIR}/services/k8s-mcp-server" -name '*.go' -print0 | xargs -0 gofmt -d)"
if [[ -n "${phase2_diff}" ]]; then
  printf '%s\n' "${phase2_diff}"
  echo "Kubernetes MCP Go source is not gofmt-clean." >&2
  exit 1
fi

echo "==> Phase 6 GitHub MCP source formatting"
phase6_diff="$(find "${ROOT_DIR}/services/github-mcp-server" -name '*.go' -print0 | xargs -0 gofmt -d)"
if [[ -n "${phase6_diff}" ]]; then
  printf '%s\n' "${phase6_diff}"
  echo "Phase 6 GitHub MCP Go source is not gofmt-clean." >&2
  exit 1
fi

echo "==> Phase 3-10 Python syntax"
python3 -m compileall -q "${ROOT_DIR}/services/agent/src" "${ROOT_DIR}/services/agent/tests"

echo "==> Phase 4 SQL files"
test -s "${ROOT_DIR}/infra/postgres/00-create-database.sql"
test -s "${ROOT_DIR}/infra/postgres/01-schema.sql"
grep -q "CREATE EXTENSION IF NOT EXISTS vector" "${ROOT_DIR}/infra/postgres/01-schema.sql"
grep -q "USING hnsw" "${ROOT_DIR}/infra/postgres/01-schema.sql"

echo "==> Phase 5 evaluation cases"
test -s "${ROOT_DIR}/evals/cases/incidents.jsonl"
grep -q '"INC-001"' "${ROOT_DIR}/evals/cases/incidents.jsonl"
grep -q '"INC-004"' "${ROOT_DIR}/evals/cases/incidents.jsonl"

echo "==> Phase 6 fixtures/evaluation cases"
test -s "${ROOT_DIR}/services/github-mcp-server/fixtures/demo.json"
test -s "${ROOT_DIR}/evals/cases/incidents-phase6.jsonl"
grep -q '"INC-001-GIT"' "${ROOT_DIR}/evals/cases/incidents-phase6.jsonl"
grep -q 'opspilot.dev/revision' "${ROOT_DIR}/demo/kubernetes/base/payment.yaml"

echo "All source checks passed."

grep -q 'OPSPILOT_GITHUB_OWNER=RakeshSuvvari' "${ROOT_DIR}/.env"
grep -q 'OPSPILOT_GITHUB_REPO=opspilot' "${ROOT_DIR}/.env"
grep -q '^stamp-git-provenance:' "${ROOT_DIR}/Makefile"
grep -q '^github-mcp-server-live:' "${ROOT_DIR}/Makefile"

echo "==> Phase 7 remediation surface"
grep -q 'OPSPILOT_REMEDIATION_ENABLED=false' "${ROOT_DIR}/.env"
grep -q 'k8s_restart_deployment' "${ROOT_DIR}/services/k8s-mcp-server/internal/tools/tools.go"
grep -q 'k8s_scale_deployment' "${ROOT_DIR}/services/k8s-mcp-server/internal/tools/tools.go"
grep -q 'k8s_rollback_deployment' "${ROOT_DIR}/services/k8s-mcp-server/internal/tools/tools.go"
test -s "${ROOT_DIR}/infra/kubernetes/opspilot/k8s-mcp-server/rbac-remediation.yaml"
grep -q 'resources: \["deployments"\]' "${ROOT_DIR}/infra/kubernetes/opspilot/k8s-mcp-server/rbac-remediation.yaml"
if grep -q 'verbs:.*delete' "${ROOT_DIR}/infra/kubernetes/opspilot/k8s-mcp-server/rbac-remediation.yaml"; then
  echo "Phase 7 remediation RBAC must not grant delete." >&2
  exit 1
fi

echo "Phase 7 remediation source checks passed."


echo "==> Phase 8 dashboard/API surface"
phase8_go_diff="$(find "${ROOT_DIR}/services/incident-api" -name '*.go' -print0 | xargs -0 gofmt -d)"
if [[ -n "${phase8_go_diff}" ]]; then
  printf '%s\n' "${phase8_go_diff}"
  echo "Phase 8 Incident API Go source is not gofmt-clean." >&2
  exit 1
fi
test -s "${ROOT_DIR}/apps/dashboard/src/App.tsx"
test -s "${ROOT_DIR}/apps/dashboard/src/components/ApprovalPanel.tsx"
test -s "${ROOT_DIR}/services/agent/src/opspilot_agent/remediation_jobs.py"
grep -q 'OPSPILOT_AGENT_API_URL=http://localhost:8001' "${ROOT_DIR}/.env"
grep -q './services/incident-api' "${ROOT_DIR}/go.work"

echo "Phase 8 dashboard/API source checks passed."


echo "==> Phase 9 persisted incident history"
grep -q 'CREATE SCHEMA IF NOT EXISTS operations' "${ROOT_DIR}/infra/postgres/01-schema.sql"
grep -q 'CREATE TABLE IF NOT EXISTS operations.investigations' "${ROOT_DIR}/infra/postgres/01-schema.sql"
test -s "${ROOT_DIR}/services/agent/src/opspilot_agent/history.py"
test -s "${ROOT_DIR}/apps/dashboard/src/components/HistoryPanel.tsx"
grep -q 'OPSPILOT_HISTORY_ENABLED=true' "${ROOT_DIR}/.env"
grep -q 'GET /api/v1/investigations' "${ROOT_DIR}/services/incident-api/internal/api/server.go"

echo "Phase 9 persistence source checks passed."


echo "==> Phase 10 final benchmark suite"
test -s "${ROOT_DIR}/evals/cases/benchmark.jsonl"
test -s "${ROOT_DIR}/benchmarks/scenarios.json"
test -s "${ROOT_DIR}/services/agent/src/opspilot_agent/benchmarks/cli.py"
grep -q '"INC-005"' "${ROOT_DIR}/evals/cases/benchmark.jsonl"
grep -q '"INC-010"' "${ROOT_DIR}/evals/cases/benchmark.jsonl"
grep -q 'opspilot-benchmark' "${ROOT_DIR}/services/agent/pyproject.toml"
grep -q 'OPSPILOT_BENCHMARK_INPUT_USD_PER_MILLION=0.75' "${ROOT_DIR}/.env"
for incident in 005-image-pull 006-missing-secret 007-bad-inventory-dns 008-broken-liveness 009-port-mismatch; do
  test -s "${ROOT_DIR}/demo/incidents/inc-${incident}/kustomization.yaml"
done

echo "Phase 10 benchmark source checks passed."
