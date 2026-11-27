"""Locking event posts once sign-ups close."""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from advanced_alchemy.alembic.commands import AlembicCommands
from advanced_alchemy.extensions.litestar import SQLAlchemyAsyncConfig

from tests.fixtures.discord_api import FakeDiscordApi
from wgm.db.config import database_config
from wgm.db.models import Event
from wgm.domain.discord.client import DiscordClient
from wgm.domain.events.closing import closing_job, lock_closed_posts, repeat
from wgm.domain.events.services import EventService

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
                event_type="Siege",
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
    assert "Sign-ups closed <t:" in edit.body["content"]
    assert all(b["disabled"] for b in edit.body["components"][0]["components"])
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
    discord_api.responses["PATCH /channels/7/messages/1"] = (404, {"code": 10008})
    discord_api.responses["PATCH /channels/7/messages/2"] = (500, {})

    locked = await lock_closed_posts(config, discord, NOW)

    assert locked == 0
    assert await _locked(config) == {"1": NOW, "2": None}


@pytest.mark.anyio
async def test_closing_job_uses_the_current_time(
    config: SQLAlchemyAsyncConfig, discord: DiscordClient
) -> None:
    await _post(config, "1", closes_at=datetime.now(UTC) - timedelta(minutes=1))

    assert await closing_job(config, discord)() == 1


@pytest.mark.anyio
async def test_repeat_keeps_going_after_a_failure() -> None:
    runs: list[int] = []

    async def job() -> None:
        runs.append(len(runs))
        if len(runs) == 1:
            raise RuntimeError("boom")

    task = asyncio.create_task(repeat(0, job))
    while len(runs) < 3:  # noqa: ASYNC110
        await asyncio.sleep(0)
    task.cancel()

    assert runs[:3] == [0, 1, 2]
