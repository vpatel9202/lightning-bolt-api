# Implementation Plan

## Status

The v1 implementation now exists in the repo. This document remains as the original
implementation map and acceptance criteria. Use `README.md` and `docs/mcp.md` for current
operator-facing commands.

## Summary

Build a reusable Python library, CLI, and MCP server for read-only Lightning Bolt API
access. The package should expose authenticated access to Lightning Bolt's
reverse-engineered JSON endpoints, normalize returned data, preserve raw payloads, and
avoid downstream business logic like provider classification, Google Calendar sync, iCal
parsing, notifications, and storage policy.

The key investigation result is that v1 should use direct HTTP auth and `POST /viewerapi`
as the primary path. Playwright is not required for normal operation.

## Core Architecture

- Package name: `lightning_bolt_api`.
- Dependency management: `uv` with `pyproject.toml` and `uv.lock`.
- HTTP client: async-first, likely `httpx.AsyncClient`, with sync convenience wrappers.
- Auth:
  - Implement direct login through `s2.lightning-bolt.com`.
  - Follow the cookie/token redirect chain.
  - Call `lblite.lightning-bolt.com/api/v1/dashboard`.
  - Exchange the rotated `LB_TKN` refresh token at `lbapi.lightning-bolt.com/token`.
  - Store cookies, refresh token, JWT, expiry, `customer_id`, `emp_id`, and `user_id`.
  - Refresh proactively at `exp - 300s`.
  - Serialize refresh because refresh tokens rotate and are single-use.
  - On refresh failure, perform full login if credentials are available.
- Session cache:
  - Cache only auth/session state, not scrape results.
  - Default to user cache dir with env/config override.
  - Never log tokens, cookies, usernames, or raw auth responses.

## Public API

Expose read-only methods:

- `login(username, password) -> LightningBoltClient`
- `from_session(session) -> LightningBoltClient`
- `get_dashboard() -> Dashboard`
- `get_viewerapi(view_id=None, start_date=None, end_date=None, tz="UTC") -> ViewerApiResponse`
- `list_views() -> list[View]`
- `list_templates(view_id) -> list[Template]`
- `fetch_schedule(view_id, start_date, end_date, template_ids=None) -> list[Slot]`
- `fetch_personal_schedule(emp_id, start_date, end_date) -> list[Slot]`
- `get_subscription(emp_id) -> Subscription`
- `get_employee_feed(customer_id, emp_id, since=None) -> ActivityFeed`

Date handling:

- Accept Python `date` objects and `YYYYMMDD` strings.
- Reject ISO strings like `2026-06-01` for LB request params.
- Format all LB date params as `YYYYMMDD`.
- Respect template `last_published_date` where available.

## Models

Use typed models for known fields and retain `raw: dict` for source payloads.

Primary models:

- `SessionState`
- `Dashboard`
- `ViewerApiResponse`
- `View`
- `Department`
- `Template`
- `Personnel`
- `Assignment`
- `Slot`
- `Subscription`
- `ActivityFeedItem`

`Slot` should include normalized IDs, provider/person fields, template/department IDs,
assignment fields, local and UTC times, pending/manual state, notes, location fields,
`emp_ptype`, `assign_atype`, and `raw`.

Convenience properties:

- `slot.is_open_shift`
- `slot.is_assigned_to(emp_id)`
- `slot.has_any_note`

Do not infer MD/APP provider type. Return source fields and let consumers classify.

## CLI

Provide `lb-api` commands:

- `login`
- `dashboard`
- `views`
- `templates --view-id 123`
- `viewerapi --view-id 123 --start 20260501 --end 20260531`
- `schedule --emp-id 10001 --start ... --end ...`
- `feed --emp-id ... --since ...`
- `subscription --emp-id ...`

Output JSON to stdout by default. Support explicit `--output path.json`. Do not write
scrape/export files automatically.

## MCP Server

Provide one MCP server runnable on host or Docker.

Transports:

- stdio for host-local MCP clients.
- streamable HTTP for host service mode and Docker.

Tools:

- `lb_get_dashboard`
- `lb_list_views`
- `lb_list_templates`
- `lb_get_viewerapi`
- `lb_fetch_schedule_range`
- `lb_get_subscription`
- `lb_get_employee_feed`

Config:

- Credentials/session via env vars or mounted secret:
  - `LB_USERNAME`
  - `LB_PASSWORD`
  - `LB_SESSION_CACHE`
  - `LB_DEFAULT_VIEW_ID`
  - `LB_DEFAULT_TZ`
- Do not accept credentials as normal MCP tool arguments unless explicitly enabled for debugging.
- Return compact normalized JSON by default, with optional `include_raw=true`.

## Tests

- Auth tests with mocked HTTP responses for login/token refresh.
- Token rotation tests verifying old refresh tokens are replaced and refresh is serialized.
- Dashboard parser tests for nested JSON and JSON-encoded string fields.
- Date validation tests.
- ViewerAPI parser tests using sanitized fixtures.
- Slot convenience tests.
- CLI tests with mocked client.
- MCP tool registration and mocked tool calls.
- Docker smoke test for HTTP MCP health/tool discovery.

## Explicit Non-Goals

- No Playwright-based DOM scraping in normal operation.
- No Google Calendar sync.
- No iCal parsing for schedule logic.
- No provider MD/APP classification.
- No shift-claiming, swap, request, or write actions.
- No automatic scrape data storage.
- No hardcoded organization-specific template IDs or provider lists.
