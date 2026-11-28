"""How an event looks in Discord: the post, its roster and its buttons.

The post is one Components V2 container: a colored box holding the title,
times, roster by role, the buttons and a tally.
See https://discord.com/developers/docs/components/reference
"""

from datetime import datetime
from typing import Any

from wgm.db.models import Event, Signup, SignupStatus

ATTENDING_ROLES = ("Healer", "Tank", "DPS")
"""Roster and button order: healers first, as the guild plans around them."""

# Button id -> (status, role). The id is sent back when the button is pressed.
CHOICES: dict[str, tuple[SignupStatus, str | None]] = {
    "tank": (SignupStatus.ATTENDING, "Tank"),
    "healer": (SignupStatus.ATTENDING, "Healer"),
    "dps": (SignupStatus.ATTENDING, "DPS"),
    "tentative": (SignupStatus.TENTATIVE, None),
    "not_attending": (SignupStatus.NOT_ATTENDING, None),
}
BUTTON_LABELS = {
    "healer": "Healer",
    "tank": "Tank",
    "dps": "DPS",
    "tentative": "Tentative",
    "not_attending": "Not attending",
}
PRIMARY, SECONDARY, DANGER = 1, 2, 4
BUTTON_STYLES = {"tentative": SECONDARY, "not_attending": DANGER}
ACTION_ROW, TEXT, SEPARATOR, CONTAINER = 1, 10, 14, 17
OPEN, CLOSED, CANCELLED = 0x3B82F6, 0x6B7280, 0xEF4444
"""The box's edge: blue while open, grey once closed, red when cancelled."""
ROLE_HEADINGS = {"Tank": "🛡️ **Tanks", "Healer": "💚 **Healers", "DPS": "🗡️ **DPS"}


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
    return f"**{event.title}** · {event.type_name}\n{when(event.starts_at)}"


def _name(signup: Signup) -> str:
    """Kael, Kael (Crusader), Kael (late) or Kael (Crusader, late)."""
    notes = [
        note for note in (signup.class_name, "late" if signup.late else "") if note
    ]
    return signup.character_name + (f" ({', '.join(notes)})" if notes else "")


def _names(signups: list[Signup]) -> str:
    return ", ".join(_name(signup) for signup in signups) or "-"


def reasons(event: Event) -> str:
    """Not attending: Vex (work), Nyx, for admins only."""
    absent = [s for s in event.signups if s.status is SignupStatus.NOT_ATTENDING]
    if not absent:
        return ""
    names = ", ".join(
        s.character_name + (f" ({s.reason})" if s.reason else "") for s in absent
    )
    return f"Not attending: {names}"


def buttons(event: Event, now: datetime) -> list[dict[str, Any]]:
    """One row of sign-up buttons for the post, greyed out once closed."""
    closed = is_closed(event, now)
    return [
        {
            "type": ACTION_ROW,
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


def _text(content: str) -> dict[str, Any]:
    return {"type": TEXT, "content": content}


def _divider(*, large: bool = False) -> dict[str, Any]:
    return {"type": SEPARATOR, "divider": True, "spacing": 2 if large else 1}


def _subtitle(event: Event) -> str:
    """The admin's description, else the event's shark fact, as a second line."""
    if event.description:
        return f"\n{event.description}"
    if event.shark_fact:
        return f"\n-# Shark fact: {event.shark_fact}"
    return ""


def _gap() -> dict[str, Any]:
    """Blank space between roster sections, without a line."""
    return {"type": SEPARATOR, "divider": False, "spacing": 2}


def status_line(event: Event, now: datetime) -> str:
    """When it starts, and whether sign-ups are open, closed or cancelled."""
    if event.cancelled_at:
        return f"🕗 {when(event.starts_at)}\n❌ **Cancelled**"
    return f"🕗 {when(event.starts_at)}\n🔒 {closing_line(event, now)}"


def roster_blocks(event: Event) -> tuple[list[str], str]:
    """The Attending heading and one section per role, then everyone else."""
    attending = [s for s in event.signups if s.status is SignupStatus.ATTENDING]
    sections = [f"### Attending ({len(attending)})"]
    for role in ATTENDING_ROLES:
        members = [s for s in attending if s.role == role]
        sections.append(f"{ROLE_HEADINGS[role]} ({len(members)})**\n{_names(members)}")
    others = []
    for status, icon, label in (
        (SignupStatus.TENTATIVE, "❔", "Tentative"),
        (SignupStatus.NOT_ATTENDING, "🚫", "Not attending"),
    ):
        members = [s for s in event.signups if s.status is status]
        others.append(f"{icon} **{label} ({len(members)})**: {_names(members)}")
    return sections, "\n".join(others)


def post_components(event: Event, now: datetime) -> list[dict[str, Any]]:
    """The whole post, as one colored box."""
    color = (
        CANCELLED if event.cancelled_at else CLOSED if is_closed(event, now) else OPEN
    )
    attending, others = roster_blocks(event)
    inside = [
        _text(f"## 🦈 [{event.type_name}] {event.title}{_subtitle(event)}"),
        _text(status_line(event, now)),
        _divider(large=True),
        _text(attending[0]),
        *(part for section in attending[1:] for part in (_gap(), _text(section))),
        _divider(large=True),
        _text(others),
        *([_divider(), *buttons(event, now)] if not event.cancelled_at else []),
        _text(f"-# {tally(event)}"),
    ]
    return [{"type": CONTAINER, "accent_color": color, "components": inside}]


def post_text(components: list[dict[str, Any]]) -> str:
    """All the text in a post, top to bottom. Handy for logs and tests."""
    lines: list[str] = []
    for component in components:
        if component.get("type") == TEXT:
            lines.append(str(component["content"]))
        lines.append(post_text(component.get("components", [])))
    return "\n".join(line for line in lines if line)
