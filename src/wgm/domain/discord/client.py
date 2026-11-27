"""The Discord REST calls the server makes while answering commands."""

from typing import Any

import httpx
from attrs import frozen

USER_AGENT = "DiscordBot (wanted-guild-manager, 0.1)"


class DiscordApiError(RuntimeError):
    """Discord answered with an error."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(f"Discord API error {status}: {detail}")
        self.status = status


@frozen
class DiscordClient:
    """Async calls to Discord's REST API as the bot."""

    bot_token: str
    api_url: str

    async def _call(self, method: str, path: str, body: Any = None) -> Any:
        async with httpx.AsyncClient(timeout=10) as http:
            response = await http.request(
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

    async def role_ids(self, guild_id: str) -> dict[str, str]:
        """Role IDs in a server, keyed by role name."""
        roles = await self._call("GET", f"/guilds/{guild_id}/roles")
        return {role["name"]: role["id"] for role in roles}

    async def create_role(self, guild_id: str, name: str) -> str:
        """Create a role with no special permissions and return its ID."""
        role = await self._call(
            "POST", f"/guilds/{guild_id}/roles", {"name": name, "mentionable": False}
        )
        return str(role["id"])
