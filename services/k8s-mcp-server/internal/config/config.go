package config

import "os"

const (
	defaultAddress   = ":8080"
	defaultNamespace = "opspilot-demo"
)

type Config struct {
	Address          string
	DefaultNamespace string
	Kubeconfig       string
}

func Load() Config {
	return Config{
		Address:          envOrDefault("OPSPILOT_MCP_ADDR", defaultAddress),
		DefaultNamespace: envOrDefault("OPSPILOT_DEFAULT_NAMESPACE", defaultNamespace),
		Kubeconfig:       os.Getenv("KUBECONFIG"),
	}
}

func envOrDefault(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}
