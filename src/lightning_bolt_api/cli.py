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
def schedule(
    start: Annotated[str, typer.Option("--start", help="Start date as YYYYMMDD.")],
    end: Annotated[str, typer.Option("--end", help="End date as YYYYMMDD.")],
    view_id: Annotated[
        int | None, typer.Option("--view-id", help="Lightning Bolt view ID.")
    ] = None,
    template_id: Annotated[
        list[int] | None, typer.Option("--template-id", help="Filter by template ID.")
    ] = None,
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
                await client.fetch_schedule(
                    view_id=view_id,
                    start_date=start,
                    end_date=end,
                    template_ids=template_id,
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
