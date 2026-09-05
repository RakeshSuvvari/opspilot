# Runbook: Pod CrashLoopBackOff

1. Inspect pod container state and restart count.
2. Read current and previous container logs.
3. Inspect recent Kubernetes events.
4. Compare the current deployment environment/configuration with the expected service configuration.
5. Do not infer a root cause from `CrashLoopBackOff` alone; identify the process-level failure first.
