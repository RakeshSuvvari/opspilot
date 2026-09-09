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
PHASE6_EVAL_CASES ?= evals/cases/incidents-phase6.jsonl
GITHUB_MCP_URL ?= http://localhost:8090/mcp

.PHONY: help verify cluster-up cluster-down build-images load-images deploy-base reset-demo status logs-checkout logs-payment logs-inventory incident-1 incident-2 incident-3 incident-4 \
	build-k8s-mcp-image load-k8s-mcp-image deploy-k8s-mcp restart-k8s-mcp restore-k8s-mcp-rbac status-k8s-mcp logs-k8s-mcp port-forward-k8s-mcp test-k8s-mcp smoke-k8s-mcp phase2-up \
	agent-setup agent-test agent-tools agent-tools-remediation investigate investigate-1 agent-api build-agent-image phase3-check \
	db-create db-init db-check rag-ingest rag-search rag-stats phase4-check \
	eval-case eval-1 eval-2 eval-3 eval-4 phase5-check \
	github-mcp-server github-mcp-server-live github-mcp-server-fixture smoke-github-mcp test-github-mcp github-health stamp-git-provenance deploy-base-live investigate-live investigate-1-change investigate-2-change investigate-3-change investigate-4-change \
	eval-change-1 eval-change-2 eval-change-3 eval-change-4 phase6-check \
	enable-remediation disable-remediation restore-k8s-remediation-rbac status-remediation phase7-up incident-1-rollout incident-2-rollout incident-3-rollout remediate remediate-1 phase7-check

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

	@echo "Phase 6 - GitHub deployment/source-change correlation"
	@echo "  make github-mcp-server       - run GitHub MCP using .env mode (live is the project default)"
	@echo "  make github-mcp-server-live  - run against RakeshSuvvari/opspilot using GitHub REST"
	@echo "  make github-mcp-server-fixture - run deterministic incident fixture history"
	@echo "  make deploy-base-live        - deploy healthy demo and stamp real Git commit provenance"
	@echo "  make stamp-git-provenance    - annotate demo Deployments with the current real repo SHA"
	@echo "  make investigate-live        - investigate current cluster with live GitHub correlation"
	@echo "  make smoke-github-mcp   - list/call GitHub MCP tools without using OpenAI"
	@echo "  make investigate-1-change - investigate INC-001 with GitHub correlation enabled"
	@echo "  make investigate-2-change - investigate INC-002 with GitHub correlation enabled"
	@echo "  make investigate-3-change - investigate INC-003 with GitHub correlation enabled"
	@echo "  make investigate-4-change - investigate INC-004 with GitHub correlation enabled"
	@echo "  make eval-change-1      - Phase 6 change-aware evaluation for INC-001"
	@echo "  make phase6-check       - source checks + Python tests + GitHub MCP formatting/tests"
	@echo ""
	@echo "Phase 7 - human-approved Kubernetes remediation"
	@echo "  make phase7-up           - enable restart/scale/rollback tools plus least-privilege writer RBAC"
	@echo "  make status-remediation  - verify writer permissions and confirm delete remains denied"
	@echo "  make incident-1-rollout  - apply INC-001 over a healthy revision so rollback history exists"
	@echo "  make remediate-1         - investigate, pause for exact approval, execute, then verify"
	@echo "  make disable-remediation - disable write tools and remove writer RBAC"
	@echo "  make phase7-check        - source checks + Phase 7 tests"
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

agent-tools-remediation: agent-setup
	@if [ -f .env ]; then set -a; source .env; set +a; fi; \
		OPSPILOT_REMEDIATION_ENABLED=true $(AGENT_PYTHON) -m opspilot_agent.cli tools --remediation

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


# Phase 6 - read-only GitHub change intelligence
github-mcp-server:
	@if [ -f .env ]; then set -a; source .env; set +a; fi; \
		go run ./services/github-mcp-server/cmd/server

github-mcp-server-live:
	@if [ -f .env ]; then set -a; source .env; set +a; fi; \
		OPSPILOT_GITHUB_MODE=live \
		OPSPILOT_GITHUB_OWNER="$${OPSPILOT_GITHUB_OWNER:-RakeshSuvvari}" \
		OPSPILOT_GITHUB_REPO="$${OPSPILOT_GITHUB_REPO:-opspilot}" \
		go run ./services/github-mcp-server/cmd/server

github-mcp-server-fixture:
	@if [ -f .env ]; then set -a; source .env; set +a; fi; \
		OPSPILOT_GITHUB_MODE=fixture go run ./services/github-mcp-server/cmd/server

stamp-git-provenance:
	@command -v git >/dev/null || (echo "git is required" && exit 1)
	@if [ -f .env ]; then set -a; source .env; set +a; fi; \
		owner="$${OPSPILOT_GITHUB_OWNER:-RakeshSuvvari}"; \
		repo="$${OPSPILOT_GITHUB_REPO:-opspilot}"; \
		current="$$(git rev-parse HEAD)"; \
		previous="$$(git rev-parse HEAD^ 2>/dev/null || printf '%s' "$$current")"; \
		if ! git diff --quiet || ! git diff --cached --quiet; then \
			echo "WARNING: working tree has uncommitted changes; provenance records HEAD, not those changes."; \
		fi; \
		for deployment in checkout payment inventory; do \
			kubectl annotate deployment/$$deployment -n $(NAMESPACE) --overwrite \
				opspilot.dev/repository="$$owner/$$repo" \
				opspilot.dev/revision="$$current" \
				opspilot.dev/previous-revision="$$previous" >/dev/null; \
		done; \
		echo "Stamped $$owner/$$repo provenance: $$previous -> $$current"

deploy-base-live: deploy-base stamp-git-provenance
	@echo "Healthy demo deployment now carries real GitHub provenance."

investigate-live: agent-setup
	@if [ -f .env ]; then set -a; source .env; set +a; fi; \
		OPSPILOT_GITHUB_ENABLED=true $(AGENT_PYTHON) -m opspilot_agent.cli investigate --namespace $(NAMESPACE) --query "$(QUERY) Correlate any relevant deployed revision with the configured live GitHub repository when source-change evidence is useful."

github-health:
	curl -s http://localhost:8090/healthz

smoke-github-mcp:
	cd services/github-mcp-server && go run ./cmd/smoke -endpoint $(GITHUB_MCP_URL)

test-github-mcp:
	cd services/github-mcp-server && go test ./...

investigate-1-change: agent-setup
	@if [ -f .env ]; then set -a; source .env; set +a; fi; \
		OPSPILOT_GITHUB_ENABLED=true $(AGENT_PYTHON) -m opspilot_agent.cli investigate --namespace $(NAMESPACE) --query "Why is the payment service failing and repeatedly restarting? Diagnose the live failure and correlate it with the deployed source change."

investigate-2-change: agent-setup
	@if [ -f .env ]; then set -a; source .env; set +a; fi; \
		OPSPILOT_GITHUB_ENABLED=true $(AGENT_PYTHON) -m opspilot_agent.cli investigate --namespace $(NAMESPACE) --query "Why is checkout repeatedly terminating? Diagnose the live failure and determine whether the deployed source change altered memory configuration."

investigate-3-change: agent-setup
	@if [ -f .env ]; then set -a; source .env; set +a; fi; \
		OPSPILOT_GITHUB_ENABLED=true $(AGENT_PYTHON) -m opspilot_agent.cli investigate --namespace $(NAMESPACE) --query "Why is inventory running but not becoming Ready? Diagnose the probe issue and correlate it with the deployed change."

investigate-4-change: agent-setup
	@if [ -f .env ]; then set -a; source .env; set +a; fi; \
		OPSPILOT_GITHUB_ENABLED=true $(AGENT_PYTHON) -m opspilot_agent.cli investigate --namespace $(NAMESPACE) --query "Checkout returns service unavailable when calling inventory. Diagnose the live timeout and correlate the deployed source/config change."

eval-change-1: agent-setup
	@if [ -f .env ]; then set -a; source .env; set +a; fi; \
		OPSPILOT_GITHUB_ENABLED=true $(AGENT_PYTHON) -m opspilot_agent.evals.cli --cases $(PHASE6_EVAL_CASES) --case INC-001-GIT --namespace $(NAMESPACE)

eval-change-2: agent-setup
	@if [ -f .env ]; then set -a; source .env; set +a; fi; \
		OPSPILOT_GITHUB_ENABLED=true $(AGENT_PYTHON) -m opspilot_agent.evals.cli --cases $(PHASE6_EVAL_CASES) --case INC-002-GIT --namespace $(NAMESPACE)

eval-change-3: agent-setup
	@if [ -f .env ]; then set -a; source .env; set +a; fi; \
		OPSPILOT_GITHUB_ENABLED=true $(AGENT_PYTHON) -m opspilot_agent.evals.cli --cases $(PHASE6_EVAL_CASES) --case INC-003-GIT --namespace $(NAMESPACE)

eval-change-4: agent-setup
	@if [ -f .env ]; then set -a; source .env; set +a; fi; \
		OPSPILOT_GITHUB_ENABLED=true $(AGENT_PYTHON) -m opspilot_agent.evals.cli --cases $(PHASE6_EVAL_CASES) --case INC-004-GIT --namespace $(NAMESPACE)

phase6-check: agent-test
	./scripts/verify-source.sh
	@echo "Phase 6 source checks passed. Start make github-mcp-server in another terminal, then use make investigate-1-change."

# Phase 7 - human-approved Kubernetes remediation
enable-remediation:
	kubectl apply -f infra/kubernetes/opspilot/k8s-mcp-server/rbac-remediation.yaml
	@if [ -f .env ]; then set -a; source .env; set +a; fi; \
		kubectl set env deployment/k8s-mcp-server -n $(SYSTEM_NAMESPACE) \
			OPSPILOT_K8S_WRITE_ENABLED=true \
			OPSPILOT_K8S_MAX_SCALE_REPLICAS="$${OPSPILOT_REMEDIATION_MAX_REPLICAS:-10}"
	kubectl rollout status deployment/k8s-mcp-server -n $(SYSTEM_NAMESPACE) --timeout=90s
	@echo "Phase 7 Kubernetes write tools enabled. Mutating agent calls still require human approval."

disable-remediation:
	-kubectl set env deployment/k8s-mcp-server -n $(SYSTEM_NAMESPACE) OPSPILOT_K8S_WRITE_ENABLED=false
	-kubectl delete rolebinding/opspilot-k8s-remediator role/opspilot-k8s-remediator -n $(NAMESPACE) --ignore-not-found=true
	kubectl rollout status deployment/k8s-mcp-server -n $(SYSTEM_NAMESPACE) --timeout=90s
	@echo "Phase 7 Kubernetes write tools disabled and remediation RBAC removed."

restore-k8s-remediation-rbac:
	@if kubectl get namespace $(SYSTEM_NAMESPACE) >/dev/null 2>&1; then \
		kubectl apply -f infra/kubernetes/opspilot/k8s-mcp-server/rbac-remediation.yaml >/dev/null; \
		echo "Restored OpsPilot remediation RBAC in $(NAMESPACE)."; \
	fi

status-remediation:
	@echo "=== MCP tool server ==="
	kubectl get deployment,pod -n $(SYSTEM_NAMESPACE) -l app=k8s-mcp-server -o wide
	@echo
	@echo "=== Remediation RBAC ==="
	@printf "patch deployments: "
	@kubectl auth can-i patch deployments -n $(NAMESPACE) --as=system:serviceaccount:$(SYSTEM_NAMESPACE):k8s-mcp-server || true
	@printf "update deployment scale: "
	@kubectl auth can-i update deployments/scale -n $(NAMESPACE) --as=system:serviceaccount:$(SYSTEM_NAMESPACE):k8s-mcp-server || true
	@printf "list replicasets: "
	@kubectl auth can-i list replicasets -n $(NAMESPACE) --as=system:serviceaccount:$(SYSTEM_NAMESPACE):k8s-mcp-server || true
	@printf "delete deployments: "
	@kubectl auth can-i delete deployments -n $(NAMESPACE) --as=system:serviceaccount:$(SYSTEM_NAMESPACE):k8s-mcp-server || true

phase7-up: phase2-up enable-remediation
	@echo "Phase 7 remediation backend is ready. Restart make port-forward-k8s-mcp if it was already running."

incident-1-rollout:
	-kubectl delete namespace $(NAMESPACE) --ignore-not-found=true --wait=true
	kubectl apply -k demo/kubernetes/base
	@$(MAKE) --no-print-directory restore-k8s-mcp-rbac
	@$(MAKE) --no-print-directory restore-k8s-remediation-rbac
	kubectl rollout status deployment/payment -n $(NAMESPACE) --timeout=60s
	kubectl apply -k demo/incidents/inc-001-missing-database-url
	@$(MAKE) --no-print-directory restore-k8s-mcp-rbac
	@$(MAKE) --no-print-directory restore-k8s-remediation-rbac
	@echo "INC-001 was rolled out over a healthy payment revision, preserving ReplicaSet history for rollback."

incident-2-rollout:
	-kubectl delete namespace $(NAMESPACE) --ignore-not-found=true --wait=true
	kubectl apply -k demo/kubernetes/base
	@$(MAKE) --no-print-directory restore-k8s-mcp-rbac
	@$(MAKE) --no-print-directory restore-k8s-remediation-rbac
	kubectl rollout status deployment/checkout -n $(NAMESPACE) --timeout=60s
	kubectl apply -k demo/incidents/inc-002-oomkilled
	@$(MAKE) --no-print-directory restore-k8s-mcp-rbac
	@$(MAKE) --no-print-directory restore-k8s-remediation-rbac
	@echo "INC-002 was rolled out over a healthy checkout revision, preserving ReplicaSet history for rollback."

incident-3-rollout:
	-kubectl delete namespace $(NAMESPACE) --ignore-not-found=true --wait=true
	kubectl apply -k demo/kubernetes/base
	@$(MAKE) --no-print-directory restore-k8s-mcp-rbac
	@$(MAKE) --no-print-directory restore-k8s-remediation-rbac
	kubectl rollout status deployment/inventory -n $(NAMESPACE) --timeout=60s
	kubectl apply -k demo/incidents/inc-003-broken-readiness
	@$(MAKE) --no-print-directory restore-k8s-mcp-rbac
	@$(MAKE) --no-print-directory restore-k8s-remediation-rbac
	@echo "INC-003 was rolled out over a healthy inventory revision, preserving ReplicaSet history for rollback."

remediate: agent-setup
	@if [ -f .env ]; then set -a; source .env; set +a; fi; \
		OPSPILOT_REMEDIATION_ENABLED=true $(AGENT_PYTHON) -m opspilot_agent.cli remediate --namespace $(NAMESPACE) --query "$(QUERY)"

remediate-1: agent-setup
	@if [ -f .env ]; then set -a; source .env; set +a; fi; \
		OPSPILOT_REMEDIATION_ENABLED=true \
		OPSPILOT_GITHUB_ENABLED=false \
		$(AGENT_PYTHON) -m opspilot_agent.cli remediate \
		--namespace $(NAMESPACE) \
		--query "Diagnose why payment is repeatedly restarting. If the failure is a newly rolled out deployment regression and rollback is supported by live revision history, request the safest corrective action, then verify recovery after approval."
		
phase7-check: agent-test
	./scripts/verify-source.sh
	@grep -q 'OPSPILOT_REMEDIATION_ENABLED=false' .env
	@grep -q 'k8s_rollback_deployment' services/k8s-mcp-server/internal/tools/tools.go
	@test -s infra/kubernetes/opspilot/k8s-mcp-server/rbac-remediation.yaml
	@echo "Phase 7 source checks passed. Next: make phase7-up && make incident-1-rollout && make remediate-1"
