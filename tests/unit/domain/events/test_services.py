from datetime import UTC, datetime, timedelta

import pytest
from advanced_alchemy.alembic.commands import AlembicCommands
from advanced_alchemy.extensions.litestar import SQLAlchemyAsyncConfig

from wgm.db.config import database_config
from wgm.db.models import Event
from wgm.domain.events.services import (
    EventInputError,
    EventService,
    GuildSettingsService,
    closing_time,
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
        event_type="Siege",
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
