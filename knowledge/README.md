# OpsPilot Knowledge Base

Markdown files in this directory are indexed into PostgreSQL by `make rag-ingest`.

Supported categories are inferred from the first folder beneath `knowledge/`:

- `runbooks/` -> `runbook`
- `postmortems/` -> `postmortem`
- `architecture/` -> `architecture`
- `incidents/` -> `incident`

Documents may optionally start with lightweight front matter:

```text
---
service: payment
document_type: runbook
---
```

`service` enables retrieval filters. `document_type` can override the folder-derived type.

Ingestion is content-hash aware. An unchanged file using the same embedding model and dimensions is skipped instead of being embedded again.
