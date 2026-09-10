# Incident API (Go)

Phase 8 dashboard gateway. It gives the React UI a single backend surface while keeping OpenAI/agent logic in the Python service.

Endpoints:

- `GET /healthz`
- `GET /api/v1/system`
- `POST /api/v1/investigations`
- `POST /api/v1/remediations`
- `GET /api/v1/remediations/{job_id}`
- `POST /api/v1/remediations/{job_id}/decision`

Defaults:

- listen: `:8088`
- Python agent API: `http://localhost:8001`
- dashboard origin: `http://localhost:5173`

## Phase 9 history routes

The Go gateway proxies persisted incident history from the agent service:

- `GET /api/v1/investigations?limit=25`
- `GET /api/v1/investigations/{investigation_id}`

The dashboard continues to use the Go API as its only backend.
