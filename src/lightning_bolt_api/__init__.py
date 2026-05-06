"""Read-only client for Lightning Bolt's reverse-engineered API."""

from lightning_bolt_api.client import AuthenticationError, LightningBoltClient, LightningBoltError
from lightning_bolt_api.models import (
    ActivityFeed,
    ActivityFeedItem,
    Assignment,
    Dashboard,
    Department,
    DiscoveredContext,
    EmployeeMatch,
    Personnel,
    SessionState,
    Slot,
    Subscription,
    Template,
    View,
    ViewerApiResponse,
)

__all__ = [
    "ActivityFeed",
    "ActivityFeedItem",
    "Assignment",
    "AuthenticationError",
    "Dashboard",
    "Department",
    "DiscoveredContext",
    "EmployeeMatch",
    "LightningBoltClient",
    "LightningBoltError",
    "Personnel",
    "SessionState",
    "Slot",
    "Subscription",
    "Template",
    "View",
    "ViewerApiResponse",
]
