"""Settings read from the environment.

Values come from environment variables, or from a `.env` file in the working
directory when one exists. See `.env.example` for the full list.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values


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


@dataclass(frozen=True, slots=True)
class DiscordSettings:
    """Settings for one Discord application."""

    public_key: str
    """Hex-encoded Ed25519 key that Discord signs interactions with."""


@dataclass(frozen=True, slots=True)
class Settings:
    """All application settings."""

    discord: DiscordSettings

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
            ),
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
