"""The Discord REST calls the server makes while answering commands."""

import time
from collections.abc import Callable
from typing import Any

import httpx
from attrs import field, frozen

USER_AGENT = "DiscordBot (wanted-guild-manager, 0.1)"
ROLE_NAMES_SECONDS = 60.0
"""How long role IDs by name are reused before asking Discord again."""


class DiscordApiError(RuntimeError):
    """Discord answered with an error."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(f"Discord API error {status}: {detail}")
        self.status = status


def _message(content: str, components: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "content": content,
        "components": components,
        "allowed_mentions": {"parse": []},
    }


@frozen
class DiscordClient:
    """Async calls to Discord's REST API as the bot.

    `http` is shared for the life of the app, so calls reuse connections.
    Role IDs by name are kept for a minute, since every restricted command
    needs them and they rarely change.
    """

    bot_token: str
    api_url: str
    http: httpx.AsyncClient
    clock: Callable[[], float] = time.monotonic
    _role_names: dict[str, tuple[float, dict[str, str]]] = field(
        factory=dict, init=False
    )

    async def _call(self, method: str, path: str, body: Any = None) -> Any:
        response = await self.http.request(
            method,
            f"{self.api_url}{path}",
            json=body,
            headers={
                "Authorization": f"Bot {self.bot_token}",
                "User-Agent": USER_AGENT,
            },
        )
        if response.is_error:
            raise DiscordApiError(response.status_code, response.text)
        return response.json() if response.content else None

    async def roles(self, guild_id: str) -> list[dict[str, Any]]:
        """All roles in a server, with their permissions."""
        roles: list[dict[str, Any]] = await self._call(
            "GET", f"/guilds/{guild_id}/roles"
        )
        return roles

    async def role_ids(self, guild_id: str) -> dict[str, str]:
        """Role IDs in a server, keyed by role name. Reused for a minute."""
        cached = self._role_names.get(guild_id)
        if cached and self.clock() - cached[0] < ROLE_NAMES_SECONDS:
            return cached[1]
        names = {role["name"]: role["id"] for role in await self.roles(guild_id)}
        self._role_names[guild_id] = (self.clock(), names)
        return names

    async def member(self, guild_id: str, user_id: str) -> dict[str, Any]:
        """A server member, including their role IDs."""
        member: dict[str, Any] = await self._call(
            "GET", f"/guilds/{guild_id}/members/{user_id}"
        )
        return member

    async def channel(self, channel_id: str) -> dict[str, Any]:
        """A channel, including its permission overwrites. 403 if unseen."""
        channel: dict[str, Any] = await self._call("GET", f"/channels/{channel_id}")
        return channel

    async def create_role(self, guild_id: str, name: str) -> str:
        """Create a role with no special permissions and return its ID."""
        role = await self._call(
            "POST", f"/guilds/{guild_id}/roles", {"name": name, "mentionable": False}
        )
        self._role_names.pop(guild_id, None)
        return str(role["id"])

    async def post_message(
        self, channel_id: str, content: str, components: list[dict[str, Any]]
    ) -> str:
        """Post a message in a channel and return its ID."""
        message = await self._call(
            "POST",
            f"/channels/{channel_id}/messages",
            _message(content, components),
        )
        return str(message["id"])

    async def edit_message(
        self,
        channel_id: str,
        message_id: str,
        content: str,
        components: list[dict[str, Any]],
    ) -> None:
        """Replace the text and buttons of a message the app posted."""
        await self._call(
            "PATCH",
            f"/channels/{channel_id}/messages/{message_id}",
            _message(content, components),
        )

    async def delete_message(self, channel_id: str, message_id: str) -> None:
        """Remove a message the app posted."""
        await self._call("DELETE", f"/channels/{channel_id}/messages/{message_id}")

    async def edit_original(
        self, application_id: str, token: str, message: dict[str, Any]
    ) -> None:
        """Replace the "thinking..." reply of a deferred interaction."""
        await self._call(
            "PATCH",
            f"/webhooks/{application_id}/{token}/messages/@original",
            message,
        )
