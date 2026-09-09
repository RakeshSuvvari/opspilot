SHELL := /bin/bash
CLUSTER_NAME ?= opspilot
NAMESPACE ?= opspilot-demo
SYSTEM_NAMESPACE ?= opspilot-system
K8S_MCP_IMAGE ?= opspilot/k8s-mcp-server:dev
AGENT_IMAGE ?= opspilot/agent:dev
AGENT_DIR ?= services/agent
AGENT_VENV ?= $(AGENT_DIR)/.venv
AGENT_PYTHON ?= $(AGENT_VENV)/bin/python
AGENT_STAMP ?= $(AGENT_VENV)/.opspilot-installed
QUERY ?= Investigate the current Kubernetes incident. Identify the most likely root cause, support it with live evidence, and recommend a safe remediation.
RAG_QUERY ?= crashloop missing database configuration
EVAL_CASE ?= INC-001
EVAL_CASES ?= evals/cases/incidents.jsonl

.PHONY: help verify cluster-up cluster-down build-images load-images deploy-base reset-demo status logs-checkout logs-payment logs-inventory incident-1 incident-2 incident-3 incident-4 \
	build-k8s-mcp-image load-k8s-mcp-image deploy-k8s-mcp restart-k8s-mcp restore-k8s-mcp-rbac status-k8s-mcp logs-k8s-mcp port-forward-k8s-mcp test-k8s-mcp smoke-k8s-mcp phase2-up \
	agent-setup agent-test agent-tools investigate investigate-1 agent-api build-agent-image phase3-check \
	db-create db-init db-check rag-ingest rag-search rag-stats phase4-check \
	eval-case eval-1 eval-2 eval-3 eval-4 phase5-check

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
	@echo "  make restart-k8s-mcp     - recreate MCP pod so a rebuilt :dev image is used"
	@echo "  make logs-k8s-mcp        - stream MCP server logs"
	@echo "  make port-forward-k8s-mcp - expose MCP server at localhost:8080"
	@echo "  make smoke-k8s-mcp       - connect as MCP client and call k8s_list_pods"
	@echo ""
	@echo "Phase 3 - Python/OpenAI incident agent"
	@echo "  make agent-setup         - create venv and install the Phase 3 agent"
	@echo "  make agent-test          - run Phase 3 unit tests"
	@echo "  make agent-tools         - verify Python agent -> Go MCP connectivity"
	@echo "  make investigate         - run an investigation; override QUERY='...'"
	@echo "  make investigate-1       - investigate the payment failure in INC-001"
	@echo "  make agent-api           - run FastAPI agent service on port 8001"
	@echo "  make phase3-check        - source checks + Phase 3 tests"
	@echo ""
	@echo "Phase 4 - PostgreSQL/pgvector RAG"
	@echo "  make db-create           - create the local opspilot PostgreSQL database"
	@echo "  make db-init             - enable pgvector and create knowledge tables/indexes"
	@echo "  make db-check            - show PostgreSQL, pgvector, document, and chunk status"
	@echo "  make rag-ingest          - embed and index Markdown files under knowledge/"
	@echo "  make rag-search          - semantic search; override RAG_QUERY='...'"
	@echo "  make rag-stats           - summarize indexed documents and chunks"
	@echo "  make phase4-check        - source checks + agent/RAG unit tests"
	@echo ""
	@echo "Phase 5 - trust, observability, and evaluation"
	@echo "  make eval-case EVAL_CASE=INC-001 - evaluate the currently injected incident"
	@echo "  make eval-1              - evaluate INC-001 (inject it first with make incident-1)"
	@echo "  make eval-2              - evaluate INC-002 (inject it first with make incident-2)"
	@echo "  make eval-3              - evaluate INC-003 (inject it first with make incident-3)"
	@echo "  make eval-4              - evaluate INC-004 after triggering /checkout once"
	@echo "  make phase5-check        - source checks + Phase 5 unit tests"
	@echo ""
	@echo "  make cluster-down        - delete local cluster"

verify:
	@command -v docker >/dev/null || (echo "docker is required" && exit 1)
	@command -v kind >/dev/null || (echo "kind is required" && exit 1)
	@command -v kubectl >/dev/null || (echo "kubectl is required" && exit 1)
	@command -v go >/dev/null || (echo "go is required for Phase 2 local tests/smoke client" && exit 1)
	@command -v python3 >/dev/null || (echo "python3 is required for Phase 3" && exit 1)
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
	@$(MAKE) --no-print-directory restart-k8s-mcp

restart-k8s-mcp:
	kubectl rollout restart deployment/k8s-mcp-server -n $(SYSTEM_NAMESPACE)
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


agent-setup: $(AGENT_STAMP)

$(AGENT_STAMP): $(AGENT_DIR)/pyproject.toml
	@test -x $(AGENT_PYTHON) || python3 -m venv $(AGENT_VENV)
	$(AGENT_PYTHON) -m pip install --upgrade pip
	$(AGENT_PYTHON) -m pip install -e $(AGENT_DIR)
	@touch $(AGENT_STAMP)

agent-test: agent-setup
	PYTHONPATH=$(AGENT_DIR)/src $(AGENT_PYTHON) -m unittest discover -s $(AGENT_DIR)/tests -v

agent-tools: agent-setup
	@if [ -f .env ]; then set -a; source .env; set +a; fi; \
		$(AGENT_PYTHON) -m opspilot_agent.cli tools

investigate: agent-setup
	@if [ -f .env ]; then set -a; source .env; set +a; fi; \
		$(AGENT_PYTHON) -m opspilot_agent.cli investigate --namespace $(NAMESPACE) --query "$(QUERY)"

investigate-1: agent-setup
	@if [ -f .env ]; then set -a; source .env; set +a; fi; \
		$(AGENT_PYTHON) -m opspilot_agent.cli investigate --namespace $(NAMESPACE) --query "Why is the payment service failing and repeatedly restarting? Diagnose the root cause from live Kubernetes evidence."

agent-api: agent-setup
	@if [ -f .env ]; then set -a; source .env; set +a; fi; \
		$(AGENT_PYTHON) -m uvicorn opspilot_agent.api:app --host "$${OPSPILOT_AGENT_HOST:-127.0.0.1}" --port "$${OPSPILOT_AGENT_PORT:-8001}"

build-agent-image:
	docker build -t $(AGENT_IMAGE) $(AGENT_DIR)

phase3-check: agent-test
	./scripts/verify-source.sh
	@echo "Phase 3 source checks passed. With the MCP port-forward running, use: make agent-tools"

# Phase 4 - PostgreSQL/pgvector knowledge base
db-create: agent-setup
	@if [ -f .env ]; then set -a; source .env; set +a; fi; \
		$(AGENT_PYTHON) -m opspilot_agent.rag.admin create

db-init: agent-setup
	@if [ -f .env ]; then set -a; source .env; set +a; fi; \
		$(AGENT_PYTHON) -m opspilot_agent.rag.admin init

db-check: agent-setup
	@if [ -f .env ]; then set -a; source .env; set +a; fi; \
		$(AGENT_PYTHON) -m opspilot_agent.rag.admin check

rag-ingest: agent-setup
	@if [ -f .env ]; then set -a; source .env; set +a; fi; \
		$(AGENT_PYTHON) -m opspilot_agent.rag.cli ingest --root knowledge

rag-search: agent-setup
	@if [ -f .env ]; then set -a; source .env; set +a; fi; \
		$(AGENT_PYTHON) -m opspilot_agent.rag.cli search --query "$(RAG_QUERY)"

rag-stats: agent-setup
	@if [ -f .env ]; then set -a; source .env; set +a; fi; \
		$(AGENT_PYTHON) -m opspilot_agent.rag.cli stats

phase4-check: agent-test
	./scripts/verify-source.sh
	@echo "Phase 4 source checks passed. Next: make db-check && make rag-search"

# Phase 5 - deterministic trust, observability, and evaluation
eval-case: agent-setup
	@if [ -f .env ]; then set -a; source .env; set +a; fi; \
		$(AGENT_PYTHON) -m opspilot_agent.evals.cli --cases $(EVAL_CASES) --case $(EVAL_CASE) --namespace $(NAMESPACE)

eval-1: agent-setup
	@$(MAKE) --no-print-directory eval-case EVAL_CASE=INC-001

eval-2: agent-setup
	@$(MAKE) --no-print-directory eval-case EVAL_CASE=INC-002

eval-3: agent-setup
	@$(MAKE) --no-print-directory eval-case EVAL_CASE=INC-003

eval-4: agent-setup
	@$(MAKE) --no-print-directory eval-case EVAL_CASE=INC-004

phase5-check: agent-test
	./scripts/verify-source.sh
	@echo "Phase 5 source checks passed. Next: inject an incident and run make eval-case EVAL_CASE=INC-00X"
