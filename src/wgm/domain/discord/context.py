"""What every /wgm command and button handler gets, and how they reply."""

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any

from attrs import field, frozen
from sqlalchemy.ext.asyncio import AsyncSession

from wgm.domain.discord.client import DiscordClient
from wgm.domain.discord.permissions import may_run
from wgm.domain.discord.schemas import (
    Interaction,
    InteractionResponse,
    InteractionResponseType,
    MessageData,
    MessageFlags,
    ModalResponse,
)
from wgm.lib.settings import Settings

if TYPE_CHECKING:
    from wgm.plugins import Plugins

NO_PINGS: dict[str, list[str]] = {"parse": []}


def private_reply(content: str) -> InteractionResponse:
    """A reply only the person who ran the command can see."""
    return InteractionResponse(
        type=InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
        data=MessageData(
            content=content, flags=MessageFlags.EPHEMERAL, allowed_mentions=NO_PINGS
        ),
    )


@frozen
class CommandContext:
    """Everything a command or button press needs to answer."""

    interaction: Interaction
    settings: Settings
    discord: DiscordClient
    session: AsyncSession
    now: datetime
    plugins: "Plugins"

    @property
    def guild_id(self) -> str:
        """The server; server-only commands never run without one."""
        return self.interaction.guild_id or ""

    @property
    def user_id(self) -> str:
        """Who ran the command."""
        member = self.interaction.member
        return member.user.id if member else ""

    async def may(self, roles: tuple[str, ...]) -> bool:
        """Whether the member has one of `roles` (or Manage Server).

        Only for server-only commands, which always run with a member.
        """
        member = self.interaction.member
        role_ids = await self.discord.role_ids(self.guild_id)
        return may_run(
            roles,
            member.roles if member else [],
            member.permissions if member else "0",
            role_ids,
        )


Handler = Callable[[CommandContext, dict[str, Any]], Awaitable[InteractionResponse]]
"""Answers one subcommand, given its option values."""
ButtonHandler = Callable[
    [CommandContext], Awaitable[InteractionResponse | ModalResponse]
]
"""Answers a button press or a submitted form, which may open a form."""
Suggest = Callable[[CommandContext, str, str], Awaitable[list[tuple[str, str]]]]
"""Suggestions for an option, given its name and what was typed so far:
(what the member sees, the value sent) pairs."""


@frozen
class Subcommand:
    """One /wgm subcommand, such as `event create`."""

    path: tuple[str, ...]
    description: str
    handler: Handler
    allowed_roles: tuple[str, ...] = ()
    """Roles that may run it; empty means everyone."""
    options: list[dict[str, Any]] = field(factory=list)
    server_only: bool = True
    """Only makes sense in a server, not in a direct message."""
    suggest: Suggest | None = None
    """Answers options marked `autocomplete` as the member types."""

    @property
    def usage(self) -> str:
        """How it is typed, such as `/wgm event create`."""
        return "/wgm " + " ".join(self.path)
