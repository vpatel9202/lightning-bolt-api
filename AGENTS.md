# AGENTS.md

This repo is the durable handoff context for building `lightning-bolt-api`.

## Mission

Build a reusable Python library, CLI, and MCP server for read-only access to Lightning
Bolt's reverse-engineered API. The library should return useful normalized data while
preserving raw Lightning Bolt JSON. It should not own downstream business logic.

## Critical Context

This repo was split out from `LBOpenShiftFinder`, which is a personal open-shift/calendar
sync app. Do not reintroduce calendar sync, iCal parsing, Google Calendar, provider
classification, or notification logic here.

Claude/Opus performed a live investigation using Chrome DevTools MCP and direct replay.
The most important result: normal operation does not need Playwright or DOM scraping.
Lightning Bolt's SPA is a thin layer over JSON endpoints. Direct HTTP auth and API calls
work.

Read before implementing:

- `docs/investigation-findings.md`
- `docs/implementation-plan.md`
- `fixtures/sanitized_viewerapi_view50.json`

## Architecture Decisions Already Made

- Python 3.12+.
- `uv` project.
- Package import name: `lightning_bolt_api`.
- CLI command: `lb-api`.
- MCP command: `lb-api-mcp`.
- Async internals with sync wrappers later.
- Direct HTTP auth first; no Playwright in the normal path.
- Session cache is allowed; scrape/export data persistence is not automatic.
- Raw payload preservation is required.
- Read-only v1.
- Host and Docker MCP support.
- MCP should support stdio and streamable HTTP.

## API Findings To Preserve

Auth:

- Login starts at `s2.lightning-bolt.com`.
- Dashboard call to `lblite.lightning-bolt.com/api/v1/dashboard` rotates `LB_TKN`.
- `POST https://lbapi.lightning-bolt.com/token` exchanges the refresh token for a 1-hour JWT.
- Refresh tokens rotate and are single-use.
- Always send `Origin: https://lblite.lightning-bolt.com`.
- Request gzip and defensively parse JSON-encoded string fields in dashboard responses.

Primary data:

- `POST https://lbapi.lightning-bolt.com/viewerapi`.
- Body should only include confirmed fields:
  - `view_id`
  - `tz`
  - `start_date`
  - `end_date`
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

## Implementation Plan

1. Build HTTP/auth layer.
   - Use `httpx.AsyncClient`.
   - Implement the 5-hop login and `/token` exchange.
   - Parse JWT expiry without verifying the signature.
   - Serialize token refresh with an async lock.
   - Add user-cache-dir session persistence with strict file permissions where possible.

2. Build parsing/model layer.
   - Add model constructors from raw dashboard/viewerapi objects.
   - Preserve `raw` on all normalized models.
   - Add date validation utilities.
   - Add defensive dashboard string-field JSON decoding.

3. Build endpoint client.
   - Dashboard.
   - ViewerAPI.
   - Views/templates derived from dashboard/viewerapi.
   - Personal schedule range.
   - Subscription metadata.
   - Employee feed.

4. Build CLI.
   - JSON stdout by default.
   - Optional `--output`.
   - Never write scrape output unless explicitly requested.
   - Never print secrets.

5. Build MCP server.
   - Same core client as CLI.
   - stdio and streamable HTTP.
   - Credentials/session via env vars or mounted secrets, not normal tool arguments.
   - Tool responses compact normalized JSON by default; optional `include_raw`.

6. Build Docker support.
   - Multi-stage Dockerfile with `uv`.
   - Default command should run HTTP MCP.
   - Document host and Docker launch examples.

7. Tests.
   - Mocked auth chain.
   - Refresh rotation and locking behavior.
   - Dashboard JSON-string quirk.
   - Date validation.
   - ViewerAPI fixture parsing.
   - Slot helper properties.
   - CLI mocked outputs.
   - MCP tool registration.
   - Docker smoke test if feasible.

## Security Rules

- Never commit `.env`, session cache files, raw captures, cookies, JWTs, refresh tokens, or
  unsanitized personnel data.
- Do not log auth response bodies.
- Do not include credentials as MCP tool arguments by default.
- Keep sanitized fixtures small and clearly marked. Public fixtures must use synthetic names
  and synthetic internal IDs.
- Public repo means all durable docs must avoid private patient/provider data and secrets.

## Current Scaffold Status

The repo currently contains placeholder client/CLI/MCP modules and initial models. Most
methods intentionally raise `NotImplementedError`. The first real implementation task is
the direct HTTP auth/session layer.
