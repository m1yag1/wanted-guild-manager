"""The endpoint Discord sends interactions to."""

from datetime import UTC, datetime

from litestar import Controller, Response, post
from litestar.background_tasks import BackgroundTask
from litestar.datastructures import State
from litestar.di import NamedDependency
from litestar.params import JSONBody
from litestar.status_codes import HTTP_200_OK
from sqlalchemy.ext.asyncio import AsyncSession

from wgm.domain.discord.client import DiscordClient
from wgm.domain.discord.commands import press_button, suggest
from wgm.domain.discord.context import CommandContext
from wgm.domain.discord.deferred import finish_command
from wgm.domain.discord.guards import require_discord_signature
from wgm.domain.discord.schemas import (
    AutocompleteResponse,
    Interaction,
    InteractionResponse,
    InteractionResponseType,
    InteractionType,
    MessageData,
    MessageFlags,
    ModalResponse,
)
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
    ) -> Response[InteractionResponse | AutocompleteResponse | ModalResponse]:
        """Answer an interaction.

        Discord sends a PING when the endpoint URL is saved, and expects a PONG.
        Buttons and submitted forms go to the plugin owning their custom_id.
        """
        if data.type is InteractionType.PING:
            return Response(InteractionResponse(type=InteractionResponseType.PONG))
        settings: Settings = state.settings
        discord: DiscordClient = state.discord
        if data.type is InteractionType.APPLICATION_COMMAND:
            return Response(
                InteractionResponse(
                    type=InteractionResponseType.DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE,
                    data=MessageData(flags=MessageFlags.EPHEMERAL),
                ),
                background=BackgroundTask(
                    finish_command,
                    data,
                    settings,
                    discord,
                    state.db_config,
                    state.plugins,
                ),
            )
        ctx = CommandContext(
            interaction=data,
            settings=settings,
            discord=discord,
            session=db_session,
            now=datetime.now(UTC),
            plugins=state.plugins,
        )
        if data.type is InteractionType.APPLICATION_COMMAND_AUTOCOMPLETE:
            return Response(await suggest(ctx))
        return Response(await press_button(ctx))
