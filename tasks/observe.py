"""Look at what is running on the droplet: logs and status."""

from pathlib import Path

from invoke.context import Context
from invoke.tasks import task

from tasks.config import CONFIG_FILE, DropletConfig, Environment
from tasks.droplet import INVENTORY, read_ip, ssh_options
from tasks.errors import friendly_errors
from tasks.shell import Shell, say


def ssh_command(
    config: DropletConfig, ip: str, remote: str, ssh: str = "ssh"
) -> list[str]:
    """An ssh command that runs `remote` on the droplet as the deploy user."""
    return [
        ssh,
        "-i", str(config.ssh_key_path),
        *ssh_options(config),
        f"{config.user}@{ip}",
        remote,
    ]  # fmt: skip


def logs_command(env: Environment, service: str, since: str, lines: int) -> str:
    """The remote command that shows an environment's logs.

    Raises:
        ValueError: `service` is not "app" or "nginx".
    """
    if service == "app":
        return f"journalctl -u wgm-{env.name} --since '{since}' --no-pager"
    if service == "nginx":
        prefix = f"/var/log/nginx/wgm-{env.name}"
        return f"tail -n {lines} {prefix}.access.log {prefix}.error.log"
    raise ValueError(f"Unknown service {service!r}; expected 'app' or 'nginx'.")


def status_command(env: Environment, ip: str) -> str:
    """The remote command that reports an environment's health."""
    host = env.hostname(ip)
    return " ; ".join(
        [
            f"echo service: $(systemctl is-active wgm-{env.name})",
            f"echo version: $(cat /opt/wgm/{env.name}/current/VERSION"
            " 2>/dev/null || echo none)",
            f"echo ping: $(curl -fsS http://127.0.0.1:{env.port}/ping || echo failed)",
            f"echo certificate: $(echo | openssl s_client -connect {host}:443"
            f" -servername {host} 2>/dev/null | openssl x509 -noout -enddate"
            " || echo none)",
        ]
    )


HELP = {
    "env": "Environment (default staging).",
    "ssh": "Path to ssh.",
    "config_file": "Settings file (default deploy/droplet.toml).",
    "inventory": "Inventory file (default deploy/ansible/inventories).",
}


@task(
    name="logs",
    help=HELP
    | {
        "service": "app (default) or nginx.",
        "since": "How far back for app logs, such as 1h or 2026-11-26 (default 1h).",
        "lines": "How many nginx log lines (default 200).",
    },
)
@friendly_errors
def logs_task(
    c: Context,
    env: str = "staging",
    service: str = "app",
    since: str = "1h",
    lines: int = 200,
    ssh: str = "ssh",
    config_file: str = str(CONFIG_FILE),
    inventory: str = str(INVENTORY),
) -> None:
    """Show an environment's app or nginx logs."""
    config = DropletConfig.load(Path(config_file))
    environment = config.environment(env)
    since = f"{since} ago" if since[-1:] in "smhd" and since[:-1].isdigit() else since
    remote = logs_command(environment, service, since, lines)
    Shell(c).run(
        ssh_command(config, read_ip(Path(inventory)), remote, ssh), capture=False
    )


@task(name="status", help=HELP)
@friendly_errors
def status_task(
    c: Context,
    env: str = "staging",
    ssh: str = "ssh",
    config_file: str = str(CONFIG_FILE),
    inventory: str = str(INVENTORY),
) -> None:
    """Show an environment's service state, version, health check and certificate."""
    config = DropletConfig.load(Path(config_file))
    environment = config.environment(env)
    ip = read_ip(Path(inventory))
    say(Shell(c).run(ssh_command(config, ip, status_command(environment, ip), ssh)))
