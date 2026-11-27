"""Turning plugins on from settings, and refusing settings that can't work."""

from collections.abc import Callable, Mapping
from typing import Any

import pytest
from attrs import evolve

from wgm.domain.discord.context import (
    ButtonHandler,
    CommandContext,
    Subcommand,
    private_reply,
)
from wgm.domain.discord.schemas import InteractionResponse
from wgm.domain.events.plugin import EventPlugin
from wgm.lib.settings import DiscordSettings, Settings
from wgm.plugins import (
    Job,
    PluginConfig,
    PluginError,
    SettingSpec,
    WgmPlugin,
    installed,
    load_plugins,
)

SETTINGS = Settings(discord=DiscordSettings(public_key="abc"))


async def _answer(ctx: CommandContext, values: dict[str, Any]) -> InteractionResponse:
    return private_reply("raid")  # pragma: no cover - never run


async def _press(ctx: CommandContext) -> InteractionResponse:
    return private_reply("pressed")  # pragma: no cover - never run


class RaidPlugin:
    """A plugin with a required setting, a dev command and a button."""

    name = "raid"
    settings: tuple[SettingSpec, ...] = (
        SettingSpec("size", "a whole number of players, such as 20", parse=int),
    )

    def subcommands(self) -> tuple[Subcommand, ...]:
        return (Subcommand(("raid", "plan"), "Plan a raid", _answer),)

    def dev_subcommands(self) -> tuple[Subcommand, ...]:
        return (Subcommand(("raid", "seed"), "Test raids", _answer),)

    def buttons(self) -> Mapping[str, ButtonHandler]:
        return {"raid": _press}

    def jobs(self, config: PluginConfig) -> tuple[Job, ...]:
        return ()

    async def setup(self, ctx: CommandContext) -> str | None:
        return None  # pragma: no cover - never run


class ConfigPlugin(RaidPlugin):
    """A plugin that tries to take a core command's name."""

    name = "config"


AVAILABLE: dict[str, Callable[[], WgmPlugin]] = {
    "raid": RaidPlugin,
    "config": ConfigPlugin,
}


def _settings(**env: str) -> Settings:
    plugins = tuple(env.pop("WGM_PLUGINS", "raid").split(","))
    return evolve(SETTINGS, plugins=plugins, environ=env)


def test_the_installed_plugins_follow_the_plugin_shape() -> None:
    plugin: WgmPlugin = EventPlugin()

    assert list(installed()) == ["event"]
    assert installed()["event"]().name == "event"
    assert plugin.name == "event"


def test_events_are_on_by_default() -> None:
    plugins = load_plugins(SETTINGS)

    assert plugins.names == ("event",)
    assert plugins.config == {"event": {"close_check_seconds": 60.0}}


def test_plugin_settings_are_read_and_parsed() -> None:
    plugins = load_plugins(_settings(WGM_RAID_SIZE=" 20 "), AVAILABLE)

    assert plugins.config["raid"] == {"size": 20}
    assert [sub.usage for sub in plugins.subcommands] == ["/wgm raid plan"]
    assert plugins.button("raid") is _press
    assert plugins.button("signup") is None


def test_dev_mode_adds_dev_subcommands() -> None:
    settings = evolve(_settings(WGM_RAID_SIZE="20"), dev_mode=True)

    plugins = load_plugins(settings, AVAILABLE)

    assert [sub.usage for sub in plugins.subcommands] == [
        "/wgm raid plan",
        "/wgm raid seed",
    ]


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({"WGM_PLUGINS": "raid,nope"}, "'nope', which isn't installed"),
        ({"WGM_PLUGINS": "config"}, "can't be called 'config'"),
        ({}, "needs WGM_RAID_SIZE: a whole number"),
        ({"WGM_RAID_SIZE": "lots"}, "WGM_RAID_SIZE='lots' isn't valid"),
    ],
)
def test_settings_that_cannot_work_stop_startup(
    env: dict[str, str], message: str
) -> None:
    with pytest.raises(PluginError, match=message):
        load_plugins(_settings(**env), AVAILABLE)


def test_unknown_plugins_list_what_is_installed() -> None:
    with pytest.raises(PluginError, match="Installed plugins: none"):
        load_plugins(_settings(), {})


@pytest.mark.parametrize("seconds", ["0", "-5", "soon"])
def test_the_close_check_must_be_a_positive_number(seconds: str) -> None:
    settings = evolve(SETTINGS, environ={"WGM_EVENT_CLOSE_CHECK_SECONDS": seconds})

    with pytest.raises(PluginError, match="WGM_EVENT_CLOSE_CHECK_SECONDS"):
        load_plugins(settings)
