"""The endpoint Discord sends interactions to."""

from datetime import UTC, datetime

from litestar import Controller, post
from litestar.datastructures import State
from litestar.di import NamedDependency
from litestar.exceptions import ClientException
from litestar.params import JSONBody
from litestar.status_codes import HTTP_200_OK
from sqlalchemy.ext.asyncio import AsyncSession

from wgm.domain.discord.client import DiscordClient
from wgm.domain.discord.commands import CommandContext, run_command
from wgm.domain.discord.guards import require_discord_signature
from wgm.domain.discord.schemas import (
    Interaction,
    InteractionResponse,
    InteractionResponseType,
    InteractionType,
)
from wgm.domain.events.services import EventService
from wgm.lib.settings import Settings


class DiscordController(Controller):
    """Receives signed interactions from Discord."""

    path = "/discord"
    tags = ["Discord"]
    guards = [require_discord_signature]

    @post("/interactions", status_code=HTTP_200_OK)
    async def interactions(
        self,
        data: JSONBody[Interaction],
        state: State,
        db_session: NamedDependency[AsyncSession],
    ) -> InteractionResponse:
        """Answer an interaction.

        Discord sends a PING when the endpoint URL is saved, and expects a PONG.

        Raises:
            ClientException: The interaction type is not handled yet.
        """
        if data.type is InteractionType.PING:
            return InteractionResponse(type=InteractionResponseType.PONG)
        if data.type is InteractionType.APPLICATION_COMMAND and data.data:
            settings: Settings = state.settings
            return await run_command(
                CommandContext(
                    interaction=data,
                    settings=settings,
                    discord=DiscordClient(
                        settings.discord.bot_token, settings.discord.api_url
                    ),
                    events=EventService(session=db_session),
                    now=datetime.now(UTC),
                )
            )
        raise ClientException(f"Unsupported interaction type: {data.type.name}")
