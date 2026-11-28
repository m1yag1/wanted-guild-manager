"""ORM models. Import every model here so Alembic sees all tables."""

from wgm.db.models.event import (
    Event,
    EventType,
    MemberClass,
    Signup,
    SignupAction,
    SignupChange,
    SignupStatus,
)
from wgm.db.models.guild import (
    DEFAULT_CLOSE_MINUTES,
    GuildSettings,
)

__all__ = [
    "DEFAULT_CLOSE_MINUTES",
    "Event",
    "EventType",
    "MemberClass",
    "GuildSettings",
    "Signup",
    "SignupAction",
    "SignupChange",
    "SignupStatus",
]
