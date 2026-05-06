"""Async client for Lightning Bolt's reverse-engineered read API."""

from __future__ import annotations

import asyncio
import difflib
import json
import os
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from platformdirs import user_cache_dir

from lightning_bolt_api.constants import (
    FEED_BASE_URL,
    LB_CLIENT_ID,
    LB_ORIGIN,
    LBAPI_BASE_URL,
    LBLITE_BASE_URL,
    S2_BASE_URL,
)
from lightning_bolt_api.models import (
    ActivityFeed,
    CompactSlot,
    ContextDiagnostics,
    DailyCoverage,
    DailyCoverageSummary,
    Dashboard,
    DiscoveredContext,
    EmployeeMatch,
    EmployeeRef,
    EmployeeScheduleSummary,
    OpenShiftSummary,
    OverlapSummary,
    ResultMetadata,
    ScheduleRangeSummary,
    SessionState,
    ShiftCountSummary,
    ShiftOverlap,
    Slot,
    Subscription,
    Template,
    View,
    ViewerApiResponse,
)
from lightning_bolt_api.parsing import (
    format_lb_date,
    parse_activity_feed,
    parse_dashboard,
    parse_jwt_payload,
    parse_subscription,
    parse_viewerapi,
    token_expired_or_stale,
)


class LightningBoltError(RuntimeError):
    """Base exception for Lightning Bolt client failures."""


class AuthenticationError(LightningBoltError):
    """Raised when authentication or token refresh fails."""


def default_session_cache_path() -> Path:
    env_path = os.getenv("LB_SESSION_CACHE")
    if env_path:
        path = Path(env_path).expanduser()
        if path.suffix or path.is_file():
            return path
        return path / "session.json"
    return Path(user_cache_dir("lightning-bolt-api")) / "session.json"


def load_session(path: str | Path | None = None) -> SessionState | None:
    cache_path = Path(path).expanduser() if path else default_session_cache_path()
    if not cache_path.exists():
        return None
    return SessionState.model_validate_json(cache_path.read_text())


def save_session(session: SessionState, path: str | Path | None = None) -> Path:
    cache_path = Path(path).expanduser() if path else default_session_cache_path()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    data = session.model_dump_json(indent=2)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(cache_path, flags, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(data)
        handle.write("\n")
    try:
        os.chmod(cache_path, 0o600)
    except OSError:
        pass
    return cache_path


class LightningBoltClient:
    """Read-only Lightning Bolt API client."""

    def __init__(
        self,
        session: SessionState | None = None,
        *,
        username: str | None = None,
        password: str | None = None,
        session_cache: str | Path | None = None,
        default_tz: str = "UTC",
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.session = session or SessionState()
        self.username = username
        self.password = password
        self.session_cache = Path(session_cache).expanduser() if session_cache else None
        self._persist_enabled = (
            session_cache is not None or username is not None or password is not None
        )
        self.default_tz = default_tz
        self._refresh_lock = asyncio.Lock()
        self._owns_http_client = http_client is None
        self.http = http_client or httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Accept-Encoding": "gzip, deflate",
                "Origin": LB_ORIGIN,
                "User-Agent": "lightning-bolt-api/0.1.0",
            },
        )
        self._restore_cookies()

    async def __aenter__(self) -> LightningBoltClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_http_client:
            await self.http.aclose()

    @classmethod
    async def login(
        cls,
        username: str,
        password: str,
        *,
        session_cache: str | Path | None = None,
        default_tz: str = "UTC",
        http_client: httpx.AsyncClient | None = None,
    ) -> LightningBoltClient:
        """Authenticate via the replayable Lightning Bolt form-login and token flow."""
        client = cls(
            username=username,
            password=password,
            session_cache=session_cache,
            default_tz=default_tz,
            http_client=http_client,
        )
        try:
            await client.full_login()
            return client
        except Exception:
            await client.aclose()
            raise

    @classmethod
    def from_session(
        cls,
        session: SessionState,
        *,
        username: str | None = None,
        password: str | None = None,
        session_cache: str | Path | None = None,
        default_tz: str = "UTC",
        http_client: httpx.AsyncClient | None = None,
    ) -> LightningBoltClient:
        return cls(
            session=session,
            username=username,
            password=password,
            session_cache=session_cache,
            default_tz=default_tz,
            http_client=http_client,
        )

    @classmethod
    def from_env(cls, *, http_client: httpx.AsyncClient | None = None) -> LightningBoltClient:
        cache = os.getenv("LB_SESSION_CACHE")
        session = load_session(cache) or SessionState()
        return cls(
            session=session,
            username=os.getenv("LB_USERNAME"),
            password=os.getenv("LB_PASSWORD"),
            session_cache=cache,
            default_tz=os.getenv("LB_DEFAULT_TZ", "UTC"),
            http_client=http_client,
        )

    async def full_login(self) -> Dashboard:
        if not self.username or not self.password:
            raise AuthenticationError("LB_USERNAME and LB_PASSWORD are required for login.")

        self.http.cookies.clear()
        self.session.cookies = {}
        origin = quote(LB_ORIGIN, safe="")
        login_url = f"{S2_BASE_URL}/?source=access&dest=app&noRedirect=true&origin={origin}"
        response = await self.http.get(login_url)
        response.raise_for_status()

        response = await self.http.post(
            login_url,
            data={
                "txtUserName": self.username,
                "txtUserPass": self.password,
                "submit": "Login",
            },
            headers={"Referer": login_url, "Origin": S2_BASE_URL},
        )
        response.raise_for_status()

        dashboard = await self.get_dashboard(require_auth=False)
        refresh_token = self._cookie_value("LB_TKN")
        if not refresh_token:
            raise AuthenticationError("Lightning Bolt login did not yield an LB_TKN refresh token.")
        await self._exchange_refresh_token(refresh_token)
        self._persist_session()
        return dashboard

    async def ensure_authenticated(self) -> None:
        if self.session.access_token and not token_expired_or_stale(self.session.expires_at):
            return
        async with self._refresh_lock:
            if self.session.access_token and not token_expired_or_stale(self.session.expires_at):
                return
            if self.session.refresh_token:
                try:
                    await self._exchange_refresh_token(self.session.refresh_token)
                    self._persist_session()
                    return
                except httpx.HTTPStatusError as exc:
                    if not self.username or not self.password:
                        raise AuthenticationError(
                            "Token refresh failed and no credentials are set."
                        ) from exc
            await self.full_login()

    async def get_dashboard(self, *, require_auth: bool = True) -> Dashboard:
        if require_auth and not self.session.refresh_token and self.username and self.password:
            return await self.full_login()
        response = await self.http.get(f"{LBLITE_BASE_URL}/api/v1/dashboard")
        if (
            require_auth
            and response.status_code == 401
            and self.username
            and self.password
        ):
            return await self.full_login()
        response.raise_for_status()
        dashboard = parse_dashboard(response.json())
        self._update_ids_from_dashboard(dashboard)
        self._capture_cookies()
        self._persist_session()
        return dashboard

    async def list_views(self) -> list[View]:
        context = await self.discover_context()
        return context.views

    async def discover_context(self) -> DiscoveredContext:
        dashboard = await self.get_dashboard()
        dashboard_views = _usable_views(dashboard.views)
        if dashboard_views:
            return DiscoveredContext(
                customer_id=self.session.customer_id,
                emp_id=self.session.emp_id,
                user_id=self.session.user_id,
                dashboard_view_count=len(dashboard.views),
                default_view=dashboard_views[0],
                views=dashboard.views,
                can_omit_view_id=True,
                default_tz=self.default_tz,
                source="dashboard",
                raw={"dashboard": dashboard.raw},
            )

        default_view_id = os.getenv("LB_DEFAULT_VIEW_ID")
        if default_view_id:
            viewer = await self._get_viewerapi_direct(view_id=int(default_view_id))
            views = _viewer_views_or_default(viewer)
            return DiscoveredContext(
                customer_id=self.session.customer_id,
                emp_id=self.session.emp_id,
                user_id=self.session.user_id,
                dashboard_view_count=0,
                default_view=views[0] if views else None,
                views=views,
                can_omit_view_id=True,
                default_tz=self.default_tz,
                source="env_default_view_id",
                personnel_count=len(viewer.personnel),
                slot_count=len(viewer.slots),
                is_personal_only=_is_personal_only_viewer(viewer, self.session.emp_id),
                raw={"dashboard": dashboard.raw, "viewerapi": viewer.raw},
            )

        viewer, source = await self._get_auto_viewerapi()
        views = _viewer_views_or_default(viewer)
        return DiscoveredContext(
            customer_id=self.session.customer_id,
            emp_id=self.session.emp_id,
            user_id=self.session.user_id,
            dashboard_view_count=0,
            default_view=views[0] if views else None,
            views=views,
            can_omit_view_id=True,
            default_tz=self.default_tz,
            source=source,
            personnel_count=len(viewer.personnel),
            slot_count=len(viewer.slots),
            is_personal_only=_is_personal_only_viewer(viewer, self.session.emp_id),
            warnings=_context_warnings(viewer, source, self.session.emp_id),
            raw={"dashboard": dashboard.raw, "viewerapi": viewer.raw},
        )

    async def list_templates(self, view_id: int) -> list[Template]:
        viewer = await self.get_viewerapi(view_id=view_id)
        return viewer.templates

    async def get_viewerapi(
        self,
        *,
        view_id: int | None = None,
        start_date: date | str | None = None,
        end_date: date | str | None = None,
        tz: str | None = None,
        auto_discover_view: bool = True,
    ) -> ViewerApiResponse:
        if view_id is None and auto_discover_view:
            viewer, _source = await self._get_auto_viewerapi(
                start_date=start_date,
                end_date=end_date,
                tz=tz,
            )
            return viewer
        return await self._get_viewerapi_direct(
            view_id=view_id,
            start_date=start_date,
            end_date=end_date,
            tz=tz,
        )

    async def _get_viewerapi_direct(
        self,
        *,
        view_id: int | None = None,
        start_date: date | str | None = None,
        end_date: date | str | None = None,
        tz: str | None = None,
    ) -> ViewerApiResponse:
        await self.ensure_authenticated()
        body: dict[str, Any] = {"tz": tz or self.default_tz}
        if view_id is not None:
            body["view_id"] = view_id
        if start_date is not None:
            body["start_date"] = format_lb_date(start_date)
        if end_date is not None:
            body["end_date"] = format_lb_date(end_date)

        response = await self.http.post(
            f"{LBAPI_BASE_URL}/viewerapi",
            json=body,
            headers=self._auth_headers(),
        )
        response.raise_for_status()
        return parse_viewerapi(response.json())

    async def fetch_schedule(
        self,
        *,
        view_id: int | None = None,
        start_date: date | str,
        end_date: date | str,
        template_ids: list[int] | None = None,
        tz: str | None = None,
    ) -> list[Slot]:
        viewer = await self.get_viewerapi(
            view_id=view_id,
            start_date=start_date,
            end_date=end_date,
            tz=tz,
        )
        if not template_ids:
            return viewer.slots
        allowed = set(template_ids)
        return [slot for slot in viewer.slots if slot.template_id in allowed]

    async def summarize_schedule_range(
        self,
        *,
        view_id: int | None = None,
        start_date: date | str,
        end_date: date | str,
        template_ids: list[int] | None = None,
        template_query: str | None = None,
        assignment_query: str | None = None,
        max_results: int | None = 200,
        offset: int = 0,
        tz: str | None = None,
    ) -> ScheduleRangeSummary:
        slots = await self.fetch_schedule(
            view_id=view_id,
            start_date=start_date,
            end_date=end_date,
            template_ids=template_ids,
            tz=tz,
        )
        slots = _filter_slots(
            slots,
            template_query=template_query,
            assignment_query=assignment_query,
        )
        page = _page_items(slots, max_results=max_results, offset=offset)
        return ScheduleRangeSummary(
            start_date=_model_date(start_date),
            end_date=_model_date(end_date),
            slot_count=len(slots),
            slots=[_compact_slot(slot) for slot in page],
            metadata=_metadata(len(slots), len(page), offset=offset),
        )

    async def fetch_personal_schedule(
        self,
        *,
        emp_id: int | None = None,
        start_date: date | str,
        end_date: date | str,
    ) -> list[Slot]:
        await self.ensure_authenticated()
        resolved_emp_id = await self.resolve_emp_id(emp_id=emp_id)
        response = await self.http.get(
            f"{LBAPI_BASE_URL}/schedule/range/",
            params={
                "start_date": format_lb_date(start_date),
                "end_date": format_lb_date(end_date),
                "listed": "true",
                "emp_id": resolved_emp_id,
            },
            headers=self._auth_headers(),
        )
        response.raise_for_status()
        return parse_viewerapi(response.json()).slots

    async def get_my_shifts(
        self,
        *,
        start_date: date | str,
        end_date: date | str,
        include_details: bool = True,
        detail_level: str | None = None,
        max_results: int = 200,
        fields: list[str] | None = None,
    ) -> EmployeeScheduleSummary:
        return await self.get_employee_shifts(
            None,
            start_date=start_date,
            end_date=end_date,
            include_details=include_details,
            detail_level=detail_level,
            max_results=max_results,
            fields=fields,
        )

    async def get_employee_shifts(
        self,
        employee: str | int | None = None,
        *,
        start_date: date | str,
        end_date: date | str,
        include_details: bool = True,
        detail_level: str | None = None,
        max_results: int = 200,
        fields: list[str] | None = None,
    ) -> EmployeeScheduleSummary:
        resolved_detail = _resolve_detail_level(detail_level, include_details)
        emp_id = await self._resolve_employee_arg(employee)
        slots = await self.fetch_personal_schedule(
            emp_id=emp_id,
            start_date=start_date,
            end_date=end_date,
        )
        limited = _limit_items(slots, max_results) if resolved_detail == "compact" else []
        return EmployeeScheduleSummary(
            employee=_employee_ref_from_slots(emp_id, slots),
            start_date=_model_date(start_date),
            end_date=_model_date(end_date),
            shift_count=len(slots),
            shift_dates=sorted({slot.slot_date for slot in slots if slot.slot_date is not None})
            if resolved_detail in {"dates", "compact"}
            else [],
            shifts=[_compact_slot(slot, fields=fields) for slot in limited],
            metadata=(
                _metadata(len(slots), len(limited))
                if resolved_detail == "compact"
                else ResultMetadata(total_matches=len(slots), returned=0, truncated=False)
            ),
        )

    async def get_my_shift_dates(
        self,
        *,
        start_date: date | str,
        end_date: date | str,
    ) -> EmployeeScheduleSummary:
        return await self.get_my_shifts(
            start_date=start_date,
            end_date=end_date,
            detail_level="dates",
        )

    async def get_employee_shift_dates(
        self,
        employee: str | int,
        *,
        start_date: date | str,
        end_date: date | str,
    ) -> EmployeeScheduleSummary:
        return await self.get_employee_shifts(
            employee,
            start_date=start_date,
            end_date=end_date,
            detail_level="dates",
        )

    async def count_employee_shifts(
        self,
        employee: str | int | None = None,
        *,
        start_date: date | str,
        end_date: date | str,
        group_by: str = "none",
    ) -> ShiftCountSummary:
        if group_by not in {"none", "date", "template", "assignment", "person"}:
            raise ValueError("group_by must be one of: none, date, template, assignment, person.")
        emp_id = await self._resolve_employee_arg(employee)
        slots = await self.fetch_personal_schedule(
            emp_id=emp_id,
            start_date=start_date,
            end_date=end_date,
        )
        groups: dict[str, int] = {}
        if group_by == "date":
            groups = dict(sorted(_count_by_date(slots).items()))
        elif group_by == "template":
            groups = dict(sorted(_count_by_template(slots).items()))
        elif group_by == "assignment":
            groups = dict(sorted(_count_by_assignment(slots).items()))
        elif group_by == "person":
            groups = dict(sorted(_count_by_person(slots).items()))
        return ShiftCountSummary(
            employee=_employee_ref_from_slots(emp_id, slots),
            start_date=_model_date(start_date),
            end_date=_model_date(end_date),
            shift_count=len(slots),
            group_by=group_by,
            groups=groups,
        )

    async def find_overlapping_shifts(
        self,
        employee_a: str | int | None,
        employee_b: str | int,
        *,
        start_date: date | str,
        end_date: date | str,
        detail_level: str = "compact",
        max_results: int = 200,
        fields: list[str] | None = None,
    ) -> OverlapSummary:
        if detail_level not in {"count", "dates", "compact"}:
            raise ValueError("detail_level must be one of: count, dates, compact.")
        emp_id_a = await self._resolve_employee_arg(employee_a)
        emp_id_b = await self._resolve_employee_arg(employee_b)
        slots_a = await self.fetch_personal_schedule(
            emp_id=emp_id_a,
            start_date=start_date,
            end_date=end_date,
        )
        slots_b = await self.fetch_personal_schedule(
            emp_id=emp_id_b,
            start_date=start_date,
            end_date=end_date,
        )
        overlaps = [
            ShiftOverlap(
                date=slot_a.slot_date,
                employee_a_shift=_compact_slot(slot_a, fields=fields),
                employee_b_shift=_compact_slot(slot_b, fields=fields),
            )
            for slot_a in slots_a
            for slot_b in slots_b
            if _slots_overlap(slot_a, slot_b)
        ]
        limited = _limit_items(overlaps, max_results) if detail_level == "compact" else []
        return OverlapSummary(
            employee_a=_employee_ref_from_slots(emp_id_a, slots_a),
            employee_b=_employee_ref_from_slots(emp_id_b, slots_b),
            start_date=_model_date(start_date),
            end_date=_model_date(end_date),
            overlap_count=len(overlaps),
            overlap_days=sorted(
                {overlap.date for overlap in overlaps if overlap.date is not None}
            ),
            overlaps=limited,
            metadata=(
                _metadata(len(overlaps), len(limited))
                if detail_level == "compact"
                else ResultMetadata(total_matches=len(overlaps), returned=0, truncated=False)
            ),
        )

    async def who_is_working(
        self,
        *,
        start_date: date | str,
        end_date: date | str,
        view_id: int | None = None,
        template_ids: list[int] | None = None,
        template_query: str | None = None,
        assignment_query: str | None = None,
        include_open: bool = False,
        include_workers: bool = False,
        max_results: int = 200,
        fields: list[str] | None = None,
        tz: str | None = None,
    ) -> DailyCoverageSummary:
        slots = await self.fetch_schedule(
            view_id=view_id,
            start_date=start_date,
            end_date=end_date,
            template_ids=template_ids,
            tz=tz,
        )
        slots = _filter_slots(
            slots,
            template_query=template_query,
            assignment_query=assignment_query,
        )
        if not include_open:
            slots = [slot for slot in slots if not slot.is_open_shift]
        slots = [slot for slot in slots if slot.emp_id is not None or slot.is_open_shift]
        limited = _limit_items(slots, max_results) if include_workers else []
        grouped: dict[date, list[CompactSlot]] = defaultdict(list)
        count_groups: dict[date, list[Slot]] = defaultdict(list)
        for slot in slots:
            if slot.slot_date is not None:
                count_groups[slot.slot_date].append(slot)
        for slot in limited:
            if slot.slot_date is not None:
                grouped[slot.slot_date].append(_compact_slot(slot, fields=fields))
        days = [
            DailyCoverage(
                date=slot_date,
                working_count=len(day_slots),
                template_counts=_count_by_template(day_slots),
                assignment_counts=_count_by_assignment(day_slots),
                workers=grouped.get(slot_date, []),
            )
            for slot_date, day_slots in sorted(count_groups.items())
        ]
        return DailyCoverageSummary(
            start_date=_model_date(start_date),
            end_date=_model_date(end_date),
            days=days,
            metadata=(
                _metadata(len(slots), len(limited))
                if include_workers
                else ResultMetadata(total_matches=len(slots), returned=0, truncated=False)
            ),
        )

    async def list_open_shifts(
        self,
        *,
        start_date: date | str,
        end_date: date | str,
        view_id: int | None = None,
        template_ids: list[int] | None = None,
        template_query: str | None = None,
        assignment_query: str | None = None,
        detail_level: str = "compact",
        max_results: int = 200,
        fields: list[str] | None = None,
        tz: str | None = None,
    ) -> OpenShiftSummary:
        if detail_level not in {"count", "dates", "compact"}:
            raise ValueError("detail_level must be one of: count, dates, compact.")
        slots = await self.fetch_schedule(
            view_id=view_id,
            start_date=start_date,
            end_date=end_date,
            template_ids=template_ids,
            tz=tz,
        )
        open_slots = [
            slot
            for slot in _filter_slots(
                slots,
                template_query=template_query,
                assignment_query=assignment_query,
            )
            if slot.is_open_shift
        ]
        limited = _limit_items(open_slots, max_results) if detail_level == "compact" else []
        return OpenShiftSummary(
            start_date=_model_date(start_date),
            end_date=_model_date(end_date),
            open_shift_count=len(open_slots),
            open_shift_dates=sorted(
                {slot.slot_date for slot in open_slots if slot.slot_date is not None}
            )
            if detail_level in {"dates", "compact"}
            else [],
            shifts=[_compact_slot(slot, fields=fields) for slot in limited],
            metadata=(
                _metadata(len(open_slots), len(limited))
                if detail_level == "compact"
                else ResultMetadata(total_matches=len(open_slots), returned=0, truncated=False)
            ),
        )

    async def get_open_shift_dates(
        self,
        *,
        start_date: date | str,
        end_date: date | str,
        view_id: int | None = None,
        template_ids: list[int] | None = None,
        template_query: str | None = None,
        assignment_query: str | None = None,
        max_results: int = 200,
        tz: str | None = None,
    ) -> OpenShiftSummary:
        return await self.list_open_shifts(
            start_date=start_date,
            end_date=end_date,
            view_id=view_id,
            template_ids=template_ids,
            template_query=template_query,
            assignment_query=assignment_query,
            detail_level="dates",
            max_results=max_results,
            tz=tz,
        )

    async def get_next_my_shifts(
        self,
        *,
        count: int = 5,
        search_days: int = 90,
    ) -> EmployeeScheduleSummary:
        return await self.get_next_employee_shifts(None, count=count, search_days=search_days)

    async def get_next_employee_shifts(
        self,
        employee: str | int | None = None,
        *,
        count: int = 5,
        search_days: int = 90,
    ) -> EmployeeScheduleSummary:
        today = date.today()
        end = today.toordinal() + search_days
        end_date = date.fromordinal(end)
        emp_id = await self._resolve_employee_arg(employee)
        slots = await self.fetch_personal_schedule(
            emp_id=emp_id,
            start_date=today,
            end_date=end_date,
        )
        upcoming = [
            slot
            for slot in slots
            if (slot.slot_date is None or slot.slot_date >= today)
        ]
        limited = _limit_items(upcoming, count)
        return EmployeeScheduleSummary(
            employee=_employee_ref_from_slots(emp_id, slots),
            start_date=today,
            end_date=end_date,
            shift_count=len(upcoming),
            shift_dates=sorted({slot.slot_date for slot in limited if slot.slot_date is not None}),
            shifts=[_compact_slot(slot) for slot in limited],
            metadata=_metadata(len(upcoming), len(limited)),
        )

    async def get_next_open_shifts(
        self,
        *,
        count: int = 10,
        search_days: int = 90,
        view_id: int | None = None,
        template_ids: list[int] | None = None,
        template_query: str | None = None,
        assignment_query: str | None = None,
        tz: str | None = None,
    ) -> OpenShiftSummary:
        today = date.today()
        end_date = date.fromordinal(today.toordinal() + search_days)
        return await self.list_open_shifts(
            start_date=today,
            end_date=end_date,
            view_id=view_id,
            template_ids=template_ids,
            template_query=template_query,
            assignment_query=assignment_query,
            detail_level="compact",
            max_results=count,
            tz=tz,
        )

    async def who_is_working_with(
        self,
        employee: str | int | None = None,
        *,
        start_date: date | str,
        end_date: date | str,
        view_id: int | None = None,
        template_query: str | None = None,
        assignment_query: str | None = None,
        include_workers: bool = False,
        max_results: int = 200,
        fields: list[str] | None = None,
        tz: str | None = None,
    ) -> DailyCoverageSummary:
        emp_id = await self._resolve_employee_arg(employee)
        employee_slots = await self.fetch_personal_schedule(
            emp_id=emp_id,
            start_date=start_date,
            end_date=end_date,
        )
        work_dates = {slot.slot_date for slot in employee_slots if slot.slot_date is not None}
        if not work_dates:
            return DailyCoverageSummary(
                start_date=_model_date(start_date),
                end_date=_model_date(end_date),
                days=[],
                metadata=ResultMetadata(),
            )
        slots = await self.fetch_schedule(
            view_id=view_id,
            start_date=start_date,
            end_date=end_date,
            tz=tz,
        )
        coworkers = [
            slot
            for slot in _filter_slots(
                slots,
                template_query=template_query,
                assignment_query=assignment_query,
            )
            if slot.slot_date in work_dates and not slot.is_open_shift and slot.emp_id is not None
        ]
        limited = _limit_items(coworkers, max_results) if include_workers else []
        grouped: dict[date, list[CompactSlot]] = defaultdict(list)
        count_groups: dict[date, list[Slot]] = defaultdict(list)
        for slot in coworkers:
            if slot.slot_date is not None:
                count_groups[slot.slot_date].append(slot)
        for slot in limited:
            if slot.slot_date is not None:
                grouped[slot.slot_date].append(_compact_slot(slot, fields=fields))
        return DailyCoverageSummary(
            start_date=_model_date(start_date),
            end_date=_model_date(end_date),
            days=[
                DailyCoverage(
                    date=slot_date,
                    working_count=len(day_slots),
                    template_counts=_count_by_template(day_slots),
                    assignment_counts=_count_by_assignment(day_slots),
                    workers=grouped.get(slot_date, []),
                )
                for slot_date, day_slots in sorted(count_groups.items())
            ],
            metadata=(
                _metadata(len(coworkers), len(limited))
                if include_workers
                else ResultMetadata(total_matches=len(coworkers), returned=0, truncated=False)
            ),
        )

    async def get_subscription(self, *, emp_id: int | None = None) -> Subscription:
        await self.ensure_authenticated()
        resolved_emp_id = await self.resolve_emp_id(emp_id=emp_id)
        response = await self.http.get(
            f"{LBAPI_BASE_URL}/subscription",
            params={"emp_id": resolved_emp_id, "dash": "true"},
            headers=self._auth_headers(),
        )
        response.raise_for_status()
        return parse_subscription(response.json(), emp_id=resolved_emp_id)

    async def find_employee(
        self,
        query: str,
        *,
        view_id: int | None = None,
        limit: int = 10,
        min_score: float = 0.7,
        tz: str | None = None,
    ) -> list[EmployeeMatch]:
        if not query.strip():
            raise ValueError("Employee query must not be empty.")
        viewer = await self.get_viewerapi(view_id=view_id, tz=tz)
        matches = [_score_personnel(query, personnel) for personnel in viewer.personnel]
        matches = [match for match in matches if match.score >= min_score]
        matches.sort(key=lambda match: (-match.score, match.display_name or ""))
        return matches[:limit]

    async def diagnose_context(self) -> ContextDiagnostics:
        viewer, source = await self._get_auto_viewerapi()
        selected_view_id = viewer.view_context.view_id if viewer.view_context else None
        return ContextDiagnostics(
            customer_id=self.session.customer_id,
            emp_id=self.session.emp_id,
            user_id=self.session.user_id,
            default_tz=self.default_tz,
            env={
                "LB_DEFAULT_VIEW_ID": bool(os.getenv("LB_DEFAULT_VIEW_ID")),
                "LB_EMP_ID": bool(os.getenv("LB_EMP_ID")),
                "LB_EMPLOYEE_NAME": bool(os.getenv("LB_EMPLOYEE_NAME")),
                "LB_VIEW_PROBE_MAX": bool(os.getenv("LB_VIEW_PROBE_MAX")),
            },
            source=source,
            selected_view_id=selected_view_id,
            personnel_count=len(viewer.personnel),
            slot_count=len(viewer.slots),
            is_personal_only=_is_personal_only_viewer(viewer, self.session.emp_id),
            warnings=_context_warnings(viewer, source, self.session.emp_id),
            raw={"view_context": viewer.view_context.raw if viewer.view_context else None},
        )

    async def resolve_emp_id(
        self,
        *,
        emp_id: int | None = None,
        employee_name: str | None = None,
    ) -> int:
        if emp_id is not None:
            return emp_id
        env_emp_id = os.getenv("LB_EMP_ID")
        if env_emp_id:
            try:
                return int(env_emp_id)
            except ValueError as exc:
                raise ValueError("LB_EMP_ID must be an integer.") from exc

        query = employee_name or os.getenv("LB_EMPLOYEE_NAME")
        if query:
            matches = await self.find_employee(query, limit=5)
            if _has_strong_employee_match(matches):
                resolved = matches[0].emp_id
                if resolved is not None:
                    return resolved
            raise ValueError(_employee_match_error(query, matches))

        if self.session.emp_id is not None:
            return self.session.emp_id
        raise ValueError("Employee ID is required. Set LB_EMP_ID or pass emp_id.")

    async def _resolve_employee_arg(self, employee: str | int | None) -> int:
        if isinstance(employee, int):
            return employee
        if employee is None or not employee.strip():
            return await self.resolve_emp_id()
        if employee.strip().isdigit():
            return int(employee)
        matches = await self.find_employee(employee, limit=5)
        if _has_strong_employee_match(matches):
            resolved = matches[0].emp_id
            if resolved is not None:
                return resolved
        raise ValueError(_employee_match_error(employee, matches))

    async def get_employee_feed(
        self,
        *,
        customer_id: int | None = None,
        emp_id: int | None = None,
        since: int | None = None,
    ) -> ActivityFeed:
        await self.ensure_authenticated()
        resolved_customer_id = customer_id or self.session.customer_id
        resolved_emp_id = await self.resolve_emp_id(emp_id=emp_id)
        if resolved_customer_id is None or resolved_emp_id is None:
            raise ValueError("customer_id and emp_id are required for employee feed.")
        params = {"last": since} if since is not None else None
        response = await self.http.get(
            f"{FEED_BASE_URL}/employee_feed/{resolved_customer_id}/{resolved_emp_id}",
            params=params,
            headers=self._auth_headers(),
        )
        response.raise_for_status()
        return parse_activity_feed(
            response.json(),
            customer_id=resolved_customer_id,
            emp_id=resolved_emp_id,
        )

    async def _get_auto_viewerapi(
        self,
        *,
        start_date: date | str | None = None,
        end_date: date | str | None = None,
        tz: str | None = None,
    ) -> tuple[ViewerApiResponse, str]:
        env_view_id = os.getenv("LB_DEFAULT_VIEW_ID")
        if env_view_id:
            return (
                await self._get_viewerapi_direct(
                    view_id=int(env_view_id),
                    start_date=start_date,
                    end_date=end_date,
                    tz=tz,
                ),
                "env_default_view_id",
            )

        if self.session.discovered_view_id is not None:
            try:
                return (
                    await self._get_viewerapi_direct(
                        view_id=self.session.discovered_view_id,
                        start_date=start_date,
                        end_date=end_date,
                        tz=tz,
                    ),
                    "cached_discovered_view_id",
                )
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in {403, 404}:
                    raise
                self.session.discovered_view_id = None
                self._persist_session()

        default_viewer = await self._get_viewerapi_direct(
            start_date=start_date,
            end_date=end_date,
            tz=tz,
        )
        if not _is_personal_only_viewer(default_viewer, self.session.emp_id):
            return default_viewer, "viewerapi_default_context"

        discovered = await self._discover_broad_view(default_viewer, tz=tz)
        if discovered is None:
            return default_viewer, "viewerapi_personal_fallback"

        view_id, viewer = discovered
        self.session.discovered_view_id = view_id
        self._persist_session()
        if start_date is not None or end_date is not None:
            viewer = await self._get_viewerapi_direct(
                view_id=view_id,
                start_date=start_date,
                end_date=end_date,
                tz=tz,
            )
        return viewer, "auto_discovered_view_id"

    async def _discover_broad_view(
        self,
        default_viewer: ViewerApiResponse,
        *,
        tz: str | None = None,
    ) -> tuple[int, ViewerApiResponse] | None:
        best: tuple[int, ViewerApiResponse] | None = None
        best_score = _viewer_breadth_score(default_viewer)
        for view_id in _candidate_view_ids(default_viewer):
            try:
                viewer = await self._get_viewerapi_direct(view_id=view_id, tz=tz)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in {403, 404}:
                    continue
                raise
            score = _viewer_breadth_score(viewer)
            if score > best_score:
                best = (view_id, viewer)
                best_score = score
        return best

    async def _exchange_refresh_token(self, refresh_token: str) -> None:
        response = await self.http.post(
            f"{LBAPI_BASE_URL}/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": LB_CLIENT_ID,
            },
            headers={"Origin": LB_ORIGIN, "Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        payload = response.json()
        access_token = payload.get("access_token") or payload.get("token")
        new_refresh_token = payload.get("refresh_token") or payload.get("refreshToken")
        if not access_token:
            raise AuthenticationError("Token response did not include an access token.")
        claims = parse_jwt_payload(access_token)
        self.session.access_token = access_token
        self.session.refresh_token = (
            new_refresh_token or self._cookie_value("LB_TKN") or refresh_token
        )
        self.session.expires_at = int(claims["exp"]) if claims.get("exp") is not None else None
        self.session.customer_id = _first_int(
            claims.get("customerID"),
            claims.get("customer_id"),
            self.session.customer_id,
        )
        self.session.emp_id = _first_int(
            claims.get("empID"), claims.get("emp_id"), self.session.emp_id
        )
        self.session.user_id = _first_int(
            claims.get("userID"), claims.get("user_id"), self.session.user_id
        )
        self._capture_cookies()

    def _auth_headers(self) -> dict[str, str]:
        if not self.session.access_token:
            raise AuthenticationError("No access token is available.")
        return {"Authorization": f"Bearer {self.session.access_token}", "Origin": LB_ORIGIN}

    def _capture_cookies(self) -> None:
        self.session.cookies = {cookie.name: cookie.value for cookie in self.http.cookies.jar}

    def _restore_cookies(self) -> None:
        for name, value in self.session.cookies.items():
            self.http.cookies.set(name, value)

    def _cookie_value(self, name: str) -> str | None:
        value = self.http.cookies.get(name)
        if value:
            return value
        return self.session.cookies.get(name)

    def _persist_session(self) -> None:
        if not self._persist_enabled:
            return
        if self.session.access_token or self.session.refresh_token or self.session.cookies:
            save_session(self.session, self.session_cache)

    def _update_ids_from_dashboard(self, dashboard: Dashboard) -> None:
        self.session.customer_id = dashboard.customer_id or self.session.customer_id
        self.session.emp_id = dashboard.emp_id or self.session.emp_id
        self.session.user_id = dashboard.user_id or self.session.user_id


def _first_int(*values: Any) -> int | None:
    for value in values:
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _viewer_views_or_default(viewer: ViewerApiResponse) -> list[View]:
    if viewer.views:
        return viewer.views
    if viewer.view_context:
        return [viewer.view_context]
    return [
        View(
            view_id=None,
            name="Default",
            raw={"source": "viewerapi_default_context", "view_id": None},
        )
    ]


def _usable_views(views: list[View]) -> list[View]:
    return [view for view in views if view.view_id and view.view_id > 0]


def _is_personal_only_viewer(viewer: ViewerApiResponse, emp_id: int | None) -> bool:
    personnel_ids = {person.emp_id for person in viewer.personnel if person.emp_id is not None}
    slot_emp_ids = {slot.emp_id for slot in viewer.slots if slot.emp_id is not None}
    if len(personnel_ids) > 1:
        return False
    if len(viewer.personnel) > 1:
        return False
    if len(personnel_ids) == 1 and emp_id is not None and emp_id not in personnel_ids:
        return False
    if not viewer.personnel:
        if len(slot_emp_ids) != 1:
            return False
        if emp_id is not None and emp_id not in slot_emp_ids:
            return False
    usable_views = _usable_views(viewer.views)
    if viewer.view_context and viewer.view_context.view_id and viewer.view_context.view_id > 0:
        usable_views.append(viewer.view_context)
    return not usable_views


def _viewer_breadth_score(viewer: ViewerApiResponse) -> int:
    personnel_ids = {person.emp_id for person in viewer.personnel if person.emp_id is not None}
    slot_emp_ids = {slot.emp_id for slot in viewer.slots if slot.emp_id is not None}
    return (len(personnel_ids) * 100_000) + (len(slot_emp_ids) * 1_000) + len(viewer.slots)


def _candidate_view_ids(viewer: ViewerApiResponse) -> list[int]:
    candidates: list[int] = []
    for view in [*viewer.views, viewer.view_context]:
        if view and view.view_id:
            candidates.append(view.view_id)
    candidates.extend(_extract_view_ids(viewer.raw))
    max_view_id = _probe_max_view_id()
    candidates.extend(range(1, max_view_id + 1))
    return _dedupe_positive_ints(candidates, max_value=max_view_id)


def _extract_view_ids(value: Any) -> list[int]:
    found: list[int] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_norm = str(key).lower()
            if "view" in key_norm:
                parsed = _coerce_int(item)
                if parsed is not None:
                    found.append(parsed)
            found.extend(_extract_view_ids(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_extract_view_ids(item))
    return found


def _probe_max_view_id() -> int:
    raw = os.getenv("LB_VIEW_PROBE_MAX", "100")
    try:
        return max(0, min(int(raw), 1000))
    except ValueError:
        return 100


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _dedupe_positive_ints(values: list[int], *, max_value: int) -> list[int]:
    deduped: list[int] = []
    seen: set[int] = set()
    for value in values:
        if value <= 0 or value > max_value or value in seen:
            continue
        deduped.append(value)
        seen.add(value)
    return deduped


def _context_warnings(
    viewer: ViewerApiResponse,
    source: str,
    emp_id: int | None,
) -> list[str]:
    if not _is_personal_only_viewer(viewer, emp_id):
        return []
    if source == "viewerapi_personal_fallback":
        return [
            "Only the authenticated user's personal schedule/personnel were visible. "
            "Broader view discovery did not find an accessible view."
        ]
    return ["The selected ViewerAPI context appears to be personal-only."]


def _model_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    formatted = format_lb_date(value)
    return datetime.strptime(formatted, "%Y%m%d").date()


def _compact_slot(slot: Slot, *, fields: list[str] | None = None) -> CompactSlot:
    data = {
        "date": slot.slot_date,
        "start_time": slot.start_time,
        "stop_time": slot.stop_time,
        "template_id": slot.template_id,
        "template_name": slot.template_name,
        "assignment_id": slot.assign_id,
        "assignment_name": slot.assign_display_name,
        "emp_id": slot.emp_id,
        "display_name": slot.display_name,
        "compact_name": slot.compact_name,
        "is_open_shift": slot.is_open_shift,
    }
    if fields:
        allowed = set(fields) | {"is_open_shift"}
        data = {key: value for key, value in data.items() if key in allowed}
    return CompactSlot(**data)


def _employee_ref_from_slots(emp_id: int | None, slots: list[Slot]) -> EmployeeRef:
    first = next((slot for slot in slots if slot.emp_id == emp_id), None)
    return EmployeeRef(
        emp_id=emp_id,
        display_name=first.display_name if first else None,
        compact_name=first.compact_name if first else None,
    )


def _limit_items[T](items: list[T], max_results: int) -> list[T]:
    if max_results < 0:
        raise ValueError("max_results must be greater than or equal to 0.")
    return items[:max_results]


def _page_items[T](
    items: list[T],
    *,
    max_results: int | None,
    offset: int = 0,
) -> list[T]:
    if offset < 0:
        raise ValueError("offset must be greater than or equal to 0.")
    if max_results is None:
        return items[offset:]
    if max_results < 0:
        raise ValueError("max_results must be greater than or equal to 0.")
    if max_results == 0:
        return items[offset:]
    return items[offset : offset + max_results]


def _metadata(total: int, returned: int, *, offset: int = 0) -> ResultMetadata:
    next_offset = offset + returned if offset + returned < total else None
    return ResultMetadata(
        total_matches=total,
        returned=returned,
        truncated=next_offset is not None,
        offset=offset,
        next_offset=next_offset,
    )


def _count_by_date(slots: list[Slot]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for slot in slots:
        if slot.slot_date is not None:
            counts[slot.slot_date.isoformat()] += 1
    return counts


def _count_by_template(slots: list[Slot]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for slot in slots:
        key = slot.template_name or str(slot.template_id or "unknown")
        counts[key] += 1
    return counts


def _count_by_assignment(slots: list[Slot]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for slot in slots:
        key = slot.assign_display_name or str(slot.assign_id or "unknown")
        counts[key] += 1
    return counts


def _count_by_person(slots: list[Slot]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for slot in slots:
        key = slot.display_name or slot.compact_name or str(slot.emp_id or "unknown")
        counts[key] += 1
    return counts


def _filter_slots(
    slots: list[Slot],
    *,
    template_query: str | None = None,
    assignment_query: str | None = None,
) -> list[Slot]:
    filtered = slots
    if template_query:
        query = template_query.lower()
        filtered = [
            slot
            for slot in filtered
            if query in (slot.template_name or "").lower()
            or query == str(slot.template_id or "").lower()
        ]
    if assignment_query:
        query = assignment_query.lower()
        filtered = [
            slot
            for slot in filtered
            if query in (slot.assign_display_name or "").lower()
            or query == str(slot.assign_id or "").lower()
            or query == (slot.assign_structure_id or "").lower()
        ]
    return filtered


def _resolve_detail_level(detail_level: str | None, include_details: bool) -> str:
    if detail_level is None:
        return "compact" if include_details else "count"
    if detail_level not in {"count", "dates", "compact"}:
        raise ValueError("detail_level must be one of: count, dates, compact.")
    return detail_level


def _slots_overlap(first: Slot, second: Slot) -> bool:
    first_start = first.start_time_utc or first.start_time
    first_stop = first.stop_time_utc or first.stop_time
    second_start = second.start_time_utc or second.start_time
    second_stop = second.stop_time_utc or second.stop_time
    if not first_start or not first_stop or not second_start or not second_stop:
        return first.slot_date is not None and first.slot_date == second.slot_date
    return first_start < second_stop and second_start < first_stop


def model_to_jsonable(model: Any, *, include_raw: bool = True) -> Any:
    if hasattr(model, "model_dump"):
        dumped = model.model_dump(mode="json", exclude_none=True)
        return dumped if include_raw else _strip_raw(dumped)
    if isinstance(model, list):
        return [model_to_jsonable(item, include_raw=include_raw) for item in model]
    dumped = json.loads(json.dumps(model, default=str))
    return dumped if include_raw else _strip_raw(dumped)


def _strip_raw(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _strip_raw(item) for key, item in value.items() if key != "raw"}
    if isinstance(value, list):
        return [_strip_raw(item) for item in value]
    return value


def _score_personnel(query: str, personnel: Any) -> EmployeeMatch:
    query_norm = _normalize_employee_text(query)
    fields = {
        "display_name": personnel.display_name,
        "compact_name": personnel.compact_name,
        "last_name": personnel.last_name,
    }
    for key in (
        "first_name",
        "middle_name",
        "full_name",
        "name",
        "email",
        "user_name",
    ):
        value = personnel.raw.get(key)
        if isinstance(value, str):
            fields[key] = value

    best = 0.0
    matched_fields: list[str] = []
    for field, value in fields.items():
        if not value:
            continue
        value_norm = _normalize_employee_text(value)
        if not value_norm:
            continue
        score = difflib.SequenceMatcher(None, query_norm, value_norm).ratio()
        if query_norm == value_norm:
            score = 1.0
        elif query_norm in value_norm or value_norm in query_norm:
            substring_score = min(len(query_norm), len(value_norm)) / max(
                len(query_norm), len(value_norm)
            )
            score = max(score, substring_score)
        if score > best:
            best = score
            matched_fields = [field]
        elif score == best:
            matched_fields.append(field)

    return EmployeeMatch(
        emp_id=personnel.emp_id,
        score=round(best, 3),
        display_name=personnel.display_name,
        last_name=personnel.last_name,
        compact_name=personnel.compact_name,
        matched_fields=matched_fields,
        raw=personnel.raw,
    )


def _normalize_employee_text(value: str) -> str:
    value = value.lower()
    value = re.sub(r"\b(md|do|pa|np|rn|phd|dr)\b\.?", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def _has_strong_employee_match(matches: list[EmployeeMatch]) -> bool:
    if not matches or matches[0].emp_id is None or matches[0].score < 0.82:
        return False
    return len(matches) == 1 or matches[0].score - matches[1].score >= 0.05


def _employee_match_error(query: str, matches: list[EmployeeMatch]) -> str:
    if not matches:
        return f"No employee matched {query!r}. Set LB_EMP_ID or use find-employee."
    candidates = [
        f"{match.emp_id}: {match.display_name or match.compact_name or match.last_name} "
        f"(score={match.score})"
        for match in matches
    ]
    return (
        f"Employee name {query!r} did not resolve to a single strong match. "
        f"Set LB_EMP_ID or choose from: {', '.join(candidates)}"
    )
