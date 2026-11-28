"""Locking event posts once sign-ups close."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from advanced_alchemy.alembic.commands import AlembicCommands
from advanced_alchemy.extensions.litestar import SQLAlchemyAsyncConfig

from tests.fixtures.discord import post_buttons, post_words
from tests.fixtures.discord_api import FakeDiscordApi
from wgm.db.config import database_config
from wgm.db.models import Event
from wgm.domain.discord.client import DiscordClient
from wgm.domain.events.closing import close_job, lock_closed_posts
from wgm.domain.events.services import EventService
from wgm.plugins import JobContext

NOW = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)


@pytest.fixture
def config(database_url: str) -> SQLAlchemyAsyncConfig:
    config = database_config(database_url)
    AlembicCommands(sqlalchemy_config=config).upgrade()
    return config


@pytest.fixture
async def discord(discord_api: FakeDiscordApi) -> AsyncIterator[DiscordClient]:
    async with httpx.AsyncClient() as http:
        yield DiscordClient("test-token", discord_api.url, http)


async def _post(
    config: SQLAlchemyAsyncConfig, message_id: str, **extra: object
) -> None:
    async with config.get_session() as session:
        await EventService(session=session).create(
            Event(
                guild_id="1",
                title=f"Event {message_id}",
                starts_at=NOW + timedelta(minutes=10),
                created_by="42",
                channel_id="7",
                message_id=message_id,
                **extra,
            ),
            auto_commit=True,
        )


async def _locked(config: SQLAlchemyAsyncConfig) -> dict[str, datetime | None]:
    async with config.get_session() as session:
        events = await EventService(session=session).get_many()
    return {event.message_id or "": event.closed_post_at for event in events}


@pytest.mark.anyio
async def test_closed_posts_are_locked_once(
    config: SQLAlchemyAsyncConfig,
    discord: DiscordClient,
    discord_api: FakeDiscordApi,
) -> None:
    await _post(config, "1", closes_at=NOW - timedelta(minutes=20))
    await _post(config, "2", closes_at=NOW + timedelta(minutes=5))

    first = await lock_closed_posts(config, discord, NOW)
    second = await lock_closed_posts(config, discord, NOW)

    assert (first, second) == (1, 0)
    edit = discord_api.requests[-1]
    assert (edit.method, edit.path) == ("PATCH", "/channels/7/messages/1")
    assert "Sign-ups closed <t:" in post_words(edit.body)
    assert all(b["disabled"] for b in post_buttons(edit.body))
    assert edit.body["allowed_mentions"] == {"parse": []}
    assert await _locked(config) == {"1": NOW, "2": None}


@pytest.mark.anyio
async def test_deleted_posts_stop_being_retried_and_other_errors_are(
    config: SQLAlchemyAsyncConfig,
    discord: DiscordClient,
    discord_api: FakeDiscordApi,
) -> None:
    closed = NOW - timedelta(minutes=1)
    await _post(config, "1", closes_at=closed)
    await _post(config, "2", closes_at=closed)
    await _post(config, "3", closes_at=closed)
    discord_api.responses["PATCH /channels/7/messages/1"] = (404, {"code": 10008})
    discord_api.responses["PATCH /channels/7/messages/2"] = (500, {})
    discord_api.responses["PATCH /channels/7/messages/3"] = (400, {"code": 50035})

    locked = await lock_closed_posts(config, discord, NOW)

    assert locked == 0
    assert await _locked(config) == {"1": NOW, "2": None, "3": NOW}


@pytest.mark.anyio
async def test_the_close_job_locks_as_of_its_clock(
    config: SQLAlchemyAsyncConfig, discord: DiscordClient
) -> None:
    await _post(config, "1", closes_at=NOW - timedelta(minutes=1))
    earlier = JobContext(config, discord, {}, clock=lambda: NOW - timedelta(hours=1))
    now = JobContext(config, discord, {}, clock=lambda: NOW)
    real = JobContext(config, discord, {})

    assert await close_job(earlier) == 0
    assert await close_job(now) == 1
    assert await close_job(real) == 0
