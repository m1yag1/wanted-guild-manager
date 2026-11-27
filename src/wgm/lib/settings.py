"""Settings read from the environment.

Values come from environment variables, or from a `.env` file in the working
directory when one exists. See `.env.example` for the full list.
"""

import os
from collections.abc import Mapping
from pathlib import Path
from zoneinfo import ZoneInfo

from attrs import field, frozen
from dotenv import dotenv_values

DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///wgm.db"
DEFAULT_TIMEZONE = "America/New_York"
DEFAULT_DISCORD_API_URL = "https://discord.com/api/v10"
DEFAULT_PLUGINS = ("event",)
TRUE = ("1", "true", "yes", "on")


class MissingSettingError(RuntimeError):
    """Raised when a required environment variable is not set."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Set the {name} environment variable (see .env.example).")
        self.name = name


def _require(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise MissingSettingError(name)
    return value


def _zone(value: str | ZoneInfo) -> ZoneInfo:
    """A time zone from its IANA name, such as America/New_York."""
    return value if isinstance(value, ZoneInfo) else ZoneInfo(value)


def _names(value: str) -> tuple[str, ...]:
    """ "event, dev" -> ("event", "dev")"""
    return tuple(name.strip() for name in value.split(",") if name.strip())


@frozen
class DiscordSettings:
    """Settings for one Discord application."""

    public_key: str
    """Hex-encoded Ed25519 key that Discord signs interactions with."""

    application_id: str = ""
    """The application's ID, needed to register commands."""

    bot_token: str = ""
    """The bot's token, needed to call Discord's API."""

    guild_id: str = ""
    """A server to register commands in, so changes show up at once (staging)."""

    api_url: str = DEFAULT_DISCORD_API_URL
    """Discord's REST API. Tests point this at a local fake."""


@frozen
class Settings:
    """All application settings."""

    discord: DiscordSettings
    database_url: str = DEFAULT_DATABASE_URL
    """SQLAlchemy URL. Defaults to a `wgm.db` file in the working directory."""
    timezone: ZoneInfo = field(default=ZoneInfo(DEFAULT_TIMEZONE), converter=_zone)
    """Time zone that managers type event times in (the guild leader's)."""
    plugins: tuple[str, ...] = DEFAULT_PLUGINS
    """Plugins to turn on (ADR 0013), from WGM_PLUGINS such as `event,dev`."""
    dev_mode: bool = False
    """Add the plugins' commands for trying things by hand. Staging only."""
    environ: Mapping[str, str] = field(factory=dict, eq=False)
    """Every WGM_* variable, for the settings plugins declare."""

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Settings":
        """Build settings from environment variables.

        Args:
            env: The environment to read, usually `os.environ`.

        Returns:
            The settings.

        Raises:
            MissingSettingError: A required variable is missing or empty.
        """
        return cls(
            discord=DiscordSettings(
                public_key=_require(env, "WGM_DISCORD_PUBLIC_KEY"),
                application_id=env.get("WGM_DISCORD_APPLICATION_ID", "").strip(),
                bot_token=env.get("WGM_DISCORD_BOT_TOKEN", "").strip(),
                guild_id=env.get("WGM_DISCORD_GUILD_ID", "").strip(),
                api_url=env.get("WGM_DISCORD_API_URL", "").strip()
                or DEFAULT_DISCORD_API_URL,
            ),
            database_url=env.get("WGM_DATABASE_URL", "").strip()
            or DEFAULT_DATABASE_URL,
            timezone=env.get("WGM_TIMEZONE", "").strip() or DEFAULT_TIMEZONE,
            plugins=_names(env.get("WGM_PLUGINS", "")) or DEFAULT_PLUGINS,
            dev_mode=env.get("WGM_DEV_MODE", "").strip().lower() in TRUE,
            environ={k: v for k, v in env.items() if k.startswith("WGM_")},
        )


def load_settings(
    environ: Mapping[str, str] = os.environ,
    env_file: Path = Path(".env"),
) -> Settings:
    """Load settings from a `.env` file and the environment.

    Real environment variables win over values in the file. The file is
    optional, and reading it does not change `os.environ`.

    Args:
        environ: Environment variables, `os.environ` by default.
        env_file: Optional dotenv file, `.env` in the working directory by default.

    Returns:
        The settings.
    """
    from_file = {k: v for k, v in dotenv_values(env_file).items() if v is not None}
    return Settings.from_env({**from_file, **environ})
