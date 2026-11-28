"""`/wgm event seed`: ready-made test events for trying the event plugin by hand.

Only there in dev mode (`WGM_DEV_MODE=true`, staging only). Elsewhere it's
neither registered with Discord nor answered.
"""

from datetime import datetime, timedelta
from typing import Any

from attrs import frozen

from wgm.db.models import Event, Signup, SignupStatus
from wgm.domain.discord.context import CommandContext, Subcommand
from wgm.domain.discord.options import choice
from wgm.domain.discord.permissions import ADMIN_ROLE
from wgm.domain.discord.schemas import InteractionResponse
from wgm.domain.events.commands import post_event

ROSTER = [
    ("Kael", SignupStatus.ATTENDING, "Tank", None, "Crusader"),
    ("Brask", SignupStatus.ATTENDING, "Tank", None, "Guardian"),
    ("Mira", SignupStatus.ATTENDING, "Healer", None, "Seeker"),
    ("Rook", SignupStatus.ATTENDING, "Healer", None, "Oracle"),
    ("Lyra", SignupStatus.ATTENDING, "DPS", None, "Mobilist"),
    ("Thorn", SignupStatus.ATTENDING, "DPS", None, "Predator"),
    ("Sable", SignupStatus.ATTENDING, "DPS", None, "Infiltrator"),
    ("Orin", SignupStatus.ATTENDING, "DPS", None, "Liberator"),
    ("Ash", SignupStatus.TENTATIVE, None, None, None),
    ("Juno", SignupStatus.TENTATIVE, None, None, None),
    ("Vex", SignupStatus.NOT_ATTENDING, None, "Working late", None),
    ("Nyx", SignupStatus.NOT_ATTENDING, None, None, None),
]
"""Made-up members for the busy roster preset."""


@frozen
class Preset:
    """A kind of test event."""

    title: str
    starts_in: timedelta
    closes_before: timedelta | None
    """None leaves the close time unset, like events made before closing existed."""
    roster: bool = False


PRESETS = {
    "closes-soon": Preset("Closes soon", timedelta(minutes=35), timedelta(minutes=30)),
    "closed": Preset("Already closed", timedelta(minutes=20), timedelta(minutes=30)),
    "busy": Preset(
        "Busy roster", timedelta(days=1), timedelta(minutes=30), roster=True
    ),
    "old-style": Preset("Old style", timedelta(minutes=40), None),
}


def test_event(preset: Preset, ctx: CommandContext, now: datetime) -> Event:
    """A `[test]` event for a preset, starting relative to `now`."""
    starts_at = now + preset.starts_in
    event = Event(
        guild_id=ctx.guild_id,
        title=f"[test] {preset.title}",
        event_type="Other",
        starts_at=starts_at,
        closes_at=starts_at - preset.closes_before if preset.closes_before else None,
        created_by=ctx.user_id,
    )
    if event.closes_at and event.closes_at <= now:
        # Posted already locked, so the close job has nothing left to do.
        event.closed_post_at = now
    if preset.roster:
        event.signups.extend(
            Signup(
                user_id=f"test-{n}",
                character_name=name,
                status=status,
                role=role,
                reason=reason,
                class_name=class_name,
            )
            for n, (name, status, role, reason, class_name) in enumerate(
                ROSTER, start=1
            )
        )
    return event


async def _seed(ctx: CommandContext, values: dict[str, Any]) -> InteractionResponse:
    preset = PRESETS[str(values["preset"])]
    return await post_event(ctx, test_event(preset, ctx, ctx.now))


DEV_SUBCOMMANDS = (
    Subcommand(
        ("event", "seed"),
        "Post a test event (dev mode only)",
        _seed,
        (ADMIN_ROLE,),
        [choice("preset", "Kind of test event", tuple(PRESETS))],
    ),
)
