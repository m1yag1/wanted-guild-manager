from pathlib import Path

import pytest
from invoke.context import Context

from tasks.config import DropletConfig
from tasks.observe import (
    logs_command,
    logs_task,
    ssh_command,
    status_command,
    status_task,
)
from tests.fixtures.commands import MakeFakeCommand
from tests.fixtures.droplet import IP


def test_ssh_command_uses_the_project_key(config: DropletConfig) -> None:
    command = ssh_command(config, IP, "uptime")

    assert command[:3] == ["ssh", "-i", str(config.ssh_key_path)]
    assert command[-2:] == [f"deploy@{IP}", "uptime"]
    assert "IdentitiesOnly=yes" in command


def test_app_logs_come_from_journald(config: DropletConfig) -> None:
    command = logs_command(config.environment("staging"), "app", "1h ago", 200)

    assert command == "journalctl -u wgm-staging --since '1h ago' --no-pager"


def test_nginx_logs_come_from_its_files(config: DropletConfig) -> None:
    command = logs_command(config.environment("staging"), "nginx", "", 50)

    assert command == (
        "tail -n 50 /var/log/nginx/wgm-staging.access.log"
        " /var/log/nginx/wgm-staging.error.log"
    )


def test_unknown_log_service(config: DropletConfig) -> None:
    with pytest.raises(ValueError, match="'app' or 'nginx'"):
        logs_command(config.environment("staging"), "db", "", 1)


def test_status_checks_service_version_ping_and_certificate(
    config: DropletConfig,
) -> None:
    command = status_command(config.environment("staging"), IP)

    assert "systemctl is-active wgm-staging" in command
    assert "/opt/wgm/staging/current/VERSION" in command
    assert "http://127.0.0.1:8001/ping" in command
    assert "staging.203-0-113-7.sslip.io:443" in command


@pytest.mark.parametrize(
    ("since", "expected"),
    [("1h", "--since '1h ago'"), ("2026-11-26", "--since '2026-11-26'")],
)
def test_logs_task(
    fake_command: MakeFakeCommand,
    config_file: Path,
    written_inventory: Path,
    since: str,
    expected: str,
) -> None:
    ssh = fake_command("ssh")

    logs_task(
        Context(),
        since=since,
        ssh=str(ssh.path),
        config_file=str(config_file),
        inventory=str(written_inventory),
    )

    assert expected in ssh.args()[0][-1]


def test_status_task_prints_the_report(
    fake_command: MakeFakeCommand,
    config_file: Path,
    written_inventory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ssh = fake_command("ssh", [("systemctl", {"stdout": "service: active\n"})])

    status_task(
        Context(),
        ssh=str(ssh.path),
        config_file=str(config_file),
        inventory=str(written_inventory),
    )

    assert "service: active" in capsys.readouterr().out
