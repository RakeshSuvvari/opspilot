package kubernetes

import (
	"context"
	"testing"

	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/util/intstr"
	"k8s.io/client-go/kubernetes/fake"
)

func TestGetDeploymentRedactsSensitiveEnvironmentAndExposesProbe(t *testing.T) {
	replicas := int32(1)
	container := corev1.Container{
		Name:  "payment",
		Image: "opspilot/payment:dev",
		Env: []corev1.EnvVar{
			{Name: "DATABASE_URL", Value: "postgres://user:password@db/payment"},
			{Name: "REQUEST_TIMEOUT_MS", Value: "50"},
		},
		ReadinessProbe: &corev1.Probe{
			ProbeHandler: corev1.ProbeHandler{
				HTTPGet: &corev1.HTTPGetAction{
					Path: "/healthz",
					Port: intstr.FromInt32(8081),
				},
			},
		},
	}
	deploymentObject := &appsv1.Deployment{
		ObjectMeta: metav1.ObjectMeta{Name: "payment", Namespace: "opspilot-demo"},
		Spec: appsv1.DeploymentSpec{
			Replicas: &replicas,
			Selector: &metav1.LabelSelector{MatchLabels: map[string]string{"app": "payment"}},
			Template: corev1.PodTemplateSpec{
				ObjectMeta: metav1.ObjectMeta{Labels: map[string]string{"app": "payment"}},
				Spec:       corev1.PodSpec{Containers: []corev1.Container{container}},
			},
		},
	}
	clientset := fake.NewSimpleClientset(deploymentObject)

	client := NewForClient(clientset)
	deployment, err := client.GetDeployment(context.Background(), "opspilot-demo", "payment")
	if err != nil {
		t.Fatalf("GetDeployment() error = %v", err)
	}

	env := deployment.Containers[0].Environment
	if env[0].Name != "DATABASE_URL" || !env[0].Redacted || env[0].Value != "<redacted>" {
		t.Fatalf("expected DATABASE_URL to be redacted, got %+v", env[0])
	}
	if env[1].Value != "50" {
		t.Fatalf("expected non-sensitive timeout value, got %+v", env[1])
	}
	if got := deployment.Containers[0].ReadinessProbe.Port; got != "8081" {
		t.Fatalf("expected probe port 8081, got %q", got)
	}
}
