"""Fixtures for building the application under test."""

from pathlib import Path

import pytest
from litestar import Litestar
from nacl.signing import SigningKey

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
def settings(signing_key: SigningKey, database_url: str) -> Settings:
    """Settings whose Discord public key matches `signing_key`."""
    return Settings(
        discord=DiscordSettings(public_key=signing_key.verify_key.encode().hex()),
        database_url=database_url,
    )


@pytest.fixture
def app(settings: Settings) -> Litestar:
    """The application built with test settings."""
    return create_app(settings)
