"""What a plugin is: the shape WGM expects, its settings and its jobs."""

from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Protocol

from advanced_alchemy.extensions.litestar import SQLAlchemyAsyncConfig
from attrs import field, frozen

from wgm.domain.discord.client import DiscordClient
from wgm.domain.discord.context import ButtonHandler, CommandContext, Subcommand

PluginConfig = Mapping[str, Any]
"""A plugin's settings by key, already parsed."""


@frozen
class SettingSpec:
    """A setting a plugin reads from `WGM_<PLUGIN>_<KEY>`."""

    key: str
    description: str
    default: str | None = None
    """None makes the setting required."""
    parse: Callable[[str], Any] = str
    """Turns the text into a value; raises ValueError for bad text."""

    def env_name(self, plugin: str) -> str:
        """close_check_seconds of event -> WGM_EVENT_CLOSE_CHECK_SECONDS"""
        return f"WGM_{plugin.upper()}_{self.key.upper()}"


@frozen
class JobContext:
    """What a background job gets each time it runs."""

    db: SQLAlchemyAsyncConfig
    discord: DiscordClient
    config: PluginConfig
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))
    """The current time. Tests pass a fixed one."""


@frozen
class Job:
    """Work a plugin runs every `seconds` while the app is up."""

    name: str
    seconds: float
    run: Callable[[JobContext], Awaitable[object]]


class WgmPlugin(Protocol):
    """One area of /wgm, such as events. See ADR 0013.

    A plugin owns the `/wgm <name> ...` command group. It doesn't subclass
    anything: any object with these members is a plugin.
    """

    name: str
    """Its name in WGM_PLUGINS and its /wgm command group."""
    settings: tuple[SettingSpec, ...]

    def subcommands(self) -> tuple[Subcommand, ...]:
        """Its /wgm <name> subcommands."""
        ...

    def dev_subcommands(self) -> tuple[Subcommand, ...]:
        """Subcommands for trying the plugin by hand, such as posting test data.

        Only registered and answered in dev mode (WGM_DEV_MODE, staging only).
        """
        ...

    def buttons(self) -> Mapping[str, ButtonHandler]:
        """Handlers for buttons and submitted forms, by custom_id prefix."""
        ...

    def jobs(self, config: PluginConfig) -> tuple[Job, ...]:
        """Background jobs, given the plugin's settings."""
        ...

    async def setup(self, ctx: CommandContext) -> str | None:
        """A line for `/wgm setup` to show, or None."""
        ...
