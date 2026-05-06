from __future__ import annotations

import base64
import json
import time
from pathlib import Path

import httpx
import pytest
import respx

from lightning_bolt_api.client import LightningBoltClient, load_session
from lightning_bolt_api.constants import LBAPI_BASE_URL, LBLITE_BASE_URL, S2_BASE_URL
from lightning_bolt_api.models import SessionState


def jwt_with_claims(**claims: object) -> str:
    header = _b64({"alg": "none", "typ": "JWT"})
    payload = _b64(claims)
    return f"{header}.{payload}."


def _b64(value: dict[str, object]) -> str:
    raw = json.dumps(value, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


@pytest.mark.asyncio
@respx.mock
async def test_login_chain_exchanges_rotated_refresh_token(tmp_path: Path) -> None:
    cache = tmp_path / "session.json"
    token = jwt_with_claims(exp=int(time.time()) + 3600, customerID=12, empID=34, userID=56)
    respx.get(url__regex=rf"{S2_BASE_URL}/.*").mock(return_value=httpx.Response(200, text="login"))
    respx.post(url__regex=rf"{S2_BASE_URL}/.*").mock(return_value=httpx.Response(200, text="ok"))
    respx.get(f"{LBLITE_BASE_URL}/api/v1/dashboard").mock(
        return_value=httpx.Response(
            200,
            json={"user": {"emp_id": 34}},
            headers={"set-cookie": "LB_TKN=refresh-one; Path=/"},
        )
    )
    token_route = respx.post(f"{LBAPI_BASE_URL}/token").mock(
        return_value=httpx.Response(
            200,
            json={"access_token": token, "refresh_token": "refresh-two"},
        )
    )

    async with await LightningBoltClient.login(
        "user",
        "password",
        session_cache=cache,
        default_tz="America/Chicago",
    ) as client:
        assert client.session.access_token == token
        assert client.session.refresh_token == "refresh-two"
        assert client.session.customer_id == 12

    assert token_route.calls.last.request.content.decode() == (
        "grant_type=refresh_token&refresh_token=refresh-one"
        "&client_id=1bc4e40b-0373-42a8-bfed-979f10b0743a"
    )
    assert load_session(cache).refresh_token == "refresh-two"  # type: ignore[union-attr]


@pytest.mark.asyncio
@respx.mock
async def test_viewerapi_uses_confirmed_body_fields() -> None:
    token = jwt_with_claims(exp=int(time.time()) + 3600)
    client = LightningBoltClient(
        session=SessionState(
            access_token=token,
            refresh_token="refresh",
            expires_at=int(time.time()) + 3600,
        ),
        session_cache=None,
    )
    route = respx.post(f"{LBAPI_BASE_URL}/viewerapi").mock(
        return_value=httpx.Response(200, json={"schedule_data": {"data": []}})
    )

    try:
        await client.get_viewerapi(
            view_id=123,
            start_date="20260501",
            end_date="20260531",
            tz="America/Chicago",
        )
    finally:
        await client.aclose()

    assert json.loads(route.calls.last.request.content) == {
        "view_id": 123,
        "tz": "America/Chicago",
        "start_date": "20260501",
        "end_date": "20260531",
    }
    assert route.calls.last.request.headers["origin"] == "https://lblite.lightning-bolt.com"


@pytest.mark.asyncio
@respx.mock
async def test_list_views_falls_back_to_viewerapi_default_context() -> None:
    token = jwt_with_claims(exp=int(time.time()) + 3600)
    client = LightningBoltClient(
        session=SessionState(
            access_token=token,
            refresh_token="refresh",
            expires_at=int(time.time()) + 3600,
        ),
        session_cache=None,
    )
    respx.get(f"{LBLITE_BASE_URL}/api/v1/dashboard").mock(
        return_value=httpx.Response(200, json={"views": []})
    )
    respx.post(f"{LBAPI_BASE_URL}/viewerapi").mock(
        return_value=httpx.Response(
            200,
            json={"view_context": {"view_id": 50, "name": "Example View"}},
        )
    )

    try:
        views = await client.list_views()
    finally:
        await client.aclose()

    assert len(views) == 1
    assert views[0].view_id == 50
    assert views[0].name == "Example View"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_schedule_can_omit_view_id() -> None:
    token = jwt_with_claims(exp=int(time.time()) + 3600)
    client = LightningBoltClient(
        session=SessionState(
            access_token=token,
            refresh_token="refresh",
            expires_at=int(time.time()) + 3600,
        ),
        session_cache=None,
    )
    route = respx.post(f"{LBAPI_BASE_URL}/viewerapi").mock(
        return_value=httpx.Response(200, json={"schedule_data": {"data": []}})
    )

    try:
        slots = await client.fetch_schedule(start_date="20260501", end_date="20260507")
    finally:
        await client.aclose()

    assert slots == []
    assert json.loads(route.calls.last.request.content) == {
        "tz": "UTC",
        "start_date": "20260501",
        "end_date": "20260507",
    }


@pytest.mark.asyncio
@respx.mock
async def test_get_subscription_uses_env_emp_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LB_EMP_ID", "20319")
    token = jwt_with_claims(exp=int(time.time()) + 3600)
    client = LightningBoltClient(
        session=SessionState(
            access_token=token,
            refresh_token="refresh",
            expires_at=int(time.time()) + 3600,
        ),
        session_cache=None,
    )
    route = respx.get(f"{LBAPI_BASE_URL}/subscription").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": 37854,
                    "emp_id": 20319,
                    "md5": "96737dd04f0a424b4e0f8ed93a28e455",
                }
            ],
        )
    )

    try:
        subscription = await client.get_subscription()
    finally:
        await client.aclose()

    assert route.calls.last.request.url.params["emp_id"] == "20319"
    assert subscription.emp_id == 20319
    assert subscription.default_calendar_url is not None


@pytest.mark.asyncio
@respx.mock
async def test_find_employee_returns_ranked_matches() -> None:
    token = jwt_with_claims(exp=int(time.time()) + 3600)
    client = LightningBoltClient(
        session=SessionState(
            access_token=token,
            refresh_token="refresh",
            expires_at=int(time.time()) + 3600,
        ),
        session_cache=None,
    )
    respx.post(f"{LBAPI_BASE_URL}/viewerapi").mock(
        return_value=httpx.Response(
            200,
            json={
                "personnel": [
                    {
                        "emp_id": 20319,
                        "display_name": "Patel, Vash MD",
                        "compact_name": "V Patel",
                        "last_name": "Patel",
                    },
                    {
                        "emp_id": 20088,
                        "display_name": "Example, Other MD",
                        "compact_name": "O Example",
                        "last_name": "Example",
                    },
                ]
            },
        )
    )

    try:
        matches = await client.find_employee("vash patel")
    finally:
        await client.aclose()

    assert len(matches) == 1
    assert matches[0].emp_id == 20319


@pytest.mark.asyncio
@respx.mock
async def test_find_employee_uses_env_default_view_and_filters_weak_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LB_DEFAULT_VIEW_ID", "50")
    token = jwt_with_claims(exp=int(time.time()) + 3600)
    client = LightningBoltClient(
        session=SessionState(
            access_token=token,
            refresh_token="refresh",
            expires_at=int(time.time()) + 3600,
        ),
        session_cache=None,
    )
    route = respx.post(f"{LBAPI_BASE_URL}/viewerapi").mock(
        return_value=httpx.Response(
            200,
            json={
                "personnel": [
                    {
                        "emp_id": 20319,
                        "display_name": "Vash Patel",
                        "compact_name": "vvp",
                        "last_name": "Patel",
                    }
                ]
            },
        )
    )

    try:
        matches = await client.find_employee("Halfast")
    finally:
        await client.aclose()

    assert matches == []
    assert json.loads(route.calls.last.request.content) == {
        "tz": "UTC",
        "view_id": 50,
    }


@pytest.mark.asyncio
@respx.mock
async def test_find_employee_auto_discovers_broad_view(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LB_VIEW_PROBE_MAX", "50")
    token = jwt_with_claims(exp=int(time.time()) + 3600)
    client = LightningBoltClient(
        session=SessionState(
            access_token=token,
            refresh_token="refresh",
            expires_at=int(time.time()) + 3600,
            emp_id=20319,
        ),
        session_cache=None,
    )

    def viewerapi_response(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body.get("view_id") == 50:
            return httpx.Response(
                200,
                json={
                    "view_context": {"view_id": 50, "name": "Hospital Medicine"},
                    "personnel": [
                        {
                            "emp_id": 20319,
                            "display_name": "Vash Patel",
                            "compact_name": "vvp",
                            "last_name": "Patel",
                        },
                        {
                            "emp_id": 20088,
                            "display_name": "Halfast, Ashley",
                            "compact_name": "A Halfast",
                            "last_name": "Halfast",
                        },
                    ],
                },
            )
        if "view_id" in body:
            return httpx.Response(404, json={"detail": "not found"})
        return httpx.Response(
            200,
            json={
                "view_context": {"view_id": 0, "name": "Me"},
                "views": [{"view_id": 0, "name": "Me"}],
                "personnel": [
                    {
                        "emp_id": 20319,
                        "display_name": "Vash Patel",
                        "compact_name": "vvp",
                        "last_name": "Patel",
                    }
                ],
            },
        )

    route = respx.post(f"{LBAPI_BASE_URL}/viewerapi").mock(side_effect=viewerapi_response)

    try:
        matches = await client.find_employee("Halfast")
        diagnostics = await client.diagnose_context()
    finally:
        await client.aclose()

    assert matches[0].emp_id == 20088
    assert client.session.discovered_view_id == 50
    assert diagnostics.source == "cached_discovered_view_id"
    assert diagnostics.selected_view_id == 50
    assert route.call_count == 52


@pytest.mark.asyncio
@respx.mock
async def test_auto_discovery_falls_back_to_personal_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LB_VIEW_PROBE_MAX", "2")
    token = jwt_with_claims(exp=int(time.time()) + 3600)
    client = LightningBoltClient(
        session=SessionState(
            access_token=token,
            refresh_token="refresh",
            expires_at=int(time.time()) + 3600,
            emp_id=20319,
        ),
        session_cache=None,
    )

    def viewerapi_response(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if "view_id" in body:
            return httpx.Response(404, json={"detail": "not found"})
        return httpx.Response(
            200,
            json={
                "view_context": {"view_id": 0, "name": "Me"},
                "views": [{"view_id": 0, "name": "Me"}],
                "personnel": [{"emp_id": 20319, "display_name": "Vash Patel"}],
            },
        )

    respx.post(f"{LBAPI_BASE_URL}/viewerapi").mock(side_effect=viewerapi_response)

    try:
        diagnostics = await client.diagnose_context()
    finally:
        await client.aclose()

    assert diagnostics.source == "viewerapi_personal_fallback"
    assert diagnostics.is_personal_only is True
    assert diagnostics.warnings


@pytest.mark.asyncio
@respx.mock
async def test_get_my_shifts_returns_compact_summary() -> None:
    token = jwt_with_claims(exp=int(time.time()) + 3600)
    client = LightningBoltClient(
        session=SessionState(
            access_token=token,
            refresh_token="refresh",
            expires_at=int(time.time()) + 3600,
            emp_id=20319,
        ),
        session_cache=None,
    )
    route = respx.get(f"{LBAPI_BASE_URL}/schedule/range/").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "emp_id": 20319,
                    "display_name": "Vash Patel",
                    "compact_name": "vvp",
                    "template": "R10",
                    "template_id": 10,
                    "slot_date": "2026-05-06",
                    "start_time": "2026-05-06T07:00:00",
                    "stop_time": "2026-05-06T17:00:00",
                }
            ],
        )
    )

    try:
        summary = await client.get_my_shifts(start_date="20260506", end_date="20260513")
    finally:
        await client.aclose()

    assert route.calls.last.request.url.params["emp_id"] == "20319"
    assert summary.shift_count == 1
    assert summary.employee.display_name == "Vash Patel"
    assert summary.shifts[0].template_name == "R10"
    assert summary.shifts[0].raw is None if hasattr(summary.shifts[0], "raw") else True


@pytest.mark.asyncio
@respx.mock
async def test_count_employee_shifts_groups_by_template() -> None:
    token = jwt_with_claims(exp=int(time.time()) + 3600)
    client = LightningBoltClient(
        session=SessionState(
            access_token=token,
            refresh_token="refresh",
            expires_at=int(time.time()) + 3600,
        ),
        session_cache=None,
    )
    respx.get(f"{LBAPI_BASE_URL}/schedule/range/").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"emp_id": 20088, "template": "A", "slot_date": "2026-05-06"},
                {"emp_id": 20088, "template": "A", "slot_date": "2026-05-07"},
                {"emp_id": 20088, "template": "B", "slot_date": "2026-05-08"},
            ],
        )
    )

    try:
        summary = await client.count_employee_shifts(
            "20088",
            start_date="20260506",
            end_date="20260513",
            group_by="template",
        )
    finally:
        await client.aclose()

    assert summary.shift_count == 3
    assert summary.groups == {"A": 2, "B": 1}


@pytest.mark.asyncio
@respx.mock
async def test_find_overlapping_shifts_uses_employee_schedule_ranges() -> None:
    token = jwt_with_claims(exp=int(time.time()) + 3600)
    client = LightningBoltClient(
        session=SessionState(
            access_token=token,
            refresh_token="refresh",
            expires_at=int(time.time()) + 3600,
            emp_id=20319,
        ),
        session_cache=None,
    )

    def schedule_response(request: httpx.Request) -> httpx.Response:
        emp_id = request.url.params["emp_id"]
        if emp_id == "20319":
            return httpx.Response(
                200,
                json=[
                    {
                        "emp_id": 20319,
                        "display_name": "Vash Patel",
                        "template": "R10",
                        "slot_date": "2026-05-06",
                        "start_time": "2026-05-06T07:00:00",
                        "stop_time": "2026-05-06T17:00:00",
                    }
                ],
            )
        return httpx.Response(
            200,
            json=[
                {
                    "emp_id": 20088,
                    "display_name": "Ashley Halfast",
                    "template": "R11",
                    "slot_date": "2026-05-06",
                    "start_time": "2026-05-06T16:00:00",
                    "stop_time": "2026-05-06T22:00:00",
                }
            ],
        )

    respx.get(f"{LBAPI_BASE_URL}/schedule/range/").mock(side_effect=schedule_response)

    try:
        summary = await client.find_overlapping_shifts(
            None,
            "20088",
            start_date="20260506",
            end_date="20260513",
        )
    finally:
        await client.aclose()

    assert summary.overlap_count == 1
    assert [day.isoformat() for day in summary.overlap_days] == ["2026-05-06"]
    assert summary.overlaps[0].employee_b_shift.display_name == "Ashley Halfast"


@pytest.mark.asyncio
@respx.mock
async def test_who_is_working_and_open_shifts_return_compact_limited_results() -> None:
    token = jwt_with_claims(exp=int(time.time()) + 3600)
    client = LightningBoltClient(
        session=SessionState(
            access_token=token,
            refresh_token="refresh",
            expires_at=int(time.time()) + 3600,
        ),
        session_cache=None,
    )
    respx.post(f"{LBAPI_BASE_URL}/viewerapi").mock(
        return_value=httpx.Response(
            200,
            json={
                "schedule_data": {
                    "data": [
                        {
                            "emp_id": 1,
                            "display_name": "One",
                            "template": "A",
                            "slot_date": "2026-05-06",
                        },
                        {
                            "emp_id": 2,
                            "display_name": "Two",
                            "template": "B",
                            "slot_date": "2026-05-06",
                        },
                        {
                            "display_name": "OPEN 1",
                            "last_name": "z.Administrative",
                            "template": "A",
                            "slot_date": "2026-05-07",
                        },
                    ]
                }
            },
        )
    )

    try:
        coverage = await client.who_is_working(
            start_date="20260506",
            end_date="20260513",
            max_results=1,
        )
        coverage_with_workers = await client.who_is_working(
            start_date="20260506",
            end_date="20260513",
            detail_level="summary",
            include_workers=True,
            max_results=1,
        )
        open_summary = await client.list_open_shifts(
            start_date="20260506",
            end_date="20260513",
        )
    finally:
        await client.aclose()

    assert coverage.metadata.total_matches == 2
    assert coverage.metadata.returned == 0
    assert coverage.days[0].template_counts == {}
    assert coverage.days[0].assignment_counts == {}
    assert coverage_with_workers.days[0].template_counts == {"A": 1, "B": 1}
    assert coverage_with_workers.days[0].assignment_counts == {}
    assert coverage_with_workers.metadata.returned == 1
    assert coverage_with_workers.metadata.truncated is True
    assert coverage_with_workers.days[0].workers[0].display_name == "One"
    assert open_summary.open_shift_count == 1
    assert open_summary.shifts[0].is_open_shift is True


@pytest.mark.asyncio
@respx.mock
async def test_schedule_summary_paginates_and_filters() -> None:
    token = jwt_with_claims(exp=int(time.time()) + 3600)
    client = LightningBoltClient(
        session=SessionState(
            access_token=token,
            refresh_token="refresh",
            expires_at=int(time.time()) + 3600,
        ),
        session_cache=None,
    )
    respx.post(f"{LBAPI_BASE_URL}/viewerapi").mock(
        return_value=httpx.Response(
            200,
            json={
                "schedule_data": {
                    "data": [
                        {"emp_id": 1, "template": "R10", "slot_date": "2026-05-06"},
                        {"emp_id": 2, "template": "R10", "slot_date": "2026-05-07"},
                        {"emp_id": 3, "template": "A5", "slot_date": "2026-05-08"},
                    ]
                }
            },
        )
    )

    try:
        summary = await client.summarize_schedule_range(
            start_date="20260506",
            end_date="20260513",
            template_query="R10",
            max_results=1,
            offset=1,
        )
    finally:
        await client.aclose()

    assert summary.slot_count == 2
    assert summary.metadata.returned == 1
    assert summary.metadata.offset == 1
    assert summary.metadata.next_offset is None
    assert summary.slots[0].emp_id == 2


@pytest.mark.asyncio
@respx.mock
async def test_employee_shift_dates_omit_shift_rows() -> None:
    token = jwt_with_claims(exp=int(time.time()) + 3600)
    client = LightningBoltClient(
        session=SessionState(
            access_token=token,
            refresh_token="refresh",
            expires_at=int(time.time()) + 3600,
        ),
        session_cache=None,
    )
    respx.get(f"{LBAPI_BASE_URL}/schedule/range/").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"emp_id": 20088, "template": "A", "slot_date": "2026-05-06"},
                {"emp_id": 20088, "template": "B", "slot_date": "2026-05-06"},
                {"emp_id": 20088, "template": "C", "slot_date": "2026-05-07"},
            ],
        )
    )

    try:
        summary = await client.get_employee_shift_dates(
            "20088",
            start_date="20260506",
            end_date="20260513",
        )
    finally:
        await client.aclose()

    assert summary.shift_count == 3
    assert [day.isoformat() for day in summary.shift_dates] == ["2026-05-06", "2026-05-07"]
    assert summary.shifts == []


@pytest.mark.asyncio
@respx.mock
async def test_concurrent_refresh_is_serialized(tmp_path: Path) -> None:
    old_exp = int(time.time()) - 10
    new_exp = int(time.time()) + 3600
    token = jwt_with_claims(exp=new_exp)
    client = LightningBoltClient(
        session=SessionState(access_token="old", refresh_token="refresh", expires_at=old_exp),
        session_cache=tmp_path / "session.json",
    )
    token_route = respx.post(f"{LBAPI_BASE_URL}/token").mock(
        return_value=httpx.Response(
            200,
            json={"access_token": token, "refresh_token": "new-refresh"},
        )
    )

    try:
        await asyncio_gather_refresh(client)
    finally:
        await client.aclose()

    assert token_route.call_count == 1
    assert client.session.refresh_token == "new-refresh"


async def asyncio_gather_refresh(client: LightningBoltClient) -> None:
    import asyncio

    await asyncio.gather(client.ensure_authenticated(), client.ensure_authenticated())
