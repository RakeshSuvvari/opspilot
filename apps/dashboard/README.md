# OpsPilot Dashboard

Phase 8 React + TypeScript UI for incident investigation and human-approved remediation.

Development:

```bash
npm install
npm run dev
```

The Vite dev server proxies `/api` to the Go Incident API at `http://localhost:8088`.

## Phase 9 incident history

The dashboard now includes an **Incident history** workspace backed by PostgreSQL through the Go Incident API. Selecting a persisted investigation reuses the same `ReportView` used by live investigations, so evidence, timeline, metrics, source correlation, and remediation actions can be reviewed later.
