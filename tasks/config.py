"""Droplet and environment settings from `deploy/droplet.toml`."""

import tomllib
from pathlib import Path

from attrs import field, frozen
from attrs.validators import and_, ge, instance_of, le

ROOT = Path(__file__).parents[1]
DEPLOY_DIR = ROOT / "deploy"
ANSIBLE_DIR = DEPLOY_DIR / "ansible"
CONFIG_FILE = DEPLOY_DIR / "droplet.toml"


@frozen
class Environment:
    """One deployed copy of the app, such as staging."""

    name: str
    subdomain: str
    port: int = field(validator=and_(instance_of(int), ge(1), le(65535)))

    def hostname(self, ip: str) -> str:
        """The sslip.io hostname for `ip`, such as staging.1-2-3-4.sslip.io."""
        base = f"{ip.replace('.', '-')}.sslip.io"
        return f"{self.subdomain}.{base}" if self.subdomain else base


def _expand(path: str | Path) -> Path:
    return Path(path).expanduser()


@frozen
class DropletConfig:
    """How the droplet is created and reached."""

    name: str
    tag: str
    region: str
    size: str
    image: str
    ssh_key_name: str
    ssh_key_path: Path = field(converter=_expand)
    known_hosts: Path = field(converter=_expand)
    user: str
    uv_version: str
    python_version: str
    environments: dict[str, Environment]

    @classmethod
    def load(cls, path: Path = CONFIG_FILE) -> "DropletConfig":
        """Read the settings file. Unknown or missing keys are an error."""
        data = tomllib.loads(path.read_text())
        return cls(
            **data["droplet"],
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
