"""The `/wgm event ...` subcommands."""

from typing import Any

from wgm.db.models import Event
from wgm.domain.discord.channel_check import ChannelCheck, check_channel
from wgm.domain.discord.client import DiscordApiError
from wgm.domain.discord.context import CommandContext, Subcommand, private_reply
from wgm.domain.discord.options import CHANNEL, TEXT_CHANNEL, choice, integer, text
from wgm.domain.discord.permissions import ADMIN_ROLE
from wgm.domain.discord.schemas import InteractionResponse
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


def events(ctx: CommandContext) -> EventService:
    """Event storage in this interaction's database session."""
    return EventService(session=ctx.session)


def guilds(ctx: CommandContext) -> GuildSettingsService:
    """Server settings in this interaction's database session."""
    return GuildSettingsService(session=ctx.session)


def _minutes(name: str, description: str, *, required: bool) -> dict[str, Any]:
    return integer(name, description, required=required, low=0, high=MAX_CLOSE_MINUTES)


async def check(ctx: CommandContext, channel_id: str) -> ChannelCheck:
    """Whether the app can post in a channel, as a checklist."""
    return await check_channel(
        ctx.discord,
        guild_id=ctx.guild_id,
        app_id=ctx.interaction.application_id,
        channel_id=channel_id,
    )


async def post_event(ctx: CommandContext, event: Event) -> InteractionResponse:
    """Save a new event and post it, or explain why it couldn't be posted.

    The post goes in the server's event channel, or where the command ran.
    """
    configured = (await guilds(ctx).for_guild(ctx.guild_id)).event_channel_id
    channel_id = configured or ctx.interaction.channel_id or ""
    event = await events(ctx).create(event)
    try:
        message_id = await ctx.discord.post_message(
            channel_id, event_post(event, ctx.now), buttons(event, ctx.now)
        )
    except DiscordApiError:
        await events(ctx).delete(event.id)
        report = (await check(ctx, channel_id)).report()
        return private_reply(
            f"I couldn't post in <#{channel_id}>, so the event wasn't created.\n\n"
            f"{report}"
        )
    event.channel_id, event.message_id = channel_id, message_id
    await events(ctx).update(event)
    return private_reply(f"Posted **{event.title}** in <#{channel_id}>.")


async def _create(ctx: CommandContext, values: dict[str, Any]) -> InteractionResponse:
    settings = await guilds(ctx).for_guild(ctx.guild_id)
    try:
        starts_at = parse_start(
            str(values["date"]), str(values["time"]), ctx.settings.timezone, ctx.now
        )
        minutes = int(values.get("close", settings.close_minutes))
        closes_at = closing_time(starts_at, minutes, ctx.now)
    except EventInputError as error:
        return private_reply(str(error))
    return await post_event(
        ctx,
        Event(
            guild_id=ctx.guild_id,
            title=str(values["title"]).strip(),
            event_type=str(values["type"]),
            starts_at=starts_at,
            closes_at=closes_at,
            created_by=ctx.user_id,
        ),
    )


async def _list(ctx: CommandContext, values: dict[str, Any]) -> InteractionResponse:
    upcoming = await events(ctx).upcoming(ctx.guild_id, ctx.now)
    posts = [
        f"{heading(event)}\n{closing_line(event, ctx.now)}\n{tally(event)}"
        for event in upcoming
    ]
    return private_reply("\n\n".join(posts) or "No upcoming events.")


async def _channel(ctx: CommandContext, values: dict[str, Any]) -> InteractionResponse:
    channel_id = str(values["channel"])
    result = await check(ctx, channel_id)
    if not result.ok:
        return private_reply(
            f"I didn't save <#{channel_id}> because I can't post there yet.\n\n"
            f"{result.report()}\nThen run this command again."
        )
    await guilds(ctx).set_event_channel(ctx.guild_id, channel_id)
    return private_reply(
        f"New events will be posted in <#{channel_id}>.\n\n{result.report()}"
    )


def _before(minutes: int) -> str:
    """30 -> "30 minutes before the start"; 0 -> "at the start"."""
    if minutes == 0:
        return "at the start"
    unit = "minute" if minutes == 1 else "minutes"
    return f"{minutes} {unit} before the start"


async def _close_time(
    ctx: CommandContext, values: dict[str, Any]
) -> InteractionResponse:
    minutes = int(values["minutes"])
    await guilds(ctx).set_close_minutes(ctx.guild_id, minutes)
    return private_reply(
        f"Sign-ups for new events will close {_before(minutes)}. "
        "Events already posted keep their closing time."
    )


async def _settings(ctx: CommandContext, values: dict[str, Any]) -> InteractionResponse:
    settings = await guilds(ctx).for_guild(ctx.guild_id)
    channel = "not set (events post where the command runs)"
    details = ""
    if settings.event_channel_id:
        channel = f"<#{settings.event_channel_id}>"
        result = await check(ctx, settings.event_channel_id)
        warning = "" if result.ok else "⚠️ Events can't be posted there yet.\n"
        details = f"\n\n{warning}{result.report()}"
    return private_reply(
        f"**Event settings**\nChannel: {channel}\n"
        f"Sign-ups close: {_before(settings.close_minutes)}\n"
        f"Times are entered in: {ctx.settings.timezone}{details}"
    )


async def setup_line(ctx: CommandContext) -> str:
    """What `/wgm setup` says about the event channel."""
    channel_id = (await guilds(ctx).for_guild(ctx.guild_id)).event_channel_id
    if channel_id is None:
        return "Next, choose where events go: `/wgm event channel`."
    return (await check(ctx, channel_id)).report()


SUBCOMMANDS = (
    Subcommand(
        ("event", "create"),
        "Post a new event",
        _create,
        (ADMIN_ROLE,),
        [
            text("title", "What the event is called", max_length=100),
            choice("type", "Kind of event", EVENT_TYPES),
            text("date", "Day, like 2026-12-05"),
            text("time", "24-hour start time in the guild's time zone, like 20:00"),
            _minutes(
                "close",
                "Minutes before the start that sign-ups close (default: server's)",
                required=False,
            ),
        ],
    ),
    Subcommand(("event", "list"), "List upcoming events", _list),
    Subcommand(
        ("event", "channel"),
        "Choose the channel where events are posted",
        _channel,
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
        _close_time,
        (ADMIN_ROLE,),
        [_minutes("minutes", "Minutes before the start, such as 30", required=True)],
    ),
    Subcommand(
        ("event", "settings"), "Show the event settings", _settings, (ADMIN_ROLE,)
    ),
)
