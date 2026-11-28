from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from advanced_alchemy.alembic.commands import AlembicCommands
from advanced_alchemy.extensions.litestar import SQLAlchemyAsyncConfig

from wgm.db.config import database_config
from wgm.db.models import Event
from wgm.domain.events.services import (
    EventInputError,
    EventService,
    GuildSettingsService,
    NewTimes,
    closing_time,
    reschedule,
)

NOW = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)


@pytest.fixture
def config(database_url: str) -> SQLAlchemyAsyncConfig:
    config = database_config(database_url)
    AlembicCommands(sqlalchemy_config=config).upgrade()
    return config


def _event(title: str, hours: int, guild: str = "1", **extra: object) -> Event:
    return Event(
        guild_id=guild,
        title=title,
        starts_at=NOW + timedelta(hours=hours),
        created_by="42",
        **extra,
    )


@pytest.mark.anyio
async def test_upcoming_lists_future_events_in_this_server_soonest_first(
    config: SQLAlchemyAsyncConfig,
) -> None:
    async with config.get_session() as session:
        events = EventService(session=session)
        for event in [
            _event("Later", 48),
            _event("Sooner", 2),
            _event("Past", -2),
            _event("Other server", 3, guild="2"),
            _event("Cancelled", 4, cancelled_at=NOW),
            _event("Deleted", 5, deleted_at=NOW),
        ]:
            await events.create(event)

        upcoming = await events.upcoming("1", NOW)

    assert [event.title for event in upcoming] == ["Sooner", "Later"]


def test_sign_ups_close_the_chosen_minutes_before_the_start() -> None:
    starts = NOW + timedelta(hours=2)

    assert closing_time(starts, 30, NOW) == starts - timedelta(minutes=30)
    assert closing_time(starts, 0, NOW) == starts


def test_a_close_time_already_passed_is_refused() -> None:
    with pytest.raises(EventInputError, match="already passed"):
        closing_time(NOW + timedelta(minutes=20), 30, NOW)


@pytest.mark.anyio
async def test_due_to_lock_finds_closed_posts_not_yet_locked(
    config: SQLAlchemyAsyncConfig,
) -> None:
    posted = {"channel_id": "7", "message_id": "8"}
    async with config.get_session() as session:
        events = EventService(session=session)
        for event in [
            _event("Closed", 1, closes_at=NOW - timedelta(minutes=1), **posted),
            _event("Started, made before closing existed", -1, **posted),
            _event("Still open", 1, closes_at=NOW + timedelta(minutes=1), **posted),
            _event("Never posted", -1),
            _event("Already locked", -1, closed_post_at=NOW, **posted),
            _event("Cancelled", -1, cancelled_at=NOW, **posted),
            _event("Deleted", -1, deleted_at=NOW, **posted),
        ]:
            await events.create(event)

        due = await events.due_to_lock(NOW)

    assert sorted(event.title for event in due) == [
        "Closed",
        "Started, made before closing existed",
    ]


@pytest.mark.anyio
async def test_close_minutes_default_to_30_and_can_change(
    config: SQLAlchemyAsyncConfig,
) -> None:
    async with config.get_session() as session:
        guilds = GuildSettingsService(session=session)
        before = await guilds.for_guild("1")
        await guilds.set_close_minutes("1", 60)
        await guilds.set_event_channel("1", "7")
        after = await guilds.for_guild("1")

    assert before.close_minutes == 30
    assert (after.close_minutes, after.event_channel_id) == (60, "7")


EASTERN = ZoneInfo("America/New_York")


def _scheduled(hours: float, close_minutes: int | None = 30) -> Event:
    event = _event("Siege", 0)
    event.starts_at = NOW + timedelta(hours=hours)
    if close_minutes is not None:
        event.closes_at = event.starts_at - timedelta(minutes=close_minutes)
    return event


def test_moving_the_start_keeps_the_close_gap() -> None:
    event = _scheduled(2)
    # NOW is 07:00 Eastern; 09:30 Eastern is 2.5 hours from NOW.
    reschedule(event, NewTimes(clock="09:30"), EASTERN, NOW)

    assert event.starts_at == NOW + timedelta(hours=2.5)
    assert event.closes_at == NOW + timedelta(hours=2)


def test_a_new_date_keeps_the_time_and_a_new_close_replaces_the_gap() -> None:
    event = _scheduled(2)

    reschedule(event, NewTimes(day="2026-11-28", close=60), EASTERN, NOW)

    assert event.starts_at == NOW + timedelta(days=1, hours=2)
    assert event.closes_at == event.starts_at - timedelta(minutes=60)


def test_events_without_a_close_time_get_one_at_the_start() -> None:
    event = _scheduled(2, close_minutes=None)

    reschedule(event, NewTimes(clock="10:00"), EASTERN, NOW)

    assert event.closes_at == event.starts_at


def test_open_sign_ups_cannot_be_closed_by_an_edit() -> None:
    event = _scheduled(2)

    with pytest.raises(EventInputError, match="already passed"):
        reschedule(event, NewTimes(close=150), EASTERN, NOW)


def test_closed_sign_ups_reopen_when_moved_later_or_stay_closed() -> None:
    reopened, still_closed = _scheduled(0.25), _scheduled(0.25)
    for event in (reopened, still_closed):
        event.closed_post_at = NOW

    reschedule(reopened, NewTimes(day="2026-11-28"), EASTERN, NOW)
    reschedule(still_closed, NewTimes(close=60), EASTERN, NOW)

    assert reopened.closed_post_at is None
    assert reopened.closes_at == reopened.starts_at - timedelta(minutes=30)
    assert still_closed.closed_post_at == NOW
    assert still_closed.closes_at == NOW - timedelta(minutes=45)


@pytest.mark.anyio
async def test_in_guild_finds_events_only_in_their_server(
    config: SQLAlchemyAsyncConfig,
) -> None:
    async with config.get_session() as session:
        events = EventService(session=session)
        event = await events.create(_event("Siege", 2))

        found = await events.in_guild(str(event.id), "1")
        other = await events.in_guild(str(event.id), "2")
        garbled = await events.in_guild("Siege night", "1")

    assert (found, other, garbled) == (event, None, None)


@pytest.mark.anyio
async def test_removing_someone_not_on_the_roster_changes_nothing(
    config: SQLAlchemyAsyncConfig,
) -> None:
    async with config.get_session() as session:
        events = EventService(session=session)
        event = await events.create(_event("Siege", 2))

        event = await events.remove_answer(event, "nobody", "42", NOW)
        history = await events.history(event)

    assert (event.signups, history) == ([], [])
