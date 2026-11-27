"""ORM models. Import every model here so Alembic sees all tables."""

from wgm.db.models.event import Event, Signup, SignupStatus
from wgm.db.models.guild import DEFAULT_CLOSE_MINUTES, GuildSettings

__all__ = ["DEFAULT_CLOSE_MINUTES", "Event", "GuildSettings", "Signup", "SignupStatus"]
