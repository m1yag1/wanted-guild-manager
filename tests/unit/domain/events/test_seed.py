"""`/wgm event seed`: test events, only in dev mode."""

from typing import Any

import pytest
from attrs import evolve

from tests.fixtures.app import Interact
from tests.fixtures.discord import ADMIN_ROLE_ID, GUILD_ID, MakeButton, MakeCommand
from tests.fixtures.discord_api import FakeDiscordApi
from wgm.lib.settings import Settings

ADMIN = {"roles": (ADMIN_ROLE_ID,)}
APP_ID = "1310000000000000000"


@pytest.fixture
def settings(settings: Settings) -> Settings:
    """Staging-style settings, with dev mode on."""
    return evolve(settings, dev_mode=True)


@pytest.fixture(autouse=True)
def roles(discord_api: FakeDiscordApi) -> FakeDiscordApi:
    discord_api.responses[f"GET /guilds/{GUILD_ID}/roles"] = (
        200,
        [{"id": ADMIN_ROLE_ID, "name": "wgm-admin", "permissions": "0"}],
    )
    return discord_api


def _post(api: FakeDiscordApi) -> dict[str, Any]:
    body: dict[str, Any] = [r for r in api.requests if r.method == "POST"][-1].body
    return body


def _disabled(post: dict[str, Any]) -> list[bool]:
    return [b["disabled"] for b in post["components"][0]["components"]]


@pytest.mark.anyio
async def test_seed_posts_each_preset(
    interact: Interact, wgm_command: MakeCommand, roles: FakeDiscordApi
) -> None:
    posts = {}
    for preset in ("closes-soon", "closed", "busy", "old-style"):
        reply = await interact(wgm_command("event seed", preset=preset, **ADMIN))
        assert reply["data"]["content"].startswith("Posted **[test] ")
        posts[preset] = _post(roles)
    listed = await interact(wgm_command("event list"))

    assert "Sign-ups close <t:" in posts["closes-soon"]["content"]
    assert not any(_disabled(posts["closes-soon"]))
    assert "Sign-ups closed <t:" in posts["closed"]["content"]
    assert all(_disabled(posts["closed"]))
    assert "DPS (4): Lyra, Thorn, Sable, Orin" in posts["busy"]["content"]
    assert "**Not attending (2)**: Vex, Nyx" in posts["busy"]["content"]
    assert "[test] Old style" in posts["old-style"]["content"]
    assert "Attending 8 · Tentative 2 · Not attending 2" in listed["data"]["content"]


@pytest.mark.anyio
async def test_members_can_press_buttons_on_a_busy_test_event(
    interact: Interact,
    wgm_command: MakeCommand,
    wgm_button: MakeButton,
    roles: FakeDiscordApi,
) -> None:
    await interact(wgm_command("event seed", preset="busy", **ADMIN))
    custom_id = _post(roles)["components"][0]["components"][0]["custom_id"]

    reply = await interact(wgm_button(custom_id))

    assert "Tank (3): Kael, Brask, " in reply["data"]["content"]


@pytest.mark.anyio
async def test_seed_is_for_admins(interact: Interact, wgm_command: MakeCommand) -> None:
    reply = await interact(wgm_command("event seed", preset="busy"))

    assert reply["data"]["content"].startswith("You need the wgm-admin role")


@pytest.mark.anyio
async def test_config_and_help_show_dev_mode_commands(
    interact: Interact, wgm_command: MakeCommand
) -> None:
    shown = await interact(wgm_command("config show", **ADMIN))
    helped = await interact(wgm_command("help", **ADMIN))

    assert "Plugins: event\n`/wgm event settings`" in shown["data"]["content"]
    assert "`/wgm event seed`: Post a test event" in helped["data"]["content"]
