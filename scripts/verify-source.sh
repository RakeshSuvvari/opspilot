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

echo "==> Phase 3-6 Python syntax"
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
