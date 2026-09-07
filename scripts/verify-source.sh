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

echo "Phase 2 Go source is gofmt-clean. Run 'make test-k8s-mcp' with Go 1.27.1 and downloaded modules for dependency-aware tests."

echo "==> Phase 3 Python syntax"
python3 -m compileall -q "${ROOT_DIR}/services/agent/src" "${ROOT_DIR}/services/agent/tests"

echo "Phase 3 Python source compiles successfully."
