"""A droplet settings file and inventory that live in a temporary folder."""

import json
from pathlib import Path

import pytest

from tasks.config import DropletConfig

DROPLET_API = {
    "id": 101,
    "name": "wgm",
    "networks": {
        "v4": [
            {"ip_address": "10.0.0.5", "type": "private"},
            {"ip_address": "203.0.113.7", "type": "public"},
        ]
    },
}
IP = "203.0.113.7"


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    """A settings file whose key and known_hosts point into tmp_path."""
    key = tmp_path / "wgm_do"
    key.write_text("private")
    key.with_suffix(".pub").write_text("ssh-ed25519 AAAAtest wgm\n")
    path = tmp_path / "droplet.toml"
    path.write_text(
        f"""
[droplet]
name = "wgm"
tag = "wgm"
region = "sfo3"
size = "s-1vcpu-1gb"
image = "ubuntu-24-04-x64"
ssh_key_name = "wgm-do"
ssh_key_path = "{key}"
known_hosts = "{tmp_path / "known_hosts"}"
user = "deploy"
uv_version = "0.13.10"
python_version = "3.13"

[environments.staging]
subdomain = "staging"
port = 8001

[environments.production]
subdomain = ""
port = 8002
"""
    )
    return path


@pytest.fixture
def config(config_file: Path) -> DropletConfig:
    """The settings from `config_file`."""
    return DropletConfig.load(config_file)


@pytest.fixture
def inventory(tmp_path: Path) -> Path:
    """Where the inventory goes; it does not exist until written."""
    return tmp_path / "inventory.json"


@pytest.fixture
def written_inventory(inventory: Path) -> Path:
    """An inventory for a droplet at `IP`."""
    inventory.write_text(json.dumps({"all": {"hosts": {"wgm": {"ansible_host": IP}}}}))
    return inventory
