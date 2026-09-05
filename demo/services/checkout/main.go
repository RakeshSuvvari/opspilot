package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strconv"
	"time"
)

type checkoutResponse struct {
	Status    string `json:"status"`
	Inventory string `json:"inventory,omitempty"`
	Error     string `json:"error,omitempty"`
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

func allocateMemory(mb int) []byte {
	if mb <= 0 {
		return nil
	}

	size := mb * 1024 * 1024
	memory := make([]byte, size)

	// Touch every memory page so the allocation is resident and visible to the
	// container memory controller. This is only used by INC-002.
	for i := 0; i < len(memory); i += 4096 {
		memory[i] = 1
	}
	if len(memory) > 0 {
		memory[len(memory)-1] = 1
	}

	return memory
}

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	inventoryURL := os.Getenv("INVENTORY_URL")
	if inventoryURL == "" {
		inventoryURL = "http://inventory:8080/inventory"
	}

	timeoutMS := envInt("INVENTORY_TIMEOUT_MS", 500)
	memoryHogMB := envInt("MEMORY_HOG_MB", 0)

	retainedMemory := allocateMemory(memoryHogMB)
	if len(retainedMemory) > 0 {
		log.Printf("allocated_and_retained_memory_mb=%d", memoryHogMB)
	}

	client := &http.Client{Timeout: time.Duration(timeoutMS) * time.Millisecond}

	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok\n"))
	})
	mux.HandleFunc("/checkout", func(w http.ResponseWriter, r *http.Request) {
		started := time.Now()

		response, err := client.Get(inventoryURL)
		if err != nil {
			message := fmt.Sprintf("inventory request failed: %v", err)
			log.Printf("request path=%s status=503 duration_ms=%d error=%q inventory_timeout_ms=%d", r.URL.Path, time.Since(started).Milliseconds(), message, timeoutMS)

			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusServiceUnavailable)
			_ = json.NewEncoder(w).Encode(checkoutResponse{Status: "failed", Error: message})
			return
		}
		defer response.Body.Close()

		body, err := io.ReadAll(response.Body)
		if err != nil {
			log.Printf("request path=%s status=502 error=%q", r.URL.Path, err)
			http.Error(w, "failed to read inventory response", http.StatusBadGateway)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(checkoutResponse{Status: "ok", Inventory: string(body)})
		log.Printf("request path=%s status=200 duration_ms=%d inventory_status=%d", r.URL.Path, time.Since(started).Milliseconds(), response.StatusCode)
	})

	// Keep a live reference for the deliberate OOM scenario.
	_ = retainedMemory

	log.Printf("checkout service listening on :%s inventory_url=%s inventory_timeout_ms=%d", port, inventoryURL, timeoutMS)
	log.Fatal(http.ListenAndServe(":"+port, mux))
}
