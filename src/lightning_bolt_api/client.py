"""Async client for Lightning Bolt's reverse-engineered read API."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import date
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
    Dashboard,
    SessionState,
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
        if path.suffix:
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
        dashboard = await self.get_dashboard()
        if dashboard.views:
            return dashboard.views
        default_view_id = os.getenv("LB_DEFAULT_VIEW_ID")
        if default_view_id:
            viewer = await self.get_viewerapi(view_id=int(default_view_id))
            return viewer.views or ([viewer.view_context] if viewer.view_context else [])
        return []

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
        view_id: int,
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

    async def fetch_personal_schedule(
        self,
        *,
        emp_id: int,
        start_date: date | str,
        end_date: date | str,
    ) -> list[Slot]:
        await self.ensure_authenticated()
        response = await self.http.get(
            f"{LBAPI_BASE_URL}/schedule/range/",
            params={
                "start_date": format_lb_date(start_date),
                "end_date": format_lb_date(end_date),
                "listed": "true",
                "emp_id": emp_id,
            },
            headers=self._auth_headers(),
        )
        response.raise_for_status()
        return parse_viewerapi(response.json()).slots

    async def get_subscription(self, *, emp_id: int) -> Subscription:
        await self.ensure_authenticated()
        response = await self.http.get(
            f"{LBAPI_BASE_URL}/subscription",
            params={"emp_id": emp_id, "dash": "true"},
            headers=self._auth_headers(),
        )
        response.raise_for_status()
        return parse_subscription(response.json(), emp_id=emp_id)

    async def get_employee_feed(
        self,
        *,
        customer_id: int | None = None,
        emp_id: int | None = None,
        since: int | None = None,
    ) -> ActivityFeed:
        await self.ensure_authenticated()
        resolved_customer_id = customer_id or self.session.customer_id
        resolved_emp_id = emp_id or self.session.emp_id
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
