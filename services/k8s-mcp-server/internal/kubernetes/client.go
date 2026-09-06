package kubernetes

import (
	"fmt"
	"os"
	"path/filepath"

	kubernetesclient "k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
	"k8s.io/client-go/tools/clientcmd"
)

type Client struct {
	clientset kubernetesclient.Interface
}

func NewClient(kubeconfig string) (*Client, error) {
	config, err := buildConfig(kubeconfig)
	if err != nil {
		return nil, err
	}

	clientset, err := kubernetesclient.NewForConfig(config)
	if err != nil {
		return nil, fmt.Errorf("create Kubernetes client: %w", err)
	}

	return &Client{clientset: clientset}, nil
}

func NewForClient(clientset kubernetesclient.Interface) *Client {
	return &Client{clientset: clientset}
}

func buildConfig(kubeconfig string) (*rest.Config, error) {
	if kubeconfig != "" {
		config, err := clientcmd.BuildConfigFromFlags("", kubeconfig)
		if err != nil {
			return nil, fmt.Errorf("load kubeconfig %q: %w", kubeconfig, err)
		}
		return config, nil
	}

	if os.Getenv("KUBERNETES_SERVICE_HOST") != "" {
		config, err := rest.InClusterConfig()
		if err != nil {
			return nil, fmt.Errorf("load in-cluster Kubernetes config: %w", err)
		}
		return config, nil
	}

	home, err := os.UserHomeDir()
	if err != nil {
		return nil, fmt.Errorf("resolve home directory: %w", err)
	}

	path := filepath.Join(home, ".kube", "config")
	config, err := clientcmd.BuildConfigFromFlags("", path)
	if err != nil {
		return nil, fmt.Errorf("load default kubeconfig %q: %w", path, err)
	}
	return config, nil
}
