"""Typed response models with raw Lightning Bolt payload preservation."""

from __future__ import annotations

import re
from datetime import date, datetime
from datetime import date as Date
from datetime import datetime as DateTime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

AssignmentOrigin = Literal["regular", "trade_in", "trade_out", "unknown_reassignment"]


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
    is_granted_request: bool | None = None
    is_manual_slot: bool | None = None
    has_note: bool | None = None
    note: str | None = None
    request_note: str | None = None
    decision_note: str | None = None
    location_ids: list[int] = Field(default_factory=list)
    location_names: list[str] = Field(default_factory=list)
    emp_ptype: int | None = None
    assign_atype: int | None = None
    original_emp_id: int | None = None
    modified_by_emp_id: int | None = None
    modified_by_display_name: str | None = None
    modified_date: datetime | None = None
    emp_request_id: int | None = None
    emp_request_status: str | None = None
    is_pending_request: bool | None = None
    slot_history: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("assign_structure_id", mode="before")
    @classmethod
    def _coerce_assign_structure_id(cls, value: Any) -> str | None:
        if value is None:
            return None
        return str(value)

    @field_validator("slot_history", mode="before")
    @classmethod
    def _coerce_slot_history(cls, value: Any) -> list[dict[str, Any]]:
        if value is None:
            return []
        return value

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
    def is_reassigned(self) -> bool:
        return self.original_emp_id is not None and self.original_emp_id != self.emp_id

    def is_trade_in_for(self, emp_id: int | None) -> bool:
        if emp_id is None:
            return False
        return self.emp_id == emp_id and self.original_emp_id not in (None, emp_id)

    def is_trade_out_from(self, emp_id: int | None) -> bool:
        if emp_id is None:
            return False
        return self.emp_id != emp_id and self.original_emp_id == emp_id

    def assignment_origin_for(self, emp_id: int | None = None) -> AssignmentOrigin:
        if not self.is_reassigned:
            return "regular"
        if self.is_trade_in_for(emp_id):
            return "trade_in"
        if self.is_trade_out_from(emp_id):
            return "trade_out"
        return "unknown_reassignment"

    @property
    def has_any_note(self) -> bool:
        return bool(self.has_note or self.note or self.request_note or self.decision_note)


class CompactSlot(BaseModel):
    date: Date | None = None
    start_time: DateTime | None = None
    stop_time: DateTime | None = None
    template_id: int | None = None
    template_name: str | None = None
    assignment_id: int | None = None
    assignment_name: str | None = None
    emp_id: int | None = None
    display_name: str | None = None
    compact_name: str | None = None
    is_open_shift: bool = False
    provider_type: str | None = None
    is_pending: bool | None = None
    is_granted_request: bool | None = None
    is_manual_slot: bool | None = None
    has_note: bool | None = None
    original_emp_id: int | None = None
    assignment_origin: AssignmentOrigin | None = None
    modified_by_emp_id: int | None = None
    modified_by_display_name: str | None = None
    modified_date: DateTime | None = None
    emp_request_id: int | None = None
    emp_request_status: str | None = None
    is_pending_request: bool | None = None


class ResultMetadata(BaseModel):
    total_matches: int = 0
    returned: int = 0
    truncated: bool = False
    offset: int = 0
    next_offset: int | None = None


class EmployeeRef(BaseModel):
    emp_id: int | None = None
    display_name: str | None = None
    compact_name: str | None = None


class EmployeeScheduleSummary(BaseModel):
    employee: EmployeeRef
    start_date: Date
    end_date: Date
    shift_count: int = 0
    shift_dates: list[Date] = Field(default_factory=list)
    shifts: list[CompactSlot] = Field(default_factory=list)
    metadata: ResultMetadata = Field(default_factory=ResultMetadata)


class SlotHistoryEntry(BaseModel):
    text: str | None = None
    timestamp: DateTime | None = None


class ShiftTrade(BaseModel):
    date: Date | None = None
    start_time: DateTime | None = None
    stop_time: DateTime | None = None
    template_id: int | None = None
    template_name: str | None = None
    assignment_id: int | None = None
    assignment_name: str | None = None
    assignment_origin: AssignmentOrigin
    emp_id: int | None = None
    display_name: str | None = None
    compact_name: str | None = None
    original_emp_id: int | None = None
    original_display_name: str | None = None
    original_compact_name: str | None = None
    modified_by_emp_id: int | None = None
    modified_by_display_name: str | None = None
    modified_date: DateTime | None = None
    note: str | None = None
    request_note: str | None = None
    decision_note: str | None = None
    emp_request_id: int | None = None
    emp_request_status: str | None = None
    is_pending: bool | None = None
    is_granted_request: bool | None = None
    is_pending_request: bool | None = None
    slot_history: list[SlotHistoryEntry] = Field(default_factory=list)


class ShiftTradeSummary(BaseModel):
    employee: EmployeeRef
    start_date: Date
    end_date: Date
    trade_count: int = 0
    trade_dates: list[Date] = Field(default_factory=list)
    trades: list[ShiftTrade] = Field(default_factory=list)
    metadata: ResultMetadata = Field(default_factory=ResultMetadata)


class ShiftCountSummary(BaseModel):
    employee: EmployeeRef
    start_date: Date
    end_date: Date
    shift_count: int = 0
    group_by: str = "none"
    groups: dict[str, int] = Field(default_factory=dict)


class DailyCoverage(BaseModel):
    date: Date
    working_count: int = 0
    template_counts: dict[str, int] = Field(default_factory=dict)
    assignment_counts: dict[str, int] = Field(default_factory=dict)
    workers: list[CompactSlot] = Field(default_factory=list)


class DailyCoverageSummary(BaseModel):
    start_date: Date
    end_date: Date
    days: list[DailyCoverage] = Field(default_factory=list)
    metadata: ResultMetadata = Field(default_factory=ResultMetadata)


class OpenShiftSummary(BaseModel):
    start_date: Date
    end_date: Date
    open_shift_count: int = 0
    open_shift_dates: list[Date] = Field(default_factory=list)
    shifts: list[CompactSlot] = Field(default_factory=list)
    metadata: ResultMetadata = Field(default_factory=ResultMetadata)


class OpenShiftGroup(BaseModel):
    provider_type: str
    open_shift_count: int = 0
    open_shift_dates: list[Date] = Field(default_factory=list)
    shifts: list[CompactSlot] = Field(default_factory=list)
    metadata: ResultMetadata = Field(default_factory=ResultMetadata)


class OpenShiftGroupSummary(BaseModel):
    start_date: Date
    end_date: Date
    open_shift_count: int = 0
    open_shift_dates: list[Date] = Field(default_factory=list)
    groups: dict[str, OpenShiftGroup] = Field(default_factory=dict)


class ScheduleRangeSummary(BaseModel):
    start_date: Date
    end_date: Date
    slot_count: int = 0
    slots: list[CompactSlot] = Field(default_factory=list)
    metadata: ResultMetadata = Field(default_factory=ResultMetadata)


class ShiftOverlap(BaseModel):
    date: Date | None = None
    employee_a_shift: CompactSlot
    employee_b_shift: CompactSlot


class OverlapSummary(BaseModel):
    employee_a: EmployeeRef
    employee_b: EmployeeRef
    start_date: Date
    end_date: Date
    overlap_count: int = 0
    overlap_days: list[date] = Field(default_factory=list)
    overlaps: list[ShiftOverlap] = Field(default_factory=list)
    metadata: ResultMetadata = Field(default_factory=ResultMetadata)


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
