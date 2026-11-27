"""Finish slash commands after telling Discord we are working on them.

Discord waits only 3 seconds for an answer. Commands that call Discord's API or
the database answer "thinking..." at once, then run here and edit the reply in.
"""

import logging
from datetime import UTC, datetime

import msgspec
from advanced_alchemy.extensions.litestar import SQLAlchemyAsyncConfig

from wgm.domain.discord.client import DiscordClient
from wgm.domain.discord.commands import run_command
from wgm.domain.discord.context import CommandContext, private_reply
from wgm.domain.discord.schemas import Interaction, InteractionResponse
from wgm.lib.settings import Settings
from wgm.plugins import Plugins

logger = logging.getLogger(__name__)


async def finish_command(
    interaction: Interaction,
    settings: Settings,
    discord: DiscordClient,
    db: SQLAlchemyAsyncConfig,
    plugins: Plugins,
) -> None:
    """Run the command in its own session and edit the real reply in."""
    async with db.get_session() as session:
        ctx = CommandContext(
            interaction=interaction,
            settings=settings,
            discord=discord,
            session=session,
            now=datetime.now(UTC),
            plugins=plugins,
        )
        reply: InteractionResponse
        try:
            reply = await run_command(ctx)
            await session.commit()
        except Exception:
            logger.exception("/wgm command failed")
            await session.rollback()
            reply = private_reply("Something went wrong. Please try again.")
    await discord.edit_original(
        interaction.application_id, interaction.token, msgspec.to_builtins(reply.data)
    )
