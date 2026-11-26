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
