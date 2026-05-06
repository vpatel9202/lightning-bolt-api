"""MCP server entry point for read-only Lightning Bolt API access."""

from __future__ import annotations

import argparse
import os
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from lightning_bolt_api.client import LightningBoltClient, model_to_jsonable


def build_server(*, host: str = "127.0.0.1", port: int = 8000) -> FastMCP:
    mcp = FastMCP(
        "lightning-bolt-api",
        instructions=(
            "Read-only Lightning Bolt API access. Credentials come from environment. "
            "Prefer compact tools such as lb_get_my_shifts, lb_get_employee_shifts, "
            "lb_count_employee_shifts, lb_find_overlapping_shifts, lb_who_is_working, "
            "and lb_list_open_shifts. Avoid broad raw ViewerAPI tools unless the user "
            "asks for debugging/raw data because they can return very large payloads."
        ),
        host=host,
        port=port,
        streamable_http_path="/mcp",
    )

    @mcp.tool()
    async def lb_get_dashboard(include_raw: bool = False) -> dict[str, Any]:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(await client.get_dashboard(), include_raw=include_raw)

    @mcp.tool()
    async def lb_list_views(include_raw: bool = False) -> list[dict[str, Any]]:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(await client.list_views(), include_raw=include_raw)

    @mcp.tool()
    async def lb_discover_context(include_raw: bool = False) -> dict[str, Any]:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(await client.discover_context(), include_raw=include_raw)

    @mcp.tool()
    async def lb_diagnose_context(include_raw: bool = False) -> dict[str, Any]:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(await client.diagnose_context(), include_raw=include_raw)

    @mcp.tool()
    async def lb_list_templates(view_id: int, include_raw: bool = False) -> list[dict[str, Any]]:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(await client.list_templates(view_id), include_raw=include_raw)

    @mcp.tool()
    async def lb_get_viewerapi(
        view_id: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        tz: str | None = None,
        include_raw: bool = False,
    ) -> dict[str, Any]:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(
                await client.get_viewerapi(
                    view_id=view_id,
                    start_date=start_date,
                    end_date=end_date,
                    tz=tz or os.getenv("LB_DEFAULT_TZ", "UTC"),
                ),
                include_raw=include_raw,
            )

    @mcp.tool()
    async def lb_fetch_schedule_range(
        start_date: str,
        end_date: str,
        view_id: int | None = None,
        template_ids: list[int] | None = None,
        tz: str | None = None,
        include_raw: bool = False,
    ) -> list[dict[str, Any]]:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(
                await client.fetch_schedule(
                    view_id=view_id,
                    start_date=start_date,
                    end_date=end_date,
                    template_ids=template_ids,
                    tz=tz or os.getenv("LB_DEFAULT_TZ", "UTC"),
                ),
                include_raw=include_raw,
            )

    @mcp.tool()
    async def lb_get_my_shifts(
        start_date: str,
        end_date: str,
        include_details: bool = True,
        max_results: int = 200,
    ) -> dict[str, Any]:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(
                await client.get_my_shifts(
                    start_date=start_date,
                    end_date=end_date,
                    include_details=include_details,
                    max_results=max_results,
                ),
                include_raw=False,
            )

    @mcp.tool()
    async def lb_get_employee_shifts(
        employee: str,
        start_date: str,
        end_date: str,
        include_details: bool = True,
        max_results: int = 200,
    ) -> dict[str, Any]:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(
                await client.get_employee_shifts(
                    employee,
                    start_date=start_date,
                    end_date=end_date,
                    include_details=include_details,
                    max_results=max_results,
                ),
                include_raw=False,
            )

    @mcp.tool()
    async def lb_count_employee_shifts(
        employee: str,
        start_date: str,
        end_date: str,
        group_by: str = "none",
    ) -> dict[str, Any]:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(
                await client.count_employee_shifts(
                    employee,
                    start_date=start_date,
                    end_date=end_date,
                    group_by=group_by,
                ),
                include_raw=False,
            )

    @mcp.tool()
    async def lb_find_overlapping_shifts(
        employee_b: str,
        start_date: str,
        end_date: str,
        employee_a: str | None = None,
        max_results: int = 200,
    ) -> dict[str, Any]:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(
                await client.find_overlapping_shifts(
                    employee_a,
                    employee_b,
                    start_date=start_date,
                    end_date=end_date,
                    max_results=max_results,
                ),
                include_raw=False,
            )

    @mcp.tool()
    async def lb_who_is_working(
        start_date: str,
        end_date: str,
        view_id: int | None = None,
        template_ids: list[int] | None = None,
        include_open: bool = False,
        max_results: int = 200,
        tz: str | None = None,
    ) -> dict[str, Any]:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(
                await client.who_is_working(
                    start_date=start_date,
                    end_date=end_date,
                    view_id=view_id,
                    template_ids=template_ids,
                    include_open=include_open,
                    max_results=max_results,
                    tz=tz or os.getenv("LB_DEFAULT_TZ", "UTC"),
                ),
                include_raw=False,
            )

    @mcp.tool()
    async def lb_list_open_shifts(
        start_date: str,
        end_date: str,
        view_id: int | None = None,
        template_ids: list[int] | None = None,
        max_results: int = 200,
        tz: str | None = None,
    ) -> dict[str, Any]:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(
                await client.list_open_shifts(
                    start_date=start_date,
                    end_date=end_date,
                    view_id=view_id,
                    template_ids=template_ids,
                    max_results=max_results,
                    tz=tz or os.getenv("LB_DEFAULT_TZ", "UTC"),
                ),
                include_raw=False,
            )

    @mcp.tool()
    async def lb_who_is_working_with(
        employee: str,
        start_date: str,
        end_date: str,
        view_id: int | None = None,
        max_results: int = 200,
        tz: str | None = None,
    ) -> dict[str, Any]:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(
                await client.who_is_working_with(
                    employee,
                    start_date=start_date,
                    end_date=end_date,
                    view_id=view_id,
                    max_results=max_results,
                    tz=tz or os.getenv("LB_DEFAULT_TZ", "UTC"),
                ),
                include_raw=False,
            )

    @mcp.tool()
    async def lb_get_subscription(
        emp_id: int | None = None,
        include_raw: bool = False,
    ) -> dict[str, Any]:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(
                await client.get_subscription(emp_id=emp_id),
                include_raw=include_raw,
            )

    @mcp.tool()
    async def lb_find_employee(
        query: str,
        view_id: int | None = None,
        limit: int = 10,
        min_score: float = 0.7,
        include_raw: bool = False,
    ) -> list[dict[str, Any]]:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(
                await client.find_employee(
                    query,
                    view_id=view_id,
                    limit=limit,
                    min_score=min_score,
                ),
                include_raw=include_raw,
            )

    @mcp.tool()
    async def lb_get_employee_feed(
        customer_id: int | None = None,
        emp_id: int | None = None,
        since: int | None = None,
        include_raw: bool = False,
    ) -> dict[str, Any]:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(
                await client.get_employee_feed(customer_id=customer_id, emp_id=emp_id, since=since),
                include_raw=include_raw,
            )

    return mcp


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="lb-api-mcp")
    subparsers = parser.add_subparsers(dest="transport")
    subparsers.add_parser("stdio")
    http_parser = subparsers.add_parser("http")
    http_parser.add_argument("--host", default="127.0.0.1")
    http_parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    transport = args.transport or "stdio"
    if transport == "stdio":
        build_server().run("stdio")
    elif transport == "http":
        build_server(host=args.host, port=args.port).run("streamable-http")
    else:
        parser.error(f"Unsupported transport: {transport}")


if __name__ == "__main__":
    main()
