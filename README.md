# lightning-bolt-api

`lightning-bolt-api` is a read-only Python client, CLI, and MCP server for Lightning
Bolt's reverse-engineered JSON API.

It is designed to retrieve useful normalized schedule data while preserving the raw
Lightning Bolt payloads for consumers that need fields the library does not normalize yet.
It does not perform calendar sync, iCal parsing, provider classification, notifications,
shift claiming, swaps, requests, or any other write action.

## What Is Built

- Direct HTTP login and token refresh, without Playwright or DOM scraping in normal use.
- Auth/session cache persistence for cookies, refresh token, JWT, expiry, and user IDs.
- Read endpoints for dashboard, ViewerAPI, schedule range, subscription metadata, and
  employee feed.
- Self-bootstrapping view discovery when `LB_DEFAULT_VIEW_ID` is not set.
- Pydantic models with `raw` payload preservation.
- `lb-api` CLI for local JSON output.
- `lb-api-mcp` server over stdio and streamable HTTP.
- Docker image for HTTP MCP mode.

## Install For Development

```bash
uv sync
UV_CACHE_DIR=/tmp/uv-cache uv run pytest
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check .
uv run lb-api version
```

The project requires Python 3.12 or newer and is managed with `uv`.

## Configure Credentials

Create `.env` from `.env.example`:

```bash
LB_USERNAME=
LB_PASSWORD=
LB_SESSION_CACHE=session-cache/session.json
LB_DEFAULT_VIEW_ID=
LB_DEFAULT_TZ=America/Chicago
```

`LB_DEFAULT_VIEW_ID` is optional. If it is not set, the client calls ViewerAPI without a
view ID and uses Lightning Bolt's default context.

Security rules:

- Never commit `.env`.
- Never commit `session-cache/` or `session_cache`.
- Never commit cookies, refresh tokens, JWTs, unsanitized raw captures, or personnel data.
- Do not pass Lightning Bolt credentials as MCP tool arguments.

## CLI Quick Start

All CLI commands write JSON to stdout by default. Use `--output path.json` only when you
explicitly want to write a file.

```bash
uv run lb-api login
uv run lb-api discover
uv run lb-api views
uv run lb-api schedule --start 20260501 --end 20260507
```

Dates must be `YYYYMMDD`. ISO strings such as `2026-05-01` are rejected because Lightning
Bolt silently ignores them for these endpoints.

Common commands:

```bash
uv run lb-api dashboard
uv run lb-api templates --view-id 123
uv run lb-api viewerapi --start 20260501 --end 20260531
uv run lb-api viewerapi --view-id 123 --start 20260501 --end 20260531
uv run lb-api schedule --start 20260501 --end 20260531
uv run lb-api schedule --view-id 123 --start 20260501 --end 20260531
uv run lb-api personal-schedule --emp-id 10001 --start 20260501 --end 20260531
uv run lb-api subscription --emp-id 10001
uv run lb-api feed --emp-id 10001 --since 1770000000
```

Use `--include-raw` when you need the preserved Lightning Bolt source payload.

## MCP Quick Start

Host stdio:

```bash
uv run lb-api-mcp stdio
```

Host streamable HTTP:

```bash
uv run lb-api-mcp http --host 127.0.0.1 --port 8000
```

The streamable HTTP endpoint is mounted at `/mcp`.

MCP tools:

- `lb_get_dashboard`
- `lb_discover_context`
- `lb_list_views`
- `lb_list_templates`
- `lb_get_viewerapi`
- `lb_fetch_schedule_range`
- `lb_get_subscription`
- `lb_get_employee_feed`

See [docs/mcp.md](docs/mcp.md) for transport setup and tool reference.

## Docker

```bash
docker build -t lightning-bolt-api .
docker run --rm \
  -p 8000:8000 \
  --env-file .env \
  -v "$PWD/session-cache:/app/session-cache" \
  lightning-bolt-api
```

The Docker image starts `lb-api-mcp http --host 0.0.0.0 --port 8000`.

## Python Client

```python
import asyncio
from dotenv import load_dotenv
from lightning_bolt_api import LightningBoltClient


async def main() -> None:
    load_dotenv()
    async with LightningBoltClient.from_env() as client:
        context = await client.discover_context()
        slots = await client.fetch_schedule(start_date="20260501", end_date="20260507")
        print(context.source, len(slots))


asyncio.run(main())
```

The core client is async-first. Sync wrappers are not currently provided.

## Documentation

- [docs/architecture.md](docs/architecture.md): how the implemented system works.
- [docs/mcp.md](docs/mcp.md): MCP transports, configuration, and tool reference.
- [docs/investigation-findings.md](docs/investigation-findings.md): historical
  reverse-engineering findings.
- [AGENTS.md](AGENTS.md): maintenance and handoff guidance for coding agents.

## License

MIT
