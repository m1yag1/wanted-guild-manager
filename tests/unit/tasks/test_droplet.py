import json
from collections.abc import Callable
from pathlib import Path

import pytest
from invoke.context import Context

from tasks.config import ANSIBLE_DIR, DropletConfig
from tasks.droplet import (
    Ansible,
    Doctl,
    Droplet,
    SshKeyError,
    SshTools,
    down,
    down_task,
    provision_task,
    provision_vars,
    read_ip,
    ssh_options,
    status,
    status_task,
    up,
    up_task,
    write_inventory,
)
from tasks.shell import Shell
from tests.fixtures.commands import FakeCommand, MakeFakeCommand
from tests.fixtures.droplet import DROPLET_API, IP

DROPLET = Droplet(id="101", name="wgm", ip=IP)
LIST = "droplet list"
KEYS = "ssh-key list"
CREATE = "droplet create"


def _doctl(fake_command: MakeFakeCommand, droplets: list[object]) -> FakeCommand:
    return fake_command(
        "doctl",
        [
            (LIST, {"stdout": json.dumps(droplets)}),
            (
                KEYS,
                {
                    "stdout": json.dumps(
                        [{"id": 1, "name": "personal"}, {"id": 9, "name": "wgm-do"}]
                    )
                },
            ),
            (CREATE, {"stdout": json.dumps([DROPLET_API])}),
        ],
    )


def _ssh(
    fake_command: MakeFakeCommand,
    *,
    passphrase: bool = False,
    in_agent: bool = True,
    deploy_login: bool = True,
) -> SshTools:
    keygen = fake_command("ssh-keygen", [("-y", {"code": int(passphrase)})])
    agent = fake_command("ssh-add", [("-T", {"code": int(not in_agent)})])
    ssh = fake_command("ssh", [("true", {"code": int(not deploy_login)})])
    return SshTools(Shell(Context()), str(ssh.path), str(keygen.path), str(agent.path))


def _messages() -> tuple[list[str], Callable[[str], None]]:
    messages: list[str] = []
    return messages, messages.append


def test_reads_the_public_ip_from_the_api() -> None:
    assert Droplet.from_api(DROPLET_API) == DROPLET


def test_finds_the_droplet_by_tag_and_name(
    fake_command: MakeFakeCommand, config: DropletConfig
) -> None:
    other = DROPLET_API | {"name": "jupyter"}
    doctl = _doctl(fake_command, [other, DROPLET_API])

    assert Doctl(Shell(Context()), str(doctl.path)).find(config) == DROPLET
    assert doctl.args()[0] == [
        "compute", "droplet", "list", "--tag-name", "wgm", "--output", "json",
    ]  # fmt: skip


@pytest.mark.parametrize("output", ["[]", ""])
def test_finds_nothing_when_no_droplet_matches(
    fake_command: MakeFakeCommand, config: DropletConfig, output: str
) -> None:
    doctl = fake_command("doctl", [(LIST, {"stdout": output})])

    assert Doctl(Shell(Context()), str(doctl.path)).find(config) is None


def test_creates_the_droplet_with_the_project_key(
    fake_command: MakeFakeCommand, config: DropletConfig
) -> None:
    doctl = _doctl(fake_command, [])

    assert Doctl(Shell(Context()), str(doctl.path)).create(config) == DROPLET
    create = doctl.args()[-1]
    assert create[:4] == ["compute", "droplet", "create", "wgm"]
    assert create[create.index("--ssh-keys") + 1] == "9"
    assert create[create.index("--tag-names") + 1] == "wgm"
    assert "--wait" in create


def test_missing_ssh_key_is_an_error(
    fake_command: MakeFakeCommand, config: DropletConfig
) -> None:
    doctl = fake_command("doctl", [(KEYS, {"stdout": "[]"})])

    with pytest.raises(ValueError, match="wgm-do"):
        Doctl(Shell(Context()), str(doctl.path)).ssh_key_id("wgm-do")


def test_ssh_options_pin_the_key_and_known_hosts(config: DropletConfig) -> None:
    options = ssh_options(config)

    assert "IdentitiesOnly=yes" in options
    assert f"UserKnownHostsFile={config.known_hosts}" in options


def test_inventory_round_trip(inventory: Path) -> None:
    write_inventory(DROPLET, inventory)

    assert read_ip(inventory) == IP


def test_reading_a_missing_inventory_explains_what_to_do(inventory: Path) -> None:
    with pytest.raises(FileNotFoundError, match="inv droplet.up"):
        read_ip(inventory)


def test_provision_vars(config: DropletConfig) -> None:
    variables = provision_vars(config, IP)

    assert variables["deploy_user"] == "deploy"
    assert variables["ssh_public_key"] == "ssh-ed25519 AAAAtest wgm"
    assert variables["environments"][0] == {
        "name": "staging",
        "port": 8001,
        "hostname": "staging.203-0-113-7.sslip.io",
    }


def test_ansible_runs_playbooks_from_the_project(
    fake_command: MakeFakeCommand, config: DropletConfig, inventory: Path
) -> None:
    playbook = fake_command("ansible-playbook")

    Ansible(Shell(Context()), config, inventory, str(playbook.path)).play(
        "deploy.yaml", user="deploy", extra_vars={"env": "staging"}
    )

    args = playbook.args()[0]
    assert args[args.index("--inventory") + 1] == str(inventory)
    assert args[args.index("--user") + 1] == "deploy"
    assert args[args.index("--private-key") + 1] == str(config.ssh_key_path)
    assert json.loads(args[args.index("--extra-vars") + 1]) == {"env": "staging"}
    assert args[-1] == str(ANSIBLE_DIR / "deploy.yaml")


def test_up_creates_and_provisions_as_root(
    fake_command: MakeFakeCommand, config: DropletConfig, inventory: Path
) -> None:
    doctl = _doctl(fake_command, [])
    playbook = fake_command("ansible-playbook")
    messages, echo = _messages()

    up(
        Doctl(Shell(Context()), str(doctl.path)),
        Ansible(Shell(Context()), config, inventory, str(playbook.path)),
        _ssh(fake_command),
        config,
        echo,
    )

    assert read_ip(inventory) == IP
    args = playbook.args()[0]
    assert args[args.index("--user") + 1] == "root"
    assert args[-1].endswith("provision.yaml")
    assert messages[-2] == "staging: https://staging.203-0-113-7.sslip.io"


def test_up_reprovisions_an_existing_droplet_as_deploy(
    fake_command: MakeFakeCommand, config: DropletConfig, inventory: Path
) -> None:
    doctl = _doctl(fake_command, [DROPLET_API])
    playbook = fake_command("ansible-playbook")
    messages, echo = _messages()

    up(
        Doctl(Shell(Context()), str(doctl.path)),
        Ansible(Shell(Context()), config, inventory, str(playbook.path)),
        _ssh(fake_command),
        config,
        echo,
    )

    assert not any(CREATE in " ".join(args) for args in doctl.args())
    args = playbook.args()[0]
    assert args[args.index("--user") + 1] == "deploy"
    assert messages[0] == f"Droplet wgm already exists at {IP}."


def test_up_finishes_a_droplet_that_was_never_provisioned(
    fake_command: MakeFakeCommand, config: DropletConfig, inventory: Path
) -> None:
    doctl = _doctl(fake_command, [DROPLET_API])
    playbook = fake_command("ansible-playbook")

    up(
        Doctl(Shell(Context()), str(doctl.path)),
        Ansible(Shell(Context()), config, inventory, str(playbook.path)),
        _ssh(fake_command, deploy_login=False),
        config,
        print,
    )

    args = playbook.args()[0]
    assert args[args.index("--user") + 1] == "root"


def test_up_stops_before_creating_when_the_key_needs_a_passphrase(
    fake_command: MakeFakeCommand, config: DropletConfig, inventory: Path
) -> None:
    doctl = _doctl(fake_command, [])
    playbook = fake_command("ansible-playbook")

    with pytest.raises(SshKeyError, match="ssh-add --apple-use-keychain"):
        up(
            Doctl(Shell(Context()), str(doctl.path)),
            Ansible(Shell(Context()), config, inventory, str(playbook.path)),
            _ssh(fake_command, passphrase=True, in_agent=False),
            config,
            print,
        )

    assert doctl.args() == []
    assert playbook.args() == []


def test_a_passphrase_key_in_the_agent_is_fine(
    fake_command: MakeFakeCommand, config: DropletConfig
) -> None:
    _ssh(fake_command, passphrase=True, in_agent=True).check_key(config)


def test_down_does_nothing_without_a_droplet(
    fake_command: MakeFakeCommand, config: DropletConfig, inventory: Path
) -> None:
    doctl = _doctl(fake_command, [])
    messages, echo = _messages()

    deleted = down(
        Doctl(Shell(Context()), str(doctl.path)),
        config,
        inventory=inventory,
        answer="wgm",
        echo=echo,
    )

    assert not deleted
    assert "nothing to do" in messages[0]


def test_down_needs_the_exact_name(
    fake_command: MakeFakeCommand, config: DropletConfig, written_inventory: Path
) -> None:
    doctl = _doctl(fake_command, [DROPLET_API])
    messages, echo = _messages()

    deleted = down(
        Doctl(Shell(Context()), str(doctl.path)),
        config,
        inventory=written_inventory,
        answer="WGM",
        echo=echo,
    )

    assert not deleted
    assert not any("delete" in args for args in doctl.args())
    assert written_inventory.exists()


def test_down_deletes_and_forgets_the_host(
    fake_command: MakeFakeCommand, config: DropletConfig, written_inventory: Path
) -> None:
    doctl = _doctl(fake_command, [DROPLET_API])
    config.known_hosts.write_text(f"{IP} ssh-ed25519 AAAA\n")
    messages, echo = _messages()

    deleted = down(
        Doctl(Shell(Context()), str(doctl.path)),
        config,
        inventory=written_inventory,
        answer="wgm",
        echo=echo,
    )

    assert deleted
    assert doctl.args()[-1] == ["compute", "droplet", "delete", "101", "--force"]
    assert not written_inventory.exists()
    assert IP not in config.known_hosts.read_text()
    assert messages == [f"Deleted droplet wgm ({IP})."]


def test_down_without_known_hosts(
    fake_command: MakeFakeCommand, config: DropletConfig, written_inventory: Path
) -> None:
    doctl = _doctl(fake_command, [DROPLET_API])

    assert down(
        Doctl(Shell(Context()), str(doctl.path)),
        config,
        inventory=written_inventory,
        answer="wgm",
        echo=print,
    )


def test_status_lists_links(
    fake_command: MakeFakeCommand, config: DropletConfig
) -> None:
    doctl = _doctl(fake_command, [DROPLET_API])
    messages, echo = _messages()

    status(Doctl(Shell(Context()), str(doctl.path)), config, echo)

    assert messages == [
        f"wgm (101) at {IP}",
        "  staging: https://staging.203-0-113-7.sslip.io",
        "  production: https://203-0-113-7.sslip.io",
    ]


def test_status_without_a_droplet(
    fake_command: MakeFakeCommand, config: DropletConfig
) -> None:
    doctl = _doctl(fake_command, [])
    messages, echo = _messages()

    status(Doctl(Shell(Context()), str(doctl.path)), config, echo)

    assert "inv droplet.up" in messages[0]


def test_tasks_use_the_given_tools_and_files(
    fake_command: MakeFakeCommand,
    config_file: Path,
    inventory: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    doctl = _doctl(fake_command, [DROPLET_API])
    playbook = fake_command("ansible-playbook", env_keys=("ANSIBLE_CONFIG",))
    files = {"config_file": str(config_file), "inventory": str(inventory)}

    tools = _ssh(fake_command)
    up_task(
        Context(),
        doctl=str(doctl.path),
        ansible=str(playbook.path),
        ssh=tools.ssh,
        ssh_keygen=tools.keygen,
        ssh_add=tools.agent,
        **files,
    )
    provision_task(Context(), ansible=str(playbook.path), **files)
    status_task(Context(), doctl=str(doctl.path), config_file=str(config_file))
    down_task(Context(), confirm="wgm", doctl=str(doctl.path), **files)

    calls = playbook.calls()
    assert len(calls) == 2
    assert calls[0]["env"]["ANSIBLE_CONFIG"] == str(ANSIBLE_DIR / "ansible.cfg")
    assert not inventory.exists()
    assert "Deleted droplet wgm" in capsys.readouterr().out
