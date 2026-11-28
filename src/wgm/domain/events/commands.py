"""The `/wgm event ...` subcommands."""

from datetime import datetime
from typing import Any

from wgm.db.models import Event
from wgm.domain.discord.channel_check import ChannelCheck, check_channel
from wgm.domain.discord.client import DiscordApiError
from wgm.domain.discord.context import CommandContext, Subcommand, private_reply
from wgm.domain.discord.options import (
    CHANNEL,
    STRING,
    TEXT_CHANNEL,
    choice,
    integer,
    text,
    user,
)
from wgm.domain.discord.permissions import ADMIN_ROLE
from wgm.domain.discord.schemas import InteractionResponse
from wgm.domain.events.classes import WEAPONS
from wgm.domain.events.posts import update_post
from wgm.domain.events.roster import (
    BUTTON_LABELS,
    CHOICES,
    buttons,
    closing_line,
    event_post,
    heading,
    is_closed,
    reasons,
    tally,
)
from wgm.domain.events.services import (
    EVENT_TYPES,
    MAX_CLOSE_MINUTES,
    Answer,
    EventInputError,
    EventService,
    GuildSettingsService,
    NewTimes,
    closing_time,
    parse_start,
    reschedule,
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
    admin = bool(upcoming) and await ctx.may((ADMIN_ROLE,))
    posts = [
        "\n".join(
            line
            for line in (
                heading(event),
                closing_line(event, ctx.now),
                tally(event),
                reasons(event) if admin else "",
            )
            if line
        )
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


def _optional(option: dict[str, Any]) -> dict[str, Any]:
    return {**option, "required": False}


EVENT_OPTION = {
    "type": STRING,
    "name": "event",
    "description": "Start typing the event's name",
    "required": True,
    "autocomplete": True,
}


async def suggest_events(
    ctx: CommandContext, option: str, typed: str
) -> list[tuple[str, str]]:
    """Upcoming events whose title contains what was typed, soonest first."""
    return await _suggest(ctx, typed, cancelled=False)


async def suggest_any_events(
    ctx: CommandContext, option: str, typed: str
) -> list[tuple[str, str]]:
    """Like `suggest_events`, including cancelled events, which are marked."""
    return await _suggest(ctx, typed, cancelled=True)


async def suggest_event_or_class(
    ctx: CommandContext, option: str, typed: str
) -> list[tuple[str, str]]:
    """Events for the event option; classes, with their weapons, for class."""
    if option != "class":
        return await suggest_events(ctx, option, typed)
    return [
        (f"{name} · {weapons}", name)
        for name, weapons in WEAPONS.items()
        if typed.strip().lower() in name.lower()
    ]


async def _suggest(
    ctx: CommandContext, typed: str, *, cancelled: bool
) -> list[tuple[str, str]]:
    zone = ctx.settings.timezone
    found = await events(ctx).upcoming(ctx.guild_id, ctx.now, cancelled=cancelled)
    return [
        (
            f"{event.title} · {_local(event.starts_at, zone)}"
            + (" (cancelled)" if event.cancelled_at else ""),
            str(event.id),
        )
        for event in found
        if typed.strip().lower() in event.title.lower()
    ]


def _local(moment: datetime, zone: Any) -> str:
    """Sat Dec 5, 8:00 PM in the guild's time zone (suggestions can't use <t:>)."""
    local = moment.astimezone(zone)
    return f"{local:%a %b} {local.day}, {local:%I:%M %p}".replace(" 0", " ")


async def _upcoming(ctx: CommandContext, values: dict[str, Any]) -> Event | None:
    event = await events(ctx).in_guild(str(values["event"]), ctx.guild_id)
    if event is None or event.cancelled_at or event.starts_at <= ctx.now:
        return None
    return event


NOT_FOUND = "Pick an upcoming event from the list as you type."


async def _edit(ctx: CommandContext, values: dict[str, Any]) -> InteractionResponse:
    event = await _upcoming(ctx, values)
    if event is None:
        return private_reply(NOT_FOUND)
    changes = {key: values[key] for key in EDITABLE if key in values}
    if not changes:
        return private_reply(
            "Nothing to change. Pick a new title, type, date, time or close."
        )
    try:
        reschedule(
            event,
            NewTimes(
                day=_text_or_none(changes.get("date")),
                clock=_text_or_none(changes.get("time")),
                close=int(changes["close"]) if "close" in changes else None,
            ),
            ctx.settings.timezone,
            ctx.now,
        )
    except EventInputError as error:
        return private_reply(str(error))
    if "title" in changes:
        event.title = str(changes["title"]).strip()
    if "type" in changes:
        event.event_type = str(changes["type"])
    problem = await update_post(ctx, event)
    await events(ctx).update(event)
    return private_reply(
        f"Updated **{event.title}**: {', '.join(changes)}.\n"
        f"{heading(event)}\n{closing_line(event, ctx.now)}{problem}"
    )


def _text_or_none(value: object) -> str | None:
    return None if value is None else str(value)


EDITABLE = ("title", "type", "date", "time", "close")


async def _cancel(ctx: CommandContext, values: dict[str, Any]) -> InteractionResponse:
    event = await _upcoming(ctx, values)
    if event is None:
        return private_reply(NOT_FOUND)
    event.cancelled_at = ctx.now
    problem = await update_post(ctx, event)
    await events(ctx).update(event)
    return private_reply(
        f"Cancelled **{event.title}**. The post now says so and has no buttons."
        f"{problem}"
    )


async def _delete(ctx: CommandContext, values: dict[str, Any]) -> InteractionResponse:
    event = await events(ctx).in_guild(str(values["event"]), ctx.guild_id)
    if event is None:
        return private_reply(NOT_FOUND)
    event.deleted_at, event.deleted_by = ctx.now, ctx.user_id
    await events(ctx).update(event)
    problem = ""
    try:
        await ctx.discord.delete_message(event.channel_id or "", event.message_id or "")
    except DiscordApiError as error:
        if error.status != NOT_FOUND_STATUS:
            problem = (
                f"\nI couldn't remove its post in <#{event.channel_id}>, so "
                "you may want to delete it by hand."
            )
    return private_reply(
        f"Deleted **{event.title}** and removed its post. Its sign ups are "
        f"kept in the database.{problem}"
    )


NOT_FOUND_STATUS = 404
"""The post was already gone."""


async def _add(ctx: CommandContext, values: dict[str, Any]) -> InteractionResponse:
    event = await _upcoming(ctx, values)
    data = ctx.interaction.data
    if event is None or data is None:
        return private_reply(NOT_FOUND)
    user_id, choice_id = str(values["member"]), str(values["answer"])
    name = data.resolved.name(user_id)
    status, role = CHOICES[choice_id]
    class_name = str(values.get("class", "")).strip().title() or None
    if class_name and (role is None or class_name not in WEAPONS):
        return private_reply(
            "Pick a class from the list, and only with Tank, Healer or DPS."
        )
    answer = Answer(user_id, name, status, role, by=ctx.user_id, class_name=class_name)
    event = await events(ctx).set_answer(event, answer, ctx.now)
    problem = await update_post(ctx, event)
    await events(ctx).update(event)
    notes = [n for n in (class_name, "late" if is_closed(event, ctx.now) else "") if n]
    note = f" ({', '.join(notes)})" if notes else ""
    return private_reply(
        f"Put **{name}** down as {BUTTON_LABELS[choice_id]}{note} for "
        f"**{event.title}**.{problem}"
    )


async def _remove(ctx: CommandContext, values: dict[str, Any]) -> InteractionResponse:
    event = await _upcoming(ctx, values)
    data = ctx.interaction.data
    if event is None or data is None:
        return private_reply(NOT_FOUND)
    user_id = str(values["member"])
    name = data.resolved.name(user_id)
    if events(ctx).signup(event, user_id) is None:
        return private_reply(f"**{name}** isn't on the roster for **{event.title}**.")
    event = await events(ctx).remove_answer(event, user_id, ctx.user_id, ctx.now)
    problem = await update_post(ctx, event)
    await events(ctx).update(event)
    return private_reply(
        f"Took **{name}** off the roster for **{event.title}**.{problem}"
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
    Subcommand(
        ("event", "edit"),
        "Change an upcoming event; its post updates too",
        _edit,
        (ADMIN_ROLE,),
        [
            EVENT_OPTION,
            _optional(text("title", "New title", max_length=100)),
            _optional(choice("type", "New kind of event", EVENT_TYPES)),
            _optional(text("date", "New day, like 2026-12-05")),
            _optional(text("time", "New 24-hour start time, like 20:00")),
            _minutes(
                "close",
                "New minutes before the start that sign-ups close",
                required=False,
            ),
        ],
        suggest=suggest_events,
    ),
    Subcommand(
        ("event", "cancel"),
        "Cancel an upcoming event; its post says so",
        _cancel,
        (ADMIN_ROLE,),
        [EVENT_OPTION],
        suggest=suggest_events,
    ),
    Subcommand(
        ("event", "delete"),
        "Delete an event and its post (the data is kept)",
        _delete,
        (ADMIN_ROLE,),
        [EVENT_OPTION],
        suggest=suggest_any_events,
    ),
    Subcommand(
        ("event", "add"),
        "Put a member on an event's roster, even after sign-ups close",
        _add,
        (ADMIN_ROLE,),
        [
            EVENT_OPTION,
            user("member", "Who to add"),
            text(
                "answer",
                "Their answer",
                choices=[{"name": v, "value": k} for k, v in BUTTON_LABELS.items()],
            ),
            _optional(
                text("class", "Their class, such as Crusader", autocomplete=True)
            ),
        ],
        suggest=suggest_event_or_class,
    ),
    Subcommand(
        ("event", "remove"),
        "Take a member off an event's roster, even after sign-ups close",
        _remove,
        (ADMIN_ROLE,),
        [EVENT_OPTION, user("member", "Who to take off")],
        suggest=suggest_events,
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
