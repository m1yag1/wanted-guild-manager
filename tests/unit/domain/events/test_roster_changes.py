"""Admins changing the roster, late marks, Not attending reasons and history."""

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
    MakeForm,
    post_buttons,
    post_words,
)
from tests.fixtures.discord_api import FakeDiscordApi
from wgm.db.config import database_config
from wgm.db.models import SignupAction
from wgm.domain.events.services import EventService
from wgm.lib.settings import Settings

ADMIN = {"roles": (ADMIN_ROLE_ID,)}
ADMIN_ID = "53908232506183680"
MEMBER = "4242"
NICKS = {MEMBER: "Lyra"}
POST = "/channels/1290000000000000001/messages/5550001"
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


def _post_edits(api: FakeDiscordApi) -> list[Any]:
    return [r.body for r in api.requests if (r.method, r.path) == ("PATCH", POST)]


@pytest.fixture
async def event_id(
    interact: Interact, wgm_command: MakeCommand, roles: FakeDiscordApi
) -> str:
    await interact(wgm_command("event create", **ADMIN, **EVENT))
    post = [r for r in roles.requests if r.method == "POST"][-1].body
    return str(post_buttons(post)[0]["custom_id"].split(":")[1])


async def _close(settings: Settings, event_id: str) -> None:
    async with database_config(settings.database_url).get_session() as session:
        events = EventService(session=session)
        event = await events.get(UUID(event_id))
        event.closes_at = datetime.now(UTC) - timedelta(minutes=1)
        await events.update(event, auto_commit=True)


@pytest.mark.anyio
async def test_admins_add_members_and_changes_after_close_are_late(
    interact: Interact,
    wgm_command: MakeCommand,
    roles: FakeDiscordApi,
    settings: Settings,
    event_id: str,
) -> None:
    added = await interact(
        wgm_command(
            "event add",
            event=event_id,
            member=MEMBER,
            answer="dps",
            nicks=NICKS,
            **ADMIN,
        )
    )
    on_time = post_words(_post_edits(roles)[-1])
    await _close(settings, event_id)
    late = await interact(
        wgm_command(
            "event add",
            event=event_id,
            member=MEMBER,
            answer="healer",
            nicks=NICKS,
            **ADMIN,
        )
    )
    locked = _post_edits(roles)[-1]

    assert _content(added) == "Put **Lyra** down as DPS for **Siege night**."
    assert "🗡️ **DPS (1)**\nLyra\n" in on_time
    assert _content(late) == "Put **Lyra** down as Healer (late) for **Siege night**."
    assert "💚 **Healers (1)**\nLyra (late)" in post_words(locked)
    assert "🗡️ **DPS (0)**\n-" in post_words(locked)
    assert all(b["disabled"] for b in post_buttons(locked))


@pytest.mark.anyio
async def test_admins_remove_members(
    interact: Interact,
    wgm_command: MakeCommand,
    wgm_button: MakeButton,
    roles: FakeDiscordApi,
    event_id: str,
) -> None:
    await interact(wgm_button(f"signup:{event_id}:tank", user_id=MEMBER, nick="Lyra"))

    removed = await interact(
        wgm_command("event remove", event=event_id, member=MEMBER, nicks=NICKS, **ADMIN)
    )
    again = await interact(
        wgm_command("event remove", event=event_id, member=MEMBER, nicks=NICKS, **ADMIN)
    )

    assert _content(removed) == "Took **Lyra** off the roster for **Siege night**."
    assert "🛡️ **Tanks (0)**\n-" in post_words(_post_edits(roles)[-1])
    assert _content(again) == "**Lyra** isn't on the roster for **Siege night**."


@pytest.mark.anyio
@pytest.mark.parametrize("command", ["event add", "event remove"])
async def test_members_cannot_change_the_roster_and_events_must_be_picked(
    interact: Interact, wgm_command: MakeCommand, event_id: str, command: str
) -> None:
    values = {"event": event_id, "member": MEMBER, "answer": "dps", "nicks": NICKS}

    member = await interact(wgm_command(command, **values))
    unknown = await interact(wgm_command(command, **{**values, "event": "x"}, **ADMIN))

    assert _content(member).startswith("You need the wgm-admin role")
    assert _content(unknown).startswith("Pick an upcoming event")


@pytest.mark.anyio
async def test_not_attending_asks_for_an_optional_reason_only_admins_see(
    interact: Interact,
    wgm_command: MakeCommand,
    wgm_button: MakeButton,
    wgm_form: MakeForm,
    event_id: str,
) -> None:
    form = await interact(wgm_button(f"signup:{event_id}:not_attending"))
    with_reason = await interact(wgm_form(f"reason:{event_id}"))
    member_list = await interact(wgm_command("event list"))
    admin_list = await interact(wgm_command("event list", **ADMIN))
    await interact(wgm_form(f"reason:{event_id}", reason="  "))
    blank = await interact(wgm_command("event list", **ADMIN))
    reopened = await interact(wgm_button(f"signup:{event_id}:not_attending"))

    assert form["type"] == 9
    assert form["data"]["custom_id"] == f"reason:{event_id}"
    field = form["data"]["components"][0]["components"][0]
    assert (field["custom_id"], field["required"]) == ("reason", False)
    assert with_reason["type"] == 7
    assert "**Not attending (1)**: Kael" in post_words(with_reason["data"])
    assert "Working late" not in post_words(with_reason["data"])
    assert "Working late" not in _content(member_list)
    assert "Not attending: Kael (Working late)" in _content(admin_list)
    assert "Not attending: Kael\n" in _content(blank) + "\n"
    assert reopened["type"] == 9  # the form again, to change the reason


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("custom_id", "message"),
    [
        ("reason:not-a-uuid", "That form isn't one of ours."),
        ("reason:00000000-0000-0000-0000-000000000000", "That event no longer exists."),
    ],
)
async def test_unknown_reason_forms(
    interact: Interact, wgm_form: MakeForm, custom_id: str, message: str
) -> None:
    reply = await interact(wgm_form(custom_id))

    assert _content(reply) == message


@pytest.mark.anyio
async def test_every_change_is_kept_in_the_history(
    interact: Interact,
    wgm_command: MakeCommand,
    wgm_button: MakeButton,
    settings: Settings,
    event_id: str,
) -> None:
    await interact(wgm_button(f"signup:{event_id}:tank"))
    await interact(wgm_button(f"signup:{event_id}:dps"))
    await _close(settings, event_id)
    await interact(
        wgm_command("event remove", event=event_id, member=ADMIN_ID, **ADMIN)
    )

    async with database_config(settings.database_url).get_session() as session:
        events = EventService(session=session)
        event = await events.get(UUID(event_id))
        history = await events.history(event)

    assert [(c.action, c.role, c.changed_by, c.late) for c in history] == [
        (SignupAction.ADDED, "Tank", ADMIN_ID, False),
        (SignupAction.CHANGED, "DPS", ADMIN_ID, False),
        (SignupAction.REMOVED, None, ADMIN_ID, True),
    ]


@pytest.mark.anyio
async def test_the_reason_form_remembers_the_last_reason_and_history_keeps_each(
    interact: Interact,
    wgm_button: MakeButton,
    wgm_form: MakeForm,
    settings: Settings,
    event_id: str,
) -> None:
    first = await interact(wgm_button(f"signup:{event_id}:not_attending"))
    await interact(wgm_form(f"reason:{event_id}", reason="Working late"))
    await interact(wgm_button(f"signup:{event_id}:tentative"))
    again = await interact(wgm_button(f"signup:{event_id}:not_attending"))
    await interact(wgm_form(f"reason:{event_id}", reason="Out of town"))

    async with database_config(settings.database_url).get_session() as session:
        events = EventService(session=session)
        history = await events.history(await events.get(UUID(event_id)))

    def field(form: dict[str, Any]) -> dict[str, Any]:
        component: dict[str, Any] = form["data"]["components"][0]["components"][0]
        return component

    assert "value" not in field(first)
    assert field(again)["value"] == "Working late"
    assert [c.reason for c in history] == ["Working late", None, "Out of town"]
