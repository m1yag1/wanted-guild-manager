"""How an event looks in Discord: the post text, the roster and its buttons."""

from datetime import datetime
from typing import Any

from wgm.db.models import Event, Signup, SignupStatus

ATTENDING_ROLES = ("Tank", "Healer", "DPS")

# Button id -> (status, role). The id is sent back when the button is pressed.
CHOICES: dict[str, tuple[SignupStatus, str | None]] = {
    "tank": (SignupStatus.ATTENDING, "Tank"),
    "healer": (SignupStatus.ATTENDING, "Healer"),
    "dps": (SignupStatus.ATTENDING, "DPS"),
    "tentative": (SignupStatus.TENTATIVE, None),
    "not_attending": (SignupStatus.NOT_ATTENDING, None),
}
BUTTON_LABELS = {
    "tank": "Tank",
    "healer": "Healer",
    "dps": "DPS",
    "tentative": "Tentative",
    "not_attending": "Not attending",
}
PRIMARY, SECONDARY, DANGER = 1, 2, 4
BUTTON_STYLES = {"tentative": SECONDARY, "not_attending": DANGER}


def when(moment: datetime) -> str:
    """A Discord timestamp: each reader sees it in their own time zone."""
    seconds = int(moment.timestamp())
    return f"<t:{seconds}:F> (<t:{seconds}:R>)"


def closes(event: Event) -> datetime:
    """When sign-ups close. Events made before closing existed close at the start."""
    return event.closes_at or event.starts_at


def is_closed(event: Event, now: datetime) -> bool:
    """Whether members can no longer change their answer."""
    return now >= closes(event)


def closing_line(event: Event, now: datetime) -> str:
    """Sign-ups close <t:...:R> / Sign-ups closed <t:...:R>"""
    seconds = int(closes(event).timestamp())
    verb = "closed" if is_closed(event, now) else "close"
    return f"Sign-ups {verb} <t:{seconds}:R>"


def counts(event: Event) -> dict[SignupStatus, int]:
    """How many members gave each answer."""
    totals = dict.fromkeys(SignupStatus, 0)
    for signup in event.signups:
        totals[signup.status] += 1
    return totals


def tally(event: Event) -> str:
    """Attending 2 · Tentative 1 · Not attending 0"""
    totals = counts(event)
    return (
        f"Attending {totals[SignupStatus.ATTENDING]} · "
        f"Tentative {totals[SignupStatus.TENTATIVE]} · "
        f"Not attending {totals[SignupStatus.NOT_ATTENDING]}"
    )


def heading(event: Event) -> str:
    """Title, type and start time."""
    return f"**{event.title}** · {event.event_type}\n{when(event.starts_at)}"


def _names(signups: list[Signup]) -> str:
    return (
        ", ".join(
            signup.character_name + (" (late)" if signup.late else "")
            for signup in signups
        )
        or "-"
    )


def reasons(event: Event) -> str:
    """Not attending: Vex (work), Nyx, for admins only."""
    absent = [s for s in event.signups if s.status is SignupStatus.NOT_ATTENDING]
    if not absent:
        return ""
    names = ", ".join(
        s.character_name + (f" ({s.reason})" if s.reason else "") for s in absent
    )
    return f"Not attending: {names}"


def roster(event: Event) -> str:
    """Who answered, grouped the way the sign-up sheet is."""
    attending = [s for s in event.signups if s.status is SignupStatus.ATTENDING]
    lines = [f"**Attending ({len(attending)})**"]
    for role in ATTENDING_ROLES:
        members = [s for s in attending if s.role == role]
        lines.append(f"{role} ({len(members)}): {_names(members)}")
    for status, label in (
        (SignupStatus.TENTATIVE, "Tentative"),
        (SignupStatus.NOT_ATTENDING, "Not attending"),
    ):
        members = [s for s in event.signups if s.status is status]
        lines.append(f"**{label} ({len(members)})**: {_names(members)}")
    return "\n".join(lines)


def event_post(event: Event, now: datetime) -> str:
    """The full post: heading and closing time (or Cancelled), then the roster."""
    status = "**Cancelled**" if event.cancelled_at else closing_line(event, now)
    return f"{heading(event)}\n{status}\n\n{roster(event)}"


def buttons(event: Event, now: datetime) -> list[dict[str, Any]]:
    """One row of sign-up buttons for the post, greyed out once closed.

    A cancelled event has no buttons.
    """
    if event.cancelled_at:
        return []
    closed = is_closed(event, now)
    return [
        {
            "type": 1,  # action row
            "components": [
                {
                    "type": 2,  # button
                    "style": BUTTON_STYLES.get(choice, PRIMARY),
                    "label": label,
                    "custom_id": f"signup:{event.id}:{choice}",
                    "disabled": closed,
                }
                for choice, label in BUTTON_LABELS.items()
            ],
        }
    ]
