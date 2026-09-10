# OpsPilot Phase 10 benchmark suite

The final benchmark contains 10 controlled scenarios: nine failures/degradations plus one healthy control.

| Case | Scenario | Main evidence |
|---|---|---|
| INC-001 | Missing `DATABASE_URL` | CrashLoopBackOff, logs, Deployment env |
| INC-002 | OOMKilled | last termination, memory limit |
| INC-003 | Broken readiness probe | events, probe port |
| INC-004 | Downstream timeout | checkout logs, timeout/delay config |
| INC-005 | Image pull failure | ImagePullBackOff, events, image tag |
| INC-006 | Missing Secret | CreateContainerConfigError, events, secret ref |
| INC-007 | Bad downstream DNS/URL | checkout logs, `INVENTORY_URL` |
| INC-008 | Broken liveness probe | liveness events, restarts, probe port |
| INC-009 | App/probe port mismatch | startup logs, `PORT`, health probe port |
| INC-010 | Healthy control | all workloads Ready; no fabricated incident |

## Run

Keep the Kubernetes MCP port-forward running and ensure RAG has been re-ingested after pulling Phase 10.

```bash
make rag-ingest
make benchmark
```

The benchmark automatically recreates the demo namespace for each case, restores read-only MCP RBAC, waits for evidence to accumulate, and generates traffic for INC-004 and INC-007.

Artifacts are written to `.opspilot/benchmarks/` in JSON, CSV, and Markdown. The benchmark reports pass rate, root-cause signal accuracy, status accuracy, required-tool coverage, remediation recommendation coverage, median/P95 latency, tool calls, tokens, and an estimated text-token cost.

For a more stable final number, run three repeats:

```bash
make benchmark BENCHMARK_REPEATS=3
```

Optional ablations:

```bash
make benchmark-no-rag
```

For the existing four deterministic GitHub change-correlation fixtures, start `make github-mcp-server-fixture` in another terminal, then run:

```bash
make benchmark-change
```

Cost estimates use configurable standard input/output token rates. They do not apply cached-input discounts and do not include embedding or other tool-specific fees.
