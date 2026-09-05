SHELL := /bin/bash
CLUSTER_NAME ?= opspilot
NAMESPACE ?= opspilot-demo

.PHONY: help verify cluster-up cluster-down build-images load-images deploy-base reset-demo status logs-checkout logs-payment logs-inventory incident-1 incident-2 incident-3 incident-4

help:
	@echo "OpsPilot Phase 1"
	@echo "  make verify       - verify required local tools"
	@echo "  make cluster-up   - create local kind cluster"
	@echo "  make build-images - build demo service images"
	@echo "  make load-images  - load demo images into kind"
	@echo "  make deploy-base  - deploy healthy baseline"
	@echo "  make incident-1   - missing DATABASE_URL / CrashLoopBackOff"
	@echo "  make incident-2   - memory limit / OOMKilled"
	@echo "  make incident-3   - broken readiness probe"
	@echo "  make incident-4   - downstream timeout / HTTP 503"
	@echo "  make status       - show pods, deployments, events"
	@echo "  make cluster-down - delete local cluster"

verify:
	@command -v docker >/dev/null || (echo "docker is required" && exit 1)
	@command -v kind >/dev/null || (echo "kind is required" && exit 1)
	@command -v kubectl >/dev/null || (echo "kubectl is required" && exit 1)
	@echo "All required tools are available."

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
	@echo "INC-001 injected. Run: make status && make logs-payment"

incident-2:
	-kubectl delete namespace $(NAMESPACE) --ignore-not-found=true --wait=true
	kubectl apply -k demo/incidents/inc-002-oomkilled
	@echo "INC-002 injected. Run: make status; then inspect checkout pod lastState/termination reason."

incident-3:
	-kubectl delete namespace $(NAMESPACE) --ignore-not-found=true --wait=true
	kubectl apply -k demo/incidents/inc-003-broken-readiness
	@echo "INC-003 injected. Run: make status; then kubectl describe pod -n $(NAMESPACE) -l app=inventory"

incident-4:
	-kubectl delete namespace $(NAMESPACE) --ignore-not-found=true --wait=true
	kubectl apply -k demo/incidents/inc-004-downstream-timeout
	@echo "INC-004 injected. Port-forward checkout and call /checkout to observe the timeout."
