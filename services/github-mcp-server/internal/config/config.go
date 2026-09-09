package config

import (
	"os"
	"strings"
)

type Config struct {
	Address     string
	Mode        string
	Owner       string
	Repository  string
	Token       string
	APIBaseURL  string
	FixtureFile string
}

func Load() Config {
	return Config{
		Address:     env("OPSPILOT_GITHUB_MCP_ADDR", ":8090"),
		Mode:        strings.ToLower(env("OPSPILOT_GITHUB_MODE", "fixture")),
		Owner:       os.Getenv("OPSPILOT_GITHUB_OWNER"),
		Repository:  os.Getenv("OPSPILOT_GITHUB_REPO"),
		Token:       os.Getenv("GITHUB_TOKEN"),
		APIBaseURL:  env("OPSPILOT_GITHUB_API_BASE", "https://api.github.com"),
		FixtureFile: env("OPSPILOT_GITHUB_FIXTURE_FILE", "services/github-mcp-server/fixtures/demo.json"),
	}
}

func env(name, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(name)); value != "" {
		return value
	}
	return fallback
}
