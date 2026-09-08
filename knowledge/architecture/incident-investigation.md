---
document_type: architecture
---
# OpsPilot Incident Investigation Architecture

OpsPilot separates current-state evidence from organizational knowledge. The Go Kubernetes MCP server exposes live, read-only pod, log, event, and Deployment diagnostics. The Python incident agent coordinates those tools and can retrieve operational knowledge from PostgreSQL with pgvector.

The PostgreSQL knowledge store contains runbooks, architecture documents, historical incidents, and postmortems. Semantic retrieval is intended to improve context and remediation guidance. Retrieved historical material must not override contradictory live Kubernetes evidence.
