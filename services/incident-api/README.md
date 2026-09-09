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
