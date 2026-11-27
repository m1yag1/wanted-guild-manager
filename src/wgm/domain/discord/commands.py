"""The /wgm slash command: its definition, who may run each part, and the answers.

The definition is what `inv discord.register-commands` sends to Discord.
See https://discord.com/developers/docs/interactions/application-commands
"""

from datetime import datetime
from typing import Any

from attrs import field, frozen

from wgm.db.models import Event, SignupStatus
from wgm.domain.discord.client import DiscordClient
from wgm.domain.discord.permissions import ADMIN_ROLE, WGM_ROLES, may_run
from wgm.domain.discord.schemas import (
    Interaction,
    InteractionOption,
    InteractionResponse,
    InteractionResponseType,
    MessageData,
    MessageFlags,
)
from wgm.domain.events.services import (
    EVENT_TYPES,
    EventInputError,
    EventService,
    counts,
    parse_start,
)
from wgm.lib.settings import Settings

SUB_COMMAND = 1
SUB_COMMAND_GROUP = 2
STRING = 3


def _text(name: str, description: str, **extra: Any) -> dict[str, Any]:
    return {
        "type": STRING,
        "name": name,
        "description": description,
        "required": True,
        **extra,
    }


@frozen
class Subcommand:
    """One /wgm subcommand, such as `event create`."""

    path: tuple[str, ...]
    description: str
    allowed_roles: tuple[str, ...] = ()
    """Roles that may run it; empty means everyone."""
    options: list[dict[str, Any]] = field(factory=list)
    server_only: bool = True
    """Only makes sense in a server, not in a direct message."""

    @property
    def usage(self) -> str:
        """How it is typed, such as `/wgm event create`."""
        return "/wgm " + " ".join(self.path)


SUBCOMMANDS = (
    Subcommand(("help",), "Show the commands you can use", server_only=False),
    Subcommand(("setup",), f"Create the {ADMIN_ROLE} role", (ADMIN_ROLE,)),
    Subcommand(
        ("event", "create"),
        "Post a new event",
        (ADMIN_ROLE,),
        [
            _text("title", "What the event is called", max_length=100),
            _text(
                "type",
                "Kind of event",
                choices=[{"name": kind, "value": kind} for kind in EVENT_TYPES],
            ),
            _text("date", "Day, like 2026-12-05"),
            _text("time", "24-hour start time in the guild's time zone, like 20:00"),
        ],
    ),
    Subcommand(("event", "list"), "List upcoming events"),
)
BY_PATH = {sub.path: sub for sub in SUBCOMMANDS}


def wgm_command() -> dict[str, Any]:
    """The /wgm definition, with `event ...` as a subcommand group."""
    options: list[dict[str, Any]] = []
    groups: dict[str, dict[str, Any]] = {}
    for sub in SUBCOMMANDS:
        leaf = {
            "type": SUB_COMMAND,
            "name": sub.path[-1],
            "description": sub.description,
            "options": sub.options,
        }
        if len(sub.path) == 1:
            options.append(leaf)
            continue
        group = groups.get(sub.path[0])
        if group is None:
            group = {
                "type": SUB_COMMAND_GROUP,
                "name": sub.path[0],
                "description": f"{sub.path[0].title()} commands",
                "options": [],
            }
            groups[sub.path[0]] = group
            options.append(group)
        group["options"].append(leaf)
    return {
        "name": "wgm",
        "type": 1,
        "description": "Wanted Guild event sign ups",
        "options": options,
    }


COMMANDS = [wgm_command()]


def selected(
    options: list[InteractionOption],
) -> tuple[tuple[str, ...], dict[str, Any]]:
    """The chosen subcommand path and its option values."""
    path: list[str] = []
    while options and options[0].type in (SUB_COMMAND, SUB_COMMAND_GROUP):
        path.append(options[0].name)
        options = options[0].options
    return tuple(path), {option.name: option.value for option in options}


def private_reply(content: str) -> InteractionResponse:
    """A reply only the person who ran the command can see."""
    return InteractionResponse(
        type=InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
        data=MessageData(content=content, flags=MessageFlags.EPHEMERAL),
    )


def public_reply(content: str) -> InteractionResponse:
    """A message everyone in the channel sees."""
    return InteractionResponse(
        type=InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
        data=MessageData(content=content),
    )


def when(moment: datetime) -> str:
    """A Discord timestamp: each reader sees it in their own time zone."""
    seconds = int(moment.timestamp())
    return f"<t:{seconds}:F> (<t:{seconds}:R>)"


def tally(event: Event) -> str:
    """Attending 2 · Tentative 1 · Not attending 0"""
    totals = counts(event)
    return (
        f"Attending {totals[SignupStatus.ATTENDING]} · "
        f"Tentative {totals[SignupStatus.TENTATIVE]} · "
        f"Not attending {totals[SignupStatus.NOT_ATTENDING]}"
    )


def event_post(event: Event) -> str:
    """The public message for an event."""
    heading = f"**{event.title}** · {event.event_type}"
    return f"{heading}\n{when(event.starts_at)}\n{tally(event)}"


@frozen
class CommandContext:
    """Everything a command needs to answer."""

    interaction: Interaction
    settings: Settings
    discord: DiscordClient
    events: EventService
    now: datetime

    @property
    def guild_id(self) -> str:
        """The server; server-only commands never run without one."""
        return self.interaction.guild_id or ""

    @property
    def user_id(self) -> str:
        """Who ran the command."""
        member = self.interaction.member
        return member.user.id if member else ""


async def _role_ids(ctx: CommandContext) -> dict[str, str]:
    if not ctx.interaction.guild_id:
        return {}
    return await ctx.discord.role_ids(ctx.interaction.guild_id)


def _allowed(sub: Subcommand, ctx: CommandContext, role_ids: dict[str, str]) -> bool:
    member = ctx.interaction.member
    if member is None:
        return not sub.allowed_roles
    return may_run(sub.allowed_roles, member.roles, member.permissions, role_ids)


async def help_text(ctx: CommandContext) -> str:
    """The /wgm commands this member may use."""
    restricted = any(sub.allowed_roles for sub in SUBCOMMANDS)
    role_ids = await _role_ids(ctx) if restricted else {}
    lines = [
        f"`{sub.usage}`: {sub.description}"
        for sub in SUBCOMMANDS
        if _allowed(sub, ctx, role_ids)
    ]
    return "**Wanted Guild Manager**\n" + "\n".join(lines)


async def _setup(ctx: CommandContext, values: dict[str, Any]) -> InteractionResponse:
    existing = await ctx.discord.role_ids(ctx.guild_id)
    created = [name for name in WGM_ROLES if name not in existing]
    for name in created:
        await ctx.discord.create_role(ctx.guild_id, name)
    if not created:
        return private_reply("All WGM roles already exist.")
    return private_reply(
        f"Created {', '.join(created)}. Give it to the members who run events."
    )


async def _event_create(
    ctx: CommandContext, values: dict[str, Any]
) -> InteractionResponse:
    try:
        starts_at = parse_start(
            str(values["date"]), str(values["time"]), ctx.settings.timezone, ctx.now
        )
    except EventInputError as error:
        return private_reply(str(error))
    event = await ctx.events.create(
        Event(
            guild_id=ctx.guild_id,
            title=str(values["title"]).strip(),
            event_type=str(values["type"]),
            starts_at=starts_at,
            created_by=ctx.user_id,
            channel_id=ctx.interaction.channel_id,
        )
    )
    return public_reply(event_post(event))


async def _event_list(
    ctx: CommandContext, values: dict[str, Any]
) -> InteractionResponse:
    events = await ctx.events.upcoming(ctx.guild_id, ctx.now)
    posts = [event_post(event) for event in events]
    return private_reply("\n\n".join(posts) or "No upcoming events.")


async def _help(ctx: CommandContext, values: dict[str, Any]) -> InteractionResponse:
    return private_reply(await help_text(ctx))


HANDLERS = {
    ("help",): _help,
    ("setup",): _setup,
    ("event", "create"): _event_create,
    ("event", "list"): _event_list,
}


async def run_command(ctx: CommandContext) -> InteractionResponse:
    """Answer a /wgm slash command."""
    data = ctx.interaction.data
    path, values = selected(data.options if data else [])
    sub = BY_PATH.get(path) if data and data.name == "wgm" else None
    if sub is None:
        return private_reply(f"Unknown command. {await help_text(ctx)}")
    if sub.server_only and not (ctx.interaction.guild_id and ctx.interaction.member):
        return private_reply("Run this in a server.")
    if sub.allowed_roles and not _allowed(sub, ctx, await _role_ids(ctx)):
        roles = " or ".join(sub.allowed_roles)
        return private_reply(f"You need the {roles} role to use `{sub.usage}`.")
    return await HANDLERS[path](ctx, values)
