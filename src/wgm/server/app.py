"""Application factory.

Run the server with Granian through the Litestar CLI:

    uv run litestar --app wgm.server.app:create_app run
"""

from advanced_alchemy.extensions.litestar import SQLAlchemyPlugin
from litestar import Litestar
from litestar.datastructures import State

from wgm.db import models  # noqa: F401  (registers the tables)
from wgm.db.config import database_config
from wgm.domain.discord.controllers import DiscordController
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
    return Litestar(
        route_handlers=[SystemController, DiscordController],
        plugins=[
            plugins.granian,
            SQLAlchemyPlugin(config=database_config(settings.database_url)),
        ],
        state=State({"settings": settings}),
    )
