"""Parsing helpers for Lightning Bolt response payloads."""

from __future__ import annotations

import base64
import json
import re
import time
from datetime import date
from typing import Any

from lightning_bolt_api.models import (
    ActivityFeed,
    ActivityFeedItem,
    Assignment,
    Dashboard,
    Department,
    Personnel,
    Slot,
    Subscription,
    Template,
    View,
    ViewerApiResponse,
)

LB_DATE_RE = re.compile(r"^\d{8}$")


def format_lb_date(value: date | str) -> str:
    """Return a Lightning Bolt request date in YYYYMMDD form."""
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    if not isinstance(value, str):
        raise TypeError("Lightning Bolt dates must be datetime.date or YYYYMMDD strings.")
    if not LB_DATE_RE.fullmatch(value):
        raise ValueError("Lightning Bolt request dates must be YYYYMMDD strings, not ISO dates.")
    return value


def decode_dashboard_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Decode dashboard fields that Lightning Bolt may return as JSON strings."""
    decoded: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, str) and value.strip().startswith(("{", "[")):
            try:
                decoded[key] = json.loads(value)
                continue
            except json.JSONDecodeError:
                pass
        decoded[key] = value
    return decoded


def parse_jwt_payload(token: str) -> dict[str, Any]:
    """Parse a JWT payload without verifying the signature."""
    try:
        payload = token.split(".")[1]
    except IndexError as exc:
        raise ValueError("Access token is not a JWT.") from exc
    padding = "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload + padding))


def token_expired_or_stale(expires_at: int | None, *, skew_seconds: int = 300) -> bool:
    if expires_at is None:
        return True
    return expires_at <= int(time.time()) + skew_seconds


def parse_view(raw: dict[str, Any]) -> View:
    return View(view_id=raw.get("view_id") or raw.get("id"), name=raw.get("name"), raw=raw)


def parse_department(raw: dict[str, Any]) -> Department:
    return Department(
        department_id=raw.get("department_id") or raw.get("id"),
        name=raw.get("name") or raw.get("display_name"),
        raw=raw,
    )


def parse_template(raw: dict[str, Any]) -> Template:
    return Template(
        template_id=raw.get("template_id") or raw.get("id"),
        name=raw.get("name"),
        name_full=raw.get("name_full") or raw.get("full_name"),
        first_published_date=raw.get("first_published_date"),
        last_published_date=raw.get("last_published_date"),
        raw=raw,
    )


def parse_personnel(raw: dict[str, Any]) -> Personnel:
    return Personnel(
        emp_id=raw.get("emp_id") or raw.get("id"),
        display_name=raw.get("display_name"),
        last_name=raw.get("last_name"),
        compact_name=raw.get("compact_name"),
        ptype_id=raw.get("ptype_id"),
        raw=raw,
    )


def parse_assignment(raw: dict[str, Any]) -> Assignment:
    return Assignment(
        assign_id=raw.get("assign_id") or raw.get("id"),
        display_name=raw.get("display_name"),
        compact_name=raw.get("compact_name"),
        description=raw.get("description"),
        raw=raw,
    )


def parse_slot(raw: dict[str, Any]) -> Slot:
    return Slot(
        slot_id=raw.get("slot_id"),
        slot_uuid=raw.get("slot_uuid"),
        emp_id=raw.get("emp_id"),
        display_name=raw.get("display_name"),
        compact_name=raw.get("compact_name"),
        last_name=raw.get("last_name"),
        template_id=raw.get("template_id"),
        template_name=raw.get("template"),
        department_id=raw.get("department_id"),
        slot_date=raw.get("slot_date"),
        start_time=raw.get("start_time"),
        stop_time=raw.get("stop_time"),
        start_time_utc=raw.get("start_time_utc"),
        stop_time_utc=raw.get("stop_time_utc"),
        assign_id=raw.get("assign_id"),
        assign_display_name=raw.get("assign_display_name"),
        assign_structure_id=raw.get("assign_structure_id"),
        is_pending=raw.get("is_pending"),
        is_granted_request=raw.get("is_granted_request"),
        is_manual_slot=raw.get("is_manual_slot"),
        has_note=raw.get("has_note"),
        note=raw.get("note"),
        request_note=raw.get("request_note"),
        decision_note=raw.get("decision_note"),
        location_ids=raw.get("location_ids") or [],
        location_names=raw.get("location_names") or [],
        emp_ptype=raw.get("emp_ptype"),
        assign_atype=raw.get("assign_atype"),
        raw=raw,
    )


def parse_dashboard(payload: dict[str, Any]) -> Dashboard:
    raw = decode_dashboard_payload(payload)
    user = raw.get("user") if isinstance(raw.get("user"), dict) else {}
    views_raw = raw.get("views") if isinstance(raw.get("views"), list) else []
    return Dashboard(
        customer_id=raw.get("customer_id") or raw.get("customerID") or user.get("customer_id"),
        emp_id=raw.get("emp_id") or raw.get("empID") or user.get("emp_id"),
        user_id=raw.get("user_id") or raw.get("userID") or user.get("user_id"),
        user_name=raw.get("user_name") or raw.get("userName") or user.get("user_name"),
        views=[parse_view(view) for view in views_raw if isinstance(view, dict)],
        raw=raw,
    )


def _extract_schedule_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    schedule_data = payload.get("schedule_data")
    if isinstance(schedule_data, dict) and isinstance(schedule_data.get("data"), list):
        return [row for row in schedule_data["data"] if isinstance(row, dict)]
    if isinstance(payload.get("schedule_data_sample"), list):
        return [row for row in payload["schedule_data_sample"] if isinstance(row, dict)]
    if isinstance(payload.get("data"), list):
        return [row for row in payload["data"] if isinstance(row, dict)]
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def parse_viewerapi(payload: Any) -> ViewerApiResponse:
    if isinstance(payload, list):
        return ViewerApiResponse(
            slots=[parse_slot(row) for row in payload if isinstance(row, dict)],
            raw={"data": payload},
        )
    if not isinstance(payload, dict):
        return ViewerApiResponse(raw={"value": payload})

    view_context_raw = payload.get("view_context")
    views_raw = payload.get("views") if isinstance(payload.get("views"), list) else []
    personnel_raw = payload.get("personnel") or payload.get("personnel_sample") or []
    assignments_raw = payload.get("assignments") or payload.get("assignments_sample") or []
    departments_raw = payload.get("departments") or []
    templates_raw = payload.get("templates") or payload.get("template_data") or []
    holidays = payload.get("holidays") or []

    return ViewerApiResponse(
        view_context=parse_view(view_context_raw) if isinstance(view_context_raw, dict) else None,
        views=[parse_view(view) for view in views_raw if isinstance(view, dict)],
        slots=[parse_slot(row) for row in _extract_schedule_rows(payload)],
        personnel=[parse_personnel(row) for row in personnel_raw if isinstance(row, dict)],
        assignments=[parse_assignment(row) for row in assignments_raw if isinstance(row, dict)],
        departments=[parse_department(row) for row in departments_raw if isinstance(row, dict)],
        templates=[parse_template(row) for row in templates_raw if isinstance(row, dict)],
        holidays=[row for row in holidays if isinstance(row, dict)],
        raw=payload,
    )


def parse_subscription(payload: Any, emp_id: int | None = None) -> Subscription:
    raw: dict[str, Any]
    record: dict[str, Any] = {}
    if isinstance(payload, dict):
        raw = payload
        if isinstance(payload.get("data"), list):
            record = next((row for row in payload["data"] if isinstance(row, dict)), {})
        else:
            record = payload
    elif isinstance(payload, list):
        raw = {"data": payload}
        record = next((row for row in payload if isinstance(row, dict)), {})
    else:
        raw = {"data": payload}

    md5 = record.get("md5")
    calendar_urls = _calendar_urls(str(md5)) if md5 else {}
    return Subscription(
        subscription_id=record.get("id") or record.get("subscription_id"),
        customer_id=record.get("customer_id"),
        emp_id=emp_id or record.get("emp_id"),
        md5=str(md5) if md5 else None,
        tz=record.get("tz"),
        calendar_urls=calendar_urls,
        default_calendar_url=calendar_urls.get("google"),
        raw=raw,
    )


def _calendar_urls(md5: str) -> dict[str, str]:
    base = f"m.lightning-bolt.com/{md5}"
    return {
        "iphone_ipad": f"https://{base}i.ics",
        "google": f"https://{base}g.ics",
        "android": f"https://{base}g.ics",
        "outlook": f"webcal://{base}o.ics",
        "lotus_notes": f"https://{base}i.ics",
        "mac_ical": f"https://{base}i.ics",
    }


def parse_activity_feed(
    payload: Any,
    *,
    customer_id: int | None,
    emp_id: int | None,
) -> ActivityFeed:
    if isinstance(payload, dict):
        raw_items = payload.get("items") or payload.get("data") or payload.get("feed") or []
        raw = payload
    elif isinstance(payload, list):
        raw_items = payload
        raw = {"items": payload}
    else:
        raw_items = []
        raw = {"value": payload}

    items = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        items.append(
            ActivityFeedItem(
                item_id=item.get("id") or item.get("item_id"),
                created_at=item.get("created_at") or item.get("date") or item.get("timestamp"),
                message=item.get("message") or item.get("text") or item.get("title"),
                raw=item,
            )
        )
    return ActivityFeed(customer_id=customer_id, emp_id=emp_id, items=items, raw=raw)
