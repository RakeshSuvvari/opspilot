package main

import (
	"encoding/json"
	"log"
	"net/http"
	"os"
	"strconv"
	"time"
)

type inventoryResponse struct {
	Item      string `json:"item"`
	Available bool   `json:"available"`
	Quantity  int    `json:"quantity"`
	DelayMS   int    `json:"delay_ms"`
}

func envInt(key string, fallback int) int {
	value := os.Getenv(key)
	if value == "" {
		return fallback
	}

	parsed, err := strconv.Atoi(value)
	if err != nil {
		log.Printf("invalid %s=%q, using %d", key, value, fallback)
		return fallback
	}
	return parsed
}

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	delayMS := envInt("RESPONSE_DELAY_MS", 100)

	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok\n"))
	})
	mux.HandleFunc("/inventory", func(w http.ResponseWriter, r *http.Request) {
		started := time.Now()
		time.Sleep(time.Duration(delayMS) * time.Millisecond)

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(inventoryResponse{
			Item:      "demo-item",
			Available: true,
			Quantity:  42,
			DelayMS:   delayMS,
		})

		log.Printf("request path=%s status=200 duration_ms=%d configured_delay_ms=%d", r.URL.Path, time.Since(started).Milliseconds(), delayMS)
	})

	log.Printf("inventory service listening on :%s response_delay_ms=%d", port, delayMS)
	log.Fatal(http.ListenAndServe(":"+port, mux))
}
