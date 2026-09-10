---
title: Kubernetes Service DNS and Downstream Endpoint Runbook
type: runbook
service: checkout
---

# Kubernetes Service DNS and Downstream Endpoint Runbook

## Symptoms

A service can be healthy itself while downstream requests fail with DNS or name-resolution errors such as `no such host`.

## Diagnosis

Inspect application logs for the failed hostname and inspect the Deployment environment for the configured downstream URL. Compare the configured service name with the expected Kubernetes Service name.

## Remediation

Correct the downstream URL or service hostname and redeploy. Verify downstream requests succeed after the rollout.
