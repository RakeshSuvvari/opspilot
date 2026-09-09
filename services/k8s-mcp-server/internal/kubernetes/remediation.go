package kubernetes

import (
	"context"
	"encoding/json"
	"fmt"
	"sort"
	"strconv"
	"time"

	appsv1 "k8s.io/api/apps/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/types"
)

const deploymentRevisionAnnotation = "deployment.kubernetes.io/revision"

func (c *Client) RestartDeployment(ctx context.Context, namespace, name string) (RestartDeploymentResult, error) {
	deployment, err := c.clientset.AppsV1().Deployments(namespace).Get(ctx, name, metav1.GetOptions{})
	if err != nil {
		return RestartDeploymentResult{}, fmt.Errorf("get deployment %s/%s: %w", namespace, name, err)
	}
	restartedAt := time.Now().UTC().Format(time.RFC3339)
	patch := map[string]any{
		"spec": map[string]any{
			"template": map[string]any{
				"metadata": map[string]any{
					"annotations": map[string]string{
						"kubectl.kubernetes.io/restartedAt": restartedAt,
						"opspilot.dev/remediated-at":        restartedAt,
					},
				},
			},
		},
	}
	payload, _ := json.Marshal(patch)
	updated, err := c.clientset.AppsV1().Deployments(namespace).Patch(ctx, name, types.MergePatchType, payload, metav1.PatchOptions{})
	if err != nil {
		return RestartDeploymentResult{}, fmt.Errorf("restart deployment %s/%s: %w", namespace, name, err)
	}
	return RestartDeploymentResult{Namespace: namespace, Deployment: name, RestartedAt: restartedAt, Generation: updated.Generation, PreviousGeneration: deployment.Generation}, nil
}

func (c *Client) ScaleDeployment(ctx context.Context, namespace, name string, replicas int32) (ScaleDeploymentResult, error) {
	current, err := c.clientset.AppsV1().Deployments(namespace).GetScale(ctx, name, metav1.GetOptions{})
	if err != nil {
		return ScaleDeploymentResult{}, fmt.Errorf("get scale for deployment %s/%s: %w", namespace, name, err)
	}
	oldReplicas := current.Spec.Replicas
	current.Spec.Replicas = replicas
	updated, err := c.clientset.AppsV1().Deployments(namespace).UpdateScale(ctx, name, current, metav1.UpdateOptions{})
	if err != nil {
		return ScaleDeploymentResult{}, fmt.Errorf("scale deployment %s/%s: %w", namespace, name, err)
	}
	return ScaleDeploymentResult{Namespace: namespace, Deployment: name, PreviousReplicas: oldReplicas, Replicas: updated.Spec.Replicas, ScaledAt: time.Now().UTC().Format(time.RFC3339)}, nil
}

func (c *Client) RollbackDeployment(ctx context.Context, namespace, name string, requestedRevision int64) (RollbackDeploymentResult, error) {
	deployments := c.clientset.AppsV1().Deployments(namespace)
	deployment, err := deployments.Get(ctx, name, metav1.GetOptions{})
	if err != nil {
		return RollbackDeploymentResult{}, fmt.Errorf("get deployment %s/%s: %w", namespace, name, err)
	}

	selector := metav1.FormatLabelSelector(deployment.Spec.Selector)
	replicaSets, err := c.clientset.AppsV1().ReplicaSets(namespace).List(ctx, metav1.ListOptions{LabelSelector: selector})
	if err != nil {
		return RollbackDeploymentResult{}, fmt.Errorf("list replica sets for deployment %s/%s: %w", namespace, name, err)
	}

	type revisionedRS struct {
		revision int64
		rs       *appsv1.ReplicaSet
	}
	candidates := make([]revisionedRS, 0)
	for i := range replicaSets.Items {
		rs := &replicaSets.Items[i]
		if !ownedByDeployment(rs, deployment.UID) {
			continue
		}
		revision, err := strconv.ParseInt(rs.Annotations[deploymentRevisionAnnotation], 10, 64)
		if err != nil {
			continue
		}
		candidates = append(candidates, revisionedRS{revision: revision, rs: rs})
	}
	if len(candidates) < 2 && requestedRevision == 0 {
		return RollbackDeploymentResult{}, fmt.Errorf("deployment %s/%s has no previous ReplicaSet revision to roll back to", namespace, name)
	}
	if len(candidates) == 0 {
		return RollbackDeploymentResult{}, fmt.Errorf("deployment %s/%s has no ReplicaSet revision history", namespace, name)
	}
	sort.Slice(candidates, func(i, j int) bool { return candidates[i].revision < candidates[j].revision })
	currentRevision := candidates[len(candidates)-1].revision

	var target revisionedRS
	found := false
	if requestedRevision > 0 {
		for _, candidate := range candidates {
			if candidate.revision == requestedRevision {
				target, found = candidate, true
				break
			}
		}
	} else {
		target, found = candidates[len(candidates)-2], true
	}
	if !found {
		return RollbackDeploymentResult{}, fmt.Errorf("deployment %s/%s revision %d was not found", namespace, name, requestedRevision)
	}

	oldSourceRevision := deployment.Annotations["opspilot.dev/revision"]
	previousSourceRevision := deployment.Annotations["opspilot.dev/previous-revision"]
	deployment.Spec.Template = *target.rs.Spec.Template.DeepCopy()
	if deployment.Spec.Template.Labels != nil {
		delete(deployment.Spec.Template.Labels, "pod-template-hash")
	}
	if deployment.Annotations == nil {
		deployment.Annotations = map[string]string{}
	}
	now := time.Now().UTC().Format(time.RFC3339)
	deployment.Annotations["opspilot.dev/remediated-at"] = now
	deployment.Annotations["opspilot.dev/rollback-from-k8s-revision"] = strconv.FormatInt(currentRevision, 10)
	deployment.Annotations["opspilot.dev/rollback-to-k8s-revision"] = strconv.FormatInt(target.revision, 10)
	if previousSourceRevision != "" {
		deployment.Annotations["opspilot.dev/revision"] = previousSourceRevision
		if oldSourceRevision != "" {
			deployment.Annotations["opspilot.dev/previous-revision"] = oldSourceRevision
		}
	}

	updated, err := deployments.Update(ctx, deployment, metav1.UpdateOptions{})
	if err != nil {
		return RollbackDeploymentResult{}, fmt.Errorf("rollback deployment %s/%s: %w", namespace, name, err)
	}
	return RollbackDeploymentResult{
		Namespace: namespace, Deployment: name,
		FromRevision: currentRevision, ToRevision: target.revision,
		TargetReplicaSet: target.rs.Name, Generation: updated.Generation,
		FromSourceRevision: oldSourceRevision, ToSourceRevision: updated.Annotations["opspilot.dev/revision"],
	}, nil
}

func ownedByDeployment(rs *appsv1.ReplicaSet, deploymentUID types.UID) bool {
	for _, owner := range rs.OwnerReferences {
		if owner.Controller != nil && *owner.Controller && owner.Kind == "Deployment" && owner.UID == deploymentUID {
			return true
		}
	}
	return false
}
