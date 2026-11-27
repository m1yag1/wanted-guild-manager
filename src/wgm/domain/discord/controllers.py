"""The endpoint Discord sends interactions to."""

from datetime import UTC, datetime

from litestar import Controller, Response, post
from litestar.background_tasks import BackgroundTask
from litestar.datastructures import State
from litestar.di import NamedDependency
from litestar.exceptions import ClientException
from litestar.params import JSONBody
from litestar.status_codes import HTTP_200_OK
from sqlalchemy.ext.asyncio import AsyncSession

from wgm.domain.discord.buttons import press
from wgm.domain.discord.client import DiscordClient
from wgm.domain.discord.commands import CommandContext
from wgm.domain.discord.deferred import finish_command
from wgm.domain.discord.guards import require_discord_signature
from wgm.domain.discord.schemas import (
    Interaction,
    InteractionResponse,
    InteractionResponseType,
    InteractionType,
    MessageData,
    MessageFlags,
)
from wgm.domain.events.services import EventService, GuildSettingsService
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
    ) -> Response[InteractionResponse]:
        """Answer an interaction.

        Discord sends a PING when the endpoint URL is saved, and expects a PONG.

        Raises:
            ClientException: The interaction type is not handled yet.
        """
        if data.type is InteractionType.PING:
            return Response(InteractionResponse(type=InteractionResponseType.PONG))
        if data.type not in (
            InteractionType.APPLICATION_COMMAND,
            InteractionType.MESSAGE_COMPONENT,
        ):
            raise ClientException(f"Unsupported interaction type: {data.type.name}")
        settings: Settings = state.settings
        discord: DiscordClient = state.discord
        if data.type is InteractionType.APPLICATION_COMMAND:
            return Response(
                InteractionResponse(
                    type=InteractionResponseType.DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE,
                    data=MessageData(flags=MessageFlags.EPHEMERAL),
                ),
                background=BackgroundTask(
                    finish_command, data, settings, discord, state.db_config
                ),
            )
        ctx = CommandContext(
            interaction=data,
            settings=settings,
            discord=discord,
            events=EventService(session=db_session),
            guilds=GuildSettingsService(session=db_session),
            now=datetime.now(UTC),
        )
        return Response(await press(ctx))
