#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "${ROOT_DIR}"

if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is required for Kustomize rendering." >&2
  exit 1
fi

if ! command -v kubeconform >/dev/null 2>&1; then
  echo "kubeconform is required for manifest validation." >&2
  exit 1
fi

kustomizations=()

while IFS= read -r kustomization; do
  kustomizations+=("${kustomization}")
done < <(
  find demo infra/kubernetes \
    -name kustomization.yaml \
    -print | sort
)

if [[ ${#kustomizations[@]} -eq 0 ]]; then
  echo "No kustomization.yaml files found." >&2
  exit 1
fi

for kustomization in "${kustomizations[@]}"; do
  dir="$(dirname "${kustomization}")"
  rendered="$(mktemp)"

  trap 'rm -f "${rendered}"' EXIT

  echo "==> validating ${dir}"

  # Render the complete Kustomize target locally.
  #
  # This validates Kustomize references, patches, resources,
  # and overlay composition without requiring a live cluster.
  kubectl kustomize "${dir}" > "${rendered}"

  if [[ ! -s "${rendered}" ]]; then
    echo "Kustomize produced no resources for ${dir}." >&2
    exit 1
  fi

  # Validate the rendered Kubernetes resources against Kubernetes
  # schemas without connecting to a Kubernetes API server.
  kubeconform \
    -strict \
    -summary \
    -exit-on-error \
    "${rendered}"

  rm -f "${rendered}"
  trap - EXIT
done

echo
echo "Validated ${#kustomizations[@]} Kustomize targets."