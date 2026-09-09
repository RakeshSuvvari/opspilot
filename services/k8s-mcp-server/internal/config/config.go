package config

import (
	"os"
	"strconv"
	"strings"
)

const (
	defaultAddress          = ":8080"
	defaultNamespace        = "opspilot-demo"
	defaultMaxScaleReplicas = 10
)

type Config struct {
	Address          string
	DefaultNamespace string
	Kubeconfig       string
	WriteEnabled     bool
	MaxScaleReplicas int32
}

func Load() Config {
	return Config{
		Address:          envOrDefault("OPSPILOT_MCP_ADDR", defaultAddress),
		DefaultNamespace: envOrDefault("OPSPILOT_DEFAULT_NAMESPACE", defaultNamespace),
		Kubeconfig:       os.Getenv("KUBECONFIG"),
		WriteEnabled:     envBool("OPSPILOT_K8S_WRITE_ENABLED", false),
		MaxScaleReplicas: int32(envInt("OPSPILOT_K8S_MAX_SCALE_REPLICAS", defaultMaxScaleReplicas)),
	}
}

func envOrDefault(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}

func envBool(key string, fallback bool) bool {
	raw := strings.TrimSpace(strings.ToLower(os.Getenv(key)))
	if raw == "" {
		return fallback
	}
	return raw == "1" || raw == "true" || raw == "yes" || raw == "on"
}

func envInt(key string, fallback int) int {
	raw := strings.TrimSpace(os.Getenv(key))
	if raw == "" {
		return fallback
	}
	value, err := strconv.Atoi(raw)
	if err != nil || value < 0 {
		return fallback
	}
	return value
}
