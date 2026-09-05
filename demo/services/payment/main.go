package main

import (
	"encoding/json"
	"log"
	"net/http"
	"os"
)

type paymentResponse struct {
	Status string `json:"status"`
}

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	databaseURL := os.Getenv("DATABASE_URL")
	if databaseURL == "" {
		log.Fatal("startup failed: DATABASE_URL environment variable not configured")
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok\n"))
	})
	mux.HandleFunc("/pay", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(paymentResponse{Status: "authorized"})
		log.Printf("request path=%s status=200", r.URL.Path)
	})

	log.Printf("payment service listening on :%s database_configured=true", port)
	log.Fatal(http.ListenAndServe(":"+port, mux))
}
