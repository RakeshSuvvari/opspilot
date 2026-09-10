---
title: Kubernetes Image Pull Failure Runbook
type: runbook
service: platform
---

# Kubernetes Image Pull Failure Runbook

## Symptoms

Pods remain in `ErrImagePull` or `ImagePullBackOff` and never start the application container.

## Diagnosis

Inspect pod container state and Kubernetes events. Confirm the exact image repository and tag in the Deployment. Common causes are a nonexistent tag, an inaccessible registry, or missing image-pull credentials.

## Remediation

Deploy an image tag that exists and is accessible. If the failure followed a rollout, roll back to the last known-good image revision. Do not repeatedly restart an unchanged pod; kubelet will continue failing to pull the same image.
