package api

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"net/http"
	"strings"
	"time"

	"opspilot/services/incident-api/internal/config"
)

const version = "0.9.0"

type Server struct {
	cfg    config.Config
	client *http.Client
	mux    *http.ServeMux
}

func New(cfg config.Config) *Server {
	s := &Server{
		cfg: cfg,
		client: &http.Client{
			Timeout: cfg.RequestTimeout,
		},
		mux: http.NewServeMux(),
	}
	s.routes()
	return s
}

func (s *Server) Handler() http.Handler {
	return s.withCORS(s.withLogging(s.mux))
}

func (s *Server) routes() {
	s.mux.HandleFunc("GET /healthz", s.healthz)
	s.mux.HandleFunc("GET /api/v1/system", s.system)
	s.mux.HandleFunc("GET /api/v1/investigations", s.proxyFixed("/v1/investigations"))
	s.mux.HandleFunc("GET /api/v1/investigations/{investigationID}", s.proxyInvestigation)
	s.mux.HandleFunc("POST /api/v1/investigations", s.proxyFixed("/v1/investigations"))
	s.mux.HandleFunc("POST /api/v1/remediations", s.proxyFixed("/v1/remediations"))
	s.mux.HandleFunc("GET /api/v1/remediations/{jobID}", s.proxyRemediation)
	s.mux.HandleFunc("POST /api/v1/remediations/{jobID}/decision", s.proxyRemediationDecision)
}

func (s *Server) healthz(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"status":        "ok",
		"version":       version,
		"agent_api_url": s.cfg.AgentAPIURL,
	})
}

func (s *Server) system(w http.ResponseWriter, r *http.Request) {
	health, healthStatus, err := s.getJSON(r.Context(), "/healthz")
	if err != nil {
		writeJSON(w, http.StatusBadGateway, map[string]any{
			"gateway": map[string]any{"status": "ok", "version": version},
			"agent":   map[string]any{"status": "unreachable", "error": err.Error()},
			"tools":   []string{},
		})
		return
	}
	tools, _, toolsErr := s.getJSON(r.Context(), "/v1/tools")
	if toolsErr != nil {
		tools = map[string]any{"tools": []string{}}
	}
	writeJSON(w, healthStatus, map[string]any{
		"gateway": map[string]any{"status": "ok", "version": version},
		"agent":   health,
		"tools":   tools["tools"],
	})
}

func (s *Server) proxyFixed(upstreamPath string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s.proxy(w, r, upstreamPath)
	}
}

func (s *Server) proxyInvestigation(w http.ResponseWriter, r *http.Request) {
	investigationID := strings.TrimSpace(r.PathValue("investigationID"))
	if investigationID == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "missing investigation id"})
		return
	}
	s.proxy(w, r, "/v1/investigations/"+investigationID)
}

func (s *Server) proxyRemediation(w http.ResponseWriter, r *http.Request) {
	jobID := strings.TrimSpace(r.PathValue("jobID"))
	if jobID == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "missing remediation job id"})
		return
	}
	s.proxy(w, r, "/v1/remediations/"+jobID)
}

func (s *Server) proxyRemediationDecision(w http.ResponseWriter, r *http.Request) {
	jobID := strings.TrimSpace(r.PathValue("jobID"))
	if jobID == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "missing remediation job id"})
		return
	}
	s.proxy(w, r, "/v1/remediations/"+jobID+"/decision")
}

func (s *Server) proxy(w http.ResponseWriter, r *http.Request, upstreamPath string) {
	var body []byte
	if r.Body != nil {
		limited := io.LimitReader(r.Body, 2<<20)
		data, err := io.ReadAll(limited)
		if err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "failed to read request body"})
			return
		}
		body = data
	}

	req, err := http.NewRequestWithContext(
		r.Context(),
		r.Method,
		s.cfg.AgentAPIURL+upstreamPath,
		bytes.NewReader(body),
	)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "failed to create upstream request"})
		return
	}
	if contentType := r.Header.Get("Content-Type"); contentType != "" {
		req.Header.Set("Content-Type", contentType)
	}
	req.URL.RawQuery = r.URL.RawQuery
	req.Header.Set("Accept", "application/json")

	resp, err := s.client.Do(req)
	if err != nil {
		writeJSON(w, http.StatusBadGateway, map[string]string{"error": "agent service unavailable"})
		return
	}
	defer resp.Body.Close()

	w.Header().Set("Content-Type", resp.Header.Get("Content-Type"))
	w.WriteHeader(resp.StatusCode)
	_, _ = io.Copy(w, io.LimitReader(resp.Body, 8<<20))
}

func (s *Server) getJSON(ctx context.Context, path string) (map[string]any, int, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, s.cfg.AgentAPIURL+path, nil)
	if err != nil {
		return nil, 0, err
	}
	resp, err := s.client.Do(req)
	if err != nil {
		return nil, 0, err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, resp.StatusCode, errors.New("upstream returned " + resp.Status)
	}
	var payload map[string]any
	if err := json.NewDecoder(io.LimitReader(resp.Body, 2<<20)).Decode(&payload); err != nil {
		return nil, resp.StatusCode, err
	}
	return payload, resp.StatusCode, nil
}

func (s *Server) withCORS(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		origin := r.Header.Get("Origin")
		if origin != "" && (origin == s.cfg.DashboardOrigin || s.cfg.DashboardOrigin == "*") {
			w.Header().Set("Access-Control-Allow-Origin", origin)
			w.Header().Set("Vary", "Origin")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
			w.Header().Set("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
		}
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func (s *Server) withLogging(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		started := time.Now()
		next.ServeHTTP(w, r)
		slog.Info("http request", "method", r.Method, "path", r.URL.Path, "duration_ms", time.Since(started).Milliseconds())
	})
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}
