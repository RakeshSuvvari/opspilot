---
document_type: runbook
---
# Kubernetes Readiness Probe Runbook

## Symptoms
A pod can be Running while remaining `Ready=False`. Kubernetes events commonly show repeated readiness probe failures, connection refused messages, HTTP error codes, or probe timeouts.

## Diagnosis
Compare the Deployment readiness probe path and port with the port and health endpoint actually served by the container. Check whether the application has completed startup before the probe begins.

## Common causes
- Probe targets the wrong port.
- Probe path does not exist.
- Initial delay is too short for application startup.
- A dependency prevents the application from becoming ready.

## Remediation
Correct the probe configuration only when evidence shows the probe itself is wrong. If the process is crashing before the probe succeeds, fix the startup failure rather than treating the probe as the root cause.
