from pathlib import Path

import pytest

from wgm.lib.settings import MissingSettingError, Settings, load_settings

KEY = "WGM_DISCORD_PUBLIC_KEY"


def test_reads_the_discord_public_key() -> None:
    settings = Settings.from_env({KEY: " abc123 "})

    assert settings.discord.public_key == "abc123"


@pytest.mark.parametrize("env", [{}, {KEY: "  "}])
def test_names_the_missing_variable(env: dict[str, str]) -> None:
    with pytest.raises(MissingSettingError, match=KEY):
        Settings.from_env(env)


def test_loads_values_from_the_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(f"{KEY}=from-file\n")

    settings = load_settings(environ={}, env_file=env_file)

    assert settings.discord.public_key == "from-file"


def test_environment_variables_win_over_the_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(f"{KEY}=from-file\n")

    settings = load_settings(environ={KEY: "from-environment"}, env_file=env_file)

    assert settings.discord.public_key == "from-environment"


def test_the_env_file_is_optional(tmp_path: Path) -> None:
    settings = load_settings(
        environ={KEY: "from-environment"}, env_file=tmp_path / "missing.env"
    )

    assert settings.discord.public_key == "from-environment"


def test_ignores_empty_entries_in_the_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(f"{KEY}\n")

    with pytest.raises(MissingSettingError, match=KEY):
        load_settings(environ={}, env_file=env_file)


def test_reads_the_optional_discord_values() -> None:
    settings = Settings.from_env(
        {
            KEY: "abc",
            "WGM_DISCORD_APPLICATION_ID": "123",
            "WGM_DISCORD_BOT_TOKEN": " token ",
            "WGM_DISCORD_GUILD_ID": "456",
        }
    )

    assert settings.discord.application_id == "123"
    assert settings.discord.bot_token == "token"
    assert settings.discord.guild_id == "456"


def test_optional_discord_values_default_to_empty() -> None:
    settings = Settings.from_env({KEY: "abc"})

    assert settings.discord.bot_token == ""
