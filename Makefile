SHELL := /bin/bash
CLUSTER_NAME ?= opspilot
NAMESPACE ?= opspilot-demo
SYSTEM_NAMESPACE ?= opspilot-system
K8S_MCP_IMAGE ?= opspilot/k8s-mcp-server:dev

.PHONY: help verify cluster-up cluster-down build-images load-images deploy-base reset-demo status logs-checkout logs-payment logs-inventory incident-1 incident-2 incident-3 incident-4 \
	build-k8s-mcp-image load-k8s-mcp-image deploy-k8s-mcp restore-k8s-mcp-rbac status-k8s-mcp logs-k8s-mcp port-forward-k8s-mcp test-k8s-mcp smoke-k8s-mcp phase2-up

help:
	@echo "OpsPilot"
	@echo ""
	@echo "Phase 1 - demo cluster"
	@echo "  make verify              - verify required local tools"
	@echo "  make cluster-up          - create local kind cluster"
	@echo "  make build-images        - build demo service images"
	@echo "  make load-images         - load demo images into kind"
	@echo "  make deploy-base         - deploy healthy baseline"
	@echo "  make incident-1          - missing DATABASE_URL / CrashLoopBackOff"
	@echo "  make incident-2          - memory limit / OOMKilled"
	@echo "  make incident-3          - broken readiness probe"
	@echo "  make incident-4          - downstream timeout / HTTP 503"
	@echo "  make status              - show demo pods, deployments, events"
	@echo ""
	@echo "Phase 2 - Go Kubernetes MCP server"
	@echo "  make phase2-up           - build, load, and deploy the MCP server"
	@echo "  make test-k8s-mcp        - run Go unit tests"
	@echo "  make status-k8s-mcp      - show MCP server workload status"
	@echo "  make logs-k8s-mcp        - stream MCP server logs"
	@echo "  make port-forward-k8s-mcp - expose MCP server at localhost:8080"
	@echo "  make smoke-k8s-mcp       - connect as MCP client and call k8s_list_pods"
	@echo ""
	@echo "  make cluster-down        - delete local cluster"

verify:
	@command -v docker >/dev/null || (echo "docker is required" && exit 1)
	@command -v kind >/dev/null || (echo "kind is required" && exit 1)
	@command -v kubectl >/dev/null || (echo "kubectl is required" && exit 1)
	@command -v go >/dev/null || (echo "go is required for Phase 2 local tests/smoke client" && exit 1)
	@echo "All required tools are available."
	@go version

cluster-up:
	kind create cluster --name $(CLUSTER_NAME) --config demo/cluster/kind-config.yaml --wait 90s

cluster-down:
	kind delete cluster --name $(CLUSTER_NAME)

build-images:
	docker build -t opspilot/checkout:dev demo/services/checkout
	docker build -t opspilot/payment:dev demo/services/payment
	docker build -t opspilot/inventory:dev demo/services/inventory

load-images:
	kind load docker-image --name $(CLUSTER_NAME) opspilot/checkout:dev opspilot/payment:dev opspilot/inventory:dev

deploy-base:
	kubectl apply -k demo/kubernetes/base
	kubectl rollout status deployment/checkout -n $(NAMESPACE) --timeout=60s
	kubectl rollout status deployment/payment -n $(NAMESPACE) --timeout=60s
	kubectl rollout status deployment/inventory -n $(NAMESPACE) --timeout=60s

reset-demo:
	-kubectl delete namespace $(NAMESPACE) --ignore-not-found=true --wait=true
	kubectl apply -k demo/kubernetes/base
	@$(MAKE) --no-print-directory restore-k8s-mcp-rbac

status:
	@echo "=== Pods ==="
	kubectl get pods -n $(NAMESPACE) -o wide
	@echo
	@echo "=== Deployments ==="
	kubectl get deployments -n $(NAMESPACE)
	@echo
	@echo "=== Recent Events ==="
	kubectl get events -n $(NAMESPACE) --sort-by=.lastTimestamp | tail -25

logs-checkout:
	kubectl logs -n $(NAMESPACE) deployment/checkout --tail=100

logs-payment:
	kubectl logs -n $(NAMESPACE) deployment/payment --tail=100

logs-inventory:
	kubectl logs -n $(NAMESPACE) deployment/inventory --tail=100

incident-1:
	-kubectl delete namespace $(NAMESPACE) --ignore-not-found=true --wait=true
	kubectl apply -k demo/incidents/inc-001-missing-database-url
	@$(MAKE) --no-print-directory restore-k8s-mcp-rbac
	@echo "INC-001 injected. Run: make status && make logs-payment"

incident-2:
	-kubectl delete namespace $(NAMESPACE) --ignore-not-found=true --wait=true
	kubectl apply -k demo/incidents/inc-002-oomkilled
	@$(MAKE) --no-print-directory restore-k8s-mcp-rbac
	@echo "INC-002 injected. Run: make status; then inspect checkout pod lastState/termination reason."

incident-3:
	-kubectl delete namespace $(NAMESPACE) --ignore-not-found=true --wait=true
	kubectl apply -k demo/incidents/inc-003-broken-readiness
	@$(MAKE) --no-print-directory restore-k8s-mcp-rbac
	@echo "INC-003 injected. Run: make status; then kubectl describe pod -n $(NAMESPACE) -l app=inventory"

incident-4:
	-kubectl delete namespace $(NAMESPACE) --ignore-not-found=true --wait=true
	kubectl apply -k demo/incidents/inc-004-downstream-timeout
	@$(MAKE) --no-print-directory restore-k8s-mcp-rbac
	@echo "INC-004 injected. Port-forward checkout and call /checkout to observe the timeout."

build-k8s-mcp-image:
	docker build -t $(K8S_MCP_IMAGE) services/k8s-mcp-server

load-k8s-mcp-image:
	kind load docker-image --name $(CLUSTER_NAME) $(K8S_MCP_IMAGE)

deploy-k8s-mcp:
	@kubectl get namespace $(NAMESPACE) >/dev/null 2>&1 || (echo "$(NAMESPACE) does not exist. Run 'make deploy-base' first." && exit 1)
	kubectl apply -k infra/kubernetes/opspilot/k8s-mcp-server
	kubectl rollout status deployment/k8s-mcp-server -n $(SYSTEM_NAMESPACE) --timeout=90s

restore-k8s-mcp-rbac:
	@if kubectl get namespace $(SYSTEM_NAMESPACE) >/dev/null 2>&1; then \
		kubectl apply -f infra/kubernetes/opspilot/k8s-mcp-server/rbac.yaml >/dev/null; \
		echo "Restored OpsPilot MCP read-only RBAC in $(NAMESPACE)."; \
	fi

status-k8s-mcp:
	kubectl get deployment,pod,service -n $(SYSTEM_NAMESPACE) -o wide
	@echo
	@echo "=== RBAC check ==="
	kubectl auth can-i list pods -n $(NAMESPACE) --as=system:serviceaccount:$(SYSTEM_NAMESPACE):k8s-mcp-server
	@printf "delete deployments: "
	@kubectl auth can-i delete deployments -n $(NAMESPACE) --as=system:serviceaccount:$(SYSTEM_NAMESPACE):k8s-mcp-server || true

logs-k8s-mcp:
	kubectl logs -n $(SYSTEM_NAMESPACE) deployment/k8s-mcp-server -f --tail=100

port-forward-k8s-mcp:
	kubectl port-forward -n $(SYSTEM_NAMESPACE) service/k8s-mcp-server 8080:8080

test-k8s-mcp:
	cd services/k8s-mcp-server && go test ./...

smoke-k8s-mcp:
	cd services/k8s-mcp-server && go run ./cmd/smoke -endpoint http://localhost:8080/mcp -namespace $(NAMESPACE)

phase2-up: build-k8s-mcp-image load-k8s-mcp-image deploy-k8s-mcp
	@echo "Phase 2 MCP server deployed. Next: make port-forward-k8s-mcp"
