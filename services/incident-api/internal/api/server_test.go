package api

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"opspilot/services/incident-api/internal/config"
)

func TestInvestigationProxy(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/investigations" {
			t.Fatalf("unexpected upstream path: %s", r.URL.Path)
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"incident"}`))
	}))
	defer upstream.Close()

	s := New(config.Config{AgentAPIURL: upstream.URL, DashboardOrigin: "http://localhost:5173", RequestTimeout: time.Second})
	req := httptest.NewRequest(http.MethodPost, "/api/v1/investigations", nil)
	rec := httptest.NewRecorder()
	s.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}
}

func TestSystemAggregatesAgentHealthAndTools(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/healthz":
			_, _ = w.Write([]byte(`{"status":"ok","model":"gpt-5.4-mini"}`))
		case "/v1/tools":
			_, _ = w.Write([]byte(`{"tools":["k8s_list_pods"]}`))
		default:
			http.NotFound(w, r)
		}
	}))
	defer upstream.Close()

	s := New(config.Config{AgentAPIURL: upstream.URL, DashboardOrigin: "http://localhost:5173", RequestTimeout: time.Second})
	req := httptest.NewRequest(http.MethodGet, "/api/v1/system", nil)
	rec := httptest.NewRecorder()
	s.Handler().ServeHTTP(rec, req)

	var payload map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &payload); err != nil {
		t.Fatal(err)
	}
	if rec.Code != http.StatusOK || payload["agent"] == nil {
		t.Fatalf("unexpected response: %d %s", rec.Code, rec.Body.String())
	}
}

func TestCORSForDashboardOrigin(t *testing.T) {
	s := New(config.Config{AgentAPIURL: "http://127.0.0.1:1", DashboardOrigin: "http://localhost:5173", RequestTimeout: time.Second})
	req := httptest.NewRequest(http.MethodOptions, "/api/v1/investigations", nil)
	req.Header.Set("Origin", "http://localhost:5173")
	rec := httptest.NewRecorder()
	s.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusNoContent {
		t.Fatalf("expected 204, got %d", rec.Code)
	}
	if got := rec.Header().Get("Access-Control-Allow-Origin"); got != "http://localhost:5173" {
		t.Fatalf("unexpected allow origin: %q", got)
	}
}

func TestInvestigationHistoryProxyPreservesQuery(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/investigations" {
			t.Fatalf("unexpected upstream path: %s", r.URL.Path)
		}
		if got := r.URL.Query().Get("limit"); got != "12" {
			t.Fatalf("expected limit query to be preserved, got %q", got)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`[]`))
	}))
	defer upstream.Close()

	s := New(config.Config{AgentAPIURL: upstream.URL, DashboardOrigin: "http://localhost:5173", RequestTimeout: time.Second})
	req := httptest.NewRequest(http.MethodGet, "/api/v1/investigations?limit=12", nil)
	rec := httptest.NewRecorder()
	s.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}
}

func TestInvestigationHistoryDetailProxy(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/investigations/inv-123" {
			t.Fatalf("unexpected upstream path: %s", r.URL.Path)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"investigation_id":"inv-123"}`))
	}))
	defer upstream.Close()

	s := New(config.Config{AgentAPIURL: upstream.URL, DashboardOrigin: "http://localhost:5173", RequestTimeout: time.Second})
	req := httptest.NewRequest(http.MethodGet, "/api/v1/investigations/inv-123", nil)
	rec := httptest.NewRecorder()
	s.Handler().ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d", rec.Code)
	}
}
