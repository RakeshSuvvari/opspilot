# OpsPilot deterministic incident evaluations

Phase 5 evaluates the agent against the four controlled Kubernetes incidents without using a second LLM as a judge.

Each case scores the returned report on:

- expected incident status
- root-cause signal coverage
- required diagnostic tool coverage
- affected resource identification
- deterministic confidence level
- RAG usage expectation
- deterministic timeline presence

The total score is 0-100. The default pass threshold is 80.

## Usage

Inject the matching incident first, keep the Kubernetes MCP port-forward running, and then evaluate it:

```bash
make incident-1
make eval-1
```

For INC-004, call `/checkout` once after injecting the incident so the timeout is represented in live application logs, then run `make eval-4`.

Evaluation JSON is saved under `.opspilot/evals/`. The underlying investigation artifact is saved under `.opspilot/runs/`.
