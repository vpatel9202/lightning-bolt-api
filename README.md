# lightning-bolt-api

Read-only Python client, CLI, and MCP server for Lightning Bolt's reverse-engineered API.

This repository is intentionally focused on API access and data return only. It does not
handle Google Calendar sync, iCal conflict logic, provider MD/APP classification, shift
claiming, swaps, or downstream storage decisions.

## Current Status

Initial scaffold. The investigation is complete enough to implement direct HTTP auth and
the main read endpoints, but the client methods are not implemented yet.

## What This Library Should Provide

- Direct non-browser authentication against Lightning Bolt's private API flow.
- Token refresh handling for 1-hour JWTs and rotated single-use refresh tokens.
- Viewer discovery and template discovery.
- Schedule data through `POST https://lbapi.lightning-bolt.com/viewerapi`.
- Light personal schedule reads through `/schedule/range/`.
- Subscription metadata reads through `/subscription`.
- Activity feed reads through `fd.lightning-bolt.com/employee_feed/...`.
- Typed normalized Python models while preserving raw LB payloads.
- CLI commands for debugging and JSON output.
- MCP server support over stdio and streamable HTTP, runnable on host or Docker.

## Quick Start For Development

```bash
uv sync
uv run pytest
uv run ruff check .
uv run lb-api version
```

Create `.env` from `.env.example` for local authenticated development. Never commit real
credentials, cookies, refresh tokens, JWTs, raw captures with PII, or session cache files.

## Durable Context

Start with these files before implementing:

- `AGENTS.md` - full implementation context and plan for future agents.
- `docs/investigation-findings.md` - Lightning Bolt auth/API findings from live investigation.
- `docs/implementation-plan.md` - current build plan.
- `fixtures/sanitized_viewerapi_view50.json` - anonymized public sample fixture from the investigation.

## Non-Goals

- No DOM scraping in the normal path.
- No provider classification or verified provider lists.
- No Google Calendar/iCal app behavior.
- No write actions such as shift claims, swaps, or request mutations.
- No automatic persistence of scrape/export data.

## License

No license has been selected yet.
