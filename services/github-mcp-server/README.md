# OpsPilot GitHub MCP Server (Phase 6)

Read-only Go MCP server for deployment/source-change correlation.

## Tools

- `github_list_recent_commits`
- `github_get_commit`
- `github_compare_commits`
- `github_find_pull_requests_for_commit`
- `github_get_pull_request`

The server supports two modes:

- `fixture` (default): deterministic local data matching OpsPilot's four demo incidents.
- `live`: GitHub REST API for one configured repository.

### Fixture mode

From the repository root:

```bash
make github-mcp-server
```

The MCP endpoint is `http://localhost:8090/mcp` and health is `http://localhost:8090/healthz`.

### Live GitHub mode

Set:

```bash
OPSPILOT_GITHUB_MODE=live
OPSPILOT_GITHUB_OWNER=<owner>
OPSPILOT_GITHUB_REPO=<repo>
GITHUB_TOKEN=<fine-grained-token>
```

For a private repository, use least-privilege read permissions. The implemented endpoints need repository Contents read access; PR correlation also needs Pull requests read access. Public repositories can be queried without a token, subject to GitHub rate limits.


## Public repository authentication

`RakeshSuvvari/opspilot` is public, so live mode works without `GITHUB_TOKEN`. For sustained agent investigations, a fine-grained read-only token is recommended to increase API rate limits. Keep the token only in local `.env`; never commit it.

Live mode reads the configured repository only. Fixture mode remains available for deterministic incident-change evaluations whose synthetic SHAs/PRs do not exist in the real repository.
