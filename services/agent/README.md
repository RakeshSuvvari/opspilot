# OpsPilot Agent

Python agent/orchestration layer for OpsPilot. It combines the Go Kubernetes MCP server, optional Go GitHub MCP server, PostgreSQL/pgvector RAG, deterministic trust/evaluation, and OpenAI Agents SDK.

Phase 6 adds optional GitHub change intelligence. Keep `OPSPILOT_GITHUB_ENABLED=false` for ordinary investigations, or start the GitHub MCP server and enable it for deployment/source-change correlation.

Default model configuration:

```bash
OPENAI_MODEL=gpt-5.4-mini
```
