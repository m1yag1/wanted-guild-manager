"""Find the plugins WGM_PLUGINS turns on and check they can run."""

from collections.abc import Callable, Mapping
from importlib.metadata import entry_points
from typing import Any

from advanced_alchemy.extensions.litestar import SQLAlchemyAsyncConfig
from attrs import frozen

from wgm.domain.discord.client import DiscordClient
from wgm.domain.discord.context import ButtonHandler, Subcommand
from wgm.lib.settings import Settings
from wgm.plugins.spec import Job, JobContext, PluginConfig, WgmPlugin

ENTRY_POINTS = "wgm.plugins"
CORE_GROUPS = ("help", "setup", "config")
"""Names the core /wgm commands use, so no plugin may take them."""


class PluginError(RuntimeError):
    """The plugin settings can't work; the message says how to fix them."""


@frozen
class Plugins:
    """The plugins that are on, with their parsed settings."""

    items: tuple[WgmPlugin, ...] = ()
    config: Mapping[str, PluginConfig] = {}
    dev_mode: bool = False
    """Include each plugin's dev subcommands (staging only)."""

    @property
    def names(self) -> tuple[str, ...]:
        """The plugins that are on, in WGM_PLUGINS order."""
        return tuple(plugin.name for plugin in self.items)

    @property
    def subcommands(self) -> tuple[Subcommand, ...]:
        """Every plugin's subcommands, plugin by plugin, with dev ones in dev mode."""
        return tuple(
            sub
            for plugin in self.items
            for sub in plugin.subcommands()
            + (plugin.dev_subcommands() if self.dev_mode else ())
        )

    def button(self, prefix: str) -> ButtonHandler | None:
        """The handler for buttons whose custom_id starts with `prefix:`."""
        for plugin in self.items:
            handler = plugin.buttons().get(prefix)
            if handler is not None:
                return handler
        return None

    def jobs(
        self, db: SQLAlchemyAsyncConfig, discord: DiscordClient
    ) -> list[tuple[Job, JobContext]]:
        """Every plugin's background jobs, each with what its runs get."""
        return [
            (job, JobContext(db, discord, self.config[plugin.name]))
            for plugin in self.items
            for job in plugin.jobs(self.config[plugin.name])
        ]


def installed() -> dict[str, Callable[[], WgmPlugin]]:
    """Plugins installed through the `wgm.plugins` entry point group, by name."""
    return {point.name: point.load() for point in entry_points(group=ENTRY_POINTS)}


def _config(plugin: WgmPlugin, env: Mapping[str, str]) -> dict[str, Any]:
    config: dict[str, Any] = {}
    for spec in plugin.settings:
        name = spec.env_name(plugin.name)
        text = env.get(name, "").strip() or spec.default
        if text is None:
            raise PluginError(
                f"The {plugin.name} plugin needs {name}: {spec.description}"
            )
        try:
            config[spec.key] = spec.parse(text)
        except ValueError:
            raise PluginError(
                f"{name}={text!r} isn't valid. It should be {spec.description}"
            ) from None
    return config


def load_plugins(
    settings: Settings,
    available: Mapping[str, Callable[[], WgmPlugin]] | None = None,
) -> Plugins:
    """The plugins `settings.plugins` turns on, checked and configured.

    Args:
        settings: Names the plugins and holds the WGM_* variables they read.
        available: Plugin factories by name. Defaults to the installed ones.

    Raises:
        PluginError: A plugin isn't installed, uses a core command name, or is
            missing a setting.
    """
    available = installed() if available is None else available
    plugins: list[WgmPlugin] = []
    for name in settings.plugins:
        if name not in available:
            known = ", ".join(sorted(available)) or "none"
            raise PluginError(
                f"WGM_PLUGINS lists {name!r}, which isn't installed. "
                f"Installed plugins: {known}."
            )
        plugin = available[name]()
        if plugin.name in CORE_GROUPS:
            raise PluginError(f"A plugin can't be called {plugin.name!r}.")
        plugins.append(plugin)
    return Plugins(
        items=tuple(plugins),
        config={p.name: _config(p, settings.environ) for p in plugins},
        dev_mode=settings.dev_mode,
    )
