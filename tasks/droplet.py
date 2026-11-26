"""Create, provision, inspect and delete the DigitalOcean droplet."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from invoke.context import Context
from invoke.tasks import task

from tasks.config import ANSIBLE_DIR, CONFIG_FILE, DropletConfig
from tasks.errors import friendly_errors
from tasks.shell import CommandError, Shell, say

Echo = Callable[[str], None]

INVENTORY = ANSIBLE_DIR / "inventories" / "wgm.json"


@dataclass(frozen=True, slots=True)
class Droplet:
    """A droplet as DigitalOcean reports it."""

    id: str
    name: str
    ip: str

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Droplet":
        """Build from one entry of `doctl ... --output json`."""
        ip = next(
            net["ip_address"]
            for net in data["networks"]["v4"]
            if net["type"] == "public"
        )
        return cls(id=str(data["id"]), name=data["name"], ip=ip)


@dataclass(frozen=True, slots=True)
class Doctl:
    """The few `doctl` calls the tasks need."""

    shell: Shell
    executable: str = "doctl"

    def _json(self, *args: str) -> Any:
        output = self.shell.run([self.executable, *args, "--output", "json"])
        return json.loads(output) if output.strip() else []

    def find(self, config: DropletConfig) -> Droplet | None:
        """The project's droplet: it must carry the tag and have the name."""
        droplets = self._json("compute", "droplet", "list", "--tag-name", config.tag)
        for data in droplets:
            if data["name"] == config.name:
                return Droplet.from_api(data)
        return None

    def ssh_key_id(self, name: str) -> str:
        """The DigitalOcean ID of the SSH key with this name.

        Raises:
            ValueError: No key has that name.
        """
        for key in self._json("compute", "ssh-key", "list"):
            if key["name"] == name:
                return str(key["id"])
        raise ValueError(f"No SSH key named {name!r} in DigitalOcean.")

    def create(self, config: DropletConfig) -> Droplet:
        """Create the droplet and wait until it is active."""
        created = self._json(
            "compute", "droplet", "create", config.name,
            "--region", config.region,
            "--size", config.size,
            "--image", config.image,
            "--ssh-keys", self.ssh_key_id(config.ssh_key_name),
            "--tag-names", config.tag,
            "--wait",
        )  # fmt: skip
        return Droplet.from_api(created[0])

    def delete(self, droplet: Droplet) -> None:
        """Delete the droplet."""
        self.shell.run(
            [self.executable, "compute", "droplet", "delete", droplet.id, "--force"]
        )


def ssh_options(config: DropletConfig) -> list[str]:
    """Options that make ssh use only the project key and known_hosts file."""
    return [
        "-o", "IdentitiesOnly=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", f"UserKnownHostsFile={config.known_hosts}",
    ]  # fmt: skip


@dataclass(frozen=True, slots=True)
class Ansible:
    """Runs the project's playbooks against the droplet."""

    shell: Shell
    config: DropletConfig
    inventory: Path = INVENTORY
    executable: str = "ansible-playbook"

    def play(self, playbook: str, *, user: str, extra_vars: dict[str, Any]) -> None:
        """Run a playbook from `deploy/ansible`, showing its output."""
        self.shell.run(
            [
                self.executable,
                "--inventory",
                str(self.inventory),
                "--user",
                user,
                "--private-key",
                str(self.config.ssh_key_path),
                "--ssh-common-args",
                " ".join(ssh_options(self.config)),
                "--extra-vars",
                json.dumps(extra_vars),
                str(ANSIBLE_DIR / playbook),
            ],  # fmt: skip
            capture=False,
        )


class SshKeyError(RuntimeError):
    """The project SSH key cannot be used without a passphrase prompt."""


@dataclass(frozen=True, slots=True)
class SshTools:
    """The ssh programs used to check the key and the login user."""

    shell: Shell
    ssh: str = "ssh"
    keygen: str = "ssh-keygen"
    agent: str = "ssh-add"

    def check_key(self, config: DropletConfig) -> None:
        """Make sure Ansible can use the key without asking for a passphrase.

        Raises:
            SshKeyError: The key has a passphrase and is not in the SSH agent.
        """
        key = config.ssh_key_path
        try:
            self.shell.run([self.keygen, "-y", "-P", "", "-f", str(key)])
            return  # no passphrase
        except CommandError:
            pass
        try:
            self.shell.run([self.agent, "-T", str(key.with_suffix(".pub"))])
        except CommandError:
            raise SshKeyError(
                f"{key} has a passphrase and is not loaded in your SSH agent. "
                f"Run: ssh-add --apple-use-keychain {key}"
            ) from None

    def login_user(self, config: DropletConfig, ip: str) -> str:
        """The deploy user once provisioning has created it, otherwise root."""
        try:
            self.shell.run(
                [
                    self.ssh, "-i", str(config.ssh_key_path), *ssh_options(config),
                    "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
                    f"{config.user}@{ip}", "true",
                ]
            )  # fmt: skip
        except CommandError:
            return "root"
        return config.user


def write_inventory(droplet: Droplet, path: Path = INVENTORY) -> None:
    """Write the Ansible inventory for the droplet (JSON is valid YAML)."""
    inventory = {"all": {"hosts": {droplet.name: {"ansible_host": droplet.ip}}}}
    path.write_text(json.dumps(inventory, indent=2) + "\n")


def read_ip(path: Path = INVENTORY) -> str:
    """The droplet IP from the inventory.

    Raises:
        FileNotFoundError: There is no inventory; run `inv droplet.up` first.
    """
    if not path.exists():
        raise FileNotFoundError("No droplet inventory yet. Run `inv droplet.up` first.")
    hosts = json.loads(path.read_text())["all"]["hosts"]
    return str(next(iter(hosts.values()))["ansible_host"])


def provision_vars(config: DropletConfig, ip: str) -> dict[str, Any]:
    """Variables for `provision.yaml`."""
    return {
        "deploy_user": config.user,
        "ssh_public_key": config.ssh_key_path.with_suffix(".pub").read_text().strip(),
        "uv_version": config.uv_version,
        "python_version": config.python_version,
        "environments": [
            {"name": env.name, "port": env.port, "hostname": env.hostname(ip)}
            for env in config.environments.values()
        ],
    }


def up(
    doctl: Doctl,
    ansible: Ansible,
    ssh: SshTools,
    config: DropletConfig,
    echo: Echo,
) -> Droplet:
    """Create the droplet if needed, then provision it."""
    ssh.check_key(config)
    droplet = doctl.find(config)
    if droplet is None:
        echo(f"Creating droplet {config.name} in {config.region} ({config.size})...")
        droplet = doctl.create(config)
        user = "root"
    else:
        echo(f"Droplet {droplet.name} already exists at {droplet.ip}.")
        user = ssh.login_user(config, droplet.ip)
    write_inventory(droplet, ansible.inventory)

    # A new droplet only lets root in; provisioning creates the deploy user
    # and then turns root login off.
    ansible.play(
        "provision.yaml", user=user, extra_vars=provision_vars(config, droplet.ip)
    )
    for env in config.environments.values():
        echo(f"{env.name}: https://{env.hostname(droplet.ip)}")
    return droplet


def down(
    doctl: Doctl,
    config: DropletConfig,
    *,
    inventory: Path,
    answer: str,
    echo: Echo,
) -> bool:
    """Delete the droplet if `answer` is its name. Returns True when deleted."""
    droplet = doctl.find(config)
    if droplet is None:
        echo(f"No droplet named {config.name} with tag {config.tag}; nothing to do.")
        return False
    if answer != config.name:
        echo("Cancelled: the name did not match.")
        return False
    doctl.delete(droplet)
    inventory.unlink(missing_ok=True)
    if config.known_hosts.exists():
        forget = ["ssh-keygen", "-R", droplet.ip, "-f", str(config.known_hosts)]
        doctl.shell.run(forget)
    echo(f"Deleted droplet {droplet.name} ({droplet.ip}).")
    return True


def status(doctl: Doctl, config: DropletConfig, echo: Echo) -> None:
    """Print the droplet and its links."""
    droplet = doctl.find(config)
    if droplet is None:
        echo(f"No droplet named {config.name}. Create it with `inv droplet.up`.")
        return
    echo(f"{droplet.name} ({droplet.id}) at {droplet.ip}")
    for env in config.environments.values():
        echo(f"  {env.name}: https://{env.hostname(droplet.ip)}")


def ansible_shell(c: Context) -> Shell:
    """A shell that points Ansible at the project's ansible.cfg."""
    return Shell(c, env={"ANSIBLE_CONFIG": str(ANSIBLE_DIR / "ansible.cfg")})


DOCTL = {"doctl": "Path to doctl."}
ANSIBLE = {"ansible": "Path to ansible-playbook."}
FILES = {
    "config_file": "Settings file (default deploy/droplet.toml).",
    "inventory": "Inventory file (default deploy/ansible/inventories/wgm.json).",
}


SSH = {
    "ssh": "Path to ssh.",
    "ssh_keygen": "Path to ssh-keygen.",
    "ssh_add": "Path to ssh-add.",
}


@task(name="up", help=DOCTL | ANSIBLE | FILES | SSH)
@friendly_errors
def up_task(
    c: Context,
    doctl: str = "doctl",
    ansible: str = "ansible-playbook",
    config_file: str = str(CONFIG_FILE),
    inventory: str = str(INVENTORY),
    ssh: str = "ssh",
    ssh_keygen: str = "ssh-keygen",
    ssh_add: str = "ssh-add",
) -> None:
    """Create the droplet if needed and provision it."""
    config = DropletConfig.load(Path(config_file))
    up(
        Doctl(Shell(c), doctl),
        Ansible(ansible_shell(c), config, Path(inventory), ansible),
        SshTools(Shell(c), ssh, ssh_keygen, ssh_add),
        config,
        say,
    )


@task(name="provision", help=ANSIBLE | FILES)
@friendly_errors
def provision_task(
    c: Context,
    ansible: str = "ansible-playbook",
    config_file: str = str(CONFIG_FILE),
    inventory: str = str(INVENTORY),
) -> None:
    """Re-run provisioning on the existing droplet as the deploy user."""
    config = DropletConfig.load(Path(config_file))
    Ansible(ansible_shell(c), config, Path(inventory), ansible).play(
        "provision.yaml",
        user=config.user,
        extra_vars=provision_vars(config, read_ip(Path(inventory))),
    )


@task(
    name="down",
    help=DOCTL | FILES | {"confirm": "The droplet name, to skip the prompt."},
)
@friendly_errors
def down_task(
    c: Context,
    confirm: str = "",
    doctl: str = "doctl",
    config_file: str = str(CONFIG_FILE),
    inventory: str = str(INVENTORY),
) -> None:
    """Delete the droplet after you type its name."""
    config = DropletConfig.load(Path(config_file))
    answer = confirm or input(f"Type {config.name!r} to delete the droplet: ")
    down(
        Doctl(Shell(c), doctl),
        config,
        inventory=Path(inventory),
        answer=answer,
        echo=say,
    )


@task(name="status", help=DOCTL | {"config_file": FILES["config_file"]})
@friendly_errors
def status_task(
    c: Context, doctl: str = "doctl", config_file: str = str(CONFIG_FILE)
) -> None:
    """Show the droplet and its links."""
    status(Doctl(Shell(c), doctl), DropletConfig.load(Path(config_file)), say)
