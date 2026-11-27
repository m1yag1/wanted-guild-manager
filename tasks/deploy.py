"""Build the app and deploy it to an environment on the droplet."""

import shutil
from pathlib import Path
from typing import Any

from attrs import frozen
from invoke.context import Context
from invoke.tasks import task

from tasks.config import CONFIG_FILE, ROOT, DropletConfig, Environment
from tasks.discord import API_URL, DiscordRest, interactions_url
from tasks.droplet import INVENTORY, Ansible, ansible_shell, read_ip
from tasks.errors import friendly_errors
from tasks.shell import Shell, say
from wgm.lib.settings import load_settings

BUILD_DIR = ROOT / "dist" / "release"
KEEP_RELEASES = 5
KEEP_BACKUPS = 10


class DirtyTreeError(RuntimeError):
    """The working tree has uncommitted changes."""


@frozen
class Build:
    """A wheel plus the pinned requirements it needs."""

    version: str
    wheel: Path
    requirements: Path


def current_version(shell: Shell, git: str = "git") -> str:
    """The version from git tags, refusing uncommitted changes.

    Raises:
        DirtyTreeError: There are uncommitted changes.
    """
    # Only version tags (v1.2.3) count; other tags such as web-prototype do not.
    describe = [git, "describe", "--tags", "--match", "v[0-9]*", "--always", "--dirty"]
    version = shell.run(describe).strip()
    if version.endswith("-dirty"):
        raise DirtyTreeError("Commit or stash your changes before deploying.")
    return version


def build(shell: Shell, version: str, out_dir: Path, uv: str = "uv") -> Build:
    """Build the wheel and export pinned requirements from uv.lock."""
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True)
    shell.run([uv, "build", "--wheel", "--out-dir", str(out_dir)])
    requirements = out_dir / "requirements.txt"
    shell.run(
        [
            uv, "export", "--frozen", "--no-dev", "--no-emit-project",
            "--format", "requirements-txt", "--output-file", str(requirements),
        ]
    )  # fmt: skip
    wheel = next(out_dir.glob("*.whl"))
    return Build(version=version, wheel=wheel, requirements=requirements)


def env_file(env: Environment, root: Path = ROOT) -> Path:
    """The local secrets file for an environment, such as `.env.staging`.

    Raises:
        FileNotFoundError: The file does not exist yet.
    """
    path = root / f".env.{env.name}"
    if not path.exists():
        raise FileNotFoundError(
            f"Create {path.name} from .env.example with the {env.name} values first."
        )
    return path


def deploy_vars(
    config: DropletConfig, env: Environment, ip: str, build: Build, secrets: Path
) -> dict[str, Any]:
    """Variables for `deploy.yaml`."""
    return {
        "env": env.name,
        "app_port": env.port,
        "hostname": env.hostname(ip),
        "version": build.version,
        "wheel": str(build.wheel),
        "requirements": str(build.requirements),
        "env_file": str(secrets),
        "python_version": config.python_version,
        "keep_releases": KEEP_RELEASES,
        "keep_backups": KEEP_BACKUPS,
    }


HELP = {
    "env": "Environment (default staging).",
    "ansible": "Path to ansible-playbook.",
    "config_file": "Settings file (default deploy/droplet.toml).",
    "inventory": "Inventory file (default deploy/ansible/inventories/wgm.json).",
}


@task(
    name="release",
    default=True,
    help=HELP
    | {
        "uv": "Path to uv.",
        "git": "Path to git.",
        "secrets": "Secrets file to install (default .env.<env>).",
        "build_dir": "Where to build the wheel (default dist/release).",
        "api_url": "Discord API base URL.",
    },
)
@friendly_errors
def release_task(
    c: Context,
    env: str = "staging",
    ansible: str = "ansible-playbook",
    uv: str = "uv",
    git: str = "git",
    config_file: str = str(CONFIG_FILE),
    inventory: str = str(INVENTORY),
    secrets: str = "",
    build_dir: str = str(BUILD_DIR),
    api_url: str = API_URL,
) -> None:
    """Build the app and deploy it as a new release."""
    config = DropletConfig.load(Path(config_file))
    environment = config.environment(env)
    ip = read_ip(Path(inventory))
    secrets_file = Path(secrets) if secrets else env_file(environment)
    shell = Shell(c)
    built = build(shell, current_version(shell, git), Path(build_dir), uv)
    say(f"Deploying {built.version} to {env} ({environment.hostname(ip)})...")
    Ansible(ansible_shell(c), config, Path(inventory), ansible).play(
        "deploy.yaml",
        user=config.user,
        extra_vars=deploy_vars(config, environment, ip, built, secrets_file),
    )
    point_discord_here(config, env, ip, secrets_file, api_url)


def point_discord_here(
    config: DropletConfig, env: str, ip: str, secrets_file: Path, api_url: str
) -> None:
    """Set the Discord app's endpoint URL, which changes with each new droplet."""
    discord = load_settings(environ={}, env_file=secrets_file).discord
    if not discord.bot_token:
        say(f"Skipped the Discord endpoint: no bot token in {secrets_file.name}.")
        return
    url = interactions_url(config, env, ip)
    DiscordRest(discord.bot_token, api_url).set_interactions_endpoint(url)
    say(f"Discord now sends interactions to {url}")


@task(name="rollback", help=HELP)
@friendly_errors
def rollback_task(
    c: Context,
    env: str = "staging",
    ansible: str = "ansible-playbook",
    config_file: str = str(CONFIG_FILE),
    inventory: str = str(INVENTORY),
) -> None:
    """Switch an environment back to its previous release."""
    config = DropletConfig.load(Path(config_file))
    environment = config.environment(env)
    Ansible(ansible_shell(c), config, Path(inventory), ansible).play(
        "rollback.yaml",
        user=config.user,
        extra_vars={"env": environment.name, "app_port": environment.port},
    )
