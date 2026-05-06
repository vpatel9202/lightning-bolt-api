"""Command line entry point for the Lightning Bolt API client."""

from __future__ import annotations

import typer

app = typer.Typer(help="Read-only Lightning Bolt API tools.")


@app.callback()
def main() -> None:
    """Use subcommands to authenticate, discover views, and fetch schedule data."""


@app.command()
def version() -> None:
    """Print package version."""
    typer.echo("lightning-bolt-api 0.1.0")
