"""Keeping an event's post in Discord in step with the event."""

from uuid import UUID

from wgm.db.models import Event
from wgm.domain.discord.client import DiscordApiError
from wgm.domain.discord.context import CommandContext, private_reply
from wgm.domain.discord.permissions import ADMIN_ROLE
from wgm.domain.discord.schemas import InteractionResponse
from wgm.domain.events.roster import closes, is_closed, post_components
from wgm.domain.events.services import EventService


async def update_post(ctx: CommandContext, event: Event) -> str:
    """Redraw the event's post. Returns a line to show if that failed, else ""."""
    if is_closed(event, ctx.now) and not event.cancelled_at:
        event.closed_post_at = event.closed_post_at or ctx.now
    try:
        await ctx.discord.edit_message(
            event.channel_id or "",
            event.message_id or "",
            post_components(event, ctx.now),
        )
    except DiscordApiError:
        return (
            f"\nI couldn't update the post in <#{event.channel_id}>. It may have "
            "been deleted."
        )
    return ""


async def open_event(
    ctx: CommandContext, event_id: UUID
) -> Event | InteractionResponse:
    """The event if members may still answer, else the reply saying why not."""
    event = await EventService(session=ctx.session).find(event_id)
    if event is None:
        return private_reply("That event no longer exists.")
    if event.cancelled_at:
        return private_reply(f"**{event.title}** was cancelled.")
    if is_closed(event, ctx.now):
        closed_at = int(closes(event).timestamp())
        return private_reply(
            f"Sign-ups for **{event.title}** closed <t:{closed_at}:R>, so your "
            f"answer can't change now. Ask someone with the {ADMIN_ROLE} role "
            "if you need a change."
        )
    return event
