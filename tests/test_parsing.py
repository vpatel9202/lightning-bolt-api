from datetime import date

import pytest

from lightning_bolt_api.parsing import (
    decode_dashboard_payload,
    format_lb_date,
    parse_viewerapi,
)


def test_format_lb_date_accepts_date() -> None:
    assert format_lb_date(date(2026, 5, 6)) == "20260506"


def test_format_lb_date_accepts_yyyymmdd() -> None:
    assert format_lb_date("20260506") == "20260506"


def test_format_lb_date_rejects_iso_string() -> None:
    with pytest.raises(ValueError):
        format_lb_date("2026-05-06")


def test_dashboard_json_string_decoding() -> None:
    decoded = decode_dashboard_payload({"views": '[{"view_id": 1, "name": "Main"}]', "ok": "yes"})

    assert decoded["views"] == [{"view_id": 1, "name": "Main"}]
    assert decoded["ok"] == "yes"


def test_viewerapi_fixture_parses_slots(fixture_payload: dict) -> None:
    parsed = parse_viewerapi(fixture_payload)

    assert parsed.view_context is not None
    assert parsed.view_context.view_id == 123
    assert parsed.slots
    assert parsed.slots[0].raw["slot_uuid"]
