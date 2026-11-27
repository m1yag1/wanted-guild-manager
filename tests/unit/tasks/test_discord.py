from pathlib import Path

import pytest
from invoke.context import Context
from invoke.exceptions import Exit

from tasks.config import DropletConfig
from tasks.discord import (
    DiscordApiError,
    DiscordRest,
    discord_settings,
    endpoint_report,
    interactions_url,
    invite_url,
    invite_url_task,
    register_commands_task,
    secrets_file,
    set_endpoint_task,
)
from tests.fixtures.discord_api import FakeDiscordApi
from tests.fixtures.droplet import IP

COMMANDS = [{"name": "wgm"}]
ENDPOINT = "https://staging.203-0-113-7.sslip.io/discord/interactions"


@pytest.fixture
def secrets(tmp_path: Path) -> Path:
    path = tmp_path / ".env.staging"
    path.write_text(
        "WGM_DISCORD_PUBLIC_KEY=abc\n"
        "WGM_DISCORD_APPLICATION_ID=111\n"
        "WGM_DISCORD_BOT_TOKEN=secret-token\n"
        "WGM_DISCORD_GUILD_ID=222\n"
    )
    return path


def test_registers_commands_in_one_server(discord_api: FakeDiscordApi) -> None:
    DiscordRest("secret-token", discord_api.url).register_commands(
        "111", "222", COMMANDS
    )

    request = discord_api.requests[0]
    assert (request.method, request.path) == (
        "PUT",
        "/applications/111/guilds/222/commands",
    )
    assert request.authorization == "Bot secret-token"
    assert request.body == COMMANDS


def test_registers_commands_globally_without_a_server(
    discord_api: FakeDiscordApi,
) -> None:
    DiscordRest("t", discord_api.url).register_commands("111", "", COMMANDS)

    assert discord_api.requests[0].path == "/applications/111/commands"


def test_sets_the_interactions_endpoint(discord_api: FakeDiscordApi) -> None:
    DiscordRest("t", discord_api.url).set_interactions_endpoint(ENDPOINT)

    request = discord_api.requests[0]
    assert (request.method, request.path) == ("PATCH", "/applications/@me")
    assert request.body == {"interactions_endpoint_url": ENDPOINT}


def test_api_errors_carry_the_status(discord_api: FakeDiscordApi) -> None:
    discord_api.responses["PATCH /applications/@me"] = (
        400,
        {"message": "interactions_endpoint_url: could not be verified"},
    )

    with pytest.raises(DiscordApiError, match="could not be verified") as raised:
        DiscordRest("t", discord_api.url).set_interactions_endpoint(ENDPOINT)

    assert raised.value.status == 400


def test_secrets_file_defaults_to_the_environment_name() -> None:
    assert secrets_file("staging").name == ".env.staging"
    assert secrets_file("staging", "/tmp/x.env") == Path("/tmp/x.env")


def test_discord_settings_need_an_app_id_and_token(tmp_path: Path) -> None:
    path = tmp_path / ".env.staging"
    path.write_text("WGM_DISCORD_PUBLIC_KEY=abc\n")

    with pytest.raises(
        ValueError, match="WGM_DISCORD_APPLICATION_ID, WGM_DISCORD_BOT_TOKEN"
    ):
        discord_settings(path)


def test_discord_settings_need_the_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match=".env.example"):
        discord_settings(tmp_path / ".env.staging")


def test_interactions_url(config: DropletConfig) -> None:
    assert interactions_url(config, "staging", IP) == ENDPOINT


def test_register_task(
    discord_api: FakeDiscordApi, secrets: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    register_commands_task(Context(), secrets=str(secrets), api_url=discord_api.url)

    assert discord_api.requests[0].path.endswith("/guilds/222/commands")
    assert "Registered /wgm for server 222." in capsys.readouterr().out


def test_register_task_globally(
    discord_api: FakeDiscordApi, secrets: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    secrets.write_text(secrets.read_text().replace("WGM_DISCORD_GUILD_ID=222\n", ""))

    register_commands_task(Context(), secrets=str(secrets), api_url=discord_api.url)

    assert "for all servers." in capsys.readouterr().out


def test_set_endpoint_task(
    discord_api: FakeDiscordApi,
    secrets: Path,
    config_file: Path,
    written_inventory: Path,
) -> None:
    set_endpoint_task(
        Context(),
        secrets=str(secrets),
        api_url=discord_api.url,
        config_file=str(config_file),
        inventory=str(written_inventory),
    )

    assert discord_api.requests[0].body == {"interactions_endpoint_url": ENDPOINT}


def test_task_errors_are_one_line(discord_api: FakeDiscordApi, tmp_path: Path) -> None:
    with pytest.raises(Exit, match="Create .env.staging"):
        register_commands_task(
            Context(), secrets=str(tmp_path / ".env.staging"), api_url=discord_api.url
        )


def test_invite_url_for_one_server() -> None:
    url = invite_url("111", "222")

    assert "client_id=111" in url
    assert "scope=bot+applications.commands" in url
    assert "permissions=268454912" in url
    assert url.endswith("&guild_id=222&disable_guild_select=true")


def test_invite_url_without_a_server() -> None:
    assert "guild_id" not in invite_url("111")


def test_invite_url_task(secrets: Path, capsys: pytest.CaptureFixture[str]) -> None:
    invite_url_task(Context(), secrets=str(secrets))

    assert capsys.readouterr().out.startswith("https://discord.com/oauth2/authorize")


def test_register_task_explains_how_to_add_the_app(
    discord_api: FakeDiscordApi, secrets: Path
) -> None:
    discord_api.responses["PUT /applications/111/guilds/222/commands"] = (
        403,
        {"message": "Missing Access", "code": 50001},
    )

    with pytest.raises(Exit, match="not in server 222 yet. Add it with https://"):
        register_commands_task(Context(), secrets=str(secrets), api_url=discord_api.url)


def test_register_task_reports_other_api_errors(
    discord_api: FakeDiscordApi, secrets: Path
) -> None:
    discord_api.responses["PUT /applications/111/guilds/222/commands"] = (
        401,
        {"message": "401: Unauthorized", "code": 0},
    )

    with pytest.raises(Exit, match="Discord API error 401"):
        register_commands_task(Context(), secrets=str(secrets), api_url=discord_api.url)


@pytest.mark.parametrize(
    ("current", "report"),
    [
        (ENDPOINT, "discord endpoint: ok"),
        (None, "discord endpoint: not set, expected"),
        ("https://old.example/discord/interactions", "discord endpoint: https://old"),
    ],
)
def test_endpoint_report(
    discord_api: FakeDiscordApi, current: str | None, report: str
) -> None:
    discord_api.responses["GET /applications/@me"] = (
        200,
        {"interactions_endpoint_url": current},
    )

    assert endpoint_report(DiscordRest("t", discord_api.url), ENDPOINT).startswith(
        report
    )


def _event_commands(api: FakeDiscordApi) -> list[str]:
    groups = api.requests[0].body[0]["options"]
    event = next(group for group in groups if group["name"] == "event")
    return [sub["name"] for sub in event["options"]]


def test_register_task_adds_dev_commands_only_in_dev_mode(
    discord_api: FakeDiscordApi, secrets: Path
) -> None:
    register_commands_task(Context(), secrets=str(secrets), api_url=discord_api.url)
    normal = _event_commands(discord_api)
    discord_api.requests.clear()
    secrets.write_text(secrets.read_text() + "WGM_DEV_MODE=true\n")

    register_commands_task(Context(), secrets=str(secrets), api_url=discord_api.url)

    assert "seed" not in normal
    assert _event_commands(discord_api)[-1] == "seed"


def test_register_task_explains_plugin_problems(
    discord_api: FakeDiscordApi, secrets: Path
) -> None:
    secrets.write_text(secrets.read_text() + "WGM_PLUGINS=event,raids\n")

    with pytest.raises(Exit, match="'raids', which isn't installed"):
        register_commands_task(Context(), secrets=str(secrets), api_url=discord_api.url)

    assert not discord_api.requests
