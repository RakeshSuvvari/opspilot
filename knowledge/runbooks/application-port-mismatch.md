---
title: Application and Kubernetes Port Mismatch Runbook
type: runbook
service: platform
---

# Application and Kubernetes Port Mismatch Runbook

## Symptoms

The process starts and listens on one port while Kubernetes readiness or liveness probes target another. Probes fail with connection-refused errors and liveness can eventually restart the container.

## Diagnosis

Compare the application's configured `PORT` environment variable, startup logs, container port, and health probe target.

## Remediation

Align the application listening port and Kubernetes health/service configuration, then roll out and verify readiness/liveness success.
