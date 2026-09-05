#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for service in checkout payment inventory; do
  echo "==> testing ${service}"
  (cd "${ROOT_DIR}/demo/services/${service}" && go test ./...)
done

echo "All Phase 1 Go services compile successfully."
