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

Then fetch personal schedule data with a compact tool:

```text
lb_get_my_shifts(start_date="20260501", end_date="20260507")
```

All date arguments must be `YYYYMMDD`.

For employee-scoped tools, set `LB_EMP_ID` when possible. If the employee ID is unknown,
call:

```text
lb_find_employee(query="name")
```

Then put the selected `emp_id` in `LB_EMP_ID` for repeatable automation.

## Token-Safe Tool Selection

MCP clients should prefer intent-level tools that return compact summaries:

- Use `lb_get_my_shifts` for "when am I working?"
- Use `lb_get_my_shift_dates` when dates alone answer the question.
- Use `lb_get_employee_shifts` for one named employee's shifts.
- Use `lb_get_employee_shift_dates` when dates alone answer the question.
- Use `lb_get_my_shift_trades` or `lb_get_employee_shift_trades` for traded shifts.
- Use `lb_count_employee_shifts` for "how many shifts?"
- Use `lb_find_overlapping_shifts` for overlap questions.
- Use `lb_who_is_working` for date coverage questions.
- Use `lb_list_open_shifts` for available open shifts.
- Use `lb_list_open_shift_groups` when the user asks for MD vs APP open shifts.
- Use `lb_get_open_shift_dates` when dates alone answer the question.
- Use `lb_who_is_working_with` for "who works with me/them?"
- Use `lb_get_next_*` tools for "next few" questions instead of broad ranges.

Avoid `lb_get_viewerapi` and `lb_fetch_schedule_range` unless the user asks for raw data,
debugging, or an advanced broad schedule export. ViewerAPI has no confirmed server-side
field projection or result limit, so broad date ranges can produce large payloads.

Use the smallest date range that answers the user. Prefer `detail_level="count"` or
`detail_level="dates"` when the user asks for counts or dates. Ask for compact rows only
when shift details are needed.

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

Low-level debug/export tool. Calls ViewerAPI and returns normalized viewer state:

- view context
- views
- slots
- personnel
- assignments
- departments
- templates
- holidays

`view_id` may be omitted. In that case the client uses automatic broad-view discovery when
the default context appears personal-only. This tool can return large payloads; prefer the
compact schedule tools for normal MCP use.

### `lb_fetch_schedule_range(start_date, end_date, view_id?, template_ids?, template_query?, assignment_query?, max_results=200, offset=0, tz?, include_raw=false)`

Low-level broad schedule tool. Returns schedule slots for a date range. `view_id` is
optional. If omitted, the client uses automatic broad-view discovery. This can return many
slots; prefer the compact tools below for model-facing answers. Results are capped by
default and include pagination metadata. Set `max_results=0` only for intentional full
exports.

### `lb_get_my_shifts(start_date, end_date, detail_level="dates", include_details=false, max_results=200, fields?)`

Returns the configured/authenticated employee's schedule via the employee-specific
schedule endpoint. `detail_level` may be `count`, `dates`, or `compact`.

### `lb_get_my_shift_dates(start_date, end_date)`

Date-only shortcut for the configured/authenticated employee.

### `lb_get_employee_shifts(employee, start_date, end_date, detail_level="dates", include_details=false, max_results=200, fields?)`

Resolves `employee` as an employee ID or fuzzy name, then returns that employee's compact
schedule. Use this instead of broad schedule tools for one-person questions.

### `lb_get_employee_shift_dates(employee, start_date, end_date)`

Date-only shortcut for one employee.

### `lb_get_my_shift_trades(start_date, end_date, view_id?, template_ids?, template_query?, assignment_query?, max_results=200, tz?)`

Returns traded shifts for the configured/authenticated employee, including trade-ins and
trade-outs. This uses ViewerAPI internally because employee-specific schedule reads do not
include shifts traded away to another employee.

### `lb_get_employee_shift_trades(employee, start_date, end_date, view_id?, template_ids?, template_query?, assignment_query?, max_results=200, tz?)`

Returns traded shifts for one employee. Rows include current assignee, original employee,
assignment origin, modification metadata, notes, request flags, and compact slot history
when Lightning Bolt exposes it.

### `lb_count_employee_shifts(employee, start_date, end_date, group_by="none")`

Returns only shift counts. `group_by` may be `none`, `date`, `template`, `assignment`, or
`person`.

### `lb_find_overlapping_shifts(employee_b, start_date, end_date, employee_a?, detail_level="dates", max_results=200, fields?)`

Finds overlapping shifts between two employees. `employee_a` defaults to the configured or
authenticated employee. Uses employee-specific schedule reads and returns only overlap
rows and overlap dates.

### `lb_who_is_working(start_date, end_date, view_id?, template_ids?, template_query?, assignment_query?, include_open=false, detail_level="count", include_workers=false, max_results=200, fields?, tz?)`

Summarizes coverage by date. By default it returns only per-date counts. Use
`detail_level="summary"` for template counts and `detail_level="assignments"` for
assignment counts. Set `include_workers=true` only when names or rows are needed.

### `lb_list_open_shifts(start_date, end_date, view_id?, template_ids?, template_query?, assignment_query?, detail_level="dates", max_results=200, fields?, tz?)`

Returns compact open-shift rows and count metadata.

### `lb_list_open_shift_groups(start_date, end_date, view_id?, template_ids?, template_query?, assignment_query?, max_results=200, fields?, md_patterns?, app_patterns?, tz?)`

Returns open shifts grouped into `md`, `app`, and `unknown`. Classification uses generic
template/assignment-name patterns by default. Use `md_patterns` / `app_patterns`, or the
matching environment variables, when an organization labels provider groups differently.

### `lb_get_open_shift_dates(start_date, end_date, view_id?, template_ids?, template_query?, assignment_query?, max_results=200, tz?)`

Date-only shortcut for open shifts.

### `lb_who_is_working_with(employee, start_date, end_date, view_id?, template_query?, assignment_query?, detail_level="count", include_workers=false, max_results=200, fields?, tz?)`

Finds the employee's shift dates with the employee-specific endpoint, then summarizes
workers on those same dates. Default output is count-only per date.

### `lb_get_next_my_shifts(count=5, search_days=90)`

Returns the next shifts for the configured/authenticated employee.

### `lb_get_next_employee_shifts(employee, count=5, search_days=90)`

Returns the next shifts for one employee.

### `lb_get_next_open_shifts(count=10, search_days=90, view_id?, template_ids?, template_query?, assignment_query?, tz?)`

Returns the next open shifts without requiring the caller to choose a broad date range.

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
