package config

import (
	"os"
	"strconv"
	"strings"
	"time"
)

type Config struct {
	Addr            string
	AgentAPIURL     string
	DashboardOrigin string
	RequestTimeout  time.Duration
}

func FromEnv() Config {
	return Config{
		Addr:            getenv("OPSPILOT_INCIDENT_API_ADDR", ":8088"),
		AgentAPIURL:     strings.TrimRight(getenv("OPSPILOT_AGENT_API_URL", "http://localhost:8001"), "/"),
		DashboardOrigin: getenv("OPSPILOT_DASHBOARD_ORIGIN", "http://localhost:5173"),
		RequestTimeout:  time.Duration(getenvInt("OPSPILOT_INCIDENT_API_TIMEOUT_SECONDS", 180)) * time.Second,
	}
}

func getenv(key, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(key)); value != "" {
		return value
	}
	return fallback
}

func getenvInt(key string, fallback int) int {
	value := strings.TrimSpace(os.Getenv(key))
	if value == "" {
		return fallback
	}
	parsed, err := strconv.Atoi(value)
	if err != nil || parsed <= 0 {
		return fallback
	}
	return parsed
}
