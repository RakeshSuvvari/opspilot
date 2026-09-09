package kubernetes

import (
	"context"
	"testing"

	appsv1 "k8s.io/api/apps/v1"
	autoscalingv1 "k8s.io/api/autoscaling/v1"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	k8stypes "k8s.io/apimachinery/pkg/types"
	kubernetesfake "k8s.io/client-go/kubernetes/fake"
	k8stesting "k8s.io/client-go/testing"
)

func TestScaleDeployment(t *testing.T) {
	replicas := int32(1)

	deployment := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{
			Name:      "checkout",
			Namespace: "opspilot-demo",
		},
		Spec: appsv1.DeploymentSpec{
			Replicas: &replicas,
		},
	}

	fakeClient := kubernetesfake.NewSimpleClientset(deployment)

	fakeClient.Fake.PrependReactor(
		"get",
		"deployments",
		func(action k8stesting.Action) (bool, runtime.Object, error) {
			if action.GetSubresource() != "scale" {
				return false, nil, nil
			}

			return true, &autoscalingv1.Scale{
				ObjectMeta: metav1.ObjectMeta{
					Name:      "checkout",
					Namespace: "opspilot-demo",
				},
				Spec: autoscalingv1.ScaleSpec{
					Replicas: 1,
				},
			}, nil
		},
	)

	fakeClient.Fake.PrependReactor(
		"update",
		"deployments",
		func(action k8stesting.Action) (bool, runtime.Object, error) {
			if action.GetSubresource() != "scale" {
				return false, nil, nil
			}

			updateAction := action.(k8stesting.UpdateAction)
			scale := updateAction.GetObject().(*autoscalingv1.Scale)

			return true, scale.DeepCopy(), nil
		},
	)

	client := NewForClient(fakeClient)

	result, err := client.ScaleDeployment(
		context.Background(),
		"opspilot-demo",
		"checkout",
		3,
	)

	if err != nil {
		t.Fatalf("ScaleDeployment() error = %v", err)
	}

	if result.PreviousReplicas != 1 || result.Replicas != 3 {
		t.Fatalf("unexpected scale result: %+v", result)
	}
}

func TestRollbackDeploymentUsesPreviousReplicaSet(t *testing.T) {
	uid := k8stypes.UID("payment-deployment")
	controller := true
	replicas := int32(1)
	deployment := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{
			Name: "payment", Namespace: "opspilot-demo", UID: uid,
			Annotations: map[string]string{
				"opspilot.dev/revision":          "bad-source",
				"opspilot.dev/previous-revision": "good-source",
			},
		},
		Spec: appsv1.DeploymentSpec{
			Replicas: &replicas,
			Selector: &metav1.LabelSelector{MatchLabels: map[string]string{"app": "payment"}},
			Template: podTemplate("payment", false),
		},
	}
	owner := []metav1.OwnerReference{{APIVersion: "apps/v1", Kind: "Deployment", Name: "payment", UID: uid, Controller: &controller}}
	rs1 := &appsv1.ReplicaSet{
		ObjectMeta: metav1.ObjectMeta{Name: "payment-good", Namespace: "opspilot-demo", OwnerReferences: owner, Annotations: map[string]string{deploymentRevisionAnnotation: "1"}, Labels: map[string]string{"app": "payment"}},
		Spec:       appsv1.ReplicaSetSpec{Selector: &metav1.LabelSelector{MatchLabels: map[string]string{"app": "payment"}}, Template: podTemplate("payment", true)},
	}
	rs2 := &appsv1.ReplicaSet{
		ObjectMeta: metav1.ObjectMeta{Name: "payment-bad", Namespace: "opspilot-demo", OwnerReferences: owner, Annotations: map[string]string{deploymentRevisionAnnotation: "2"}, Labels: map[string]string{"app": "payment"}},
		Spec:       appsv1.ReplicaSetSpec{Selector: &metav1.LabelSelector{MatchLabels: map[string]string{"app": "payment"}}, Template: podTemplate("payment", false)},
	}
	fakeClient := kubernetesfake.NewSimpleClientset(deployment, rs1, rs2)
	client := NewForClient(fakeClient)

	result, err := client.RollbackDeployment(context.Background(), "opspilot-demo", "payment", 0)
	if err != nil {
		t.Fatalf("RollbackDeployment() error = %v", err)
	}
	if result.FromRevision != 2 || result.ToRevision != 1 {
		t.Fatalf("unexpected rollback revisions: %+v", result)
	}
	updated, err := fakeClient.AppsV1().Deployments("opspilot-demo").Get(context.Background(), "payment", metav1.GetOptions{})
	if err != nil {
		t.Fatalf("get updated deployment: %v", err)
	}
	if len(updated.Spec.Template.Spec.Containers[0].Env) < 2 || updated.Spec.Template.Spec.Containers[0].Env[1].Name != "DATABASE_URL" {
		t.Fatalf("rollback did not restore healthy pod template: %+v", updated.Spec.Template.Spec.Containers[0].Env)
	}
	if updated.Annotations["opspilot.dev/revision"] != "good-source" {
		t.Fatalf("source provenance was not rolled back: %+v", updated.Annotations)
	}
}

func podTemplate(name string, healthy bool) corev1.PodTemplateSpec {
	env := []corev1.EnvVar{{Name: "PORT", Value: "8080"}}
	if healthy {
		env = append(env, corev1.EnvVar{Name: "DATABASE_URL", Value: "postgres://demo"})
	}
	return corev1.PodTemplateSpec{
		ObjectMeta: metav1.ObjectMeta{Labels: map[string]string{"app": name, "pod-template-hash": "oldhash"}},
		Spec:       corev1.PodSpec{Containers: []corev1.Container{{Name: name, Image: "opspilot/" + name + ":dev", Env: env}}},
	}
}
