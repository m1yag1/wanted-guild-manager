import json
from pathlib import Path

import pytest
from invoke.context import Context

from tasks.config import DropletConfig
from tasks.deploy import (
    KEEP_RELEASES,
    Build,
    DirtyTreeError,
    build,
    current_version,
    deploy_vars,
    env_file,
    point_discord_here,
    release_task,
    rollback_task,
)
from tasks.shell import Shell
from tests.fixtures.commands import FakeCommand, MakeFakeCommand
from tests.fixtures.discord_api import FakeDiscordApi
from tests.fixtures.droplet import IP


def _uv(fake_command: MakeFakeCommand, out_dir: Path) -> FakeCommand:
    wheel = out_dir / "wanted_guild_manager-0.0.0-py3-none-any.whl"
    return fake_command("uv", [("build", {"files": [str(wheel)]})])


def test_version_comes_from_git(fake_command: MakeFakeCommand) -> None:
    git = fake_command("git", [("describe", {"stdout": "v0.1.0-2-gabc1234\n"})])

    assert current_version(Shell(Context()), str(git.path)) == "v0.1.0-2-gabc1234"
    assert git.args()[0] == [
        "describe", "--tags", "--match", "v[0-9]*", "--always", "--dirty",
    ]  # fmt: skip


def test_refuses_uncommitted_changes(fake_command: MakeFakeCommand) -> None:
    git = fake_command("git", [("describe", {"stdout": "abc1234-dirty\n"})])

    with pytest.raises(DirtyTreeError):
        current_version(Shell(Context()), str(git.path))


def test_builds_a_wheel_and_pinned_requirements(
    fake_command: MakeFakeCommand, tmp_path: Path
) -> None:
    out_dir = tmp_path / "release"
    out_dir.mkdir()
    (out_dir / "stale.whl").write_text("")
    uv = _uv(fake_command, out_dir)

    built = build(Shell(Context()), "v1", out_dir, str(uv.path))

    assert built.wheel.name.startswith("wanted_guild_manager")
    assert built.requirements == out_dir / "requirements.txt"
    assert not (out_dir / "stale.whl").exists()
    export = uv.args()[1]
    assert export[:2] == ["export", "--frozen"]
    assert "--no-dev" in export


def test_finds_the_secrets_file(tmp_path: Path, config: DropletConfig) -> None:
    (tmp_path / ".env.staging").write_text("WGM_DISCORD_PUBLIC_KEY=abc\n")

    assert env_file(config.environment("staging"), tmp_path).name == ".env.staging"


def test_missing_secrets_file_explains_what_to_do(
    tmp_path: Path, config: DropletConfig
) -> None:
    with pytest.raises(FileNotFoundError, match=".env.example"):
        env_file(config.environment("staging"), tmp_path)


def test_deploy_vars(config: DropletConfig, tmp_path: Path) -> None:
    built = Build("v1", tmp_path / "app.whl", tmp_path / "requirements.txt")

    variables = deploy_vars(
        config, config.environment("staging"), IP, built, tmp_path / ".env.staging"
    )

    assert variables["hostname"] == "staging.203-0-113-7.sslip.io"
    assert variables["app_port"] == 8001
    assert variables["version"] == "v1"
    assert variables["keep_releases"] == KEEP_RELEASES


def test_release_task_builds_and_runs_the_deploy_playbook(
    fake_command: MakeFakeCommand,
    config_file: Path,
    written_inventory: Path,
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "release"
    uv = _uv(fake_command, out_dir)
    git = fake_command("git", [("describe", {"stdout": "v0.2.0\n"})])
    playbook = fake_command("ansible-playbook")
    secrets = tmp_path / ".env.staging"
    secrets.write_text("WGM_DISCORD_PUBLIC_KEY=abc\n")

    release_task(
        Context(),
        env="staging",
        ansible=str(playbook.path),
        uv=str(uv.path),
        git=str(git.path),
        config_file=str(config_file),
        inventory=str(written_inventory),
        secrets=str(secrets),
        build_dir=str(out_dir),
    )

    args = playbook.args()[0]
    assert args[-1].endswith("deploy.yaml")
    variables = json.loads(args[args.index("--extra-vars") + 1])
    assert variables["version"] == "v0.2.0"
    assert variables["env_file"] == str(secrets)


def test_rollback_task_runs_the_rollback_playbook(
    fake_command: MakeFakeCommand, config_file: Path, written_inventory: Path
) -> None:
    playbook = fake_command("ansible-playbook")

    rollback_task(
        Context(),
        env="staging",
        ansible=str(playbook.path),
        config_file=str(config_file),
        inventory=str(written_inventory),
    )

    args = playbook.args()[0]
    assert args[-1].endswith("rollback.yaml")
    assert json.loads(args[args.index("--extra-vars") + 1]) == {
        "env": "staging",
        "app_port": 8001,
    }


def test_points_discord_at_the_new_droplet(
    discord_api: FakeDiscordApi, config: DropletConfig, tmp_path: Path
) -> None:
    secrets = tmp_path / ".env.staging"
    secrets.write_text("WGM_DISCORD_PUBLIC_KEY=abc\nWGM_DISCORD_BOT_TOKEN=token\n")

    point_discord_here(config, "staging", IP, secrets, discord_api.url)

    assert discord_api.requests[0].body == {
        "interactions_endpoint_url": (
            "https://staging.203-0-113-7.sslip.io/discord/interactions"
        )
    }


def test_skips_discord_without_a_bot_token(
    discord_api: FakeDiscordApi,
    config: DropletConfig,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    secrets = tmp_path / ".env.staging"
    secrets.write_text("WGM_DISCORD_PUBLIC_KEY=abc\n")

    point_discord_here(config, "staging", IP, secrets, discord_api.url)

    assert discord_api.requests == []
    assert "Skipped the Discord endpoint" in capsys.readouterr().out
