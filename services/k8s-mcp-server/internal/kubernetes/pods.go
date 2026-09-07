package kubernetes

import (
	"context"
	"fmt"
	"sort"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

func (c *Client) ListPods(ctx context.Context, namespace, labelSelector string) ([]PodSummary, error) {
	pods, err := c.clientset.CoreV1().Pods(namespace).List(ctx, metav1.ListOptions{LabelSelector: labelSelector})
	if err != nil {
		return nil, fmt.Errorf("list pods in namespace %q: %w", namespace, err)
	}

	result := make([]PodSummary, 0, len(pods.Items))
	for i := range pods.Items {
		pod := &pods.Items[i]
		summary := PodSummary{
			Name:      pod.Name,
			Namespace: pod.Namespace,
			Phase:     string(pod.Status.Phase),
			Ready:     podReady(pod.Status.Conditions),
			Node:      pod.Spec.NodeName,
			PodIP:     pod.Status.PodIP,
			Labels:    pod.Labels,
		}
		if pod.Status.StartTime != nil {
			summary.StartTime = timestamp(*pod.Status.StartTime)
		}
		for _, status := range pod.Status.ContainerStatuses {
			container := summarizeContainerStatus(status)
			summary.Restarts += status.RestartCount
			summary.ContainerStates = append(summary.ContainerStates, container)
		}
		result = append(result, summary)
	}

	sort.Slice(result, func(i, j int) bool { return result[i].Name < result[j].Name })
	return result, nil
}

func (c *Client) GetPod(ctx context.Context, namespace, name string) (PodDetails, error) {
	pod, err := c.clientset.CoreV1().Pods(namespace).Get(ctx, name, metav1.GetOptions{})
	if err != nil {
		return PodDetails{}, fmt.Errorf("get pod %s/%s: %w", namespace, name, err)
	}

	summary := PodSummary{
		Name:      pod.Name,
		Namespace: pod.Namespace,
		Phase:     string(pod.Status.Phase),
		Ready:     podReady(pod.Status.Conditions),
		Node:      pod.Spec.NodeName,
		PodIP:     pod.Status.PodIP,
		Labels:    pod.Labels,
	}
	if pod.Status.StartTime != nil {
		summary.StartTime = timestamp(*pod.Status.StartTime)
	}

	statusByName := make(map[string]ContainerState, len(pod.Status.ContainerStatuses))
	for _, status := range pod.Status.ContainerStatuses {
		state := summarizeContainerStatus(status)
		statusByName[status.Name] = state
		summary.Restarts += status.RestartCount
		summary.ContainerStates = append(summary.ContainerStates, state)
	}

	result := PodDetails{PodSummary: summary}
	for _, condition := range pod.Status.Conditions {
		result.Conditions = append(result.Conditions, PodCondition{
			Type:               string(condition.Type),
			Status:             string(condition.Status),
			Reason:             condition.Reason,
			Message:            condition.Message,
			LastTransitionTime: timestamp(condition.LastTransitionTime),
		})
	}

	for _, container := range pod.Spec.Containers {
		details := ContainerDetails{
			ContainerState: statusByName[container.Name],
			Image:          container.Image,
			Requests:       resourcesToStrings(container.Resources.Requests),
			Limits:         resourcesToStrings(container.Resources.Limits),
			Environment:    environmentVariables(container.Env),
			ReadinessProbe: probeDetails(container.ReadinessProbe),
			LivenessProbe:  probeDetails(container.LivenessProbe),
		}
		if details.Name == "" {
			details.Name = container.Name
			details.State = "unknown"
		}
		result.Containers = append(result.Containers, details)
	}

	return result, nil
}
