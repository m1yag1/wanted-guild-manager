"""Event rules and storage."""

from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService
from attrs import frozen
from sqlalchemy import func, select

from wgm.db.models import (
    DEFAULT_CLOSE_MINUTES,
    Event,
    GuildSettings,
    Signup,
    SignupAction,
    SignupChange,
    SignupStatus,
)

EVENT_TYPES = (
    "Siege",
    "Boonstone",
    "Riftstone",
    "Archboss",
    "Guild Raid",
    "Arena",
    "Other",
)
MAX_CLOSE_MINUTES = 7 * 24 * 60
"""Sign-ups can close at most a week before the start."""


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


def closing_time(starts_at: datetime, minutes: int, now: datetime) -> datetime:
    """When sign-ups close: `minutes` before the start, which must be later than now.

    Raises:
        EventInputError: Sign-ups would already be closed.
    """
    closes_at = starts_at - timedelta(minutes=minutes)
    if closes_at <= now:
        raise EventInputError(
            f"Sign-ups would close {minutes} minutes before the start, which has "
            "already passed. Use a later start or a smaller `close`."
        )
    return closes_at


@frozen
class Answer:
    """A member's answer for an event, and who gave it."""

    user_id: str
    name: str
    status: SignupStatus
    role: str | None
    by: str
    """The member themselves, or the admin who set it."""
    reason: str | None = None


@frozen
class NewTimes:
    """What an edit changes about when an event happens. None keeps it."""

    day: str | None = None
    clock: str | None = None
    close: int | None = None
    """Minutes before the start that sign-ups close."""


def reschedule(event: Event, new: NewTimes, zone: ZoneInfo, now: datetime) -> None:
    """Move an event's start and close times. Missing parts stay as they are.

    Moving the start keeps the same gap before sign-ups close unless `close`
    gives a new one. Sign-ups that are still open must stay open. Sign-ups that
    already closed may stay closed, or reopen when the close moves later.

    Raises:
        EventInputError: The new times are malformed, already passed, or would
            close sign-ups that are open now.
    """
    local = event.starts_at.astimezone(zone)
    starts_at = event.starts_at
    if new.day is not None or new.clock is not None:
        starts_at = parse_start(
            new.day or local.date().isoformat(),
            new.clock or f"{local:%H:%M}",
            zone,
            now,
        )
    gap = event.starts_at - (event.closes_at or event.starts_at)
    minutes = new.close if new.close is not None else int(gap.total_seconds() // 60)
    closes_at = starts_at - timedelta(minutes=minutes)
    was_open = now < (event.closes_at or event.starts_at)
    if was_open:
        closes_at = closing_time(starts_at, minutes, now)
    event.starts_at, event.closes_at = starts_at, closes_at
    if closes_at > now:
        event.closed_post_at = None


class EventService(SQLAlchemyAsyncRepositoryService[Event]):
    """Stores and finds events."""

    class Repo(SQLAlchemyAsyncRepository[Event]):
        """Event data access."""

        model_type = Event

    repository_type = Repo

    async def upcoming(
        self, guild_id: str, now: datetime, *, cancelled: bool = False
    ) -> list[Event]:
        """Events in a server that have not started, soonest first.

        Deleted events are never included, and cancelled ones only on request.
        """
        statement = (
            select(Event)
            .where(
                Event.guild_id == guild_id,
                Event.starts_at > now,
                Event.deleted_at.is_(None),
            )
            .order_by(Event.starts_at)
        )
        if not cancelled:
            statement = statement.where(Event.cancelled_at.is_(None))
        return list(await self.repository.get_many(statement=statement))

    def signup(self, event: Event, user_id: str) -> Signup | None:
        """A member's current answer for an event, if any."""
        return next((s for s in event.signups if s.user_id == user_id), None)

    async def set_answer(self, event: Event, answer: Answer, now: datetime) -> Event:
        """Record a member's answer, replacing any earlier one, and log it.

        Changes after sign-ups close are marked late.
        """
        late = now >= (event.closes_at or event.starts_at)
        current = self.signup(event, answer.user_id)
        action = SignupAction.CHANGED
        if current is None:
            action = SignupAction.ADDED
            current = Signup(user_id=answer.user_id)
            event.signups.append(current)
        current.character_name, current.status, current.role = (
            answer.name,
            answer.status,
            answer.role,
        )
        current.reason = answer.reason
        current.changed_by, current.late = answer.by, late
        self._log(event, current, action, answer.by, late)
        return await self.update(event)

    async def remove_answer(
        self, event: Event, user_id: str, by: str, now: datetime
    ) -> Event:
        """Take a member off the roster and log it. Does nothing if not on it."""
        current = self.signup(event, user_id)
        if current is not None:
            event.signups.remove(current)
            late = now >= (event.closes_at or event.starts_at)
            self._log(event, current, SignupAction.REMOVED, by, late)
        return await self.update(event)

    def _log(
        self,
        event: Event,
        signup: Signup,
        action: SignupAction,
        by: str,
        late: bool,  # noqa: FBT001
    ) -> None:
        removed = action is SignupAction.REMOVED
        self.repository.session.add(
            SignupChange(
                event_id=event.id,
                user_id=signup.user_id,
                character_name=signup.character_name,
                action=action,
                status=None if removed else signup.status,
                role=None if removed else signup.role,
                changed_by=by,
                late=late,
            )
        )

    async def history(self, event: Event) -> list[SignupChange]:
        """Every roster change for an event, oldest first."""
        statement = (
            select(SignupChange)
            .where(SignupChange.event_id == event.id)
            .order_by(SignupChange.created_at)
        )
        result = await self.repository.session.execute(statement)
        return list(result.scalars())

    async def find(self, event_id: UUID) -> Event | None:
        """An event by ID, with its sign ups. Deleted events aren't found."""
        return await self.get_one_or_none(id=event_id, deleted_at=None)

    async def in_guild(self, event_id: str, guild_id: str) -> Event | None:
        """An event in this server by its ID as text, or None."""
        try:
            found = await self.find(UUID(event_id))
        except ValueError:
            return None
        return found if found and found.guild_id == guild_id else None

    async def due_to_lock(self, now: datetime) -> list[Event]:
        """Posted events whose sign-ups have closed but whose post still has buttons."""
        statement = select(Event).where(
            func.coalesce(Event.closes_at, Event.starts_at) <= now,
            Event.closed_post_at.is_(None),
            Event.message_id.is_not(None),
            Event.cancelled_at.is_(None),
            Event.deleted_at.is_(None),
        )
        return list(await self.repository.get_many(statement=statement))


class GuildSettingsService(SQLAlchemyAsyncRepositoryService[GuildSettings]):
    """Stores per-server settings."""

    class Repo(SQLAlchemyAsyncRepository[GuildSettings]):
        """Guild settings data access."""

        model_type = GuildSettings

    repository_type = Repo

    async def for_guild(self, guild_id: str) -> GuildSettings:
        """A server's settings, with defaults if never changed."""
        found = await self.get_one_or_none(guild_id=guild_id)
        return found or GuildSettings(
            guild_id=guild_id, close_minutes=DEFAULT_CLOSE_MINUTES
        )

    async def _change(self, guild_id: str, **values: Any) -> GuildSettings:
        settings = await self.get_one_or_none(guild_id=guild_id)
        if settings is None:
            return await self.create(GuildSettings(guild_id=guild_id, **values))
        for name, value in values.items():
            setattr(settings, name, value)
        return await self.update(settings)

    async def set_event_channel(self, guild_id: str, channel_id: str) -> GuildSettings:
        """Choose where event posts go."""
        return await self._change(guild_id, event_channel_id=channel_id)

    async def set_close_minutes(self, guild_id: str, minutes: int) -> GuildSettings:
        """Choose how long before the start sign-ups close, for new events."""
        return await self._change(guild_id, close_minutes=minutes)
