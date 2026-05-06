# AGENTS.md

This repo is the durable handoff context for maintaining `lightning-bolt-api`.

## Mission

Maintain a reusable Python library, CLI, and MCP server for read-only access to Lightning
Bolt's reverse-engineered API. The library should return useful normalized data while
preserving raw Lightning Bolt JSON. It should not own downstream business logic.

## Current State

The v1 implementation is built and pushed.

Implemented:

- Direct HTTP authentication with `httpx.AsyncClient`.
- Session cache persistence for auth/session state.
- Refresh-token rotation with serialized refresh.
- Dashboard, ViewerAPI, personal schedule range, subscription, and employee feed reads.
- Self-bootstrapping view discovery when `LB_DEFAULT_VIEW_ID` is not set.
- Pydantic models with preserved `raw` payloads.
- `lb-api` CLI.
- `lb-api-mcp` server over stdio and streamable HTTP.
- Docker image for HTTP MCP mode.
- Mocked tests for auth, parsing, CLI, MCP registration, and discovery behavior.

Start with:

- `README.md` for user-facing setup and examples.
- `docs/lightning-bolt-api.md` for reverse-engineered API behavior and reimplementation
  guidance.
- `docs/architecture.md` for how the implemented system works.
- `docs/mcp.md` for MCP operation and tool reference.
- `docs/investigation-findings.md` for historical reverse-engineering evidence.
- `fixtures/sanitized_viewerapi_view50.json` for public parser fixture data.

## Critical Context

This repo was split out from `LBOpenShiftFinder`, which is a personal open-shift/calendar
sync app. Do not reintroduce calendar sync, iCal parsing, Google Calendar, provider
classification, notification logic, or organization-specific scheduling policy here.

The most important investigation result is that normal operation does not need Playwright
or DOM scraping. Lightning Bolt's SPA is a thin layer over JSON endpoints. Direct HTTP
auth and API calls work.

Chrome DevTools MCP or Playwright MCP may be useful for revalidating Lightning Bolt
behavior if the site changes, but browser automation must not become the normal runtime
path unless the project direction explicitly changes.

## Architecture Decisions

- Python 3.12+.
- `uv` project.
- Package import name: `lightning_bolt_api`.
- CLI command: `lb-api`.
- MCP command: `lb-api-mcp`.
- Async internals.
- Direct HTTP auth first.
- Read-only v1.
- Session cache is allowed; schedule/export persistence is not automatic.
- Raw payload preservation is required.
- Host and Docker MCP support.
- MCP supports stdio and streamable HTTP.
- Credentials/session come from environment variables or mounted secrets, not MCP tool
  arguments.

## API Findings To Preserve

Auth:

- Login starts at `s2.lightning-bolt.com`.
- Dashboard call to `lblite.lightning-bolt.com/api/v1/dashboard` rotates `LB_TKN`.
- `POST https://lbapi.lightning-bolt.com/token` exchanges the refresh token for a 1-hour JWT.
- Refresh tokens rotate and are single-use.
- Always send `Origin: https://lblite.lightning-bolt.com`.
- Request gzip/deflate and defensively parse JSON-encoded string fields in dashboard
  responses.

Primary data:

- `POST https://lbapi.lightning-bolt.com/viewerapi`.
- Body should only include confirmed fields:
  - `view_id`
  - `tz`
  - `start_date`
  - `end_date`
- `view_id` can be omitted for Lightning Bolt's default viewer context.
- Dates must be `YYYYMMDD`. Reject ISO strings for request params.
- The response includes schedule slots, personnel, assignments, departments/templates,
  holidays, settings, permissions, and view context.

Other read endpoints:

- `/schedule/range/?start_date=YYYYMMDD&end_date=YYYYMMDD&listed=true&emp_id=N`
- `/subscription?emp_id=N&dash=true`
- `https://fd.lightning-bolt.com/employee_feed/{customer_id}/{emp_id}?last=<unix_ts>`

## Non-Goals

- No provider MD/APP classification.
- No provider ground-truth files.
- No DOM scraping as primary implementation.
- No Google Calendar sync.
- No iCal schedule parsing for business logic.
- No shift claiming, swaps, request creation, or other write actions.
- No automatic generated export storage.
- No hardcoded organization-specific template IDs or provider assumptions.

## Maintenance Workflow

Run checks before committing:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest
UV_CACHE_DIR=/tmp/uv-cache uv run ruff check .
```

For live validation, use a small date range first:

```bash
uv run lb-api login
uv run lb-api discover
uv run lb-api schedule --start 20260501 --end 20260507
```

Live validation can update the ignored session cache. It must not create tracked raw
captures, secrets, or unsanitized data.

## Security Rules

- Never commit `.env`, session cache files, raw captures, cookies, JWTs, refresh tokens, or
  unsanitized personnel data.
- Do not log auth response bodies.
- Do not include credentials as MCP tool arguments by default.
- Keep sanitized fixtures small and clearly marked.
- Public fixtures must use synthetic names and synthetic internal IDs.
- Public docs must avoid private patient/provider data and secrets.
