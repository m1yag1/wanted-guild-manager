"""The endpoint Discord sends interactions to."""

from litestar import Controller, post
from litestar.exceptions import ClientException
from litestar.params import JSONBody
from litestar.status_codes import HTTP_200_OK

from wgm.domain.discord.commands import run_command
from wgm.domain.discord.guards import require_discord_signature
from wgm.domain.discord.schemas import (
    Interaction,
    InteractionResponse,
    InteractionResponseType,
    InteractionType,
)


class DiscordController(Controller):
    """Receives signed interactions from Discord."""

    path = "/discord"
    tags = ["Discord"]
    guards = [require_discord_signature]

    @post("/interactions", status_code=HTTP_200_OK)
    async def interactions(self, data: JSONBody[Interaction]) -> InteractionResponse:
        """Answer an interaction.

        Discord sends a PING when the endpoint URL is saved, and expects a PONG.

        Raises:
            ClientException: The interaction type is not handled yet.
        """
        if data.type is InteractionType.PING:
            return InteractionResponse(type=InteractionResponseType.PONG)
        if data.type is InteractionType.APPLICATION_COMMAND and data.data:
            return run_command(data.data)
        raise ClientException(f"Unsupported interaction type: {data.type.name}")
