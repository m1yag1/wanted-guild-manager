"""Fixtures for building the application under test."""

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest
from advanced_alchemy.alembic.commands import AlembicCommands
from litestar import Litestar
from litestar.testing import AsyncTestClient
from nacl.signing import SigningKey

from tests.fixtures.discord import Sign
from tests.fixtures.discord_api import FakeDiscordApi
from wgm.db.config import database_config
from wgm.lib.settings import DiscordSettings, Settings
from wgm.server.app import create_app


@pytest.fixture
def anyio_backend() -> str:
    """Run async tests on asyncio only."""
    return "asyncio"


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    """A SQLite database in a temporary folder."""
    return f"sqlite+aiosqlite:///{tmp_path / 'wgm.db'}"


@pytest.fixture
def settings(
    signing_key: SigningKey, database_url: str, discord_api: FakeDiscordApi
) -> Settings:
    """Settings whose Discord key matches `signing_key` and API is the local fake."""
    return Settings(
        discord=DiscordSettings(
            public_key=signing_key.verify_key.encode().hex(),
            bot_token="test-token",
            api_url=discord_api.url,
        ),
        database_url=database_url,
    )


@pytest.fixture
def app(settings: Settings) -> Litestar:
    """The application built with test settings, on a migrated database."""
    AlembicCommands(sqlalchemy_config=database_config(settings.database_url)).upgrade()
    return create_app(settings)


Interact = Callable[[bytes], Awaitable[dict[str, Any]]]


@pytest.fixture
def interact(app: Litestar, sign: Sign, discord_api: FakeDiscordApi) -> Interact:
    """Send a signed interaction and return what the member ends up seeing.

    Slash commands answer "thinking..." first and then edit in the real reply
    through Discord's API, so for those this returns that edited-in reply.
    """

    async def send(body: bytes) -> dict[str, Any]:
        signed, headers = sign(body)
        async with AsyncTestClient(app=app) as client:
            response = await client.post(
                "/discord/interactions", content=signed, headers=headers
            )
        assert response.status_code == 200, response.text
        reply: dict[str, Any] = response.json()
        if reply["type"] != 5:
            return reply
        edit = [r for r in discord_api.requests if r.method == "PATCH"][-1]
        assert edit.path.endswith("/messages/@original")
        return {"type": 4, "data": edit.body}

    return send
