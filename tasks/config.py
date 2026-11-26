"""Droplet and environment settings from `deploy/droplet.toml`."""

import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).parents[1]
DEPLOY_DIR = ROOT / "deploy"
ANSIBLE_DIR = DEPLOY_DIR / "ansible"
CONFIG_FILE = DEPLOY_DIR / "droplet.toml"


@dataclass(frozen=True, slots=True)
class Environment:
    """One deployed copy of the app, such as staging."""

    name: str
    subdomain: str
    port: int

    def hostname(self, ip: str) -> str:
        """The sslip.io hostname for `ip`, such as staging.1-2-3-4.sslip.io."""
        base = f"{ip.replace('.', '-')}.sslip.io"
        return f"{self.subdomain}.{base}" if self.subdomain else base


@dataclass(frozen=True, slots=True)
class DropletConfig:
    """How the droplet is created and reached."""

    name: str
    tag: str
    region: str
    size: str
    image: str
    ssh_key_name: str
    ssh_key_path: Path
    known_hosts: Path
    user: str
    uv_version: str
    python_version: str
    environments: dict[str, Environment]

    @classmethod
    def load(cls, path: Path = CONFIG_FILE) -> "DropletConfig":
        """Read the settings file."""
        data = tomllib.loads(path.read_text())
        droplet = data["droplet"]
        return cls(
            name=droplet["name"],
            tag=droplet["tag"],
            region=droplet["region"],
            size=droplet["size"],
            image=droplet["image"],
            ssh_key_name=droplet["ssh_key_name"],
            ssh_key_path=Path(droplet["ssh_key_path"]).expanduser(),
            known_hosts=Path(droplet["known_hosts"]).expanduser(),
            user=droplet["user"],
            uv_version=droplet["uv_version"],
            python_version=droplet["python_version"],
            environments={
                name: Environment(
                    name=name, subdomain=env["subdomain"], port=env["port"]
                )
                for name, env in data["environments"].items()
            },
        )

    def environment(self, name: str) -> Environment:
        """Look up an environment by name.

        Raises:
            ValueError: No environment has that name.
        """
        if name not in self.environments:
            known = ", ".join(sorted(self.environments))
            raise ValueError(f"Unknown environment {name!r}; expected one of: {known}")
        return self.environments[name]
