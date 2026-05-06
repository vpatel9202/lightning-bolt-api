"""Typed response models with raw Lightning Bolt payload preservation."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RawModel(BaseModel):
    """Base model that keeps the source LB object for debugging and downstream fields."""

    model_config = ConfigDict(extra="allow")
    raw: dict[str, Any] = Field(default_factory=dict)


class View(RawModel):
    view_id: int | None = None
    name: str | None = None


class Department(RawModel):
    department_id: int | None = None
    name: str | None = None


class Template(RawModel):
    template_id: int | None = None
    name: str | None = None
    name_full: str | None = None
    first_published_date: date | None = None
    last_published_date: date | None = None


class Personnel(RawModel):
    emp_id: int | None = None
    display_name: str | None = None
    last_name: str | None = None
    compact_name: str | None = None
    ptype_id: int | None = None


class EmployeeMatch(RawModel):
    emp_id: int | None = None
    score: float = 0.0
    display_name: str | None = None
    last_name: str | None = None
    compact_name: str | None = None
    matched_fields: list[str] = Field(default_factory=list)


class Assignment(RawModel):
    assign_id: int | None = None
    display_name: str | None = None
    compact_name: str | None = None
    description: str | None = None


class Dashboard(RawModel):
    customer_id: int | None = None
    emp_id: int | None = None
    user_id: int | None = None
    user_name: str | None = None
    views: list[View] = Field(default_factory=list)


class DiscoveredContext(RawModel):
    customer_id: int | None = None
    emp_id: int | None = None
    user_id: int | None = None
    dashboard_view_count: int = 0
    default_view: View | None = None
    views: list[View] = Field(default_factory=list)
    can_omit_view_id: bool = False
    default_tz: str = "UTC"
    source: str = "unknown"
    personnel_count: int | None = None
    slot_count: int | None = None
    is_personal_only: bool | None = None
    warnings: list[str] = Field(default_factory=list)


class ContextDiagnostics(RawModel):
    customer_id: int | None = None
    emp_id: int | None = None
    user_id: int | None = None
    default_tz: str = "UTC"
    env: dict[str, bool] = Field(default_factory=dict)
    source: str = "unknown"
    selected_view_id: int | None = None
    personnel_count: int = 0
    slot_count: int = 0
    is_personal_only: bool = False
    warnings: list[str] = Field(default_factory=list)


class Slot(RawModel):
    slot_id: int | None = None
    slot_uuid: str | None = None
    emp_id: int | None = None
    display_name: str | None = None
    compact_name: str | None = None
    last_name: str | None = None
    template_id: int | None = None
    template_name: str | None = None
    department_id: int | None = None
    slot_date: date | None = None
    start_time: datetime | None = None
    stop_time: datetime | None = None
    start_time_utc: datetime | None = None
    stop_time_utc: datetime | None = None
    assign_id: int | None = None
    assign_display_name: str | None = None
    assign_structure_id: str | None = None
    is_pending: bool | None = None
    is_manual_slot: bool | None = None
    has_note: bool | None = None
    note: str | None = None
    request_note: str | None = None
    decision_note: str | None = None
    location_ids: list[int] = Field(default_factory=list)
    location_names: list[str] = Field(default_factory=list)
    emp_ptype: int | None = None
    assign_atype: int | None = None

    @field_validator("assign_structure_id", mode="before")
    @classmethod
    def _coerce_assign_structure_id(cls, value: Any) -> str | None:
        if value is None:
            return None
        return str(value)

    @property
    def is_open_shift(self) -> bool:
        return (
            self.last_name == "z.Administrative"
            and self.display_name is not None
            and re.fullmatch(r"OPEN \d+", self.display_name) is not None
        )

    def is_assigned_to(self, emp_id: int) -> bool:
        return self.emp_id == emp_id

    @property
    def has_any_note(self) -> bool:
        return bool(self.has_note or self.note or self.request_note or self.decision_note)


class ViewerApiResponse(RawModel):
    view_context: View | None = None
    views: list[View] = Field(default_factory=list)
    slots: list[Slot] = Field(default_factory=list)
    personnel: list[Personnel] = Field(default_factory=list)
    assignments: list[Assignment] = Field(default_factory=list)
    departments: list[Department] = Field(default_factory=list)
    templates: list[Template] = Field(default_factory=list)
    holidays: list[dict[str, Any]] = Field(default_factory=list)


class Subscription(RawModel):
    subscription_id: int | None = None
    customer_id: int | None = None
    emp_id: int | None = None
    md5: str | None = None
    tz: str | None = None
    calendar_urls: dict[str, str] = Field(default_factory=dict)
    default_calendar_url: str | None = None


class ActivityFeedItem(RawModel):
    item_id: int | str | None = None
    created_at: datetime | None = None
    message: str | None = None


class ActivityFeed(RawModel):
    customer_id: int | None = None
    emp_id: int | None = None
    items: list[ActivityFeedItem] = Field(default_factory=list)


class SessionState(BaseModel):
    access_token: str | None = None
    refresh_token: str | None = None
    expires_at: int | None = None
    customer_id: int | None = None
    emp_id: int | None = None
    user_id: int | None = None
    discovered_view_id: int | None = None
    cookies: dict[str, str] = Field(default_factory=dict)
