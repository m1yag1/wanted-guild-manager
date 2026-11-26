"""Health check routes."""

import msgspec
from litestar import Controller, get


class PingResponse(msgspec.Struct):
    """Body of a successful health check."""

    message: str


class HealthController(Controller):
    """Routes that report whether the server is up."""

    tags = ["Health"]

    @get("/ping")
    async def ping(self) -> PingResponse:
        """Answer a health check.

        Returns:
            A response whose message is always "pong!".
        """
        return PingResponse(message="pong!")
