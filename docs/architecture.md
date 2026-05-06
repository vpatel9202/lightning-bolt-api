# Architecture

This document describes the current implementation of `lightning-bolt-api`.

For protocol-level details needed to reimplement the client in another language, see
[Lightning Bolt API Reference](lightning-bolt-api.md).

## Purpose

The package provides read-only access to Lightning Bolt's JSON endpoints. It normalizes
common data into typed models and preserves raw payloads so callers can inspect fields that
are not yet modeled.

The package intentionally does not own downstream business logic. Calendar sync, provider
classification, notifications, shift claims, swaps, and request creation belong outside
this repository.

## Runtime Shape

The project exposes three interfaces over the same core client:

- Python package: `lightning_bolt_api`
- CLI command: `lb-api`
- MCP command: `lb-api-mcp`

The core client is async-first and lives in `lightning_bolt_api.client`. The CLI and MCP
server both create `LightningBoltClient.from_env()` instances and use the same read
methods.

## Authentication And Session State

Authentication uses direct HTTP with `httpx.AsyncClient`.

The login flow is:

1. Start at `https://s2.lightning-bolt.com`.
2. Submit the form credentials.
3. Follow redirects into `lblite.lightning-bolt.com`.
4. Call `/api/v1/dashboard`, which rotates `LB_TKN`.
5. Exchange `LB_TKN` at `https://lbapi.lightning-bolt.com/token`.
6. Use the returned JWT as `Authorization: Bearer ...` for API reads.

Refresh tokens rotate and are single-use. The client serializes refreshes with an
`asyncio.Lock`, refreshes before expiry, and falls back to a full login when credentials
are available.

The session cache stores auth/session state only:

- access token
- refresh token
- expiry
- customer ID
- employee ID
- user ID
- cookies

It does not store schedule exports or scrape results. The default cache path comes from
`LB_SESSION_CACHE` when set, otherwise the user cache directory is used. Cache files are
written with best-effort `0600` permissions.

## Data Access

Primary schedule data comes from:

```text
POST https://lbapi.lightning-bolt.com/viewerapi
```

The request body only uses confirmed fields:

- `view_id`
- `tz`
- `start_date`
- `end_date`

`view_id` is optional. When it is omitted, Lightning Bolt returns the default viewer
context for the authenticated user. This is how the library supports first-run discovery
without requiring `LB_DEFAULT_VIEW_ID`.

Other read endpoints:

- `/schedule/range/?start_date=YYYYMMDD&end_date=YYYYMMDD&listed=true&emp_id=N`
- `/subscription?emp_id=N&dash=true`
- `https://fd.lightning-bolt.com/employee_feed/{customer_id}/{emp_id}?last=<unix_ts>`

All Lightning Bolt request dates must be `YYYYMMDD`. ISO date strings are rejected before
requests are sent.

Employee-scoped reads prefer `LB_EMP_ID`. If that is not set, `LB_EMPLOYEE_NAME` can be
used for fuzzy matching against ViewerAPI personnel, and the authenticated session
employee ID is the final fallback.

## Discovery

The client discovers usable context in this order:

1. Dashboard `views`, when present.
2. `LB_DEFAULT_VIEW_ID`, when configured.
3. ViewerAPI without `view_id`, using Lightning Bolt's default context.

`discover_context()` returns a `DiscoveredContext` model with the source of discovery,
available views, default view, user IDs, timezone, and whether callers can omit
`view_id`.

`fetch_schedule()` accepts `view_id=None`. In that case it uses `LB_DEFAULT_VIEW_ID` when
available, otherwise it omits `view_id` and relies on ViewerAPI default context.

## Models And Raw Payloads

Models live in `lightning_bolt_api.models` and are Pydantic models. Most response models
inherit from `RawModel`, which includes:

```python
raw: dict[str, Any]
```

Key models:

- `Dashboard`
- `DiscoveredContext`
- `ViewerApiResponse`
- `View`
- `Department`
- `Template`
- `Personnel`
- `EmployeeMatch`
- `Assignment`
- `Slot`
- `Subscription`
- `ActivityFeed`
- `ActivityFeedItem`
- `SessionState`

`Slot` includes helper properties for read-side convenience:

- `is_open_shift`
- `is_assigned_to(emp_id)`
- `has_any_note`

The helpers do not classify providers as MD, APP, or any organization-specific type.

## CLI

The CLI is implemented with Typer. It loads `.env`, creates a client from environment
variables, and writes JSON to stdout by default.

CLI commands:

- `version`
- `login`
- `dashboard`
- `views`
- `templates`
- `viewerapi`
- `discover`
- `schedule`
- `personal-schedule`
- `subscription`
- `feed`

Commands accept `--output` for explicit file output and `--include-raw` where raw payloads
are useful.

## MCP Server

The MCP server uses `mcp.server.fastmcp.FastMCP`.

Supported transports:

- stdio
- streamable HTTP at `/mcp`

The MCP server reads credentials and session configuration from environment variables. MCP
tools do not accept credentials as normal arguments.

## Docker

The Docker image installs the package with `uv sync --frozen --no-dev` and starts the
installed MCP console script:

```text
/app/.venv/bin/lb-api-mcp http --host 0.0.0.0 --port 8000
```

Mount a session cache directory when running the container so auth state can persist
between starts.

## Validation

The test suite uses mocked HTTP responses and the sanitized ViewerAPI fixture. Coverage
includes auth chain behavior, refresh serialization, date validation, parser behavior, CLI
smoke tests, MCP tool registration, and default view discovery.

Useful checks:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check .
docker build -t lightning-bolt-api .
```

Live validation should use small date ranges and must not write raw unsanitized payloads
to tracked files.
