package kubernetes

import (
	"context"
	"testing"

	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/resource"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes/fake"
)

func TestGetPodIncludesFailureEvidence(t *testing.T) {
	clientset := fake.NewSimpleClientset(&corev1.Pod{
		ObjectMeta: metav1.ObjectMeta{Name: "checkout-abc", Namespace: "opspilot-demo", Labels: map[string]string{"app": "checkout"}},
		Spec: corev1.PodSpec{Containers: []corev1.Container{{
			Name:  "checkout",
			Image: "opspilot/checkout:dev",
			Resources: corev1.ResourceRequirements{Limits: corev1.ResourceList{
				corev1.ResourceMemory: resource.MustParse("64Mi"),
			}},
		}}},
		Status: corev1.PodStatus{
			Phase:      corev1.PodRunning,
			Conditions: []corev1.PodCondition{{Type: corev1.PodReady, Status: corev1.ConditionFalse}},
			ContainerStatuses: []corev1.ContainerStatus{{
				Name:         "checkout",
				RestartCount: 3,
				LastTerminationState: corev1.ContainerState{Terminated: &corev1.ContainerStateTerminated{
					Reason:   "OOMKilled",
					ExitCode: 137,
				}},
			}},
		},
	})

	client := NewForClient(clientset)
	pod, err := client.GetPod(context.Background(), "opspilot-demo", "checkout-abc")
	if err != nil {
		t.Fatalf("GetPod() error = %v", err)
	}
	if pod.Ready {
		t.Fatal("expected pod to be not ready")
	}
	if pod.Restarts != 3 {
		t.Fatalf("expected 3 restarts, got %d", pod.Restarts)
	}
	if got := pod.Containers[0].LastTerminationReason; got != "OOMKilled" {
		t.Fatalf("expected OOMKilled, got %q", got)
	}
	if got := pod.Containers[0].LastExitCode; got != 137 {
		t.Fatalf("expected exit code 137, got %d", got)
	}
	if got := pod.Containers[0].Limits["memory"]; got != "64Mi" {
		t.Fatalf("expected 64Mi memory limit, got %q", got)
	}
}
