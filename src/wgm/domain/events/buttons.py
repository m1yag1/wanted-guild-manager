"""Answer presses of the sign-up buttons under an event post.

Pressing Not attending opens a small form for an optional reason, which only
admins see. Submitting it records the answer.
"""

from uuid import UUID

from wgm.db.models import Event, SignupStatus
from wgm.domain.discord.context import NO_PINGS, CommandContext, private_reply
from wgm.domain.discord.schemas import (
    InteractionResponse,
    InteractionResponseType,
    Member,
    MessageData,
    ModalData,
    ModalResponse,
)
from wgm.domain.events.class_picker import class_prompt
from wgm.domain.events.posts import open_event, update_post
from wgm.domain.events.roster import CHOICES, buttons, event_post
from wgm.domain.events.services import Answer, EventService

REASON = "reason"
"""The form's custom_id prefix and its text field's id."""
REASON_LENGTH = 200


def parse_custom_id(custom_id: str) -> tuple[UUID, str] | None:
    """`signup:<event id>:<choice>` -> (event id, choice), or None."""
    parts = custom_id.split(":")
    if len(parts) != 3 or parts[0] != "signup" or parts[2] not in CHOICES:  # noqa: PLR2004
        return None
    try:
        return UUID(parts[1]), parts[2]
    except ValueError:
        return None


def _name(member: Member) -> str:
    return member.nick or member.user.global_name or member.user.username


def redrawn(event: Event, ctx: CommandContext) -> InteractionResponse:
    """Replace the post the member pressed with its new roster."""
    return InteractionResponse(
        type=InteractionResponseType.UPDATE_MESSAGE,
        data=MessageData(
            content=event_post(event, ctx.now),
            components=buttons(event, ctx.now),
            allowed_mentions=NO_PINGS,
        ),
    )


def reason_form(event: Event) -> ModalResponse:
    """The Not attending form, with one optional text field."""
    return ModalResponse(
        ModalData(
            custom_id=f"{REASON}:{event.id}",
            title="Not attending"[:45],
            components=[
                {
                    "type": 1,
                    "components": [
                        {
                            "type": 4,  # text input
                            "custom_id": REASON,
                            "style": 2,  # paragraph
                            "label": "Reason (optional, only admins see it)",
                            "required": False,
                            "max_length": REASON_LENGTH,
                        }
                    ],
                }
            ],
        )
    )


async def press(ctx: CommandContext) -> InteractionResponse | ModalResponse:
    """Record the member's answer and redraw the post.

    Pressing the answer they already gave takes them off the roster.
    """
    data = ctx.interaction.data
    member = ctx.interaction.member
    parsed = parse_custom_id(data.custom_id if data else "")
    if parsed is None or member is None:
        return private_reply("That button isn't one of ours.")
    event = await open_event(ctx, parsed[0])
    if not isinstance(event, Event):
        return event
    events = EventService(session=ctx.session)
    status, role = CHOICES[parsed[1]]
    current = events.signup(event, member.user.id)
    if current and (current.status, current.role) == (status, role):
        event = await events.remove_answer(
            event, member.user.id, member.user.id, ctx.now
        )
        return redrawn(event, ctx)
    if status is SignupStatus.NOT_ATTENDING:
        return reason_form(event)
    answer = Answer(member.user.id, _name(member), status, role, by=member.user.id)
    event = await events.set_answer(event, answer, ctx.now)
    if role is None:
        return redrawn(event, ctx)
    # Ask for their class privately; the post is redrawn through the API.
    await update_post(ctx, event)
    return InteractionResponse(
        type=InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
        data=await class_prompt(ctx, event, role),
    )


async def submit_reason(ctx: CommandContext) -> InteractionResponse:
    """Record Not attending, with the reason from the form if one was given."""
    data = ctx.interaction.data
    member = ctx.interaction.member
    custom_id = data.custom_id if data else ""
    try:
        event_id = UUID(custom_id.removeprefix(f"{REASON}:"))
    except ValueError:
        event_id = None
    if data is None or member is None or event_id is None:
        return private_reply("That form isn't one of ours.")
    event = await open_event(ctx, event_id)
    if not isinstance(event, Event):
        return event
    reason = data.field(REASON).strip()[:REASON_LENGTH] or None
    answer = Answer(
        member.user.id,
        _name(member),
        SignupStatus.NOT_ATTENDING,
        None,
        by=member.user.id,
        reason=reason,
    )
    event = await EventService(session=ctx.session).set_answer(event, answer, ctx.now)
    return redrawn(event, ctx)
