"""Per-server settings that admins change with /wgm config."""

from advanced_alchemy.base import UUIDAuditBase
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

DEFAULT_CLOSE_MINUTES = 30


class GuildSettings(UUIDAuditBase):
    """Settings for one Discord server."""

    __tablename__ = "guild_settings"

    guild_id: Mapped[str] = mapped_column(String(32), unique=True)
    event_channel_id: Mapped[str | None] = mapped_column(String(32), default=None)
    """Where event posts go. Unset: the channel the command ran in."""
    close_minutes: Mapped[int] = mapped_column(
        default=DEFAULT_CLOSE_MINUTES, server_default=str(DEFAULT_CLOSE_MINUTES)
    )
    """Sign-ups close this many minutes before an event starts."""
