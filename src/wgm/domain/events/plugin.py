"""The event plugin: events, sign-up buttons, and locking posts at close."""

from collections.abc import Mapping

from wgm.domain.discord.context import ButtonHandler, CommandContext, Subcommand
from wgm.domain.events.buttons import press
from wgm.domain.events.closing import close_job
from wgm.domain.events.commands import SUBCOMMANDS, setup_line
from wgm.domain.events.seed import DEV_SUBCOMMANDS
from wgm.plugins.spec import Job, PluginConfig, SettingSpec


def _seconds(text: str) -> float:
    seconds = float(text)
    if seconds <= 0:
        raise ValueError(text)
    return seconds


class EventPlugin:
    """`/wgm event ...`, the sign-up buttons, and the close-lock job."""

    name = "event"
    settings: tuple[SettingSpec, ...] = (
        SettingSpec(
            "close_check_seconds",
            "how often to check for closed sign-ups, in seconds, such as 60",
            default="60",
            parse=_seconds,
        ),
    )

    def subcommands(self) -> tuple[Subcommand, ...]:
        """`/wgm event create`, `list`, `channel`, `close-time`, `settings`."""
        return SUBCOMMANDS

    def dev_subcommands(self) -> tuple[Subcommand, ...]:
        """`/wgm event seed`, to post test events."""
        return DEV_SUBCOMMANDS

    def buttons(self) -> Mapping[str, ButtonHandler]:
        """The sign-up buttons, `signup:<event id>:<choice>`."""
        return {"signup": press}

    def jobs(self, config: PluginConfig) -> tuple[Job, ...]:
        """Lock posts as their sign-ups close."""
        return (Job("lock closed posts", config["close_check_seconds"], close_job),)

    async def setup(self, ctx: CommandContext) -> str | None:
        """Point to the event channel, or check it."""
        return await setup_line(ctx)
