"""Plugins: each area of /wgm, such as events, is one plugin. See ADR 0013."""

from wgm.plugins.loader import PluginError, Plugins, installed, load_plugins
from wgm.plugins.spec import Job, JobContext, PluginConfig, SettingSpec, WgmPlugin

__all__ = [
    "Job",
    "JobContext",
    "PluginConfig",
    "PluginError",
    "Plugins",
    "SettingSpec",
    "WgmPlugin",
    "installed",
    "load_plugins",
]
