"""Event rules and storage."""

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService
from sqlalchemy import select

from wgm.db.models import Event, SignupStatus

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


def counts(event: Event) -> dict[SignupStatus, int]:
    """How many members gave each answer."""
    totals = dict.fromkeys(SignupStatus, 0)
    for signup in event.signups:
        totals[signup.status] += 1
    return totals


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
