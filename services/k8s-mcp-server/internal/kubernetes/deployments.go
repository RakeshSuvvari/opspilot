package kubernetes

import (
	"context"
	"fmt"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

func (c *Client) GetDeployment(ctx context.Context, namespace, name string) (DeploymentDetails, error) {
	deployment, err := c.clientset.AppsV1().Deployments(namespace).Get(ctx, name, metav1.GetOptions{})
	if err != nil {
		return DeploymentDetails{}, fmt.Errorf("get deployment %s/%s: %w", namespace, name, err)
	}

	result := DeploymentDetails{
		Name:               deployment.Name,
		Namespace:          deployment.Namespace,
		Generation:         deployment.Generation,
		ObservedGeneration: deployment.Status.ObservedGeneration,
		ReadyReplicas:      deployment.Status.ReadyReplicas,
		AvailableReplicas:  deployment.Status.AvailableReplicas,
		UpdatedReplicas:    deployment.Status.UpdatedReplicas,
		Strategy:           string(deployment.Spec.Strategy.Type),
		Selector:           deployment.Spec.Selector.MatchLabels,
		PodTemplateLabels:  deployment.Spec.Template.Labels,
	}
	if deployment.Spec.Replicas != nil {
		result.Replicas = *deployment.Spec.Replicas
	}

	for _, container := range deployment.Spec.Template.Spec.Containers {
		result.Containers = append(result.Containers, DeploymentContainer{
			Name:           container.Name,
			Image:          container.Image,
			Requests:       resourcesToStrings(container.Resources.Requests),
			Limits:         resourcesToStrings(container.Resources.Limits),
			Environment:    environmentVariables(container.Env),
			ReadinessProbe: probeDetails(container.ReadinessProbe),
			LivenessProbe:  probeDetails(container.LivenessProbe),
		})
	}

	for _, condition := range deployment.Status.Conditions {
		result.Conditions = append(result.Conditions, DeploymentCondition{
			Type:               string(condition.Type),
			Status:             string(condition.Status),
			Reason:             condition.Reason,
			Message:            condition.Message,
			LastTransitionTime: timestamp(condition.LastTransitionTime),
		})
	}

	return result, nil
}
