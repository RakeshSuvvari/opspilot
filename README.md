# OpsPilot

**Agentic Kubernetes Incident Response Platform**

OpsPilot combines **Go** infrastructure services with a **Python/OpenAI** agent to investigate Kubernetes incidents using live cluster evidence, PostgreSQL/pgvector RAG, deterministic evaluation, and deployment/source-change intelligence.

## Current milestone: Phase 6

```text
Engineer
   |
   v
OpenAI Incident Agent (Python, gpt-5.4-mini by default)
   |
   +------------------+----------------------+--------------------+
   |                  |                      |                    |
   | MCP              | MCP                  | function tool      |
   v                  v                      v                    |
Kubernetes MCP     GitHub MCP            search_knowledge         |
Server (Go)        Server (Go)              |                    |
   |                  |                      v                    |
   v                  v                PostgreSQL + pgvector      |
Kubernetes API     GitHub commits/PRs       |                    |
   |                  |                 Runbooks/postmortems      |
   +------------------+----------------------+                    |
                         |                                       |
                         v                                       |
                Evidence-backed RCA                              |
                + source-change correlation                      |
                         |                                       |
                         v                                       |
                Deterministic trust layer                        |
                timeline / confidence / evals / usage            |
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
