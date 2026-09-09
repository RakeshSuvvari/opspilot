package main

import (
	"log/slog"
	"net/http"
	"os"

	"opspilot/services/incident-api/internal/api"
	"opspilot/services/incident-api/internal/config"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	slog.SetDefault(logger)

	cfg := config.FromEnv()
	server := api.New(cfg)

	slog.Info("starting OpsPilot Incident API", "addr", cfg.Addr, "agent_api", cfg.AgentAPIURL)
	if err := http.ListenAndServe(cfg.Addr, server.Handler()); err != nil {
		slog.Error("incident api stopped", "error", err)
		os.Exit(1)
	}
}
