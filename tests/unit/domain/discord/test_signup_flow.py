"""Event channel config, posting there, and the sign-up buttons."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

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

CHANNEL = "777"
APP_ID = "1310000000000000000"
POSTING = str((1 << 10) | (1 << 11) | (1 << 14) | (1 << 16))
EVENT = {"title": "Siege night", "type": "Siege", "date": "2099-12-05", "time": "20:00"}
ADMIN = {"roles": (ADMIN_ROLE_ID,)}
# 2099-12-05 20:00 Eastern is 2099-12-06 01:00 UTC.
STARTS = datetime(2099, 12, 6, 1, 0, tzinfo=UTC)


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


def _last_edit(api: FakeDiscordApi) -> str:
    """The text of the last edit to an event post."""
    edits = [
        r
        for r in api.requests
        if r.method == "PATCH" and r.path.startswith("/channels")
    ]
    return post_words(edits[-1].body)


async def _event_id(
    interact: Interact, api: FakeDiscordApi, wgm_command: MakeCommand
) -> str:
    await interact(wgm_command("event create", **ADMIN, **EVENT))
    custom_id = post_buttons(_last_post(api))[0]["custom_id"]
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
    assert post_words(post.body).startswith("## 🦈 [Siege] Siege night\n🕗 <t:")
    assert post_buttons(post.body)[2]["label"] == "DPS"
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
    tank_post = _last_edit(roles)
    other = await interact(
        wgm_button(f"signup:{event_id}:tentative", user_id="2", nick=None)
    )
    await interact(wgm_button(f"signup:{event_id}:healer"))
    healer = _last_edit(roles)
    again = await interact(wgm_button(f"signup:{event_id}:healer"))
    still = _last_edit(roles)
    tentative = await interact(
        wgm_button(f"signup:{event_id}:tentative", user_id="2", nick=None)
    )

    assert tank["type"] == 4
    assert tank["data"]["flags"] == 64
    assert _content(tank).startswith("You're down as **Tank**")
    assert "🛡️ **Tanks (1)**\nKael" in tank_post
    assert "**Tentative (1)**: Mason" in post_words(other["data"])
    assert "🛡️ **Tanks (0)**\n-" in healer
    assert "💚 **Healers (1)**\nKael" in healer
    # Pressing your answer again keeps you on the roster.
    assert _content(again).startswith("You're down as **Healer**")
    assert "💚 **Healers (1)**\nKael" in still
    assert "**Tentative (1)**: Mason" in post_words(tentative["data"])
    assert post_buttons(tentative["data"])[0]["label"] == "Healer"


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


def _closes(post: dict[str, Any]) -> str:
    lines = post_words(post).splitlines()
    return next(line for line in lines if line.startswith("🔒 Sign-ups"))[2:]


def _stamp(moment: datetime) -> int:
    return int(moment.timestamp())


@pytest.mark.anyio
async def test_sign_ups_close_30_minutes_before_unless_chosen(
    interact: Interact,
    wgm_command: MakeCommand,
    roles: FakeDiscordApi,
) -> None:
    await interact(wgm_command("event create", **ADMIN, **EVENT))
    default = _closes(_last_post(roles))
    await interact(wgm_command("event create", close=0, **ADMIN, **EVENT))
    at_start = _closes(_last_post(roles))
    listed = await interact(wgm_command("event list"))

    half_hour = _stamp(STARTS - timedelta(minutes=30))
    assert default == f"Sign-ups close <t:{half_hour}:R>"
    assert at_start == f"Sign-ups close <t:{_stamp(STARTS)}:R>"
    assert f"Sign-ups close <t:{half_hour}:R>\nAttending 0" in _content(listed)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("minutes", "said"),
    [
        (60, "60 minutes before the start"),
        (1, "1 minute before the start"),
        (0, "at the start"),
    ],
)
async def test_admins_choose_the_server_close_time(
    interact: Interact,
    wgm_command: MakeCommand,
    roles: FakeDiscordApi,
    minutes: int,
    said: str,
) -> None:
    before = await interact(wgm_command("event settings", **ADMIN))
    reply = await interact(wgm_command("event close-time", minutes=minutes, **ADMIN))
    after = await interact(wgm_command("event settings", **ADMIN))
    await interact(wgm_command("event create", **ADMIN, **EVENT))

    assert "Sign-ups close: 30 minutes before the start" in _content(before)
    assert _content(reply).startswith(f"Sign-ups for new events will close {said}.")
    assert f"Sign-ups close: {said}" in _content(after)
    closes = _stamp(STARTS - timedelta(minutes=minutes))
    assert _closes(_last_post(roles)) == f"Sign-ups close <t:{closes}:R>"


@pytest.mark.anyio
async def test_members_cannot_change_the_close_time(
    interact: Interact, wgm_command: MakeCommand
) -> None:
    reply = await interact(wgm_command("event close-time", minutes=5))

    assert _content(reply).startswith("You need the wgm-admin role")


@pytest.mark.anyio
async def test_events_whose_sign_ups_would_already_be_closed_are_refused(
    interact: Interact,
    wgm_command: MakeCommand,
    roles: FakeDiscordApi,
) -> None:
    soon = datetime.now(ZoneInfo("America/New_York")) + timedelta(hours=1)
    event = {**EVENT, "date": f"{soon:%Y-%m-%d}", "time": f"{soon:%H:%M}"}

    reply = await interact(wgm_command("event create", close=120, **ADMIN, **event))

    assert "already passed" in _content(reply)
    assert not [r for r in roles.requests if r.method == "POST"]


@pytest.mark.anyio
async def test_buttons_refuse_changes_after_sign_ups_close(
    interact: Interact,
    wgm_command: MakeCommand,
    wgm_button: MakeButton,
    roles: FakeDiscordApi,
    settings: Settings,
) -> None:
    event_id = await _event_id(interact, roles, wgm_command)
    await interact(wgm_button(f"signup:{event_id}:tank"))
    closed = datetime.now(UTC) - timedelta(minutes=1)
    async with database_config(settings.database_url).get_session() as session:
        events = EventService(session=session)
        event = await events.get(UUID(event_id))
        event.closes_at = closed
        await events.update(event, auto_commit=True)

    reply = await interact(wgm_button(f"signup:{event_id}:dps"))
    listed = await interact(wgm_command("event list"))

    assert reply["type"] == 4
    assert reply["data"]["flags"] == 64
    assert _content(reply).startswith(
        f"Sign-ups for **Siege night** closed <t:{_stamp(closed)}:R>"
    )
    assert "wgm-admin" in _content(reply)
    assert "Attending 1" in _content(listed)
