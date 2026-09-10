#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "${ROOT_DIR}"

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is required for manifest validation." >&2
  exit 1
fi

kustomizations=()

while IFS= read -r kustomization; do
  kustomizations+=("${kustomization}")
done < <(find demo infra/kubernetes -name kustomization.yaml -print | sort)

if [[ ${#kustomizations[@]} -eq 0 ]]; then
  echo "No kustomization.yaml files found." >&2
  exit 1
fi

for kustomization in "${kustomizations[@]}"; do
  dir="$(dirname "${kustomization}")"
  rendered="$(mktemp)"

  trap 'rm -f "${rendered}"' EXIT

  echo "==> validating ${dir}"

  kubectl kustomize "${dir}" > "${rendered}"

  test -s "${rendered}"

  kubectl apply \
    --dry-run=client \
    --validate=false \
    -f "${rendered}" >/dev/null

  rm -f "${rendered}"
  trap - EXIT
done

echo "Validated ${#kustomizations[@]} Kustomize targets."