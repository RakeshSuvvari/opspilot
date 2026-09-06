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
	"github.com/opspilot/opspilot/services/k8s-mcp-server/internal/config"
	k8s "github.com/opspilot/opspilot/services/k8s-mcp-server/internal/kubernetes"
	"github.com/opspilot/opspilot/services/k8s-mcp-server/internal/tools"
)

const version = "0.2.0"

func main() {
	cfg := config.Load()
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))

	client, err := k8s.NewClient(cfg.Kubeconfig)
	if err != nil {
		logger.Error("failed to initialize Kubernetes client", "error", err)
		os.Exit(1)
	}

	mcpServer := mcp.NewServer(&mcp.Implementation{
		Name:    "opspilot-k8s",
		Version: version,
	}, nil)
	tools.New(client, cfg.DefaultNamespace).Register(mcpServer)

	mcpHandler := mcp.NewStreamableHTTPHandler(func(*http.Request) *mcp.Server {
		return mcpServer
	}, &mcp.StreamableHTTPOptions{Stateless: true})

	mux := http.NewServeMux()
	mux.Handle("/mcp", mcpHandler)
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]string{"status": "ok", "version": version})
	})

	server := &http.Server{
		Addr:              cfg.Address,
		Handler:           requestLogger(logger, mux),
		ReadHeaderTimeout: 5 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	go func() {
		logger.Info("k8s MCP server started",
			"address", cfg.Address,
			"mcp_path", "/mcp",
			"default_namespace", cfg.DefaultNamespace,
			"version", version,
		)
		if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			logger.Error("HTTP server failed", "error", err)
			os.Exit(1)
		}
	}()

	<-ctx.Done()
	logger.Info("shutting down k8s MCP server")

	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := server.Shutdown(shutdownCtx); err != nil {
		logger.Error("graceful shutdown failed", "error", err)
	}
}

func requestLogger(logger *slog.Logger, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		started := time.Now()
		next.ServeHTTP(w, r)
		logger.Info("http request",
			"method", r.Method,
			"path", r.URL.Path,
			"duration_ms", time.Since(started).Milliseconds(),
		)
	})
}
