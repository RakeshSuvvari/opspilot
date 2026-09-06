package tools

import (
	"context"
	"fmt"

	"github.com/modelcontextprotocol/go-sdk/mcp"
	k8s "github.com/opspilot/opspilot/services/k8s-mcp-server/internal/kubernetes"
)

type Server struct {
	client           *k8s.Client
	defaultNamespace string
}

func New(client *k8s.Client, defaultNamespace string) *Server {
	return &Server{client: client, defaultNamespace: defaultNamespace}
}

func (s *Server) Register(server *mcp.Server) {
	mcp.AddTool(server, &mcp.Tool{
		Name:        "k8s_list_pods",
		Description: "List Kubernetes pods and their concise runtime status. Use this first to identify unhealthy pods, restarts, and container states.",
	}, s.listPods)

	mcp.AddTool(server, &mcp.Tool{
		Name:        "k8s_get_pod",
		Description: "Get detailed Kubernetes pod diagnostics including container state, last termination reason, resource requests/limits, environment metadata, and health probes.",
	}, s.getPod)

	mcp.AddTool(server, &mcp.Tool{
		Name:        "k8s_get_pod_logs",
		Description: "Read the recent logs for a Kubernetes pod or a specific container. Output is capped to protect the agent context window.",
	}, s.getPodLogs)

	mcp.AddTool(server, &mcp.Tool{
		Name:        "k8s_get_events",
		Description: "Get recent Kubernetes events for a namespace or involved object. Useful for scheduling failures, probe failures, image errors, OOMs, and restart evidence.",
	}, s.getEvents)

	mcp.AddTool(server, &mcp.Tool{
		Name:        "k8s_get_deployment",
		Description: "Inspect a Kubernetes Deployment including replicas, container images, resources, non-secret environment configuration, and readiness/liveness probes.",
	}, s.getDeployment)
}

type listPodsInput struct {
	Namespace     string `json:"namespace,omitempty" jsonschema:"Kubernetes namespace. Defaults to the server's configured namespace."`
	LabelSelector string `json:"label_selector,omitempty" jsonschema:"Optional Kubernetes label selector, for example app=payment."`
}

type listPodsOutput struct {
	Namespace string           `json:"namespace"`
	Count     int              `json:"count"`
	Pods      []k8s.PodSummary `json:"pods"`
}

func (s *Server) listPods(ctx context.Context, _ *mcp.CallToolRequest, input listPodsInput) (*mcp.CallToolResult, listPodsOutput, error) {
	namespace := s.namespace(input.Namespace)
	pods, err := s.client.ListPods(ctx, namespace, input.LabelSelector)
	if err != nil {
		return nil, listPodsOutput{}, err
	}
	return nil, listPodsOutput{Namespace: namespace, Count: len(pods), Pods: pods}, nil
}

type getPodInput struct {
	Namespace string `json:"namespace,omitempty" jsonschema:"Kubernetes namespace. Defaults to the server's configured namespace."`
	PodName   string `json:"pod_name" jsonschema:"Exact Kubernetes pod name to inspect."`
}

func (s *Server) getPod(ctx context.Context, _ *mcp.CallToolRequest, input getPodInput) (*mcp.CallToolResult, k8s.PodDetails, error) {
	if input.PodName == "" {
		return nil, k8s.PodDetails{}, fmt.Errorf("pod_name is required")
	}
	returnValue, err := s.client.GetPod(ctx, s.namespace(input.Namespace), input.PodName)
	return nil, returnValue, err
}

type getPodLogsInput struct {
	Namespace string `json:"namespace,omitempty" jsonschema:"Kubernetes namespace. Defaults to the server's configured namespace."`
	PodName   string `json:"pod_name" jsonschema:"Exact Kubernetes pod name."`
	Container string `json:"container,omitempty" jsonschema:"Optional container name. Required for multi-container pods when Kubernetes cannot infer it."`
	TailLines int64  `json:"tail_lines,omitempty" jsonschema:"Number of recent log lines. Defaults to 200 and is capped at 1000."`
	Previous  bool   `json:"previous,omitempty" jsonschema:"Read logs from the previous terminated container instance. Useful after a restart."`
}

func (s *Server) getPodLogs(ctx context.Context, _ *mcp.CallToolRequest, input getPodLogsInput) (*mcp.CallToolResult, k8s.PodLogs, error) {
	if input.PodName == "" {
		return nil, k8s.PodLogs{}, fmt.Errorf("pod_name is required")
	}
	returnValue, err := s.client.GetPodLogs(ctx, s.namespace(input.Namespace), input.PodName, input.Container, input.TailLines, input.Previous)
	return nil, returnValue, err
}

type getEventsInput struct {
	Namespace  string `json:"namespace,omitempty" jsonschema:"Kubernetes namespace. Defaults to the server's configured namespace."`
	ObjectName string `json:"object_name,omitempty" jsonschema:"Optional involved Kubernetes object name such as a pod or deployment."`
	ObjectKind string `json:"object_kind,omitempty" jsonschema:"Optional involved object kind such as Pod or Deployment."`
	Limit      int    `json:"limit,omitempty" jsonschema:"Maximum number of recent events. Defaults to 50 and is capped at 200."`
}

type getEventsOutput struct {
	Namespace string             `json:"namespace"`
	Count     int                `json:"count"`
	Events    []k8s.EventSummary `json:"events"`
}

func (s *Server) getEvents(ctx context.Context, _ *mcp.CallToolRequest, input getEventsInput) (*mcp.CallToolResult, getEventsOutput, error) {
	namespace := s.namespace(input.Namespace)
	events, err := s.client.GetEvents(ctx, namespace, input.ObjectName, input.ObjectKind, input.Limit)
	if err != nil {
		return nil, getEventsOutput{}, err
	}
	return nil, getEventsOutput{Namespace: namespace, Count: len(events), Events: events}, nil
}

type getDeploymentInput struct {
	Namespace      string `json:"namespace,omitempty" jsonschema:"Kubernetes namespace. Defaults to the server's configured namespace."`
	DeploymentName string `json:"deployment_name" jsonschema:"Exact Kubernetes Deployment name to inspect."`
}

func (s *Server) getDeployment(ctx context.Context, _ *mcp.CallToolRequest, input getDeploymentInput) (*mcp.CallToolResult, k8s.DeploymentDetails, error) {
	if input.DeploymentName == "" {
		return nil, k8s.DeploymentDetails{}, fmt.Errorf("deployment_name is required")
	}
	returnValue, err := s.client.GetDeployment(ctx, s.namespace(input.Namespace), input.DeploymentName)
	return nil, returnValue, err
}

func (s *Server) namespace(namespace string) string {
	if namespace != "" {
		return namespace
	}
	return s.defaultNamespace
}
