"""The private class dropdown a member gets after pressing Tank, Healer or DPS.

The class they last confirmed for that role is pre-selected, but they still
confirm it. Picking another class applies it at once. "Other classes" offers
the classes the first dropdown left out, such as Seeker played as DPS.

Custom ids: `class:pick:<event>:<role>:<n>` for dropdowns,
`class:ok:<event>:<role>:<class>` to confirm, `class:more:<event>:<role>`.
"""

from typing import Any
from uuid import UUID

from wgm.db.models import Event
from wgm.domain.discord.context import CommandContext, private_reply
from wgm.domain.discord.schemas import (
    InteractionResponse,
    InteractionResponseType,
    MessageData,
    MessageFlags,
)
from wgm.domain.events.classes import WEAPONS, ranked, the_rest
from wgm.domain.events.posts import open_event, update_post
from wgm.domain.events.services import EventService

PREFIX = "class"
SELECT, BUTTON, ACTION_ROW = 3, 2, 1
PRIMARY, SECONDARY = 1, 2


def _select(
    event: Event, role: str, n: int, names: list[str], *, chosen: str | None = None
) -> dict[str, Any]:
    return {
        "type": ACTION_ROW,
        "components": [
            {
                "type": SELECT,
                "custom_id": f"{PREFIX}:pick:{event.id}:{role}:{n}",
                "placeholder": "Pick your class",
                "options": [
                    {
                        "label": name,
                        "value": name,
                        "description": WEAPONS[name],
                        "default": name == chosen,
                    }
                    for name in names
                ],
            }
        ],
    }


async def class_prompt(ctx: CommandContext, event: Event, role: str) -> MessageData:
    """The private message: a dropdown, Confirm (if remembered) and Other classes."""
    events = EventService(session=ctx.session)
    shown = ranked(role, await events.class_counts(event.guild_id, role))
    last = await events.last_class(event.guild_id, ctx.user_id, role)
    chosen = last if last in shown else None
    row = [
        {
            "type": BUTTON,
            "style": SECONDARY,
            "label": "Other classes",
            "custom_id": f"{PREFIX}:more:{event.id}:{role}",
        }
    ]
    if chosen:
        row.insert(
            0,
            {
                "type": BUTTON,
                "style": PRIMARY,
                "label": f"Confirm {chosen}",
                "custom_id": f"{PREFIX}:ok:{event.id}:{role}:{chosen}",
            },
        )
    hint = (
        f" Last time you brought **{chosen}**: confirm it or pick another."
        if chosen
        else ""
    )
    return MessageData(
        content=f"You're down as **{role}** for **{event.title}**. Which class "
        f"are you bringing?{hint}",
        flags=MessageFlags.EPHEMERAL,
        components=[
            _select(event, role, 0, shown, chosen=chosen),
            {"type": ACTION_ROW, "components": row},
        ],
        allowed_mentions={"parse": []},
    )


def _done(content: str) -> InteractionResponse:
    """Replace the private class message, removing its dropdowns."""
    return InteractionResponse(
        type=InteractionResponseType.UPDATE_MESSAGE,
        data=MessageData(content=content, components=[]),
    )


async def pick_class(ctx: CommandContext) -> InteractionResponse:
    """Answer the dropdown, Confirm, or Other classes."""
    data = ctx.interaction.data
    parts = (data.custom_id if data else "").split(":")
    try:
        action, event_id, role = parts[1], UUID(parts[2]), parts[3]
    except (IndexError, ValueError):
        return private_reply("That button isn't one of ours.")
    event = await open_event(ctx, event_id)
    if not isinstance(event, Event):
        return event
    events = EventService(session=ctx.session)
    signup = events.signup(event, ctx.user_id)
    if signup is None or signup.role != role:
        return _done(f"You're not down as {role} for **{event.title}** anymore.")
    if action == "more":
        shown = ranked(role, await events.class_counts(event.guild_id, role))
        rows = [
            _select(event, role, n, names)
            for n, names in enumerate(the_rest(shown).values(), start=1)
        ]
        return InteractionResponse(
            type=InteractionResponseType.UPDATE_MESSAGE,
            data=MessageData(
                content=f"Other classes, to bring as **{role}**:", components=rows
            ),
        )
    picked = parts[4] if action == "ok" and len(parts) > 4 else ""  # noqa: PLR2004
    if action == "pick" and data and data.values:
        picked = data.values[0]
    if picked not in WEAPONS:
        return private_reply("That class isn't on the list.")
    event = await events.set_class(event, signup, picked)
    problem = await update_post(ctx, event)
    return _done(
        f"You're down as **{role}** ({picked}) for **{event.title}**.{problem}"
    )
