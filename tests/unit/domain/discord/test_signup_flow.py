"""Event channel config, posting there, and the sign-up buttons."""

from typing import Any

import pytest

from tests.fixtures.app import Interact
from tests.fixtures.discord import (
    ADMIN_ROLE_ID,
    GUILD_ID,
    MakeButton,
    MakeCommand,
)
from tests.fixtures.discord_api import FakeDiscordApi

CHANNEL = "777"
APP_ID = "1310000000000000000"
POSTING = str((1 << 10) | (1 << 11) | (1 << 14) | (1 << 16))
EVENT = {"title": "Siege night", "type": "Siege", "date": "2099-12-05", "time": "20:00"}
ADMIN = {"roles": (ADMIN_ROLE_ID,)}


@pytest.fixture(autouse=True)
def roles(discord_api: FakeDiscordApi) -> FakeDiscordApi:
    discord_api.responses[f"GET /guilds/{GUILD_ID}/roles"] = (
        200,
        [
            {"id": GUILD_ID, "name": "@everyone", "permissions": POSTING},
            {"id": ADMIN_ROLE_ID, "name": "wgm-admin", "permissions": "0"},
        ],
    )
    discord_api.responses[f"GET /guilds/{GUILD_ID}/members/{APP_ID}"] = (
        200,
        {"roles": []},
    )
    discord_api.responses[f"POST /channels/{CHANNEL}/messages"] = (
        200,
        {"id": "5550001"},
    )
    discord_api.responses[f"GET /channels/{CHANNEL}"] = (
        200,
        {"id": CHANNEL, "name": "sign-up", "permission_overwrites": []},
    )
    return discord_api


def _content(reply: dict[str, Any]) -> str:
    return str(reply["data"]["content"])


def _last_post(api: FakeDiscordApi) -> dict[str, Any]:
    """The last message the app posted in a channel."""
    posts = [r for r in api.requests if r.method == "POST" and "/messages" in r.path]
    body: dict[str, Any] = posts[-1].body
    return body


async def _event_id(
    interact: Interact, api: FakeDiscordApi, wgm_command: MakeCommand
) -> str:
    await interact(wgm_command("event create", **ADMIN, **EVENT))
    custom_id = _last_post(api)["components"][0]["components"][0]["custom_id"]
    return str(custom_id.split(":")[1])


@pytest.mark.anyio
async def test_config_shows_defaults(
    interact: Interact, wgm_command: MakeCommand
) -> None:
    reply = await interact(wgm_command("event settings", **ADMIN))
    server = await interact(wgm_command("config show", **ADMIN))

    assert "Channel: not set" in _content(reply)
    assert "Times are entered in: America/New_York" in _content(reply)
    assert "Time zone: America/New_York" in _content(server)


@pytest.mark.anyio
async def test_events_post_in_the_configured_channel(
    interact: Interact,
    wgm_command: MakeCommand,
    roles: FakeDiscordApi,
) -> None:
    set_reply = await interact(wgm_command("event channel", channel=CHANNEL, **ADMIN))
    shown = await interact(wgm_command("event settings", **ADMIN))
    again = await interact(wgm_command("event channel", channel=CHANNEL, **ADMIN))
    created = await interact(wgm_command("event create", **ADMIN, **EVENT))

    assert _content(set_reply).startswith(
        f"New events will be posted in <#{CHANNEL}>.\n\nPermissions the app needs"
    )
    assert "✅ Send Messages" in _content(set_reply)
    assert "❌" not in _content(set_reply)
    assert f"Channel: <#{CHANNEL}>" in _content(shown)
    assert "⚠️" not in _content(shown)
    assert _content(again) == _content(set_reply)
    assert _content(created) == f"Posted **Siege night** in <#{CHANNEL}>."
    post = next(r for r in roles.requests if r.method == "POST")
    assert post.path == f"/channels/{CHANNEL}/messages"
    assert post.body["content"].startswith("**Siege night**")
    assert post.body["components"][0]["components"][2]["label"] == "DPS"
    assert post.body["allowed_mentions"] == {"parse": []}


@pytest.mark.anyio
async def test_members_cannot_change_settings(
    interact: Interact, wgm_command: MakeCommand
) -> None:
    reply = await interact(wgm_command("event channel", channel=CHANNEL))

    assert _content(reply).startswith("You need the wgm-admin role")


@pytest.mark.anyio
async def test_buttons_sign_up_change_and_remove(
    interact: Interact,
    wgm_command: MakeCommand,
    wgm_button: MakeButton,
    roles: FakeDiscordApi,
) -> None:
    event_id = await _event_id(interact, roles, wgm_command)

    tank = await interact(wgm_button(f"signup:{event_id}:tank"))
    other = await interact(
        wgm_button(f"signup:{event_id}:tentative", user_id="2", nick=None)
    )
    healer = await interact(wgm_button(f"signup:{event_id}:healer"))
    removed = await interact(wgm_button(f"signup:{event_id}:healer"))

    assert tank["type"] == 7
    assert "Tank (1): Kael" in _content(tank)
    assert "**Tentative (1)**: Mason" in _content(other)
    assert "Tank (0): -" in _content(healer)
    assert "Healer (1): Kael" in _content(healer)
    assert "**Attending (0)**" in _content(removed)
    assert "**Tentative (1)**: Mason" in _content(removed)
    assert removed["data"]["components"][0]["components"][0]["label"] == "Tank"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("custom_id", "message"),
    [
        ("other:thing", "isn't one of ours"),
        ("signup:not-a-uuid:tank", "isn't one of ours"),
        ("signup:00000000-0000-0000-0000-000000000000:dance", "isn't one of ours"),
        ("signup:00000000-0000-0000-0000-000000000000:tank", "no longer exists"),
    ],
)
async def test_unknown_buttons(
    interact: Interact,
    wgm_button: MakeButton,
    custom_id: str,
    message: str,
) -> None:
    reply = await interact(wgm_button(custom_id))

    assert message in _content(reply)
    assert reply["data"]["flags"] == 64


@pytest.mark.anyio
async def test_a_channel_the_app_cannot_post_in_is_explained(
    interact: Interact,
    wgm_command: MakeCommand,
    roles: FakeDiscordApi,
) -> None:
    roles.responses[f"POST /channels/{CHANNEL}/messages"] = (
        403,
        {"message": "Missing Access", "code": 50001},
    )
    await interact(wgm_command("event channel", channel=CHANNEL, **ADMIN))

    created = await interact(wgm_command("event create", **ADMIN, **EVENT))
    listed = await interact(wgm_command("event list"))

    assert _content(created).startswith(
        f"I couldn't post in <#{CHANNEL}>, so the event wasn't created."
    )
    assert created["data"]["flags"] == 64
    assert _content(listed) == "No upcoming events."


@pytest.mark.anyio
async def test_a_channel_the_app_cannot_see_is_not_saved(
    interact: Interact,
    wgm_command: MakeCommand,
    roles: FakeDiscordApi,
) -> None:
    roles.responses[f"GET /channels/{CHANNEL}"] = (
        403,
        {"message": "Missing Access", "code": 50001},
    )

    reply = await interact(wgm_command("event channel", channel=CHANNEL, **ADMIN))
    shown = await interact(wgm_command("event settings", **ADMIN))

    assert _content(reply).startswith(f"I didn't save <#{CHANNEL}>")
    assert "❌ View Channel" in _content(reply)
    assert "Edit Channel** → **Permissions**" in _content(reply)
    assert "403" not in _content(reply)
    assert "Channel: not set" in _content(shown)


@pytest.mark.anyio
async def test_config_show_warns_when_the_channel_stops_working(
    interact: Interact,
    wgm_command: MakeCommand,
    roles: FakeDiscordApi,
) -> None:
    await interact(wgm_command("event channel", channel=CHANNEL, **ADMIN))
    roles.responses[f"GET /channels/{CHANNEL}"] = (
        403,
        {"message": "Missing Access", "code": 50001},
    )

    shown = await interact(wgm_command("event settings", **ADMIN))

    assert "⚠️ Events can't be posted there yet." in _content(shown)
    assert "❌ Embed Links" in _content(shown)


@pytest.mark.anyio
async def test_setup_checks_the_event_channel(
    interact: Interact,
    wgm_command: MakeCommand,
    roles: FakeDiscordApi,
) -> None:
    first = await interact(wgm_command("setup", **ADMIN))
    await interact(wgm_command("event channel", channel=CHANNEL, **ADMIN))
    roles.responses[f"GET /channels/{CHANNEL}"] = (
        200,
        {
            "id": CHANNEL,
            "permission_overwrites": [
                {"id": GUILD_ID, "type": 0, "allow": "0", "deny": str(1 << 11)}
            ],
        },
    )

    second = await interact(wgm_command("setup", **ADMIN))

    assert "Next, choose where events go" in _content(first)
    assert "✅ View Channel" in _content(second)
    assert "❌ Send Messages" in _content(second)
