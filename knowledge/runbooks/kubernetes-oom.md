# Runbook: Kubernetes OOM termination

When a container repeatedly restarts, inspect `lastState.terminated.reason`, exit code, and configured resource limits. `OOMKilled` together with exit code 137 is strong evidence that the process exceeded its container memory limit.
