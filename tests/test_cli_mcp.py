import pytest
from typer.testing import CliRunner

from lightning_bolt_api.cli import app
from lightning_bolt_api.mcp_server import build_server


def test_cli_version() -> None:
    result = CliRunner().invoke(app, ["version"])

    assert result.exit_code == 0
    assert "lightning-bolt-api 0.1.0" in result.stdout


@pytest.mark.asyncio
async def test_mcp_tool_registration() -> None:
    server = build_server()
    tools = await server.list_tools()

    names = {tool.name for tool in tools}
    assert "lb_discover_context" in names
    assert "lb_get_dashboard" in names
    assert "lb_get_viewerapi" in names
    assert "lb_get_employee_feed" in names
    assert "lb_find_employee" in names
    assert "lb_get_subscription" in names
