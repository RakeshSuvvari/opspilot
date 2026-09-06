#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for service in checkout payment inventory; do
  echo "==> testing ${service}"
  (cd "${ROOT_DIR}/demo/services/${service}" && GOWORK=off go test ./...)
done

echo "All Phase 1 Go services compile successfully."

echo "==> Phase 2 source syntax"
find "${ROOT_DIR}/services/k8s-mcp-server" -name '*.go' -print0 | xargs -0 gofmt -d

echo "Phase 2 Go source is gofmt-clean. Dependency-aware tests require Go 1.25+ and downloaded modules."
