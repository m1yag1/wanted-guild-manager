from datetime import UTC, datetime, timedelta
from uuid import uuid4

from wgm.db.models import Event, Signup, SignupStatus
from wgm.domain.events.roster import (
    buttons,
    closing_line,
    event_post,
    reasons,
    roster,
    tally,
    when,
)

STARTS = datetime(2026, 12, 6, 1, 0, tzinfo=UTC)
CLOSES = STARTS - timedelta(minutes=30)
BEFORE = CLOSES - timedelta(hours=1)


def _event() -> Event:
    event = Event(
        id=uuid4(),
        guild_id="1",
        title="Siege night",
        event_type="Siege",
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


def test_roster_groups_like_the_signup_sheet() -> None:
    assert roster(_event()) == (
        "**Attending (3)**\n"
        "Tank (1): Kael\n"
        "Healer (2): Mira, Rook\n"
        "DPS (0): -\n"
        "**Tentative (1)**: Ash\n"
        "**Not attending (1)**: Vex"
    )


def test_post_has_heading_then_roster() -> None:
    post = event_post(_event(), BEFORE)

    assert post.startswith("**Siege night** · Siege\n<t:")
    assert f"\nSign-ups close <t:{int(CLOSES.timestamp())}:R>\n\n" in post
    assert "\n\n**Attending (3)**" in post


def test_buttons_carry_the_event_and_choice() -> None:
    event = _event()
    row = buttons(event, BEFORE)[0]["components"]

    assert [b["label"] for b in row] == [
        "Tank",
        "Healer",
        "DPS",
        "Tentative",
        "Not attending",
    ]
    assert row[0]["custom_id"] == f"signup:{event.id}:tank"
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

    assert "Tank (1): Kael (late)" in roster(event)
