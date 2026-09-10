---
title: Kubernetes Secret Configuration Runbook
type: runbook
service: platform
---

# Kubernetes Secret Configuration Runbook

## Symptoms

A pod can remain in `CreateContainerConfigError` when a referenced Secret or Secret key does not exist. Application logs may be unavailable because the container never starts.

## Diagnosis

Inspect pod state and Kubernetes events for messages such as `secret not found` or missing keys. Inspect the Deployment environment source to identify the expected Secret and key. Treat Secret values as sensitive and do not expose them during diagnosis.

## Remediation

Create or restore the expected Secret through the approved secret-management path, or correct the Deployment reference. Verify the pod starts and becomes Ready afterward.
