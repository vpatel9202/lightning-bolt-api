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
- Derived calendar subscription URLs from subscription metadata.
- Employee ID discovery with fuzzy matching against ViewerAPI personnel.
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

Subscription URL derivation:

- Lightning Bolt returns subscription metadata, not the app-specific URLs directly.
- Derive URLs from `md5` on `m.lightning-bolt.com`.
- `g.ics` is used for Google Calendar and Android.
- `i.ics` is used for iPhone/iPad, IBM Lotus Notes, and Calendar for Mac/iCal.
- `o.ics` is used for Outlook with the `webcal://` scheme.

Employee-scoped reads:

- Prefer `LB_EMP_ID` for stable automation.
- `LB_EMPLOYEE_NAME` is a fuzzy-match fallback for discovery and convenience.
- `find_employee` uses `LB_DEFAULT_VIEW_ID` when set; without a broader view, the default
  "Me" context may only expose the authenticated user.
- Do not rely on display names as durable identifiers.

## Non-Goals

- No provider MD/APP classification.
- No provider ground-truth files.
- No DOM scraping as primary implementation.
- No Google Calendar sync.
- No iCal schedule parsing for business logic.
- No calendar subscription feed parsing for business logic.
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

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:ca08a54f -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd dolt push
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
<!-- END BEADS INTEGRATION -->
