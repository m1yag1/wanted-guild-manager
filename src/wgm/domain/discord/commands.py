"""The /wgm slash command: its definition, who may run each part, and the answers.

The definition is what `inv discord.register-commands` sends to Discord.
See https://discord.com/developers/docs/interactions/application-commands
"""

from datetime import datetime
from typing import Any

from attrs import field, frozen

from wgm.db.models import Event
from wgm.domain.discord.channel_check import ChannelCheck, check_channel
from wgm.domain.discord.client import DiscordApiError, DiscordClient
from wgm.domain.discord.permissions import ADMIN_ROLE, WGM_ROLES, may_run
from wgm.domain.discord.schemas import (
    Interaction,
    InteractionOption,
    InteractionResponse,
    InteractionResponseType,
    MessageData,
    MessageFlags,
)
from wgm.domain.events.roster import (
    buttons,
    closing_line,
    event_post,
    heading,
    tally,
)
from wgm.domain.events.services import (
    EVENT_TYPES,
    MAX_CLOSE_MINUTES,
    EventInputError,
    EventService,
    GuildSettingsService,
    closing_time,
    parse_start,
)
from wgm.lib.settings import Settings

SUB_COMMAND = 1
SUB_COMMAND_GROUP = 2
STRING = 3
INTEGER = 4
CHANNEL = 7
TEXT_CHANNEL = 0


def _text(name: str, description: str, **extra: Any) -> dict[str, Any]:
    return {
        "type": STRING,
        "name": name,
        "description": description,
        "required": True,
        **extra,
    }


def _minutes(name: str, description: str, *, required: bool) -> dict[str, Any]:
    return {
        "type": INTEGER,
        "name": name,
        "description": description,
        "required": required,
        "min_value": 0,
        "max_value": MAX_CLOSE_MINUTES,
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
            _minutes(
                "close",
                "Minutes before the start that sign-ups close (default: server's)",
                required=False,
            ),
        ],
    ),
    Subcommand(("event", "list"), "List upcoming events"),
    Subcommand(
        ("event", "channel"),
        "Choose the channel where events are posted",
        (ADMIN_ROLE,),
        [
            {
                "type": CHANNEL,
                "name": "channel",
                "description": "Channel for event posts, such as #sign-up",
                "required": True,
                "channel_types": [TEXT_CHANNEL],
            }
        ],
    ),
    Subcommand(
        ("event", "close-time"),
        "Choose how long before the start sign-ups close",
        (ADMIN_ROLE,),
        [_minutes("minutes", "Minutes before the start, such as 30", required=True)],
    ),
    Subcommand(("event", "settings"), "Show the event settings", (ADMIN_ROLE,)),
    Subcommand(("config", "show"), "Show server-wide settings", (ADMIN_ROLE,)),
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
    """Everything a command needs to answer."""

    interaction: Interaction
    settings: Settings
    discord: DiscordClient
    events: EventService
    guilds: GuildSettingsService
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


async def _check(ctx: CommandContext, channel_id: str) -> ChannelCheck:
    return await check_channel(
        ctx.discord,
        guild_id=ctx.guild_id,
        app_id=ctx.interaction.application_id,
        channel_id=channel_id,
    )


async def _setup(ctx: CommandContext, values: dict[str, Any]) -> InteractionResponse:
    existing = await ctx.discord.role_ids(ctx.guild_id)
    created = [name for name in WGM_ROLES if name not in existing]
    for name in created:
        await ctx.discord.create_role(ctx.guild_id, name)
    roles = (
        f"Created {', '.join(created)}. Give it to the members who run events."
        if created
        else "All WGM roles already exist."
    )
    channel_id = (await ctx.guilds.for_guild(ctx.guild_id)).event_channel_id
    if channel_id is None:
        return private_reply(
            f"{roles}\nNext, choose where events go: `/wgm event channel`."
        )
    return private_reply(f"{roles}\n\n{(await _check(ctx, channel_id)).report()}")


async def _event_create(
    ctx: CommandContext, values: dict[str, Any]
) -> InteractionResponse:
    guild = await ctx.guilds.for_guild(ctx.guild_id)
    try:
        starts_at = parse_start(
            str(values["date"]), str(values["time"]), ctx.settings.timezone, ctx.now
        )
        minutes = int(values.get("close", guild.close_minutes))
        closes_at = closing_time(starts_at, minutes, ctx.now)
    except EventInputError as error:
        return private_reply(str(error))
    event = await ctx.events.create(
        Event(
            guild_id=ctx.guild_id,
            title=str(values["title"]).strip(),
            event_type=str(values["type"]),
            starts_at=starts_at,
            closes_at=closes_at,
            created_by=ctx.user_id,
            channel_id=ctx.interaction.channel_id,
        )
    )
    channel_id = guild.event_channel_id or ctx.interaction.channel_id or ""
    try:
        message_id = await ctx.discord.post_message(
            channel_id, event_post(event, ctx.now), buttons(event, ctx.now)
        )
    except DiscordApiError:
        await ctx.events.delete(event.id)
        check = await _check(ctx, channel_id)
        return private_reply(
            f"I couldn't post in <#{channel_id}>, so the event wasn't created.\n\n"
            f"{check.report()}"
        )
    event.channel_id, event.message_id = channel_id, message_id
    await ctx.events.update(event)
    return private_reply(f"Posted **{event.title}** in <#{channel_id}>.")


async def _event_list(
    ctx: CommandContext, values: dict[str, Any]
) -> InteractionResponse:
    events = await ctx.events.upcoming(ctx.guild_id, ctx.now)
    posts = [
        f"{heading(event)}\n{closing_line(event, ctx.now)}\n{tally(event)}"
        for event in events
    ]
    return private_reply("\n\n".join(posts) or "No upcoming events.")


async def _event_channel(
    ctx: CommandContext, values: dict[str, Any]
) -> InteractionResponse:
    channel_id = str(values["channel"])
    check = await _check(ctx, channel_id)
    if not check.ok:
        return private_reply(
            f"I didn't save <#{channel_id}> because I can't post there yet.\n\n"
            f"{check.report()}\nThen run this command again."
        )
    await ctx.guilds.set_event_channel(ctx.guild_id, channel_id)
    return private_reply(
        f"New events will be posted in <#{channel_id}>.\n\n{check.report()}"
    )


async def _event_close_time(
    ctx: CommandContext, values: dict[str, Any]
) -> InteractionResponse:
    minutes = int(values["minutes"])
    await ctx.guilds.set_close_minutes(ctx.guild_id, minutes)
    return private_reply(
        f"Sign-ups for new events will close {_before(minutes)}. "
        "Events already posted keep their closing time."
    )


def _before(minutes: int) -> str:
    """30 -> "30 minutes before the start"; 0 -> "at the start"."""
    if minutes == 0:
        return "at the start"
    unit = "minute" if minutes == 1 else "minutes"
    return f"{minutes} {unit} before the start"


async def _event_settings(
    ctx: CommandContext, values: dict[str, Any]
) -> InteractionResponse:
    settings = await ctx.guilds.for_guild(ctx.guild_id)
    channel = "not set (events post where the command runs)"
    details = ""
    if settings.event_channel_id:
        channel = f"<#{settings.event_channel_id}>"
        check = await _check(ctx, settings.event_channel_id)
        warning = "" if check.ok else "⚠️ Events can't be posted there yet.\n"
        details = f"\n\n{warning}{check.report()}"
    return private_reply(
        f"**Event settings**\nChannel: {channel}\n"
        f"Sign-ups close: {_before(settings.close_minutes)}\n"
        f"Times are entered in: {ctx.settings.timezone}{details}"
    )


async def _config_show(
    ctx: CommandContext, values: dict[str, Any]
) -> InteractionResponse:
    return private_reply(
        f"**Server settings**\nTime zone: {ctx.settings.timezone}\n"
        "Event settings: `/wgm event settings`"
    )


async def _help(ctx: CommandContext, values: dict[str, Any]) -> InteractionResponse:
    return private_reply(await help_text(ctx))


HANDLERS = {
    ("help",): _help,
    ("setup",): _setup,
    ("event", "create"): _event_create,
    ("event", "list"): _event_list,
    ("event", "channel"): _event_channel,
    ("event", "close-time"): _event_close_time,
    ("event", "settings"): _event_settings,
    ("config", "show"): _config_show,
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
