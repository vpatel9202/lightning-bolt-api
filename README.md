# lightning-bolt-api

Read-only Python client, CLI, and MCP server for Lightning Bolt's reverse-engineered API.

This package focuses on API access and data return only. It does not handle Google
Calendar sync, iCal conflict logic, provider classification, shift claiming, swaps,
notifications, or downstream storage decisions.

## Current Status

The core v1 implementation is async-first and uses direct HTTP auth. Browser automation is
not part of the normal runtime path. Chrome DevTools or Playwright can still be used during
development if Lightning Bolt changes the web UI or network flow and the direct HTTP path
needs to be revalidated.

Implemented:

- Direct login, dashboard refresh-token rotation, and `/token` JWT exchange.
- Session cache persistence for auth/session state only.
- ViewerAPI, personal schedule range, subscription, and employee feed reads.
- Typed normalized models with preserved `raw` payloads.
- `lb-api` CLI.
- `lb-api-mcp` MCP server over stdio and streamable HTTP.
- Docker image for HTTP MCP mode.

## Development

```bash
uv sync
UV_CACHE_DIR=/tmp/uv-cache uv run pytest
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check .
uv run lb-api version
```

Create `.env` from `.env.example` for authenticated local testing:

```bash
LB_USERNAME=
LB_PASSWORD=
LB_SESSION_CACHE=session-cache/session.json
LB_DEFAULT_VIEW_ID=
LB_DEFAULT_TZ=America/Chicago
```

`session-cache/` is gitignored. Never commit real credentials, cookies, refresh tokens,
JWTs, raw captures with PII, or session cache files.

## CLI

All commands write JSON to stdout by default. Use `--output path.json` when you explicitly
want a file.

```bash
uv run lb-api login
uv run lb-api dashboard
uv run lb-api views
uv run lb-api templates --view-id 123
uv run lb-api viewerapi --view-id 123 --start 20260501 --end 20260531
uv run lb-api schedule --view-id 123 --start 20260501 --end 20260531
uv run lb-api personal-schedule --emp-id 10001 --start 20260501 --end 20260531
uv run lb-api subscription --emp-id 10001
uv run lb-api feed --emp-id 10001 --since 1770000000
```

Request dates must be `YYYYMMDD`. ISO strings such as `2026-05-01` are rejected because
Lightning Bolt silently ignores them for these endpoints.

## MCP

Host stdio:

```bash
uv run lb-api-mcp stdio
```

Host streamable HTTP:

```bash
uv run lb-api-mcp http --host 127.0.0.1 --port 8000
```

The streamable HTTP MCP endpoint is mounted at `/mcp`. Credentials and session state come
from environment variables or mounted secrets, not MCP tool arguments.

Tools:

- `lb_get_dashboard`
- `lb_list_views`
- `lb_list_templates`
- `lb_get_viewerapi`
- `lb_fetch_schedule_range`
- `lb_get_subscription`
- `lb_get_employee_feed`

Tool responses return compact normalized JSON by default. Pass `include_raw=true` when you
need preserved Lightning Bolt payloads.

## Docker

```bash
docker build -t lightning-bolt-api .
docker run --rm \
  -p 8000:8000 \
  --env-file .env \
  -v "$PWD/session-cache:/app/session-cache" \
  lightning-bolt-api
```

The default Docker command runs HTTP MCP on `0.0.0.0:8000`.

## Live Validation

Use a small date range first:

```bash
uv run lb-api login
uv run lb-api dashboard
uv run lb-api views
uv run lb-api viewerapi --view-id "$LB_DEFAULT_VIEW_ID" --start 20260501 --end 20260507
```

After validation, check `git status --short` and make sure only intended source/docs/test
files changed. `.env` and `session-cache/` must remain untracked.

## Durable Context

Start with these files before changing behavior:

- `AGENTS.md` - full implementation context and constraints for future agents.
- `docs/investigation-findings.md` - Lightning Bolt auth/API findings from live investigation.
- `docs/implementation-plan.md` - original build plan.
- `fixtures/sanitized_viewerapi_view50.json` - anonymized public sample fixture.

## License

MIT
