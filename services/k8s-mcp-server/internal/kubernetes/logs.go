package kubernetes

import (
	"context"
	"fmt"

	corev1 "k8s.io/api/core/v1"
)

const (
	defaultTailLines int64 = 200
	maxTailLines     int64 = 1000
)

func (c *Client) GetPodLogs(ctx context.Context, namespace, pod, container string, tailLines int64, previous bool) (PodLogs, error) {
	if tailLines <= 0 {
		tailLines = defaultTailLines
	}
	if tailLines > maxTailLines {
		tailLines = maxTailLines
	}

	options := &corev1.PodLogOptions{
		Container: container,
		Previous:  previous,
		TailLines: &tailLines,
	}
	logs, err := c.clientset.CoreV1().Pods(namespace).GetLogs(pod, options).DoRaw(ctx)
	if err != nil {
		return PodLogs{}, fmt.Errorf("get logs for pod %s/%s: %w", namespace, pod, err)
	}

	return PodLogs{
		Namespace: namespace,
		Pod:       pod,
		Container: container,
		Previous:  previous,
		TailLines: tailLines,
		Logs:      string(logs),
	}, nil
}
