"""Each server's own list of event types."""

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from advanced_alchemy.alembic.commands import AlembicCommands
from advanced_alchemy.extensions.litestar import SQLAlchemyAsyncConfig

from tests.fixtures.app import Interact
from tests.fixtures.discord import (
    ADMIN_ROLE_ID,
    GUILD_ID,
    MakeCommand,
    post_buttons,
    post_words,
)
from tests.fixtures.discord_api import FakeDiscordApi
from wgm.db.config import database_config
from wgm.domain.events.services import EventTypeService

ADMIN = {"roles": (ADMIN_ROLE_ID,)}
EVENT = {"title": "Rift run", "date": "2099-12-05", "time": "20:00"}
NOW = datetime(2026, 11, 28, tzinfo=UTC)
DEFAULTS = "Boonstone, Guild Bosses, Inter-server, Riftstone, Siege"


@pytest.fixture
def config(database_url: str) -> SQLAlchemyAsyncConfig:
    config = database_config(database_url)
    AlembicCommands(sqlalchemy_config=config).upgrade()
    return config


@pytest.fixture(autouse=True)
def roles(discord_api: FakeDiscordApi) -> FakeDiscordApi:
    discord_api.responses[f"GET /guilds/{GUILD_ID}/roles"] = (
        200,
        [{"id": ADMIN_ROLE_ID, "name": "wgm-admin", "permissions": "0"}],
    )
    return discord_api


def _content(reply: dict[str, Any]) -> str:
    return str(reply["data"]["content"])


def _typing(command: bytes, option: str) -> bytes:
    payload = json.loads(command)
    payload["type"] = 4
    for each in payload["data"]["options"][0]["options"][0]["options"]:
        each["focused"] = each["name"] == option
    return json.dumps(payload).encode()


@pytest.mark.anyio
async def test_servers_start_with_the_defaults_and_removed_types_come_back(
    config: SQLAlchemyAsyncConfig,
) -> None:
    async with config.get_session() as session:
        types = EventTypeService(session=session)
        first = [t.name for t in await types.listed("1")]
        siege = await types.find("1", " SIEGE ")
        await types.remove("1", "Siege", NOW)
        gone = await types.find("1", "Siege")
        back = [t.name for t in await types.add("1", "siege")]
        test = await types.for_tests("1", NOW)
        again = await types.for_tests("1", NOW)

    assert ", ".join(first) == DEFAULTS
    assert siege is not None
    assert siege.name == "Siege"
    assert gone is None
    assert back == first  # the same row, unarchived, keeps its place
    assert test is again
    assert test.archived_at == NOW


@pytest.mark.anyio
async def test_admins_list_add_and_remove_types(
    interact: Interact, wgm_command: MakeCommand
) -> None:
    listed = await interact(wgm_command("event types", action="list", **ADMIN))
    added = await interact(
        wgm_command("event types", action="add", name="  Castle   Siege ", **ADMIN)
    )
    again = await interact(
        wgm_command("event types", action="add", name="castle siege", **ADMIN)
    )
    removed = await interact(
        wgm_command("event types", action="remove", name="inter-server", **ADMIN)
    )
    missing = await interact(
        wgm_command("event types", action="remove", name="Arena", **ADMIN)
    )
    unnamed = await interact(wgm_command("event types", action="add", **ADMIN))
    too_long = await interact(
        wgm_command("event types", action="add", name="x" * 40, **ADMIN)
    )

    assert _content(listed) == f"This server's event types: {DEFAULTS}"
    assert _content(added) == (
        f"Added **Castle Siege**. Event types now: {DEFAULTS}, Castle Siege"
    )
    assert _content(again) == "**castle siege** is already on the list."
    assert _content(removed).startswith("Removed **inter-server**. Events that use")
    assert "Inter-server" not in _content(removed)
    assert _content(missing) == "**Arena** isn't on the list."
    assert _content(unnamed) == "Give the `name` of the type to add."
    assert _content(too_long) == "Use a name of 1 to 32 characters."


@pytest.mark.anyio
async def test_an_empty_list_says_how_to_add_one(
    interact: Interact, wgm_command: MakeCommand
) -> None:
    for name in DEFAULTS.split(", "):
        await interact(wgm_command("event types", action="remove", name=name, **ADMIN))

    listed = await interact(wgm_command("event types", action="list", **ADMIN))

    assert _content(listed) == (
        "This server's event types: none yet. Add one with `action:add`"
    )


@pytest.mark.anyio
async def test_members_cannot_change_types(
    interact: Interact, wgm_command: MakeCommand
) -> None:
    reply = await interact(wgm_command("event types", action="list"))

    assert _content(reply).startswith("You need the wgm-admin role")


@pytest.mark.anyio
async def test_events_use_the_servers_types_in_its_spelling(
    interact: Interact, wgm_command: MakeCommand, roles: FakeDiscordApi
) -> None:
    created = await interact(
        wgm_command("event create", type="riftstone", **ADMIN, **EVENT)
    )
    post = [r for r in roles.requests if r.method == "POST"][-1].body
    unknown = await interact(
        wgm_command("event create", type="Arena", **ADMIN, **EVENT)
    )

    assert _content(created).startswith("Posted **Rift run**")
    assert post_words(post).startswith("## 🦈 [Riftstone] Rift run\n")
    assert _content(unknown).startswith(
        "**Arena** isn't one of this server's event types. Add it first"
    )


@pytest.mark.anyio
async def test_removed_types_stay_on_events_and_bad_edits_change_nothing(
    interact: Interact, wgm_command: MakeCommand, roles: FakeDiscordApi
) -> None:
    await interact(wgm_command("event create", type="Siege", **ADMIN, **EVENT))
    post = [r for r in roles.requests if r.method == "POST"][-1].body
    event_id = post_buttons(post)[0]["custom_id"].split(":")[1]
    await interact(wgm_command("event types", action="remove", name="Siege", **ADMIN))

    bad = await interact(
        wgm_command("event edit", event=event_id, type="Arena", time="21:00", **ADMIN)
    )
    listed = await interact(wgm_command("event list"))

    assert _content(bad).startswith("**Arena** isn't one of this server's")
    assert "**Rift run** · Siege" in _content(listed)
    assert "<t:4100202000:F>" in _content(listed)  # time unchanged


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("command", "values"),
    [
        ("event create", {"type": "rift", **EVENT}),
        ("event types", {"action": "remove", "name": "rift"}),
    ],
)
async def test_type_options_suggest_the_servers_types(
    interact: Interact, wgm_command: MakeCommand, command: str, values: dict[str, str]
) -> None:
    option = "type" if "type" in values else "name"

    reply = await interact(_typing(wgm_command(command, **values), option))

    assert reply["data"]["choices"] == [{"name": "Riftstone", "value": "Riftstone"}]
