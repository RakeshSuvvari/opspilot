#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for service in checkout payment inventory; do
  echo "==> testing ${service}"
  (cd "${ROOT_DIR}/demo/services/${service}" && GOWORK=off go test ./...)
done

echo "All Phase 1 Go services compile successfully."

echo "==> Phase 2 source formatting"
phase2_diff="$(find "${ROOT_DIR}/services/k8s-mcp-server" -name '*.go' -print0 | xargs -0 gofmt -d)"
if [[ -n "${phase2_diff}" ]]; then
  printf '%s\n' "${phase2_diff}"
  echo "Phase 2 Go source is not gofmt-clean." >&2
  exit 1
fi

echo "Phase 2 Go source is gofmt-clean."

echo "==> Phase 3-5 Python syntax"
python3 -m compileall -q "${ROOT_DIR}/services/agent/src" "${ROOT_DIR}/services/agent/tests"

echo "Phase 3-5 Python source compiles successfully."

echo "==> Phase 4 SQL files"
test -s "${ROOT_DIR}/infra/postgres/00-create-database.sql"
test -s "${ROOT_DIR}/infra/postgres/01-schema.sql"
grep -q "CREATE EXTENSION IF NOT EXISTS vector" "${ROOT_DIR}/infra/postgres/01-schema.sql"
grep -q "USING hnsw" "${ROOT_DIR}/infra/postgres/01-schema.sql"

echo "Phase 4 PostgreSQL schema files are present."

echo "==> Phase 5 evaluation cases"
test -s "${ROOT_DIR}/evals/cases/incidents.jsonl"
grep -q '"INC-001"' "${ROOT_DIR}/evals/cases/incidents.jsonl"
grep -q '"INC-004"' "${ROOT_DIR}/evals/cases/incidents.jsonl"

echo "Phase 5 evaluation cases are present."
