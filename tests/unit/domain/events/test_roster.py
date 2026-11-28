import random
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from wgm.db.models import Event, EventType, Signup, SignupStatus
from wgm.domain.events.roster import (
    CANCELLED,
    CLOSED,
    OPEN,
    buttons,
    closing_line,
    post_components,
    post_text,
    reasons,
    roster_blocks,
    tally,
    when,
)
from wgm.domain.events.sharks import SHARK_FACTS, shark_fact

STARTS = datetime(2026, 12, 6, 1, 0, tzinfo=UTC)
CLOSES = STARTS - timedelta(minutes=30)
BEFORE = CLOSES - timedelta(hours=1)


def _event() -> Event:
    event = Event(
        id=uuid4(),
        guild_id="1",
        title="Siege night",
        event_type=EventType(guild_id="1", name="Siege"),
        starts_at=STARTS,
        closes_at=CLOSES,
        created_by="42",
    )
    for user, name, status, role in [
        ("1", "Kael", SignupStatus.ATTENDING, "Tank"),
        ("2", "Mira", SignupStatus.ATTENDING, "Healer"),
        ("3", "Rook", SignupStatus.ATTENDING, "Healer"),
        ("4", "Ash", SignupStatus.TENTATIVE, None),
        ("5", "Vex", SignupStatus.NOT_ATTENDING, None),
    ]:
        event.signups.append(
            Signup(user_id=user, character_name=name, status=status, role=role)
        )
    return event


def test_when_uses_discord_timestamps() -> None:
    seconds = int(STARTS.timestamp())

    assert when(STARTS) == f"<t:{seconds}:F> (<t:{seconds}:R>)"


def test_tally_counts_each_answer() -> None:
    assert tally(_event()) == "Attending 3 · Tentative 1 · Not attending 1"


def test_roster_groups_by_role() -> None:
    attending, others = roster_blocks(_event())

    assert attending == [
        "### Attending (3)",
        "💚 **Healers (2)**\nMira, Rook",
        "🛡️ **Tanks (1)**\nKael",
        "🗡️ **DPS (0)**\n-",
    ]
    assert others == ("❔ **Tentative (1)**: Ash\n🚫 **Not attending (1)**: Vex")


def _box(event: Event, now: datetime) -> dict[str, Any]:
    (box,) = post_components(event, now)
    return box


def test_the_post_is_one_box_with_the_shark_title_and_buttons_inside() -> None:
    box = _box(_event(), BEFORE)
    text = post_text([box])

    assert box["type"] == 17
    assert box["accent_color"] == OPEN
    assert text.startswith("## 🦈 [Siege] Siege night\n🕗 <t:")
    assert f"🔒 Sign-ups close <t:{int(CLOSES.timestamp())}:R>" in text
    assert text.endswith("-# Attending 3 · Tentative 1 · Not attending 1")
    rows = [c for c in box["components"] if c["type"] == 1]
    assert [b["label"] for b in rows[0]["components"]][:3] == [
        "Healer",
        "Tank",
        "DPS",
    ]
    gaps = [c for c in box["components"] if c["type"] == 14 and not c["divider"]]
    assert len(gaps) == 3


def test_the_box_turns_grey_when_closed_and_red_when_cancelled() -> None:
    event = _event()
    closed = _box(event, CLOSES)
    event.cancelled_at = BEFORE
    cancelled = _box(event, BEFORE)

    assert closed["accent_color"] == CLOSED
    assert "🔒 Sign-ups closed" in post_text([closed])
    assert cancelled["accent_color"] == CANCELLED
    assert "❌ **Cancelled**" in post_text([cancelled])
    assert not [c for c in cancelled["components"] if c["type"] == 1]


def test_buttons_carry_the_event_and_choice() -> None:
    event = _event()
    row = buttons(event, BEFORE)[0]["components"]

    assert [b["label"] for b in row] == [
        "Healer",
        "Tank",
        "DPS",
        "Tentative",
        "Not attending",
    ]
    assert row[0]["custom_id"] == f"signup:{event.id}:healer"
    assert row[-1]["style"] == 4
    assert not any(b["disabled"] for b in row)


def test_closed_posts_say_so_and_grey_out_the_buttons() -> None:
    event = _event()

    row = buttons(event, CLOSES)[0]["components"]

    assert closing_line(event, CLOSES).startswith("Sign-ups closed <t:")
    assert all(b["disabled"] for b in row)


def test_events_from_before_closing_existed_close_at_the_start() -> None:
    event = _event()
    event.closes_at = None

    assert closing_line(event, CLOSES) == (
        f"Sign-ups close <t:{int(STARTS.timestamp())}:R>"
    )


def test_reasons_list_who_is_not_attending_and_why() -> None:
    event = _event()
    event.signups[-1].reason = "Working late"

    assert reasons(event) == "Not attending: Vex (Working late)"
    event.signups.pop()
    assert reasons(event) == ""


def test_late_changes_are_marked() -> None:
    event = _event()
    event.signups[0].late = True

    assert "🛡️ **Tanks (1)**\nKael (late)" in roster_blocks(event)[0]


def test_the_second_line_is_the_description_or_a_shark_fact() -> None:
    event = _event()
    bare = post_text(post_components(event, BEFORE))
    event.shark_fact = "Sharks are older than trees."
    fact = post_text(post_components(event, BEFORE))
    event.description = "Bring all you've got!"
    described = post_text(post_components(event, BEFORE))

    assert bare.startswith("## 🦈 [Siege] Siege night\n🕗")
    assert fact.startswith(
        "## 🦈 [Siege] Siege night\n-# Shark fact: Sharks are older than trees."
    )
    assert described.startswith("## 🦈 [Siege] Siege night\nBring all you've got!\n🕗")


def test_shark_facts_are_short_enough_for_the_database() -> None:
    assert all(len(fact) <= 200 for fact in SHARK_FACTS)
    assert shark_fact(random.Random(1)) in SHARK_FACTS
