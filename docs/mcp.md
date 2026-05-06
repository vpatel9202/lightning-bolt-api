# MCP Server Notes

The MCP server should expose read-only Lightning Bolt operations over both host-local
stdio and streamable HTTP.

Planned host commands:

```bash
uv run lb-api-mcp stdio
uv run lb-api-mcp http --host 127.0.0.1 --port 8000
```

Planned Docker command:

```bash
docker build -t lightning-bolt-api .
docker run --rm -p 8000:8000 --env-file .env lightning-bolt-api
```

Required configuration should come from environment variables or mounted secrets:

- `LB_USERNAME`
- `LB_PASSWORD`
- `LB_SESSION_CACHE`
- `LB_DEFAULT_VIEW_ID`
- `LB_DEFAULT_TZ`

Do not pass credentials as normal MCP tool parameters by default. Tool inputs should
describe data requests, not secrets.

Planned tools:

- `lb_get_dashboard`
- `lb_list_views`
- `lb_list_templates`
- `lb_get_viewerapi`
- `lb_fetch_schedule_range`
- `lb_get_subscription`
- `lb_get_employee_feed`
