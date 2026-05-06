"""Command line entry point for the Lightning Bolt API client."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Annotated, Any

import typer
from dotenv import load_dotenv

from lightning_bolt_api.client import (
    LightningBoltClient,
    default_session_cache_path,
    model_to_jsonable,
)

app = typer.Typer(help="Read-only Lightning Bolt API tools.", no_args_is_help=True)


@app.callback()
def main() -> None:
    """Use subcommands to authenticate, discover views, and fetch schedule data."""
    load_dotenv()


@app.command()
def version() -> None:
    """Print package version."""
    typer.echo("lightning-bolt-api 0.1.0")


@app.command()
def login() -> None:
    """Authenticate and cache session state without printing secrets."""

    async def run() -> dict[str, Any]:
        async with await LightningBoltClient.login(
            os.getenv("LB_USERNAME", ""),
            os.getenv("LB_PASSWORD", ""),
            session_cache=os.getenv("LB_SESSION_CACHE"),
            default_tz=os.getenv("LB_DEFAULT_TZ", "UTC"),
        ) as client:
            return {
                "authenticated": bool(client.session.access_token),
                "customer_id": client.session.customer_id,
                "emp_id": client.session.emp_id,
                "user_id": client.session.user_id,
                "expires_at": client.session.expires_at,
                "session_cache": str(default_session_cache_path()),
            }

    _emit(asyncio.run(run()), None)


@app.command()
def dashboard(
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write JSON to this file.")
    ] = None,
    include_raw: Annotated[
        bool, typer.Option(help="Include preserved raw Lightning Bolt JSON.")
    ] = False,
) -> None:
    """Fetch dashboard metadata."""

    async def run() -> Any:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(await client.get_dashboard(), include_raw=include_raw)

    _emit(asyncio.run(run()), output)


@app.command()
def views(
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write JSON to this file.")
    ] = None,
    include_raw: Annotated[
        bool, typer.Option(help="Include preserved raw Lightning Bolt JSON.")
    ] = False,
) -> None:
    """List available views."""

    async def run() -> Any:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(await client.list_views(), include_raw=include_raw)

    _emit(asyncio.run(run()), output)


@app.command()
def templates(
    view_id: Annotated[int, typer.Option("--view-id", help="Lightning Bolt view ID.")],
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write JSON to this file.")
    ] = None,
    include_raw: Annotated[
        bool, typer.Option(help="Include preserved raw Lightning Bolt JSON.")
    ] = False,
) -> None:
    """List templates for a view."""

    async def run() -> Any:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(await client.list_templates(view_id), include_raw=include_raw)

    _emit(asyncio.run(run()), output)


@app.command("viewerapi")
def viewerapi_command(
    view_id: Annotated[
        int | None, typer.Option("--view-id", help="Lightning Bolt view ID.")
    ] = None,
    start: Annotated[str | None, typer.Option("--start", help="Start date as YYYYMMDD.")] = None,
    end: Annotated[str | None, typer.Option("--end", help="End date as YYYYMMDD.")] = None,
    tz: Annotated[str | None, typer.Option("--tz", help="IANA timezone.")] = None,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write JSON to this file.")
    ] = None,
    include_raw: Annotated[
        bool, typer.Option(help="Include preserved raw Lightning Bolt JSON.")
    ] = False,
) -> None:
    """Fetch raw viewer state normalized into stable fields."""

    async def run() -> Any:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(
                await client.get_viewerapi(
                    view_id=view_id,
                    start_date=start,
                    end_date=end,
                    tz=tz,
                ),
                include_raw=include_raw,
            )

    _emit(asyncio.run(run()), output)


@app.command()
def discover(
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write JSON to this file.")
    ] = None,
    include_raw: Annotated[
        bool, typer.Option(help="Include preserved raw Lightning Bolt JSON.")
    ] = False,
) -> None:
    """Discover usable default Lightning Bolt context."""

    async def run() -> Any:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(await client.discover_context(), include_raw=include_raw)

    _emit(asyncio.run(run()), output)


@app.command()
def diagnose(
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write JSON to this file.")
    ] = None,
    include_raw: Annotated[
        bool, typer.Option(help="Include preserved raw Lightning Bolt JSON.")
    ] = False,
) -> None:
    """Report the active schedule/personnel context without exposing secrets."""

    async def run() -> Any:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(await client.diagnose_context(), include_raw=include_raw)

    _emit(asyncio.run(run()), output)


@app.command()
def schedule(
    start: Annotated[str, typer.Option("--start", help="Start date as YYYYMMDD.")],
    end: Annotated[str, typer.Option("--end", help="End date as YYYYMMDD.")],
    view_id: Annotated[
        int | None, typer.Option("--view-id", help="Lightning Bolt view ID.")
    ] = None,
    template_id: Annotated[
        list[int] | None, typer.Option("--template-id", help="Filter by template ID.")
    ] = None,
    template_query: Annotated[
        str | None, typer.Option("--template-query", help="Filter by template name/id.")
    ] = None,
    assignment_query: Annotated[
        str | None, typer.Option("--assignment-query", help="Filter by assignment name/id.")
    ] = None,
    max_results: Annotated[
        int | None,
        typer.Option("--max-results", help="Maximum compact slots to return. Use 0 for all."),
    ] = 200,
    offset: Annotated[int, typer.Option("--offset", help="Pagination offset.")] = 0,
    tz: Annotated[str | None, typer.Option("--tz", help="IANA timezone.")] = None,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write JSON to this file.")
    ] = None,
    include_raw: Annotated[
        bool, typer.Option(help="Include preserved raw Lightning Bolt JSON.")
    ] = False,
) -> None:
    """Fetch schedule slots from ViewerAPI."""

    async def run() -> Any:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(
                await client.summarize_schedule_range(
                    view_id=view_id,
                    start_date=start,
                    end_date=end,
                    template_ids=template_id,
                    template_query=template_query,
                    assignment_query=assignment_query,
                    max_results=max_results,
                    offset=offset,
                    tz=tz,
                ),
                include_raw=include_raw,
            )

    _emit(asyncio.run(run()), output)


@app.command("personal-schedule")
def personal_schedule(
    start: Annotated[str, typer.Option("--start", help="Start date as YYYYMMDD.")],
    end: Annotated[str, typer.Option("--end", help="End date as YYYYMMDD.")],
    emp_id: Annotated[
        int | None, typer.Option("--emp-id", help="Lightning Bolt employee ID.")
    ] = None,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write JSON to this file.")
    ] = None,
    include_raw: Annotated[
        bool, typer.Option(help="Include preserved raw Lightning Bolt JSON.")
    ] = False,
) -> None:
    """Fetch personal schedule range slots."""

    async def run() -> Any:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(
                await client.fetch_personal_schedule(emp_id=emp_id, start_date=start, end_date=end),
                include_raw=include_raw,
            )

    _emit(asyncio.run(run()), output)


@app.command("my-shifts")
def my_shifts(
    start: Annotated[str, typer.Option("--start", help="Start date as YYYYMMDD.")],
    end: Annotated[str, typer.Option("--end", help="End date as YYYYMMDD.")],
    include_details: Annotated[
        bool, typer.Option(help="Include compact shift details instead of counts only.")
    ] = True,
    detail_level: Annotated[
        str | None, typer.Option("--detail-level", help="One of: count, dates, compact.")
    ] = None,
    max_results: Annotated[
        int, typer.Option("--max-results", help="Maximum compact shifts to return.")
    ] = 200,
    field: Annotated[
        list[str] | None, typer.Option("--field", help="Compact slot field to include.")
    ] = None,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write JSON to this file.")
    ] = None,
) -> None:
    """Fetch the configured/authenticated employee's shifts using compact output."""

    async def run() -> Any:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(
                await client.get_my_shifts(
                    start_date=start,
                    end_date=end,
                    include_details=include_details,
                    detail_level=detail_level,
                    max_results=max_results,
                    fields=field,
                ),
                include_raw=False,
            )

    _emit(asyncio.run(run()), output)


@app.command("employee-shifts")
def employee_shifts(
    employee: Annotated[str, typer.Argument(help="Employee ID or fuzzy name.")],
    start: Annotated[str, typer.Option("--start", help="Start date as YYYYMMDD.")],
    end: Annotated[str, typer.Option("--end", help="End date as YYYYMMDD.")],
    include_details: Annotated[
        bool, typer.Option(help="Include compact shift details instead of counts only.")
    ] = True,
    detail_level: Annotated[
        str | None, typer.Option("--detail-level", help="One of: count, dates, compact.")
    ] = None,
    max_results: Annotated[
        int, typer.Option("--max-results", help="Maximum compact shifts to return.")
    ] = 200,
    field: Annotated[
        list[str] | None, typer.Option("--field", help="Compact slot field to include.")
    ] = None,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write JSON to this file.")
    ] = None,
) -> None:
    """Fetch one employee's shifts using compact output."""

    async def run() -> Any:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(
                await client.get_employee_shifts(
                    employee,
                    start_date=start,
                    end_date=end,
                    include_details=include_details,
                    detail_level=detail_level,
                    max_results=max_results,
                    fields=field,
                ),
                include_raw=False,
            )

    _emit(asyncio.run(run()), output)


@app.command("count-shifts")
def count_shifts(
    employee: Annotated[str, typer.Argument(help="Employee ID or fuzzy name.")],
    start: Annotated[str, typer.Option("--start", help="Start date as YYYYMMDD.")],
    end: Annotated[str, typer.Option("--end", help="End date as YYYYMMDD.")],
    group_by: Annotated[
        str, typer.Option("--group-by", help="One of: none, date, template, assignment, person.")
    ] = "none",
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write JSON to this file.")
    ] = None,
) -> None:
    """Count one employee's shifts without returning the full schedule."""

    async def run() -> Any:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(
                await client.count_employee_shifts(
                    employee,
                    start_date=start,
                    end_date=end,
                    group_by=group_by,
                ),
                include_raw=False,
            )

    _emit(asyncio.run(run()), output)


@app.command("my-shift-dates")
def my_shift_dates(
    start: Annotated[str, typer.Option("--start", help="Start date as YYYYMMDD.")],
    end: Annotated[str, typer.Option("--end", help="End date as YYYYMMDD.")],
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write JSON to this file.")
    ] = None,
) -> None:
    """Fetch the configured/authenticated employee's shift dates."""

    async def run() -> Any:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(
                await client.get_my_shift_dates(start_date=start, end_date=end),
                include_raw=False,
            )

    _emit(asyncio.run(run()), output)


@app.command("employee-shift-dates")
def employee_shift_dates(
    employee: Annotated[str, typer.Argument(help="Employee ID or fuzzy name.")],
    start: Annotated[str, typer.Option("--start", help="Start date as YYYYMMDD.")],
    end: Annotated[str, typer.Option("--end", help="End date as YYYYMMDD.")],
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write JSON to this file.")
    ] = None,
) -> None:
    """Fetch one employee's shift dates."""

    async def run() -> Any:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(
                await client.get_employee_shift_dates(employee, start_date=start, end_date=end),
                include_raw=False,
            )

    _emit(asyncio.run(run()), output)


@app.command("overlaps")
def overlaps(
    employee_b: Annotated[str, typer.Argument(help="Second employee ID or fuzzy name.")],
    start: Annotated[str, typer.Option("--start", help="Start date as YYYYMMDD.")],
    end: Annotated[str, typer.Option("--end", help="End date as YYYYMMDD.")],
    employee_a: Annotated[
        str | None,
        typer.Option("--employee-a", help="First employee ID or fuzzy name. Defaults to me."),
    ] = None,
    detail_level: Annotated[
        str, typer.Option("--detail-level", help="One of: count, dates, compact.")
    ] = "compact",
    max_results: Annotated[
        int, typer.Option("--max-results", help="Maximum overlap rows to return.")
    ] = 200,
    field: Annotated[
        list[str] | None, typer.Option("--field", help="Compact slot field to include.")
    ] = None,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write JSON to this file.")
    ] = None,
) -> None:
    """Find overlapping shifts between two employees with compact output."""

    async def run() -> Any:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(
                await client.find_overlapping_shifts(
                    employee_a,
                    employee_b,
                    start_date=start,
                    end_date=end,
                    detail_level=detail_level,
                    max_results=max_results,
                    fields=field,
                ),
                include_raw=False,
            )

    _emit(asyncio.run(run()), output)


@app.command("who-is-working")
def who_is_working(
    start: Annotated[str, typer.Option("--start", help="Start date as YYYYMMDD.")],
    end: Annotated[str, typer.Option("--end", help="End date as YYYYMMDD.")],
    view_id: Annotated[
        int | None, typer.Option("--view-id", help="Lightning Bolt view ID.")
    ] = None,
    template_id: Annotated[
        list[int] | None, typer.Option("--template-id", help="Filter by template ID.")
    ] = None,
    template_query: Annotated[
        str | None, typer.Option("--template-query", help="Filter by template name/id.")
    ] = None,
    assignment_query: Annotated[
        str | None, typer.Option("--assignment-query", help="Filter by assignment name/id.")
    ] = None,
    include_open: Annotated[bool, typer.Option(help="Include open shifts.")] = False,
    include_workers: Annotated[bool, typer.Option(help="Include compact worker rows.")] = False,
    max_results: Annotated[
        int, typer.Option("--max-results", help="Maximum compact worker rows to return.")
    ] = 200,
    field: Annotated[
        list[str] | None, typer.Option("--field", help="Compact slot field to include.")
    ] = None,
    tz: Annotated[str | None, typer.Option("--tz", help="IANA timezone.")] = None,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write JSON to this file.")
    ] = None,
) -> None:
    """Summarize who is working by date without returning raw ViewerAPI slots."""

    async def run() -> Any:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(
                await client.who_is_working(
                    start_date=start,
                    end_date=end,
                    view_id=view_id,
                    template_ids=template_id,
                    template_query=template_query,
                    assignment_query=assignment_query,
                    include_open=include_open,
                    include_workers=include_workers,
                    max_results=max_results,
                    fields=field,
                    tz=tz,
                ),
                include_raw=False,
            )

    _emit(asyncio.run(run()), output)


@app.command("open-shifts")
def open_shifts(
    start: Annotated[str, typer.Option("--start", help="Start date as YYYYMMDD.")],
    end: Annotated[str, typer.Option("--end", help="End date as YYYYMMDD.")],
    view_id: Annotated[
        int | None, typer.Option("--view-id", help="Lightning Bolt view ID.")
    ] = None,
    template_id: Annotated[
        list[int] | None, typer.Option("--template-id", help="Filter by template ID.")
    ] = None,
    template_query: Annotated[
        str | None, typer.Option("--template-query", help="Filter by template name/id.")
    ] = None,
    assignment_query: Annotated[
        str | None, typer.Option("--assignment-query", help="Filter by assignment name/id.")
    ] = None,
    detail_level: Annotated[
        str, typer.Option("--detail-level", help="One of: count, dates, compact.")
    ] = "compact",
    max_results: Annotated[
        int, typer.Option("--max-results", help="Maximum open shifts to return.")
    ] = 200,
    field: Annotated[
        list[str] | None, typer.Option("--field", help="Compact slot field to include.")
    ] = None,
    tz: Annotated[str | None, typer.Option("--tz", help="IANA timezone.")] = None,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write JSON to this file.")
    ] = None,
) -> None:
    """List open shifts with compact output."""

    async def run() -> Any:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(
                await client.list_open_shifts(
                    start_date=start,
                    end_date=end,
                    view_id=view_id,
                    template_ids=template_id,
                    template_query=template_query,
                    assignment_query=assignment_query,
                    detail_level=detail_level,
                    max_results=max_results,
                    fields=field,
                    tz=tz,
                ),
                include_raw=False,
            )

    _emit(asyncio.run(run()), output)


@app.command("working-with")
def working_with(
    employee: Annotated[str, typer.Argument(help="Employee ID or fuzzy name.")],
    start: Annotated[str, typer.Option("--start", help="Start date as YYYYMMDD.")],
    end: Annotated[str, typer.Option("--end", help="End date as YYYYMMDD.")],
    view_id: Annotated[
        int | None, typer.Option("--view-id", help="Lightning Bolt view ID.")
    ] = None,
    template_query: Annotated[
        str | None, typer.Option("--template-query", help="Filter by template name/id.")
    ] = None,
    assignment_query: Annotated[
        str | None, typer.Option("--assignment-query", help="Filter by assignment name/id.")
    ] = None,
    include_workers: Annotated[bool, typer.Option(help="Include compact worker rows.")] = False,
    max_results: Annotated[
        int, typer.Option("--max-results", help="Maximum compact coworker rows to return.")
    ] = 200,
    field: Annotated[
        list[str] | None, typer.Option("--field", help="Compact slot field to include.")
    ] = None,
    tz: Annotated[str | None, typer.Option("--tz", help="IANA timezone.")] = None,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write JSON to this file.")
    ] = None,
) -> None:
    """Summarize who is working on the employee's shift dates."""

    async def run() -> Any:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(
                await client.who_is_working_with(
                    employee,
                    start_date=start,
                    end_date=end,
                    view_id=view_id,
                    template_query=template_query,
                    assignment_query=assignment_query,
                    include_workers=include_workers,
                    max_results=max_results,
                    fields=field,
                    tz=tz,
                ),
                include_raw=False,
            )

    _emit(asyncio.run(run()), output)


@app.command("open-shift-dates")
def open_shift_dates(
    start: Annotated[str, typer.Option("--start", help="Start date as YYYYMMDD.")],
    end: Annotated[str, typer.Option("--end", help="End date as YYYYMMDD.")],
    view_id: Annotated[
        int | None, typer.Option("--view-id", help="Lightning Bolt view ID.")
    ] = None,
    template_id: Annotated[
        list[int] | None, typer.Option("--template-id", help="Filter by template ID.")
    ] = None,
    template_query: Annotated[
        str | None, typer.Option("--template-query", help="Filter by template name/id.")
    ] = None,
    assignment_query: Annotated[
        str | None, typer.Option("--assignment-query", help="Filter by assignment name/id.")
    ] = None,
    max_results: Annotated[
        int, typer.Option("--max-results", help="Maximum open shifts to inspect.")
    ] = 200,
    tz: Annotated[str | None, typer.Option("--tz", help="IANA timezone.")] = None,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write JSON to this file.")
    ] = None,
) -> None:
    """List dates with open shifts."""

    async def run() -> Any:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(
                await client.get_open_shift_dates(
                    start_date=start,
                    end_date=end,
                    view_id=view_id,
                    template_ids=template_id,
                    template_query=template_query,
                    assignment_query=assignment_query,
                    max_results=max_results,
                    tz=tz,
                ),
                include_raw=False,
            )

    _emit(asyncio.run(run()), output)


@app.command("next-my-shifts")
def next_my_shifts(
    count: Annotated[int, typer.Option("--count", help="Number of shifts to return.")] = 5,
    search_days: Annotated[
        int, typer.Option("--search-days", help="Days ahead to search.")
    ] = 90,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write JSON to this file.")
    ] = None,
) -> None:
    """Fetch the next shifts for the configured/authenticated employee."""

    async def run() -> Any:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(
                await client.get_next_my_shifts(count=count, search_days=search_days),
                include_raw=False,
            )

    _emit(asyncio.run(run()), output)


@app.command("next-employee-shifts")
def next_employee_shifts(
    employee: Annotated[str, typer.Argument(help="Employee ID or fuzzy name.")],
    count: Annotated[int, typer.Option("--count", help="Number of shifts to return.")] = 5,
    search_days: Annotated[
        int, typer.Option("--search-days", help="Days ahead to search.")
    ] = 90,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write JSON to this file.")
    ] = None,
) -> None:
    """Fetch the next shifts for one employee."""

    async def run() -> Any:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(
                await client.get_next_employee_shifts(
                    employee,
                    count=count,
                    search_days=search_days,
                ),
                include_raw=False,
            )

    _emit(asyncio.run(run()), output)


@app.command("next-open-shifts")
def next_open_shifts(
    count: Annotated[int, typer.Option("--count", help="Number of open shifts to return.")] = 10,
    search_days: Annotated[
        int, typer.Option("--search-days", help="Days ahead to search.")
    ] = 90,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write JSON to this file.")
    ] = None,
) -> None:
    """Fetch the next open shifts."""

    async def run() -> Any:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(
                await client.get_next_open_shifts(count=count, search_days=search_days),
                include_raw=False,
            )

    _emit(asyncio.run(run()), output)


@app.command()
def subscription(
    emp_id: Annotated[
        int | None, typer.Option("--emp-id", help="Lightning Bolt employee ID.")
    ] = None,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write JSON to this file.")
    ] = None,
    include_raw: Annotated[
        bool, typer.Option(help="Include preserved raw Lightning Bolt JSON.")
    ] = False,
) -> None:
    """Fetch subscription metadata."""

    async def run() -> Any:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(
                await client.get_subscription(emp_id=emp_id),
                include_raw=include_raw,
            )

    _emit(asyncio.run(run()), output)


@app.command("find-employee")
def find_employee(
    query: Annotated[str, typer.Argument(help="Employee name or nickname to search for.")],
    view_id: Annotated[
        int | None, typer.Option("--view-id", help="Lightning Bolt view ID.")
    ] = None,
    limit: Annotated[int, typer.Option("--limit", help="Maximum number of matches.")] = 10,
    min_score: Annotated[
        float, typer.Option("--min-score", help="Minimum fuzzy-match score from 0.0 to 1.0.")
    ] = 0.7,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write JSON to this file.")
    ] = None,
    include_raw: Annotated[
        bool, typer.Option(help="Include preserved raw Lightning Bolt JSON.")
    ] = False,
) -> None:
    """Find employee IDs by fuzzy matching visible personnel."""

    async def run() -> Any:
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

    _emit(asyncio.run(run()), output)


@app.command()
def feed(
    emp_id: Annotated[
        int | None, typer.Option("--emp-id", help="Lightning Bolt employee ID.")
    ] = None,
    customer_id: Annotated[
        int | None, typer.Option("--customer-id", help="Lightning Bolt customer ID.")
    ] = None,
    since: Annotated[
        int | None, typer.Option("--since", help="Unix timestamp for feed cursor.")
    ] = None,
    output: Annotated[
        Path | None, typer.Option("--output", "-o", help="Write JSON to this file.")
    ] = None,
    include_raw: Annotated[
        bool, typer.Option(help="Include preserved raw Lightning Bolt JSON.")
    ] = False,
) -> None:
    """Fetch employee activity feed."""

    async def run() -> Any:
        async with LightningBoltClient.from_env() as client:
            return model_to_jsonable(
                await client.get_employee_feed(customer_id=customer_id, emp_id=emp_id, since=since),
                include_raw=include_raw,
            )

    _emit(asyncio.run(run()), output)


def _emit(data: Any, output: Path | None) -> None:
    text = json.dumps(data, indent=2, sort_keys=True)
    if output:
        output.write_text(text + "\n")
        return
    typer.echo(text)
