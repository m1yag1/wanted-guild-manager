"""Answer presses of the sign-up buttons under an event post."""

from uuid import UUID

from wgm.domain.discord.context import NO_PINGS, CommandContext, private_reply
from wgm.domain.discord.permissions import ADMIN_ROLE
from wgm.domain.discord.schemas import (
    InteractionResponse,
    InteractionResponseType,
    MessageData,
)
from wgm.domain.events.roster import CHOICES, buttons, closes, event_post, is_closed
from wgm.domain.events.services import EventService


def parse_custom_id(custom_id: str) -> tuple[UUID, str] | None:
    """`signup:<event id>:<choice>` -> (event id, choice), or None."""
    parts = custom_id.split(":")
    if len(parts) != 3 or parts[0] != "signup" or parts[2] not in CHOICES:  # noqa: PLR2004
        return None
    try:
        return UUID(parts[1]), parts[2]
    except ValueError:
        return None


async def press(ctx: CommandContext) -> InteractionResponse:
    """Record the member's answer and redraw the post."""
    data = ctx.interaction.data
    member = ctx.interaction.member
    parsed = parse_custom_id(data.custom_id if data else "")
    if parsed is None or member is None:
        return private_reply("That button isn't one of ours.")
    events = EventService(session=ctx.session)
    event = await events.find(parsed[0])
    if event is None:
        return private_reply("That event no longer exists.")
    if is_closed(event, ctx.now):
        closed_at = int(closes(event).timestamp())
        return private_reply(
            f"Sign-ups for **{event.title}** closed <t:{closed_at}:R>, so your "
            f"answer can't change now. Ask someone with the {ADMIN_ROLE} role "
            "if you need a change."
        )
    status, role = CHOICES[parsed[1]]
    name = member.nick or member.user.global_name or member.user.username
    event = await events.answer(
        event, user_id=member.user.id, name=name, status=status, role=role
    )
    return InteractionResponse(
        type=InteractionResponseType.UPDATE_MESSAGE,
        data=MessageData(
            content=event_post(event, ctx.now),
            components=buttons(event, ctx.now),
            allowed_mentions=NO_PINGS,
        ),
    )
