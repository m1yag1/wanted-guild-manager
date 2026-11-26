"""The Litestar application.

Run it with Granian:

    uv run granian --interface asgi wgm.app:app
"""

from litestar import Litestar, get


@get("/ping")
async def ping() -> dict[str, str]:
    """Answer a health check."""
    return {"message": "pong!"}


app = Litestar(route_handlers=[ping])
