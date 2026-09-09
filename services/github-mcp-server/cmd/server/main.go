package main

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/opspilot/opspilot/services/github-mcp-server/internal/config"
	"github.com/opspilot/opspilot/services/github-mcp-server/internal/githubapi"
	"github.com/opspilot/opspilot/services/github-mcp-server/internal/tools"
)

const version = "0.6.0"

func main() {
	cfg := config.Load()
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))

	var client githubapi.Client
	var err error
	switch cfg.Mode {
	case "fixture":
		client, err = githubapi.NewFixtureClient(cfg.FixtureFile)
	case "live":
		client, err = githubapi.NewLiveClient(cfg.APIBaseURL, cfg.Owner, cfg.Repository, cfg.Token)
	default:
		logger.Error("unsupported GitHub MCP mode", "mode", cfg.Mode)
		os.Exit(1)
	}
	if err != nil {
		logger.Error("failed to initialize GitHub client", "error", err)
		os.Exit(1)
	}

	mcpServer := mcp.NewServer(&mcp.Implementation{Name: "opspilot-github", Version: version}, nil)
	tools.New(client).Register(mcpServer)
	mcpHandler := mcp.NewStreamableHTTPHandler(func(*http.Request) *mcp.Server { return mcpServer }, &mcp.StreamableHTTPOptions{Stateless: true})

	mux := http.NewServeMux()
	mux.Handle("/mcp", mcpHandler)
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) {
		repo := client.Repository()
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]string{"status": "ok", "version": version, "mode": cfg.Mode, "repository": repo.Owner + "/" + repo.Name})
	})

	server := &http.Server{Addr: cfg.Address, Handler: requestLogger(logger, mux), ReadHeaderTimeout: 5 * time.Second, IdleTimeout: 60 * time.Second}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	go func() {
		repo := client.Repository()
		logger.Info("github MCP server started", "address", cfg.Address, "mode", cfg.Mode, "repository", repo.Owner+"/"+repo.Name, "version", version)
		if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			logger.Error("HTTP server failed", "error", err)
			os.Exit(1)
		}
	}()

	<-ctx.Done()
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	_ = server.Shutdown(shutdownCtx)
}

func requestLogger(logger *slog.Logger, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		started := time.Now()
		next.ServeHTTP(w, r)
		logger.Info("http request", "method", r.Method, "path", r.URL.Path, "duration_ms", time.Since(started).Milliseconds())
	})
}
