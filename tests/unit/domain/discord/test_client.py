"""The Discord client's short-lived role cache."""

import httpx
import pytest

from tests.fixtures.discord_api import FakeDiscordApi
from wgm.domain.discord.client import ROLE_NAMES_SECONDS, DiscordClient

ROLES = "/guilds/1/roles"


@pytest.mark.anyio
async def test_role_ids_are_reused_for_a_minute_and_after_creating_a_role(
    discord_api: FakeDiscordApi,
) -> None:
    discord_api.responses[f"GET {ROLES}"] = (200, [{"id": "9", "name": "wgm-admin"}])
    discord_api.responses[f"POST {ROLES}"] = (200, {"id": "10"})
    clock = [0.0]

    def fetches() -> int:
        return sum(1 for r in discord_api.requests if r.method == "GET")

    async with httpx.AsyncClient() as http:
        discord = DiscordClient("t", discord_api.url, http, clock=lambda: clock[0])
        first = await discord.role_ids("1")
        await discord.role_ids("1")
        reused = fetches()
        clock[0] = ROLE_NAMES_SECONDS
        await discord.role_ids("1")
        expired = fetches()
        await discord.create_role("1", "wgm-guildmate")
        await discord.role_ids("1")
        after_create = fetches()

    assert first == {"wgm-admin": "9"}
    assert (reused, expired, after_create) == (1, 2, 3)
