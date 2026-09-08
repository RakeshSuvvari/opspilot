---
service: payment
document_type: runbook
---
# Payment Service Database Configuration Runbook

## Symptoms
The payment workload may enter `CrashLoopBackOff`, repeatedly restart, or fail readiness checks when its required database configuration is absent or invalid.

## Required configuration
The payment service requires `DATABASE_URL` at process startup. The value should be supplied through an approved Kubernetes Secret or another controlled configuration source rather than committed directly in a Deployment manifest.

## Diagnosis
1. Inspect the payment pod state and restart count.
2. Read current and previous container logs for startup configuration errors.
3. Inspect the payment Deployment environment and referenced Secrets or ConfigMaps.
4. Separate missing configuration from database reachability. A missing `DATABASE_URL` prevents startup before a connection attempt can occur.

## Remediation
Restore the required database configuration, perform a controlled rollout, and verify that the new pod becomes Ready and its restart count remains stable.
