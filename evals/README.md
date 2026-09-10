# OpsPilot deterministic evaluations

OpsPilot uses deterministic evaluation rules rather than a second LLM judge.

`evals/cases/incidents.jsonl` contains the original four Phase 5 scenarios. `evals/cases/incidents-phase6.jsonl` contains four GitHub change-correlation variants. `evals/cases/benchmark.jsonl` is the Phase 10 final 10-case suite.

Each evaluation scores expected status, root-cause signal groups, required tool coverage, affected resources, confidence, knowledge usage, timeline presence, and—where configured—source-change correlation.

For the automated final suite use:

```bash
make benchmark
```

See `benchmarks/README.md` for scenario details, aggregate metrics, repeats, RAG ablation, and GitHub change-correlation benchmarking.
