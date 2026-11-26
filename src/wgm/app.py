"""Application factory.

Run the server with Granian through the Litestar CLI:

    uv run litestar --app wgm.app:create_app run
"""

from litestar import Litestar
from litestar_granian import GranianPlugin

from wgm.health import HealthController


def create_app() -> Litestar:
    """Build the Litestar application.

    Returns:
        The configured application.
    """
    return Litestar(
        route_handlers=[HealthController],
        plugins=[GranianPlugin()],
    )
