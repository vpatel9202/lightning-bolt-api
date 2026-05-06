# MCP Server

`lb-api-mcp` exposes read-only Lightning Bolt tools for MCP clients. It uses the same
`LightningBoltClient` implementation as the Python API and CLI.

## Configuration

Configure the server with environment variables or mounted secrets:

| Variable | Required | Description |
| --- | --- | --- |
| `LB_USERNAME` | Yes for login | Lightning Bolt username. |
| `LB_PASSWORD` | Yes for login | Lightning Bolt password. |
| `LB_SESSION_CACHE` | Recommended | Session cache file or directory. |
| `LB_EMP_ID` | No | Preferred default employee ID for employee-scoped reads. |
| `LB_EMPLOYEE_NAME` | No | Fuzzy-match fallback when the employee ID is unknown. |
| `LB_DEFAULT_VIEW_ID` | No | Optional view override. Discovery works without it. |
| `LB_VIEW_PROBE_MAX` | No | Numeric fallback probe cap. Defaults to `100`. |
| `LB_DEFAULT_TZ` | No | IANA timezone. Defaults to `UTC` if unset. |

Credentials are intentionally not accepted as normal MCP tool arguments. Tool arguments
describe data requests only.

## First Run

Start by calling:

```text
lb_discover_context
```

This confirms authentication and returns the usable default context. If dashboard metadata
does not list usable views and the default ViewerAPI response appears personal-only, the
server probes bounded read-only candidate views and caches the broadest accessible result.
A first-time user does not need to know a view ID before fetching schedule data.

Then fetch schedule data with:

```text
lb_fetch_schedule_range(start_date="20260501", end_date="20260507")
```

All date arguments must be `YYYYMMDD`.

For employee-scoped tools, set `LB_EMP_ID` when possible. If the employee ID is unknown,
call:

```text
lb_find_employee(query="name")
```

Then put the selected `emp_id` in `LB_EMP_ID` for repeatable automation.

## Host Stdio

Use stdio for local MCP clients that launch the server process directly:

```bash
uv run lb-api-mcp stdio
```

The process reads `.env` from the current working directory.

## Host Streamable HTTP

Use streamable HTTP when running the server as a local service:

```bash
uv run lb-api-mcp http --host 127.0.0.1 --port 8000
```

The streamable HTTP endpoint is:

```text
http://127.0.0.1:8000/mcp
```

## Docker

Build and run the HTTP MCP server:

```bash
docker build -t lightning-bolt-api .
docker run --rm \
  -p 8000:8000 \
  --env-file .env \
  -v "$PWD/session-cache:/app/session-cache" \
  lightning-bolt-api
```

The default container command starts:

```text
lb-api-mcp http --host 0.0.0.0 --port 8000
```

Mount the session cache so token refresh state can persist across container restarts.

## Tool Reference

### `lb_discover_context(include_raw=false)`

Returns current discovery metadata:

- authenticated user IDs when known
- dashboard view count
- inferred default view
- available views
- whether callers can omit `view_id`
- default timezone
- discovery source
- personnel and slot counts
- warnings when only a personal context is visible

Use this as the first tool when the user does not know a Lightning Bolt view ID.

### `lb_diagnose_context(include_raw=false)`

Reports the active schedule/personnel context without exposing secrets. It includes env
flag presence, selected view ID, discovery source, personnel count, slot count, and
warnings. Use this when employee lookup unexpectedly returns no matches.

### `lb_list_views(include_raw=false)`

Lists available views from the discovered context. If Lightning Bolt only returns
synthetic `view_id=0` views for the personal context, automatic discovery may still select
a broader usable view for schedule and employee reads.

### `lb_get_dashboard(include_raw=false)`

Returns normalized dashboard metadata and optionally the preserved dashboard payload.

### `lb_list_templates(view_id, include_raw=false)`

Lists templates for a known view ID.

### `lb_get_viewerapi(view_id?, start_date?, end_date?, tz?, include_raw=false)`

Calls ViewerAPI and returns normalized viewer state:

- view context
- views
- slots
- personnel
- assignments
- departments
- templates
- holidays

`view_id` may be omitted. In that case the client uses automatic broad-view discovery when
the default context appears personal-only.

### `lb_fetch_schedule_range(start_date, end_date, view_id?, template_ids?, tz?, include_raw=false)`

Returns schedule slots for a date range. `view_id` is optional. If omitted, the client uses
automatic broad-view discovery. `LB_DEFAULT_VIEW_ID` is only an override.

### `lb_get_subscription(emp_id?, include_raw=false)`

Returns subscription metadata and derived app-specific calendar URLs. If `emp_id` is
omitted, the server resolves it from `LB_EMP_ID`, `LB_EMPLOYEE_NAME`, or the authenticated
session.

Compact responses include `calendar_urls` and `default_calendar_url`; pass
`include_raw=true` only when the original Lightning Bolt subscription payload is needed.

### `lb_find_employee(query, view_id?, limit=10, include_raw=false)`

Returns ranked personnel matches so users can discover the stable employee ID to put in
`LB_EMP_ID`.

Each match includes `emp_id`, score, visible names, and matched fields. The tool uses
automatic broad-view discovery when `view_id` is omitted, and filters out weak matches
below the default minimum score of `0.7`.

### `lb_get_employee_feed(customer_id?, emp_id?, since?, include_raw=false)`

Returns employee feed items. If `emp_id` is omitted, the server uses the same employee
resolution behavior as `lb_get_subscription`.

## Raw Payloads

Tool responses are compact normalized JSON by default. Pass `include_raw=true` when a
client needs the preserved Lightning Bolt payload.

Raw payloads may contain sensitive data in real accounts. Do not write them to tracked
files unless they have been sanitized.

## Troubleshooting

- If auth fails, run `uv run lb-api login` with the same environment to validate
  credentials and session-cache behavior.
- If `lb_list_views` returns only a default view, call `lb_discover_context` to inspect the
  discovery source.
- If schedule results are empty, verify the date range is published in Lightning Bolt and
  that dates are `YYYYMMDD`.
- If HTTP MCP does not respond, confirm the client is using `/mcp`, not `/`.
