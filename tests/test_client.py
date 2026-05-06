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
