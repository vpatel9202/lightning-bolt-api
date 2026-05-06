"""Client skeleton for Lightning Bolt's reverse-engineered read API.

Implementation notes live in AGENTS.md and docs/. This module intentionally starts
small; the first implementation should build direct HTTP auth before adding any
browser automation fallback.
"""

from __future__ import annotations

from datetime import date

from lightning_bolt_api.models import SessionState, Slot, Template, View, ViewerApiResponse


class LightningBoltClient:
    """Read-only Lightning Bolt API client."""

    def __init__(self, session: SessionState | None = None) -> None:
        self.session = session or SessionState()

    @classmethod
    async def login(cls, username: str, password: str) -> LightningBoltClient:
        """Authenticate via the replayable LB form-login and token exchange flow."""
        raise NotImplementedError("Direct HTTP auth flow is planned but not implemented yet.")

    @classmethod
    def from_session(cls, session: SessionState) -> LightningBoltClient:
        return cls(session=session)

    async def list_views(self) -> list[View]:
        raise NotImplementedError

    async def list_templates(self, view_id: int) -> list[Template]:
        raise NotImplementedError

    async def get_viewerapi(
        self,
        *,
        view_id: int | None = None,
        start_date: date | str | None = None,
        end_date: date | str | None = None,
        tz: str = "UTC",
    ) -> ViewerApiResponse:
        raise NotImplementedError

    async def fetch_schedule(
        self,
        *,
        view_id: int,
        start_date: date | str,
        end_date: date | str,
        template_ids: list[int] | None = None,
    ) -> list[Slot]:
        raise NotImplementedError
