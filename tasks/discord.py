"""Talk to Discord's API: register the /wgm command and set the endpoint URL."""

from pathlib import Path
from typing import Any

import httpx
from attrs import frozen
from invoke.context import Context
from invoke.tasks import task

from tasks.config import CONFIG_FILE, ROOT, DropletConfig
from tasks.droplet import INVENTORY, read_ip
from tasks.errors import friendly_errors
from tasks.shell import say
from wgm.domain.discord.commands import COMMANDS
from wgm.lib.settings import DiscordSettings, load_settings

API_URL = "https://discord.com/api/v10"
USER_AGENT = "DiscordBot (wanted-guild-manager, 0.1)"
MISSING_ACCESS = 50001

# Bot permissions the invite asks for: Manage Roles, View Channels,
# Send Messages, Embed Links.
PERMISSIONS = (1 << 28) | (1 << 10) | (1 << 11) | (1 << 14)


class DiscordApiError(RuntimeError):
    """Discord answered with an error."""

    def __init__(self, status: int, detail: str, code: int = 0) -> None:
        super().__init__(f"Discord API error {status}: {detail}")
        self.status = status
        self.code = code


@frozen
class DiscordRest:
    """The few Discord REST calls the tasks need, authenticated as the bot."""

    bot_token: str
    base_url: str = API_URL

    def _call(self, method: str, path: str, body: Any) -> Any:
        response = httpx.request(
            method,
            f"{self.base_url}{path}",
            json=body,
            headers={
                "Authorization": f"Bot {self.bot_token}",
                "User-Agent": USER_AGENT,
            },
            timeout=30,
        )
        if response.is_error:
            code = response.json().get("code", 0) if response.content else 0
            raise DiscordApiError(response.status_code, response.text, code)
        return response.json() if response.content else None

    def register_commands(
        self, application_id: str, guild_id: str, commands: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Replace the app's commands, in one server if `guild_id` is set.

        Server commands update at once; global ones can take a while to appear.
        """
        scope = f"/guilds/{guild_id}" if guild_id else ""
        path = f"/applications/{application_id}{scope}/commands"
        registered: list[dict[str, Any]] = self._call("PUT", path, commands)
        return registered

    def interactions_endpoint(self) -> str:
        """The URL Discord currently sends interactions to, or "" if none."""
        app: dict[str, Any] = self._call("GET", "/applications/@me", None)
        return app.get("interactions_endpoint_url") or ""

    def set_interactions_endpoint(self, url: str) -> None:
        """Point the app at our server. Discord sends it a PING to check it."""
        self._call("PATCH", "/applications/@me", {"interactions_endpoint_url": url})


def invite_url(application_id: str, guild_id: str = "") -> str:
    """The link that adds the app to a server with the permissions it needs."""
    url = (
        "https://discord.com/oauth2/authorize"
        f"?client_id={application_id}&scope=bot+applications.commands"
        f"&permissions={PERMISSIONS}"
    )
    return f"{url}&guild_id={guild_id}&disable_guild_select=true" if guild_id else url


def endpoint_report(rest: DiscordRest, expected: str) -> str:
    """One line saying whether Discord points at `expected`."""
    actual = rest.interactions_endpoint()
    if actual == expected:
        return "discord endpoint: ok"
    shown = actual or "not set"
    return (
        f"discord endpoint: {shown}, expected {expected}. "
        "Fix it with `inv discord.set-endpoint`."
    )


def secrets_file(env: str, path: str = "") -> Path:
    """The secrets file for an environment, `.env.<env>` unless given."""
    return Path(path) if path else ROOT / f".env.{env}"


def discord_settings(env_file: Path) -> DiscordSettings:
    """Discord settings from a secrets file only, ignoring this shell's environment.

    Raises:
        ValueError: The application ID or bot token is missing.
    """
    if not env_file.exists():
        raise FileNotFoundError(f"Create {env_file.name} from .env.example first.")
    discord = load_settings(environ={}, env_file=env_file).discord
    missing = [
        name
        for name, value in [
            ("WGM_DISCORD_APPLICATION_ID", discord.application_id),
            ("WGM_DISCORD_BOT_TOKEN", discord.bot_token),
        ]
        if not value
    ]
    if missing:
        raise ValueError(f"Set {', '.join(missing)} in {env_file.name}.")
    return discord


def interactions_url(config: DropletConfig, env: str, ip: str) -> str:
    """The public URL Discord sends interactions to."""
    return f"https://{config.environment(env).hostname(ip)}/discord/interactions"


HELP = {
    "env": "Environment (default staging).",
    "secrets": "Secrets file (default .env.<env>).",
    "api_url": "Discord API base URL.",
}


@task(name="register-commands", help=HELP)
@friendly_errors
def register_commands_task(
    c: Context, env: str = "staging", secrets: str = "", api_url: str = API_URL
) -> None:
    """Register the /wgm slash command with Discord."""
    discord = discord_settings(secrets_file(env, secrets))
    try:
        registered = DiscordRest(discord.bot_token, api_url).register_commands(
            discord.application_id, discord.guild_id, COMMANDS
        )
    except DiscordApiError as error:
        if error.code != MISSING_ACCESS:
            raise
        link = invite_url(discord.application_id, discord.guild_id)
        raise ValueError(
            f"The app is not in server {discord.guild_id} yet. Add it with {link}"
        ) from None
    where = f"server {discord.guild_id}" if discord.guild_id else "all servers"
    names = ", ".join(f"/{command['name']}" for command in registered)
    say(f"Registered {names} for {where}.")


@task(name="invite-url", help={"env": HELP["env"], "secrets": HELP["secrets"]})
@friendly_errors
def invite_url_task(c: Context, env: str = "staging", secrets: str = "") -> None:
    """Print the link that adds the Discord app to your server."""
    discord = discord_settings(secrets_file(env, secrets))
    say(invite_url(discord.application_id, discord.guild_id))


@task(
    name="set-endpoint",
    help=HELP
    | {
        "config_file": "Settings file (default deploy/droplet.toml).",
        "inventory": "Inventory file (default deploy/ansible/inventories/wgm.json).",
    },
)
@friendly_errors
def set_endpoint_task(
    c: Context,
    env: str = "staging",
    secrets: str = "",
    api_url: str = API_URL,
    config_file: str = str(CONFIG_FILE),
    inventory: str = str(INVENTORY),
) -> None:
    """Point the Discord app at this environment's interactions endpoint."""
    discord = discord_settings(secrets_file(env, secrets))
    config = DropletConfig.load(Path(config_file))
    url = interactions_url(config, env, read_ip(Path(inventory)))
    DiscordRest(discord.bot_token, api_url).set_interactions_endpoint(url)
    say(f"Discord now sends interactions to {url}")
