"""Application factory.

Run the server with Granian through the Litestar CLI:

    uv run litestar --app wgm.server.app:create_app run
"""

from litestar import Litestar

from wgm.domain.system.controllers import SystemController
from wgm.server import plugins


def create_app() -> Litestar:
    """Build the Litestar application.

    Returns:
        The configured application.
    """
    return Litestar(
        route_handlers=[SystemController],
        plugins=[plugins.granian],
    )
