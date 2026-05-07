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
    assert "lb_diagnose_context" in names
    assert "lb_get_dashboard" in names
    assert "lb_get_viewerapi" in names
    assert "lb_get_employee_feed" in names
    assert "lb_find_employee" in names
    assert "lb_get_subscription" in names
    assert "lb_get_my_shifts" in names
    assert "lb_get_my_shift_dates" in names
    assert "lb_get_employee_shifts" in names
    assert "lb_get_employee_shift_dates" in names
    assert "lb_count_employee_shifts" in names
    assert "lb_find_overlapping_shifts" in names
    assert "lb_who_is_working" in names
    assert "lb_list_open_shifts" in names
    assert "lb_list_open_shift_groups" in names
    assert "lb_get_open_shift_dates" in names
    assert "lb_who_is_working_with" in names
    assert "lb_get_next_my_shifts" in names
    assert "lb_get_next_employee_shifts" in names
    assert "lb_get_next_open_shifts" in names
