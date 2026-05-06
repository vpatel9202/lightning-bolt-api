# MCP Server

`lb-api-mcp` exposes the same read-only Lightning Bolt operations as the Python client and
CLI.

## Configuration

Use environment variables or mounted secrets:

- `LB_USERNAME`
- `LB_PASSWORD`
- `LB_SESSION_CACHE`
- `LB_DEFAULT_VIEW_ID`
- `LB_DEFAULT_TZ`

Credentials are intentionally not normal MCP tool arguments. Tool inputs describe data
requests only.

## Host Commands

```bash
uv run lb-api-mcp stdio
uv run lb-api-mcp http --host 127.0.0.1 --port 8000
```

Streamable HTTP is mounted at `/mcp`.

## Docker

```bash
docker build -t lightning-bolt-api .
docker run --rm \
  -p 8000:8000 \
  --env-file .env \
  -v "$PWD/session-cache:/app/session-cache" \
  lightning-bolt-api
```

## Tools

- `lb_get_dashboard(include_raw=false)`
- `lb_discover_context(include_raw=false)`
- `lb_list_views(include_raw=false)`
- `lb_list_templates(view_id, include_raw=false)`
- `lb_get_viewerapi(view_id?, start_date?, end_date?, tz?, include_raw=false)`
- `lb_fetch_schedule_range(start_date, end_date, view_id?, template_ids?, tz?, include_raw=false)`
- `lb_get_subscription(emp_id, include_raw=false)`
- `lb_get_employee_feed(customer_id?, emp_id?, since?, include_raw=false)`

All dates must be `YYYYMMDD`.

`LB_DEFAULT_VIEW_ID` is optional. If dashboard metadata has no views, `lb_list_views` and
`lb_discover_context` use ViewerAPI's default context so a first-time user does not need to
know a Lightning Bolt view ID before fetching schedule data.
