package kubernetes

import (
	"fmt"
	"sort"
	"strings"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/util/intstr"
)

func podReady(conditions []corev1.PodCondition) bool {
	for _, condition := range conditions {
		if condition.Type == corev1.PodReady {
			return condition.Status == corev1.ConditionTrue
		}
	}
	return false
}

func summarizeContainerStatus(status corev1.ContainerStatus) ContainerState {
	result := ContainerState{
		Name:         status.Name,
		Ready:        status.Ready,
		RestartCount: status.RestartCount,
	}

	switch {
	case status.State.Running != nil:
		result.State = "running"
		result.StartedAt = status.State.Running.StartedAt.Time.UTC().Format(timeFormat)
	case status.State.Waiting != nil:
		result.State = "waiting"
		result.Reason = status.State.Waiting.Reason
	case status.State.Terminated != nil:
		result.State = "terminated"
		result.Reason = status.State.Terminated.Reason
		result.ExitCode = status.State.Terminated.ExitCode
		result.StartedAt = status.State.Terminated.StartedAt.Time.UTC().Format(timeFormat)
		result.FinishedAt = status.State.Terminated.FinishedAt.Time.UTC().Format(timeFormat)
	default:
		result.State = "unknown"
	}

	// Preserve previous termination evidence without overwriting the current state.
	if status.LastTerminationState.Terminated != nil {
		terminated := status.LastTerminationState.Terminated
		result.LastTerminationReason = terminated.Reason
		result.LastExitCode = terminated.ExitCode
		result.LastFinishedAt = terminated.FinishedAt.Time.UTC().Format(timeFormat)
	}

	return result
}

func resourcesToStrings(resources corev1.ResourceList) map[string]string {
	if len(resources) == 0 {
		return nil
	}
	result := make(map[string]string, len(resources))
	for name, quantity := range resources {
		result[string(name)] = quantity.String()
	}
	return result
}

func environmentVariables(env []corev1.EnvVar) []EnvironmentVar {
	result := make([]EnvironmentVar, 0, len(env))
	for _, item := range env {
		value := EnvironmentVar{Name: item.Name}
		switch {
		case item.ValueFrom != nil:
			value.ValueFrom = envValueFrom(item.ValueFrom)
			if item.ValueFrom.SecretKeyRef != nil {
				value.Redacted = true
			}
		case sensitiveEnvironmentName(item.Name):
			value.Value = "<redacted>"
			value.Redacted = true
		default:
			value.Value = item.Value
		}
		result = append(result, value)
	}
	sort.Slice(result, func(i, j int) bool { return result[i].Name < result[j].Name })
	return result
}

func envValueFrom(source *corev1.EnvVarSource) string {
	switch {
	case source.SecretKeyRef != nil:
		return fmt.Sprintf("secret:%s/%s", source.SecretKeyRef.Name, source.SecretKeyRef.Key)
	case source.ConfigMapKeyRef != nil:
		return fmt.Sprintf("configmap:%s/%s", source.ConfigMapKeyRef.Name, source.ConfigMapKeyRef.Key)
	case source.FieldRef != nil:
		return "field:" + source.FieldRef.FieldPath
	case source.ResourceFieldRef != nil:
		return "resource:" + source.ResourceFieldRef.Resource
	default:
		return "unknown"
	}
}

func sensitiveEnvironmentName(name string) bool {
	upper := strings.ToUpper(name)
	for _, fragment := range []string{"PASSWORD", "PASSWD", "SECRET", "TOKEN", "API_KEY", "APIKEY", "PRIVATE_KEY", "CREDENTIAL", "DATABASE_URL"} {
		if strings.Contains(upper, fragment) {
			return true
		}
	}
	return false
}

func probeDetails(probe *corev1.Probe) *ProbeDetails {
	if probe == nil {
		return nil
	}
	result := &ProbeDetails{
		InitialDelaySecs: probe.InitialDelaySeconds,
		PeriodSecs:       probe.PeriodSeconds,
		TimeoutSecs:      probe.TimeoutSeconds,
		FailureThreshold: probe.FailureThreshold,
	}

	switch {
	case probe.HTTPGet != nil:
		result.Type = "http_get"
		result.Path = probe.HTTPGet.Path
		result.Port = intOrString(probe.HTTPGet.Port)
		result.Scheme = string(probe.HTTPGet.Scheme)
	case probe.TCPSocket != nil:
		result.Type = "tcp_socket"
		result.Port = intOrString(probe.TCPSocket.Port)
	case probe.Exec != nil:
		result.Type = "exec"
		result.Command = append([]string(nil), probe.Exec.Command...)
	case probe.GRPC != nil:
		result.Type = "grpc"
		result.Port = fmt.Sprintf("%d", probe.GRPC.Port)
	default:
		result.Type = "unknown"
	}
	return result
}

func intOrString(value intstr.IntOrString) string {
	if value.Type == intstr.String {
		return value.StrVal
	}
	return fmt.Sprintf("%d", value.IntVal)
}

func timestamp(meta metav1.Time) string {
	if meta.IsZero() {
		return ""
	}
	return meta.Time.UTC().Format(timeFormat)
}

const timeFormat = "2006-01-02T15:04:05Z07:00"
