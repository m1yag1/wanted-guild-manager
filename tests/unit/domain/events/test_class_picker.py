"""Picking a class after signing up, remembering it, and admins setting it."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest

from tests.fixtures.app import Interact
from tests.fixtures.discord import (
    ADMIN_ROLE_ID,
    GUILD_ID,
    MakeButton,
    MakeCommand,
    post_buttons,
    post_words,
)
from tests.fixtures.discord_api import FakeDiscordApi
from wgm.db.config import database_config
from wgm.domain.events.services import EventService
from wgm.lib.settings import Settings

ADMIN = {"roles": (ADMIN_ROLE_ID,)}
EVENT = {"title": "Siege night", "type": "Siege", "date": "2099-12-05", "time": "20:00"}


@pytest.fixture(autouse=True)
def roles(discord_api: FakeDiscordApi) -> FakeDiscordApi:
    discord_api.responses[f"GET /guilds/{GUILD_ID}/roles"] = (
        200,
        [{"id": ADMIN_ROLE_ID, "name": "wgm-admin", "permissions": "0"}],
    )
    return discord_api


def _content(reply: dict[str, Any]) -> str:
    return str(reply["data"]["content"])


def _post(api: FakeDiscordApi) -> str:
    edits = [
        r
        for r in api.requests
        if r.method == "PATCH" and r.path.startswith("/channels")
    ]
    return post_words(edits[-1].body)


def _rows(reply: dict[str, Any]) -> list[list[dict[str, Any]]]:
    return [row["components"] for row in reply["data"]["components"]]


async def _create(
    interact: Interact, wgm_command: MakeCommand, api: FakeDiscordApi
) -> str:
    await interact(wgm_command("event create", **ADMIN, **EVENT))
    post = [r for r in api.requests if r.method == "POST"][-1].body
    return str(post_buttons(post)[0]["custom_id"].split(":")[1])


@pytest.mark.anyio
async def test_first_time_members_pick_from_their_roles_classes(
    interact: Interact,
    wgm_command: MakeCommand,
    wgm_button: MakeButton,
    roles: FakeDiscordApi,
) -> None:
    event_id = await _create(interact, wgm_command, roles)

    prompt = await interact(wgm_button(f"signup:{event_id}:tank"))
    dropdown, buttons = _rows(prompt)
    picked = await interact(wgm_button(dropdown[0]["custom_id"], values=["Crusader"]))

    assert [o["label"] for o in dropdown[0]["options"]][:2] == ["Berserker", "Crusader"]
    assert dropdown[0]["options"][1]["description"] == "Greatsword + Sword"
    assert not any(o["default"] for o in dropdown[0]["options"])
    assert [b["label"] for b in buttons] == ["Other classes"]
    assert picked["type"] == 7
    assert _content(picked) == "You're down as **Tank** (Crusader) for **Siege night**."
    assert picked["data"]["components"] == []
    assert "🛡️ **Tanks (1)**\nKael (Crusader)" in _post(roles)


@pytest.mark.anyio
async def test_returning_members_confirm_their_last_class(
    interact: Interact,
    wgm_command: MakeCommand,
    wgm_button: MakeButton,
    roles: FakeDiscordApi,
) -> None:
    first = await _create(interact, wgm_command, roles)
    await interact(wgm_button(f"signup:{first}:tank"))
    await interact(wgm_button(f"class:pick:{first}:Tank:0", values=["Crusader"]))
    second = await _create(interact, wgm_command, roles)

    prompt = await interact(wgm_button(f"signup:{second}:tank"))
    before = _post(roles)
    dropdown, buttons = _rows(prompt)
    confirmed = await interact(wgm_button(buttons[0]["custom_id"]))

    assert "Last time you brought **Crusader**" in _content(prompt)
    assert dropdown[0]["options"][0] == {
        "label": "Crusader",
        "value": "Crusader",
        "description": "Greatsword + Sword",
        "default": True,
    }
    assert [b["label"] for b in buttons] == ["Confirm Crusader", "Other classes"]
    assert "🛡️ **Tanks (1)**\nKael\n" in before
    assert _content(confirmed).startswith("You're down as **Tank** (Crusader)")
    assert "🛡️ **Tanks (1)**\nKael (Crusader)" in _post(roles)


@pytest.mark.anyio
async def test_other_classes_offer_off_role_picks(
    interact: Interact,
    wgm_command: MakeCommand,
    wgm_button: MakeButton,
    roles: FakeDiscordApi,
) -> None:
    event_id = await _create(interact, wgm_command, roles)
    await interact(wgm_button(f"signup:{event_id}:dps"))

    more = await interact(wgm_button(f"class:more:{event_id}:DPS"))
    (groups,) = _rows(more)
    healers = await interact(wgm_button(groups[1]["custom_id"]))
    dropdown, (back,) = _rows(healers)
    went_back = await interact(wgm_button(back["custom_id"]))
    picked = await interact(wgm_button(dropdown[0]["custom_id"], values=["Seeker"]))
    again = await interact(wgm_button(f"signup:{event_id}:tank", user_id="2"))

    assert more["type"] == 7
    assert _content(more) == "Which role's classes? You'll still be down as **DPS**."
    assert [b["label"] for b in groups] == [
        "Tank classes",
        "Healer classes",
        "Back to DPS classes",
    ]
    assert _content(healers) == "Healer classes, to bring as **DPS**:"
    assert len(dropdown[0]["options"]) == 8
    assert sum(1 for row in _rows(healers) for c in row if c["type"] == 3) == 1
    assert _content(went_back).startswith("You're down as **DPS**")
    assert len(_rows(went_back)[0][0]["options"]) == 25
    assert _content(picked).startswith("You're down as **DPS** (Seeker)")
    assert "🗡️ **DPS (1)**\nKael (Seeker)" in _post(roles)
    assert again["type"] == 4


@pytest.mark.anyio
async def test_switching_roles_clears_the_class_and_old_dropdowns_say_so(
    interact: Interact,
    wgm_command: MakeCommand,
    wgm_button: MakeButton,
    roles: FakeDiscordApi,
) -> None:
    event_id = await _create(interact, wgm_command, roles)
    await interact(wgm_button(f"signup:{event_id}:tank"))
    await interact(wgm_button(f"class:pick:{event_id}:Tank:0", values=["Crusader"]))

    await interact(wgm_button(f"signup:{event_id}:healer"))
    stale = await interact(
        wgm_button(f"class:pick:{event_id}:Tank:0", values=["Warden"])
    )

    assert "💚 **Healers (1)**\nKael\n" in _post(roles)
    assert _content(stale) == "You're not down as Tank for **Siege night** anymore."


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("custom_id", "values", "message"),
    [
        ("class:pick", None, "That button isn't one of ours."),
        (
            "class:pick:not-a-uuid:Tank:0",
            ["Crusader"],
            "That button isn't one of ours.",
        ),
        ("class:ok:{event}:Tank:Nobody", None, "That class isn't on the list."),
        ("class:pick:{event}:Tank:0", [], "That class isn't on the list."),
    ],
)
async def test_broken_class_picks(
    interact: Interact,
    wgm_command: MakeCommand,
    wgm_button: MakeButton,
    roles: FakeDiscordApi,
    custom_id: str,
    values: list[str] | None,
    message: str,
) -> None:
    event_id = await _create(interact, wgm_command, roles)
    await interact(wgm_button(f"signup:{event_id}:tank"))

    reply = await interact(wgm_button(custom_id.format(event=event_id), values=values))

    assert _content(reply) == message


@pytest.mark.anyio
async def test_class_picks_after_close_are_refused(
    interact: Interact,
    wgm_command: MakeCommand,
    wgm_button: MakeButton,
    roles: FakeDiscordApi,
    settings: Settings,
) -> None:
    event_id = await _create(interact, wgm_command, roles)
    await interact(wgm_button(f"signup:{event_id}:tank"))
    async with database_config(settings.database_url).get_session() as session:
        events = EventService(session=session)
        event = await events.get(UUID(event_id))
        event.closes_at = datetime.now(UTC) - timedelta(minutes=1)
        await events.update(event, auto_commit=True)

    reply = await interact(
        wgm_button(f"class:pick:{event_id}:Tank:0", values=["Crusader"])
    )

    assert "closed" in _content(reply)


@pytest.mark.anyio
async def test_admins_can_add_members_with_a_class(
    interact: Interact,
    wgm_command: MakeCommand,
    roles: FakeDiscordApi,
) -> None:
    event_id = await _create(interact, wgm_command, roles)
    member = {"event": event_id, "member": "4242", "nicks": {"4242": "Lyra"}}

    added = await interact(
        wgm_command(
            "event add", answer="dps", **{"class": "mobilist"}, **member, **ADMIN
        )
    )
    tentative = await interact(
        wgm_command(
            "event add", answer="tentative", **{"class": "Seeker"}, **member, **ADMIN
        )
    )
    unknown = await interact(
        wgm_command("event add", answer="dps", **{"class": "Bard"}, **member, **ADMIN)
    )

    assert _content(added) == "Put **Lyra** down as DPS (Mobilist) for **Siege night**."
    assert "🗡️ **DPS (1)**\nLyra (Mobilist)" in _post(roles)
    assert _content(tentative).startswith("Pick a class from the list")
    assert _content(unknown).startswith("Pick a class from the list")


@pytest.mark.anyio
async def test_the_class_option_suggests_classes_with_their_weapons(
    interact: Interact, wgm_command: MakeCommand, roles: FakeDiscordApi
) -> None:
    event_id = await _create(interact, wgm_command, roles)
    payload = json.loads(
        wgm_command("event add", event=event_id, answer="dps", **{"class": "see"})
    )
    payload["type"] = 4
    for option in payload["data"]["options"][0]["options"][0]["options"]:
        option["focused"] = option["name"] == "class"

    reply = await interact(json.dumps(payload).encode())

    assert reply["data"]["choices"] == [
        {"name": "Seeker · Longbow + Wand", "value": "Seeker"}
    ]
    for option in payload["data"]["options"][0]["options"][0]["options"]:
        option["focused"] = option["name"] == "event"
        if option["name"] == "event":
            option["value"] = "sie"
    events = await interact(json.dumps(payload).encode())
    assert events["data"]["choices"] == [
        {"name": "Siege night · Sat Dec 5, 8:00 PM", "value": event_id}
    ]
