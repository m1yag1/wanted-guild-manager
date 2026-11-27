"""/wgm commands end to end: signed request in, reply out, database and fake API."""

from typing import Any

import pytest
from litestar import Litestar
from litestar.testing import AsyncTestClient

from tests.fixtures.discord import (
    ADMIN_ROLE_ID,
    GUILD_ID,
    MANAGE_SERVER,
    MakeCommand,
    Sign,
)
from tests.fixtures.discord_api import FakeDiscordApi

ROLES = f"GET /guilds/{GUILD_ID}/roles"
CREATE_ROLE = f"POST /guilds/{GUILD_ID}/roles"
EVENT = {"title": "Siege night", "type": "Siege", "date": "2099-12-05", "time": "20:00"}


@pytest.fixture
def roles(discord_api: FakeDiscordApi) -> FakeDiscordApi:
    """The server already has the wgm-admin role."""
    discord_api.responses[ROLES] = (
        200,
        [{"id": "1", "name": "@everyone"}, {"id": ADMIN_ROLE_ID, "name": "wgm-admin"}],
    )
    return discord_api


async def _run(app: Litestar, sign: Sign, body: bytes) -> dict[str, Any]:
    signed, headers = sign(body)
    async with AsyncTestClient(app=app) as client:
        response = await client.post(
            "/discord/interactions", content=signed, headers=headers
        )
    assert response.status_code == 200, response.text
    reply: dict[str, Any] = response.json()
    return reply


def _content(reply: dict[str, Any]) -> str:
    return str(reply["data"]["content"])


def _private(reply: dict[str, Any]) -> bool:
    return bool(reply["data"].get("flags") == 64)


@pytest.mark.anyio
async def test_help_shows_members_only_what_they_can_use(
    app: Litestar, sign: Sign, wgm_command: MakeCommand, roles: FakeDiscordApi
) -> None:
    reply = await _run(app, sign, wgm_command("help"))

    assert "`/wgm help`" in _content(reply)
    assert "`/wgm event list`" in _content(reply)
    assert "event create" not in _content(reply)


@pytest.mark.anyio
async def test_help_shows_admins_everything(
    app: Litestar, sign: Sign, wgm_command: MakeCommand, roles: FakeDiscordApi
) -> None:
    reply = await _run(app, sign, wgm_command("help", roles=(ADMIN_ROLE_ID,)))

    assert "`/wgm event create`" in _content(reply)
    assert "`/wgm setup`" in _content(reply)


@pytest.mark.anyio
async def test_members_cannot_create_events(
    app: Litestar, sign: Sign, wgm_command: MakeCommand, roles: FakeDiscordApi
) -> None:
    reply = await _run(app, sign, wgm_command("event create", **EVENT))

    assert _private(reply)
    assert _content(reply) == (
        "You need the wgm-admin role to use `/wgm event create`."
    )


@pytest.mark.anyio
async def test_admins_post_events_and_everyone_can_list_them(
    app: Litestar, sign: Sign, wgm_command: MakeCommand, roles: FakeDiscordApi
) -> None:
    posted = await _run(
        app, sign, wgm_command("event create", roles=(ADMIN_ROLE_ID,), **EVENT)
    )
    listed = await _run(app, sign, wgm_command("event list"))

    assert not _private(posted)
    assert _content(posted).startswith("**Siege night** · Siege\n<t:")
    assert "Attending 0 · Tentative 0 · Not attending 0" in _content(posted)
    assert _private(listed)
    assert _content(listed) == _content(posted)


@pytest.mark.anyio
async def test_server_managers_can_create_events_before_setup(
    app: Litestar, sign: Sign, wgm_command: MakeCommand, discord_api: FakeDiscordApi
) -> None:
    discord_api.responses[ROLES] = (200, [])

    reply = await _run(
        app, sign, wgm_command("event create", permissions=MANAGE_SERVER, **EVENT)
    )

    assert not _private(reply)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("day", "message"),
    [("12/05/2099", "Use a date like"), ("2000-01-01", "already passed")],
)
async def test_bad_dates_are_explained_privately(
    app: Litestar,
    sign: Sign,
    wgm_command: MakeCommand,
    roles: FakeDiscordApi,
    day: str,
    message: str,
) -> None:
    values = EVENT | {"date": day}

    reply = await _run(
        app, sign, wgm_command("event create", roles=(ADMIN_ROLE_ID,), **values)
    )

    assert _private(reply)
    assert message in _content(reply)


@pytest.mark.anyio
async def test_listing_with_no_events(
    app: Litestar, sign: Sign, wgm_command: MakeCommand
) -> None:
    reply = await _run(app, sign, wgm_command("event list"))

    assert _content(reply) == "No upcoming events."


@pytest.mark.anyio
async def test_setup_creates_the_admin_role(
    app: Litestar, sign: Sign, wgm_command: MakeCommand, discord_api: FakeDiscordApi
) -> None:
    discord_api.responses[ROLES] = (200, [{"id": "1", "name": "@everyone"}])
    discord_api.responses[CREATE_ROLE] = (200, {"id": "900", "name": "wgm-admin"})

    reply = await _run(app, sign, wgm_command("setup", permissions=MANAGE_SERVER))

    created = [r for r in discord_api.requests if r.method == "POST"]
    assert created[0].body == {"name": "wgm-admin", "mentionable": False}
    assert created[0].authorization == "Bot test-token"
    assert _content(reply).startswith("Created wgm-admin.")


@pytest.mark.anyio
async def test_setup_twice_changes_nothing(
    app: Litestar, sign: Sign, wgm_command: MakeCommand, roles: FakeDiscordApi
) -> None:
    reply = await _run(app, sign, wgm_command("setup", roles=(ADMIN_ROLE_ID,)))

    assert not any(r.method == "POST" for r in roles.requests)
    assert _content(reply) == "All WGM roles already exist."


@pytest.mark.anyio
@pytest.mark.parametrize("path", ["setup", "event create", "event list"])
async def test_server_commands_outside_a_server(
    app: Litestar, sign: Sign, wgm_command: MakeCommand, path: str
) -> None:
    values = EVENT if path == "event create" else {}

    reply = await _run(app, sign, wgm_command(path, in_server=False, **values))

    assert _content(reply) == "Run this in a server."


@pytest.mark.anyio
async def test_help_outside_a_server_lists_open_commands(
    app: Litestar, sign: Sign, wgm_command: MakeCommand
) -> None:
    reply = await _run(app, sign, wgm_command("help", in_server=False))

    assert "`/wgm event list`" in _content(reply)
    assert "setup" not in _content(reply)


@pytest.mark.anyio
async def test_discord_errors_fail_the_request(
    app: Litestar, sign: Sign, wgm_command: MakeCommand, discord_api: FakeDiscordApi
) -> None:
    discord_api.responses[ROLES] = (403, {"message": "Missing Access", "code": 50001})
    signed, headers = sign(wgm_command("help"))

    async with AsyncTestClient(app=app) as client:
        response = await client.post(
            "/discord/interactions", content=signed, headers=headers
        )

    assert response.status_code == 500
