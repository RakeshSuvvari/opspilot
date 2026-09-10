---
title: Kubernetes Liveness Probe Runbook
type: runbook
service: platform
---

# Kubernetes Liveness Probe Runbook

## Symptoms

An application starts successfully but kubelet repeatedly restarts it because the liveness probe fails.

## Diagnosis

Inspect Kubernetes events for liveness probe failures and compare the liveness probe path and port with the application's actual listening endpoint. Distinguish liveness failures from readiness failures: liveness causes restarts, while readiness primarily controls traffic eligibility.

## Remediation

Correct the liveness probe port/path to the actual health endpoint. Avoid relaxing probes until the configuration mismatch is understood.
