"""Fixtures for building the application under test."""

from pathlib import Path

import pytest
from advanced_alchemy.alembic.commands import AlembicCommands
from litestar import Litestar
from nacl.signing import SigningKey

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
