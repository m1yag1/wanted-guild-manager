"""Event rules and storage."""

from datetime import UTC, date, datetime, time
from uuid import UUID
from zoneinfo import ZoneInfo

from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService
from sqlalchemy import select

from wgm.db.models import Event, GuildSettings, Signup, SignupStatus

EVENT_TYPES = (
    "Siege",
    "Boonstone",
    "Riftstone",
    "Archboss",
    "Guild Raid",
    "Arena",
    "Other",
)


class EventInputError(ValueError):
    """The manager typed something we cannot use; the message says what."""


def parse_start(day: str, clock: str, zone: ZoneInfo, now: datetime) -> datetime:
    """Turn a typed date and time in `zone` into a UTC datetime in the future.

    Args:
        day: Like 2026-12-05.
        clock: 24-hour time like 20:00.
        zone: The guild's time zone.
        now: The current time, to reject past events.

    Raises:
        EventInputError: The date or time is malformed or in the past.
    """
    try:
        local = datetime.combine(
            date.fromisoformat(day.strip()), time.fromisoformat(clock.strip())
        )
    except ValueError:
        raise EventInputError(
            "Use a date like 2026-12-05 and a 24-hour time like 20:00."
        ) from None
    starts_at = local.replace(tzinfo=zone).astimezone(UTC)
    if starts_at <= now:
        raise EventInputError("That time has already passed.")
    return starts_at


class EventService(SQLAlchemyAsyncRepositoryService[Event]):
    """Stores and finds events."""

    class Repo(SQLAlchemyAsyncRepository[Event]):
        """Event data access."""

        model_type = Event

    repository_type = Repo

    async def upcoming(self, guild_id: str, now: datetime) -> list[Event]:
        """Events in a server that have not started and are not cancelled."""
        statement = (
            select(Event)
            .where(
                Event.guild_id == guild_id,
                Event.starts_at > now,
                Event.cancelled_at.is_(None),
            )
            .order_by(Event.starts_at)
        )
        return list(await self.repository.get_many(statement=statement))

    async def answer(
        self,
        event: Event,
        *,
        user_id: str,
        name: str,
        status: SignupStatus,
        role: str | None,
    ) -> Event:
        """Record a member's answer. Giving the same answer again removes it."""
        current = next((s for s in event.signups if s.user_id == user_id), None)
        if current is None:
            event.signups.append(
                Signup(user_id=user_id, character_name=name, status=status, role=role)
            )
        elif (current.status, current.role) == (status, role):
            event.signups.remove(current)
        else:
            current.status, current.role, current.character_name = status, role, name
        return await self.update(event)

    async def find(self, event_id: UUID) -> Event | None:
        """An event by ID, with its sign ups."""
        return await self.get_one_or_none(id=event_id)


class GuildSettingsService(SQLAlchemyAsyncRepositoryService[GuildSettings]):
    """Stores per-server settings."""

    class Repo(SQLAlchemyAsyncRepository[GuildSettings]):
        """Guild settings data access."""

        model_type = GuildSettings

    repository_type = Repo

    async def for_guild(self, guild_id: str) -> GuildSettings:
        """A server's settings, with defaults if never changed."""
        found = await self.get_one_or_none(guild_id=guild_id)
        return found or GuildSettings(guild_id=guild_id)

    async def set_event_channel(self, guild_id: str, channel_id: str) -> GuildSettings:
        """Choose where event posts go."""
        settings = await self.get_one_or_none(guild_id=guild_id)
        if settings is None:
            return await self.create(
                GuildSettings(guild_id=guild_id, event_channel_id=channel_id)
            )
        settings.event_channel_id = channel_id
        return await self.update(settings)
