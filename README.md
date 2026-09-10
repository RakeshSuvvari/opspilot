# OpsPilot

**Agentic Kubernetes Incident Response Platform**

OpsPilot combines **Go** infrastructure services with a **Python/OpenAI** agent to investigate Kubernetes incidents using live cluster evidence, PostgreSQL/pgvector RAG, deterministic evaluation, deployment/source-change intelligence, human-approved remediation, and a React/TypeScript operations dashboard.

## Current milestone: Phase 9

```text
Engineer / SRE
     |
     v
React + TypeScript Dashboard
     |
     v
Go Incident API (:8088)
     |
     v
Python OpenAI Agent API (:8001)
     |
     +----------------+----------------+----------------+
     |                |                |                |
     v                v                v                v
Kubernetes MCP     GitHub MCP      PostgreSQL/RAG   HITL approvals
Go                 Go              pgvector         pause/resume
     |                |                |                |
     +----------------+----------------+----------------+
                              |
                              v
                  Evidence-backed RCA + remediation
                  timeline / scoring / evals / metrics
```


## Phase 9: persisted incident history

Phase 9 stores completed investigations in the existing PostgreSQL `opspilot` database. The `operations` schema keeps searchable investigation metadata plus normalized tool-call and remediation-action records, while the full structured report is stored as JSONB for exact replay in the dashboard.

```text
operations.investigations
operations.tool_calls
operations.remediation_actions
```

Run the idempotent database migration once after updating:

```bash
make db-init
make db-check
```

Then start the Phase 8 services as usual. The React/TypeScript dashboard now has an **Incident history** view. Completed CLI, API, evaluation, and remediation runs are persisted automatically when `OPSPILOT_HISTORY_ENABLED=true`.

Persistence is intentionally non-fatal: if PostgreSQL history is temporarily unavailable, OpsPilot still returns the completed RCA and keeps the local `.opspilot/runs` artifact fallback. The dashboard reports history as unavailable instead of breaking live investigation.

With the Go Incident API running, history can also be checked directly:

```bash
make history-list
```

## Phase 6: deployment/source-change correlation

Kubernetes Deployments in the demo carry provenance annotations:

```text
opspilot.dev/repository
opspilot.dev/revision
opspilot.dev/previous-revision
```

`k8s_get_deployment` exposes those annotations. When GitHub change intelligence is enabled, the agent can correlate the exact deployed revision with the repository using these read-only GitHub MCP tools:

- `github_list_recent_commits`
- `github_get_commit`
- `github_compare_commits`
- `github_find_pull_requests_for_commit`
- `github_get_pull_request`

The preferred flow is:

```text
live failure
   -> k8s_get_deployment
   -> deployed current + previous revision
   -> github_compare_commits(previous, current)
   -> github_find_pull_requests_for_commit(current)
   -> GitHub diff explains the live symptom
   -> change-aware RCA
```

A commit is not treated as causal proof merely because it is recent. OpsPilot requires the revision to match deployment provenance and the source/config diff to explain the independently observed live Kubernetes failure.

## GitHub MCP modes

### Fixture mode (default for the demo)

Fixture mode requires no GitHub account or token. The file:

```text
services/github-mcp-server/fixtures/demo.json
```

contains deterministic commit/PR history corresponding to INC-001 through INC-004.

Start it in a separate terminal:

```bash
make github-mcp-server
```

Health check:

```bash
make github-health
```

Expected endpoint:

```text
http://localhost:8090/mcp
```

Smoke test without OpenAI usage:

```bash
make smoke-github-mcp
```

### Live GitHub mode

Set in `.env`:

```bash
OPSPILOT_GITHUB_MODE=live
OPSPILOT_GITHUB_OWNER=<owner>
OPSPILOT_GITHUB_REPO=<repository>
GITHUB_TOKEN=<read-only-token>
```

For private repositories, use least-privilege read permissions. OpsPilot only performs GET operations.

## Run a Phase 6 investigation

Terminal 1 — Kubernetes MCP:

```bash
make port-forward-k8s-mcp
```

Terminal 2 — GitHub MCP:

```bash
make github-mcp-server
```

Terminal 3 — inject and investigate:

```bash
make incident-1
make investigate-1-change
```

A successful report should include a section similar to:

```text
Deployment/source change correlation
- Repository: opspilot-demo/opspilot-demo-services
- Current revision: aaaaaaaaa...
- Previous revision: 111111111...
- Pull request: #42
- Change: DATABASE_URL was removed from the payment deployment.
- Causal link: the deployed diff removed the exact configuration the live logs say is required.
```

The `Tools used` section should include both Kubernetes/RAG tools and GitHub tools such as:

```text
github_compare_commits
github_find_pull_requests_for_commit
github_get_pull_request
```

## Phase 6 evaluations

Phase 5 evaluation cases remain available under:

```text
evals/cases/incidents.jsonl
```

Change-aware Phase 6 cases live under:

```text
evals/cases/incidents-phase6.jsonl
```

Example:

```bash
make incident-1
make eval-change-1
```

For INC-004, generate the failing request before evaluating:

```bash
make incident-4
kubectl port-forward -n opspilot-demo service/checkout 8081:8080
curl -i http://localhost:8081/checkout
make eval-change-4
```

Change-aware evaluation checks the original RCA dimensions plus source-change correlation, expected diff signals, and required GitHub tool coverage.

## Main stack

- Go 1.27.1
- Python 3.11+
- Kubernetes + kind
- Docker
- Model Context Protocol (MCP)
- OpenAI Agents SDK / Responses API
- `gpt-5.4-mini` default model
- PostgreSQL + pgvector
- OpenAI embeddings
- FastAPI
- GitHub REST API (live mode)

## Security model

Both infrastructure MCP servers are read-only in Phase 6:

- Kubernetes MCP: get/list/watch + pod logs; no create/update/patch/delete.
- GitHub MCP: repository read operations only; no commits, merges, PR updates, or repository writes.
- RAG is supporting context and cannot override live cluster evidence.
- Tool outputs and deployment annotations should never contain access tokens.

## Checks

```bash
make phase6-check
```

On your Go 1.27.1 environment you can also run:

```bash
make test-k8s-mcp
make test-github-mcp
```

## Next milestone

After Phase 6, the highest-value next step is human-in-the-loop remediation: proposed rollback/restart/scale actions behind explicit approval, restricted RBAC, and post-action verification.


### Live personal GitHub repository

Phase 6 is configured for `RakeshSuvvari/opspilot` in `.env.example`. Because the repository is public, `GITHUB_TOKEN` is optional; a fine-grained read-only token is recommended for higher REST API limits.

Run the real repository path with:

```bash
make github-mcp-server-live
make github-health
make smoke-github-mcp
```

For a healthy deployment whose images were built from the current checkout, stamp real source provenance after deployment:

```bash
make deploy-base-live
```

This records `git rev-parse HEAD` and its parent as Deployment annotations. If the working tree is dirty, OpsPilot prints a warning because the built bytes may not exactly match the recorded commit.

The `eval-change-*` targets intentionally continue to use fixture history until equivalent incident-producing commits/PRs exist in the real repository. Do not treat unrelated real commits as causal evidence for those injected failures.

## Phase 7 — Human-approved Kubernetes remediation

Phase 7 adds a deliberately narrow write path to the existing Kubernetes MCP server. Read-only
investigations remain the default. When remediation mode is enabled, the Go MCP server additionally
publishes:

- `k8s_restart_deployment`
- `k8s_scale_deployment`
- `k8s_rollback_deployment`

The Python agent connects to these tools with OpenAI Agents SDK approval gating. A mutating MCP call
pauses before execution, the CLI prints the exact tool name and arguments, and the action runs only
after the operator explicitly approves it. Rejected actions are returned to the model as rejected and
are recorded in the final report.

The Kubernetes ServiceAccount receives write privileges only through a separate Phase 7 Role. It may
patch/update Deployments, update Deployment scale, and read ReplicaSet history. It still cannot delete
Deployments, edit Secrets, change RBAC, or mutate arbitrary Kubernetes resources.

### Local Phase 7 flow

```bash
# Rebuild the Go MCP server, enable its write tools, and apply the narrow writer Role.
make phase7-up

# Existing port-forwards must be restarted because phase7-up recreates the MCP pod.
make port-forward-k8s-mcp

# Verify patch/update/list permissions while delete stays denied.
make status-remediation

# Create a real Kubernetes rollout regression rather than starting directly in a bad state.
# This preserves a healthy ReplicaSet so rollback is meaningful.
make incident-1-rollout

# In another terminal, start the human-approved agent flow.
make remediate-1
```

When the agent requests an action, OpsPilot shows a prompt similar to:

```text
HUMAN APPROVAL REQUIRED
Tool:   k8s_rollback_deployment
Risk:   HIGH
Arguments:
{
  "namespace": "opspilot-demo",
  "deployment_name": "payment"
}
Approve this exact Kubernetes action? [y/N]:
```

After approval, the run resumes from the paused agent state, executes the Go MCP tool, and instructs
the agent to verify the new Deployment/pod state with the read-only Kubernetes tools before returning
the final report. The report records approval counts and deterministic `remediation_actions` so an
action cannot be presented as executed merely because the model recommended it.

Disable the mutation surface when finished:

```bash
make disable-remediation
```


## Phase 8 — Go Incident API + React/TypeScript dashboard

Phase 8 adds a browser-based operator surface without moving AI orchestration into the frontend. The dashboard talks only to the Go Incident API, which proxies the Python agent service. Read-only investigations return synchronously; remediation runs are represented as jobs so an OpenAI Agents SDK approval interruption can remain paused while the browser presents the exact mutating tool call.

The dashboard shows:

- incident status, deterministic confidence, and evidence score
- root cause and affected resources
- evidence and deterministic incident timeline
- GitHub deployment/source correlation when available
- token, latency, and tool-call metrics
- recommended remediation and follow-up checks
- exact human-approval cards for restart/scale/rollback
- executed/rejected remediation action history

### Local Phase 8 flow

The Kubernetes MCP server must already be running with Phase 7 remediation enabled. Start these services in separate terminals:

```bash
# Terminal 1
make port-forward-k8s-mcp

# Terminal 2 (when GitHub is enabled in .env)
make github-mcp-server-live

# Terminal 3
make agent-api-remediation

# Terminal 4
make incident-api

# Terminal 5
make dashboard
```

Open `http://localhost:5173`. The Vite development server proxies `/api` to the Go Incident API on port 8088.

For the controlled rollback demo:

```bash
make incident-1-rollout
```

Choose **Remediate** in the dashboard and ask OpsPilot to diagnose the payment restart. When the agent requests `k8s_rollback_deployment`, the UI displays the exact namespace/deployment arguments and pauses until **Approve exact action** or **Reject** is selected.

Phase 8 remediation jobs are intentionally stored in memory. Restarting the Python agent service clears active jobs; persistent incident/job storage is a later production-hardening step.

## Phase 9 — PostgreSQL incident history

Completed investigations are persisted in the existing PostgreSQL `opspilot` database under the `operations` schema. The React dashboard exposes an **Incident history** view that lists prior runs and reopens the exact stored structured report. Persistence is non-fatal: if history storage is unavailable, the live RCA is still returned and local `.opspilot/runs` artifacts remain a fallback.

## Phase 10 — Final evaluation and benchmarks

Phase 10 expands the controlled evaluation suite to 10 scenarios: nine failure/degradation cases plus a healthy control. The benchmark runner automatically injects each scenario, restores Kubernetes MCP RBAC, generates checkout traffic when required, runs the OpenAI investigator, scores the report, and aggregates operational metrics.

Primary run:

```bash
# Index the new Phase 10 runbooks once.
make rag-ingest

# Keep the Kubernetes MCP port-forward running in another terminal.
make benchmark
```

For more stable final numbers:

```bash
make benchmark BENCHMARK_REPEATS=3
```

Artifacts are written under `.opspilot/benchmarks/` as JSON, CSV, and Markdown. Reported metrics include pass rate, root-cause signal accuracy, status accuracy, required-tool coverage, remediation recommendation coverage, median/P95 latency, average tool calls, total tokens, and estimated text-token cost.

Optional RAG ablation:

```bash
make benchmark-no-rag
```

Optional GitHub change-correlation benchmark for the existing four deterministic fixtures:

```bash
# Terminal 1
make github-mcp-server-fixture

# Terminal 2
make benchmark-change
```

The standard 10-case benchmark intentionally disables GitHub so the five new scenarios are not falsely correlated with nonexistent source commits. The four Phase 6 fixture cases remain the controlled benchmark for deployment/source-change correlation.
