"""`/wgm event edit` and `cancel`, end to end, with the event picker."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any

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

ADMIN = {"roles": (ADMIN_ROLE_ID,)}
CHANNEL = "1290000000000000001"
POST = f"/channels/{CHANNEL}/messages/5550001"
EVENT = {"title": "Siege night", "type": "Siege", "date": "2099-12-05", "time": "20:00"}
# 2099-12-05 20:00 Eastern is 2099-12-06 01:00 UTC.
STARTS = datetime(2099, 12, 6, 1, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def roles(discord_api: FakeDiscordApi) -> FakeDiscordApi:
    discord_api.responses[f"GET /guilds/{GUILD_ID}/roles"] = (
        200,
        [{"id": ADMIN_ROLE_ID, "name": "wgm-admin", "permissions": "0"}],
    )
    return discord_api


def _content(reply: dict[str, Any]) -> str:
    return str(reply["data"]["content"])


def _edits(api: FakeDiscordApi) -> list[Any]:
    return [r.body for r in api.requests if (r.method, r.path) == ("PATCH", POST)]


def _event_id(api: FakeDiscordApi) -> str:
    post = [r for r in api.requests if r.method == "POST"][-1].body
    return str(post_buttons(post)[0]["custom_id"].split(":")[1])


@pytest.fixture
async def event_id(
    interact: Interact, wgm_command: MakeCommand, roles: FakeDiscordApi
) -> str:
    await interact(wgm_command("event create", **ADMIN, **EVENT))
    return _event_id(roles)


def _typing(command: bytes, option: str) -> bytes:
    """Turn a command body into Discord asking for suggestions for `option`."""
    payload = json.loads(command)
    payload["type"] = 4
    leaf = payload["data"]["options"][0]["options"][0]["options"]
    for each in leaf:
        each["focused"] = each["name"] == option
    return json.dumps(payload).encode()


@pytest.mark.anyio
async def test_the_event_picker_suggests_upcoming_events_by_title(
    interact: Interact, wgm_command: MakeCommand, event_id: str
) -> None:
    await interact(wgm_command("event create", **ADMIN, **{**EVENT, "title": "Raid"}))

    everything = await interact(_typing(wgm_command("event edit", event=""), "event"))
    siege = await interact(_typing(wgm_command("event cancel", event="sie"), "event"))

    assert everything["type"] == 8
    assert [c["name"] for c in everything["data"]["choices"]] == [
        "Siege night · Sat Dec 5, 8:00 PM",
        "Raid · Sat Dec 5, 8:00 PM",
    ]
    assert siege["data"]["choices"] == [
        {"name": "Siege night · Sat Dec 5, 8:00 PM", "value": event_id}
    ]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "command",
    [
        "help",  # no suggestions for this command
        "event list",
    ],
)
async def test_commands_without_a_picker_suggest_nothing(
    interact: Interact, wgm_command: MakeCommand, command: str
) -> None:
    payload = json.loads(wgm_command(command))
    payload["type"] = 4

    reply = await interact(json.dumps(payload).encode())

    assert reply == {"type": 8, "data": {"choices": []}}


@pytest.mark.anyio
async def test_editing_updates_the_event_and_its_post(
    interact: Interact,
    wgm_command: MakeCommand,
    roles: FakeDiscordApi,
    event_id: str,
) -> None:
    reply = await interact(
        wgm_command(
            "event edit", event=event_id, title="Siege, moved", time="21:00", **ADMIN
        )
    )
    listed = await interact(wgm_command("event list"))

    later = STARTS + timedelta(hours=1)
    assert _content(reply).startswith("Updated **Siege, moved**: title, time.")
    edit = _edits(roles)[-1]
    assert post_words(edit).startswith("## 🦈 [Siege] Siege, moved\n")
    closes = int((later - timedelta(minutes=30)).timestamp())
    assert f"Sign-ups close <t:{closes}:R>" in post_words(edit)
    assert edit["allowed_mentions"] == {"parse": []}
    assert f"<t:{int(later.timestamp())}:F>" in _content(listed)


@pytest.mark.anyio
async def test_editing_the_type_and_close(
    interact: Interact,
    wgm_command: MakeCommand,
    roles: FakeDiscordApi,
    event_id: str,
) -> None:
    reply = await interact(
        wgm_command("event edit", event=event_id, type="Boonstone", close=0, **ADMIN)
    )

    assert _content(reply).startswith("Updated **Siege night**: type, close.")
    assert "## 🦈 [Boonstone] Siege night\n" in post_words(_edits(roles)[-1])
    assert f"Sign-ups close <t:{int(STARTS.timestamp())}:R>" in _content(reply)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({}, "Nothing to change."),
        ({"date": "soon"}, "Use a date like 2026-12-05"),
        ({"event": "Siege night"}, "Pick an upcoming event from the list"),
    ],
)
async def test_edits_that_cannot_work_are_explained(
    interact: Interact,
    wgm_command: MakeCommand,
    roles: FakeDiscordApi,
    event_id: str,
    values: dict[str, str],
    message: str,
) -> None:
    reply = await interact(
        wgm_command("event edit", **{"event": event_id, **values}, **ADMIN)
    )

    assert _content(reply).startswith(message)
    assert not _edits(roles)


@pytest.mark.anyio
async def test_members_cannot_edit_or_cancel(
    interact: Interact, wgm_command: MakeCommand, event_id: str
) -> None:
    edit = await interact(wgm_command("event edit", event=event_id, title="Mine"))
    cancel = await interact(wgm_command("event cancel", event=event_id))

    assert _content(edit).startswith("You need the wgm-admin role")
    assert _content(cancel).startswith("You need the wgm-admin role")


@pytest.mark.anyio
async def test_cancelling_marks_the_post_and_removes_the_buttons(
    interact: Interact,
    wgm_command: MakeCommand,
    wgm_button: MakeButton,
    roles: FakeDiscordApi,
    event_id: str,
) -> None:
    reply = await interact(wgm_command("event cancel", event=event_id, **ADMIN))
    again = await interact(wgm_command("event cancel", event=event_id, **ADMIN))
    listed = await interact(wgm_command("event list"))
    pressed = await interact(wgm_button(f"signup:{event_id}:tank"))

    assert _content(reply).startswith("Cancelled **Siege night**.")
    edit = _edits(roles)[-1]
    assert "❌ **Cancelled**" in post_words(edit)
    assert post_buttons(edit) == []
    assert _content(again).startswith("Pick an upcoming event")
    assert _content(listed) == "No upcoming events."
    assert _content(pressed) == "**Siege night** was cancelled."
    assert pressed["data"]["flags"] == 64


@pytest.mark.anyio
async def test_a_deleted_post_is_mentioned_but_the_change_is_kept(
    interact: Interact,
    wgm_command: MakeCommand,
    roles: FakeDiscordApi,
    event_id: str,
) -> None:
    roles.responses[f"PATCH {POST}"] = (404, {"code": 10008})

    reply = await interact(
        wgm_command("event edit", event=event_id, title="New", **ADMIN)
    )
    listed = await interact(wgm_command("event list"))

    assert "I couldn't update the post" in _content(reply)
    assert "**New**" in _content(listed)


def _deletes(api: FakeDiscordApi) -> list[str]:
    return [r.path for r in api.requests if r.method == "DELETE"]


@pytest.mark.anyio
async def test_deleting_removes_the_post_and_hides_the_event(
    interact: Interact,
    wgm_command: MakeCommand,
    wgm_button: MakeButton,
    roles: FakeDiscordApi,
    event_id: str,
) -> None:
    await interact(wgm_command("event cancel", event=event_id, **ADMIN))
    picker = await interact(_typing(wgm_command("event delete", event=""), "event"))

    reply = await interact(wgm_command("event delete", event=event_id, **ADMIN))
    again = await interact(wgm_command("event delete", event=event_id, **ADMIN))
    after = await interact(_typing(wgm_command("event delete", event=""), "event"))
    pressed = await interact(wgm_button(f"signup:{event_id}:tank"))

    assert picker["data"]["choices"][0]["name"].endswith("(cancelled)")
    assert _content(reply).startswith("Deleted **Siege night** and removed its post.")
    assert _deletes(roles) == [POST]
    assert _content(again).startswith("Pick an upcoming event")
    assert after["data"]["choices"] == []
    assert _content(pressed) == "That event no longer exists."


@pytest.mark.anyio
@pytest.mark.parametrize(("status", "warned"), [(404, False), (403, True)])
async def test_deleting_when_the_post_is_gone_or_out_of_reach(
    interact: Interact,
    wgm_command: MakeCommand,
    roles: FakeDiscordApi,
    event_id: str,
    status: int,
    warned: bool,
) -> None:
    roles.responses[f"DELETE {POST}"] = (status, {"code": 0})

    reply = await interact(wgm_command("event delete", event=event_id, **ADMIN))
    listed = await interact(wgm_command("event list"))

    assert _content(reply).startswith("Deleted **Siege night**")
    assert ("delete it by hand" in _content(reply)) is warned
    assert _content(listed) == "No upcoming events."


@pytest.mark.anyio
async def test_members_cannot_delete(
    interact: Interact, wgm_command: MakeCommand, event_id: str
) -> None:
    reply = await interact(wgm_command("event delete", event=event_id))

    assert _content(reply).startswith("You need the wgm-admin role")


@pytest.mark.anyio
async def test_descriptions_are_set_changed_and_cleared(
    interact: Interact, wgm_command: MakeCommand, roles: FakeDiscordApi
) -> None:
    rivals = "We're fighting the Krakens, so bring all you've got!"
    await interact(wgm_command("event create", description=rivals, **ADMIN, **EVENT))
    created = [r for r in roles.requests if r.method == "POST"][-1].body
    event_id = post_buttons(created)[0]["custom_id"].split(":")[1]

    await interact(
        wgm_command("event edit", event=event_id, description="Gear up!", **ADMIN)
    )
    changed = post_words(_edits(roles)[-1])
    await interact(wgm_command("event edit", event=event_id, description="-", **ADMIN))
    cleared = post_words(_edits(roles)[-1])

    assert post_words(created).startswith(f"## 🦈 [Siege] Siege night\n{rivals}\n")
    assert changed.startswith("## 🦈 [Siege] Siege night\nGear up!\n")
    assert cleared.startswith("## 🦈 [Siege] Siege night\n-# Shark fact: ")
