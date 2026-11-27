"""Application factory.

Run the server with Granian through the Litestar CLI:

    uv run litestar --app wgm.server.app:create_app run
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from advanced_alchemy.extensions.litestar import SQLAlchemyPlugin
from litestar import Litestar
from litestar.datastructures import State

from wgm.db import models  # noqa: F401  (registers the tables)
from wgm.db.config import database_config
from wgm.domain.discord.client import DiscordClient
from wgm.domain.discord.controllers import DiscordController
from wgm.domain.events.closing import CHECK_SECONDS, closing_job, repeat
from wgm.domain.system.controllers import SystemController
from wgm.lib.settings import Settings, load_settings
from wgm.server import plugins


def create_app(settings: Settings | None = None) -> Litestar:
    """Build the Litestar application.

    Args:
        settings: Settings to use. Defaults to `load_settings()`, which reads
            `.env` and the environment.

    Returns:
        The configured application.
    """
    settings = settings or load_settings()
    db = database_config(settings.database_url)

    @asynccontextmanager
    async def discord_client(app: Litestar) -> AsyncIterator[None]:
        """One Discord API client, with pooled connections, for the app's life."""
        async with httpx.AsyncClient(timeout=10) as http:
            app.state.discord = DiscordClient(
                settings.discord.bot_token, settings.discord.api_url, http
            )
            yield

    @asynccontextmanager
    async def close_sign_ups(app: Litestar) -> AsyncIterator[None]:
        """Lock event posts as their sign-ups close, while the app runs."""
        task = asyncio.create_task(
            repeat(CHECK_SECONDS, closing_job(db, app.state.discord))
        )
        yield
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    return Litestar(
        route_handlers=[SystemController, DiscordController],
        plugins=[plugins.granian, SQLAlchemyPlugin(config=db)],
        lifespan=[discord_client, close_sign_ups],
        state=State({"settings": settings, "db_config": db}),
    )
