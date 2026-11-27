from pathlib import Path

import attrs
import pytest

from tasks.config import CONFIG_FILE, DropletConfig, Environment


def test_loads_the_project_settings() -> None:
    config = DropletConfig.load(CONFIG_FILE)

    assert config.name == "wgm"
    assert config.ssh_key_name == "wgm-do"
    assert not str(config.ssh_key_path).startswith("~")
    assert set(config.environments) == {"staging"}


def test_staging_hostname_has_a_prefix() -> None:
    env = Environment(name="staging", subdomain="staging", port=8001)

    assert env.hostname("1.2.3.4") == "staging.1-2-3-4.sslip.io"


def test_production_hostname_has_no_prefix() -> None:
    env = Environment(name="production", subdomain="", port=8002)

    assert env.hostname("1.2.3.4") == "1-2-3-4.sslip.io"


def test_looks_up_environments_by_name(config: DropletConfig) -> None:
    assert config.environment("staging").port == 8001


def test_unknown_environments_list_the_choices(config: DropletConfig) -> None:
    with pytest.raises(ValueError, match="production, staging"):
        config.environment("qa")


@pytest.mark.parametrize("port", [0, 70000, "8001"])
def test_rejects_bad_ports(port: object) -> None:
    with pytest.raises((ValueError, TypeError)):
        Environment(name="staging", subdomain="staging", port=port)  # type: ignore[arg-type]


def test_expands_home_in_key_paths(config: DropletConfig) -> None:
    moved = attrs.evolve(config, ssh_key_path="~/.ssh/wgm_do")

    assert moved.ssh_key_path == Path.home() / ".ssh" / "wgm_do"


def test_unknown_settings_are_an_error(config_file: Path) -> None:
    config_file.write_text(
        config_file.read_text().replace('user = "deploy"', 'user = "deploy"\nusr = "x"')
    )

    with pytest.raises(TypeError, match="usr"):
        DropletConfig.load(config_file)
