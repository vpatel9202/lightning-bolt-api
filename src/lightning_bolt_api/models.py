"""Typed response models with raw Lightning Bolt payload preservation."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RawModel(BaseModel):
    """Base model that keeps the source LB object for debugging and downstream fields."""

    model_config = ConfigDict(extra="allow")
    raw: dict[str, Any] = Field(default_factory=dict)


class View(RawModel):
    view_id: int | None = None
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


class Assignment(RawModel):
    assign_id: int | None = None
    display_name: str | None = None
    compact_name: str | None = None
    description: str | None = None


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
    slots: list[Slot] = Field(default_factory=list)
    personnel: list[Personnel] = Field(default_factory=list)
    assignments: list[Assignment] = Field(default_factory=list)
    departments: list[dict[str, Any]] = Field(default_factory=list)
    holidays: list[dict[str, Any]] = Field(default_factory=list)


class SessionState(BaseModel):
    access_token: str | None = None
    refresh_token: str | None = None
    expires_at: int | None = None
    customer_id: int | None = None
    emp_id: int | None = None
    user_id: int | None = None
