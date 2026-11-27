from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from wgm.domain.discord.commands import SUBCOMMANDS, selected, wgm_command
from wgm.domain.discord.schemas import InteractionOption
from wgm.domain.events.services import EventInputError, parse_start

EASTERN = ZoneInfo("America/New_York")
NOW = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)


def test_wgm_groups_event_subcommands() -> None:
    command = wgm_command()
    top = {option["name"]: option for option in command["options"]}

    assert set(top) == {"help", "setup", "event", "config"}
    assert top["event"]["type"] == 2
    assert [o["name"] for o in top["event"]["options"]] == [
        "create",
        "list",
        "channel",
        "close-time",
        "settings",
    ]
    assert [o["name"] for o in top["config"]["options"]] == ["show"]


def test_event_create_offers_the_event_types() -> None:
    create = next(sub for sub in SUBCOMMANDS if sub.path == ("event", "create"))
    kinds = next(o for o in create.options if o["name"] == "type")["choices"]

    assert [kind["value"] for kind in kinds][:2] == ["Siege", "Boonstone"]
    assert create.allowed_roles == ("wgm-admin",)


def test_selected_walks_groups_and_collects_values() -> None:
    options = [
        InteractionOption(
            "event",
            2,
            options=[
                InteractionOption(
                    "create", 1, options=[InteractionOption("title", 3, "Siege")]
                )
            ],
        )
    ]

    assert selected(options) == (("event", "create"), {"title": "Siege"})


def test_typed_times_are_eastern_by_default() -> None:
    # 8 pm Eastern in December (EST, UTC-5) is 01:00 UTC the next day.
    starts = parse_start("2026-12-05", "20:00", EASTERN, NOW)

    assert starts == datetime(2026, 12, 6, 1, 0, tzinfo=UTC)


def test_summer_times_follow_daylight_saving() -> None:
    starts = parse_start("2027-07-05", "20:00", EASTERN, NOW)

    assert starts == datetime(2027, 7, 6, 0, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("day", "clock"), [("12/05/2026", "20:00"), ("2026-12-05", "8pm")]
)
def test_malformed_dates_and_times(day: str, clock: str) -> None:
    with pytest.raises(EventInputError, match="2026-12-05"):
        parse_start(day, clock, EASTERN, NOW)


def test_past_times_are_refused() -> None:
    with pytest.raises(EventInputError, match="already passed"):
        parse_start("2026-11-01", "20:00", EASTERN, NOW)
