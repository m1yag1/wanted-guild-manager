"""System routes."""

from litestar import Controller, get

from wgm.domain.system.schemas import PingResponse


class SystemController(Controller):
    """Routes that report whether the server is up."""

    tags = ["System"]

    @get("/ping")
    async def ping(self) -> PingResponse:
        """Answer a health check.

        Returns:
            A response whose message is always "pong!".
        """
        return PingResponse(message="pong!")
