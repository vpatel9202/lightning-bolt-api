from datetime import date

import pytest

from lightning_bolt_api.parsing import (
    decode_dashboard_payload,
    format_lb_date,
    parse_slot,
    parse_subscription,
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


def test_parse_slot_preserves_reassignment_provenance() -> None:
    parsed = parse_slot(
        {
            "slot_id": 709760,
            "emp_id": 20319,
            "original_emp_id": 20066,
            "modified_by_emp_id": 20097,
            "modified_by_display_name": "Scheduler",
            "modified_date": "2026-04-24T08:32:11",
            "emp_request_id": 12345,
            "emp_request_status": "approved",
            "is_pending_request": False,
            "slot_history": [{"emp_id": 20066}, {"emp_id": 20319}],
        }
    )

    assert parsed.original_emp_id == 20066
    assert parsed.modified_by_emp_id == 20097
    assert parsed.modified_by_display_name == "Scheduler"
    assert parsed.modified_date is not None
    assert parsed.emp_request_id == 12345
    assert parsed.emp_request_status == "approved"
    assert parsed.is_pending_request is False
    assert parsed.slot_history == [{"emp_id": 20066}, {"emp_id": 20319}]
    assert parsed.assignment_origin_for(20319) == "trade_in"


def test_subscription_list_derives_calendar_urls() -> None:
    parsed = parse_subscription(
        [
            {
                "id": 37854,
                "customer_id": 908,
                "emp_id": 20319,
                "md5": "96737dd04f0a424b4e0f8ed93a28e455",
                "tz": "US/Central",
            }
        ]
    )

    assert parsed.subscription_id == 37854
    assert parsed.customer_id == 908
    assert parsed.emp_id == 20319
    assert parsed.tz == "US/Central"
    assert parsed.default_calendar_url == (
        "https://m.lightning-bolt.com/96737dd04f0a424b4e0f8ed93a28e455g.ics"
    )
    assert parsed.calendar_urls == {
        "iphone_ipad": "https://m.lightning-bolt.com/96737dd04f0a424b4e0f8ed93a28e455i.ics",
        "google": "https://m.lightning-bolt.com/96737dd04f0a424b4e0f8ed93a28e455g.ics",
        "android": "https://m.lightning-bolt.com/96737dd04f0a424b4e0f8ed93a28e455g.ics",
        "outlook": "webcal://m.lightning-bolt.com/96737dd04f0a424b4e0f8ed93a28e455o.ics",
        "lotus_notes": "https://m.lightning-bolt.com/96737dd04f0a424b4e0f8ed93a28e455i.ics",
        "mac_ical": "https://m.lightning-bolt.com/96737dd04f0a424b4e0f8ed93a28e455i.ics",
    }
    assert parsed.raw["data"][0]["id"] == 37854


def test_subscription_dict_without_md5_has_no_calendar_urls() -> None:
    parsed = parse_subscription({"id": 1, "emp_id": 2})

    assert parsed.subscription_id == 1
    assert parsed.emp_id == 2
    assert parsed.calendar_urls == {}
    assert parsed.default_calendar_url is None
