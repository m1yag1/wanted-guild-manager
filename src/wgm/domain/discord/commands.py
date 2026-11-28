"""The /wgm slash command: the core subcommands, and answering any subcommand.

Plugins add the rest (ADR 0013). The definition built here is what
`inv discord.register-commands` sends to Discord.
See https://discord.com/developers/docs/interactions/application-commands
"""

from typing import Any

from wgm.domain.discord.context import (
    CommandContext,
    Subcommand,
    private_reply,
)
from wgm.domain.discord.options import SUB_COMMAND, SUB_COMMAND_GROUP
from wgm.domain.discord.permissions import ADMIN_ROLE, WGM_ROLES, may_run
from wgm.domain.discord.schemas import (
    AutocompleteResponse,
    Choice,
    ChoicesData,
    InteractionOption,
    InteractionResponse,
    InteractionType,
    ModalResponse,
)
from wgm.plugins import Plugins


async def _help(ctx: CommandContext, values: dict[str, Any]) -> InteractionResponse:
    return private_reply(await help_text(ctx))


async def _setup(ctx: CommandContext, values: dict[str, Any]) -> InteractionResponse:
    existing = await ctx.discord.role_ids(ctx.guild_id)
    created = [name for name in WGM_ROLES if name not in existing]
    for name in created:
        await ctx.discord.create_role(ctx.guild_id, name)
    lines = [
        f"Created {', '.join(created)}. Give it to the members who run events."
        if created
        else "All WGM roles already exist."
    ]
    steps = [await plugin.setup(ctx) for plugin in ctx.plugins.items]
    lines += [step for step in steps if step]
    return private_reply("\n\n".join(lines))


async def _config_show(
    ctx: CommandContext, values: dict[str, Any]
) -> InteractionResponse:
    groups = "\n".join(
        f"`/wgm {name} settings`"
        for name in ctx.plugins.names
        if any(sub.path == (name, "settings") for sub in ctx.plugins.subcommands)
    )
    return private_reply(
        f"**Server settings**\nTime zone: {ctx.settings.timezone}\n"
        f"Plugins: {', '.join(ctx.plugins.names) or 'none'}\n{groups}".rstrip()
    )


CORE = (
    Subcommand(("help",), "Show the commands you can use", _help, server_only=False),
    Subcommand(("setup",), f"Create the {ADMIN_ROLE} role", _setup, (ADMIN_ROLE,)),
    Subcommand(
        ("config", "show"), "Show server-wide settings", _config_show, (ADMIN_ROLE,)
    ),
)


def all_subcommands(plugins: Plugins) -> tuple[Subcommand, ...]:
    """The core subcommands, then each plugin's."""
    return CORE + plugins.subcommands


def wgm_command(plugins: Plugins) -> dict[str, Any]:
    """The /wgm definition, with each group (such as `event`) holding its own."""
    options: list[dict[str, Any]] = []
    groups: dict[str, dict[str, Any]] = {}
    for sub in all_subcommands(plugins):
        leaf = {
            "type": SUB_COMMAND,
            "name": sub.path[-1],
            "description": sub.description,
            "options": sub.options,
        }
        if len(sub.path) == 1:
            options.append(leaf)
            continue
        group = groups.get(sub.path[0])
        if group is None:
            group = {
                "type": SUB_COMMAND_GROUP,
                "name": sub.path[0],
                "description": f"{sub.path[0].title()} commands",
                "options": [],
            }
            groups[sub.path[0]] = group
            options.append(group)
        group["options"].append(leaf)
    return {
        "name": "wgm",
        "type": 1,
        "description": "Wanted Guild event sign ups",
        "options": options,
    }


def _leaf(
    options: list[InteractionOption],
) -> tuple[tuple[str, ...], list[InteractionOption]]:
    path: list[str] = []
    while options and options[0].type in (SUB_COMMAND, SUB_COMMAND_GROUP):
        path.append(options[0].name)
        options = options[0].options
    return tuple(path), options


def selected(
    options: list[InteractionOption],
) -> tuple[tuple[str, ...], dict[str, Any]]:
    """The chosen subcommand path and its option values."""
    path, leaf = _leaf(options)
    return path, {option.name: option.value for option in leaf}


async def _role_ids(ctx: CommandContext) -> dict[str, str]:
    if not ctx.interaction.guild_id:
        return {}
    return await ctx.discord.role_ids(ctx.interaction.guild_id)


def _allowed(sub: Subcommand, ctx: CommandContext, role_ids: dict[str, str]) -> bool:
    member = ctx.interaction.member
    if member is None:
        return not sub.allowed_roles
    return may_run(sub.allowed_roles, member.roles, member.permissions, role_ids)


async def help_text(ctx: CommandContext) -> str:
    """The /wgm commands this member may use."""
    subcommands = all_subcommands(ctx.plugins)
    restricted = any(sub.allowed_roles for sub in subcommands)
    role_ids = await _role_ids(ctx) if restricted else {}
    lines = [
        f"`{sub.usage}`: {sub.description}"
        for sub in subcommands
        if _allowed(sub, ctx, role_ids)
    ]
    return "**Wanted Guild Manager**\n" + "\n".join(lines)


async def run_command(ctx: CommandContext) -> InteractionResponse:
    """Answer a /wgm slash command."""
    data = ctx.interaction.data
    path, values = selected(data.options if data else [])
    by_path = {sub.path: sub for sub in all_subcommands(ctx.plugins)}
    sub = by_path.get(path) if data and data.name == "wgm" else None
    if sub is None:
        return private_reply(f"Unknown command. {await help_text(ctx)}")
    if sub.server_only and not (ctx.interaction.guild_id and ctx.interaction.member):
        return private_reply("Run this in a server.")
    if sub.allowed_roles and not _allowed(sub, ctx, await _role_ids(ctx)):
        roles = " or ".join(sub.allowed_roles)
        return private_reply(f"You need the {roles} role to use `{sub.usage}`.")
    return await sub.handler(ctx, values)


MAX_CHOICES = 25
"""Discord shows at most 25 suggestions."""


async def suggest(ctx: CommandContext) -> AutocompleteResponse:
    """Suggestions for the option a member is typing, such as which event."""
    data = ctx.interaction.data
    path, leaf = _leaf(data.options if data else [])
    sub = {sub.path: sub for sub in all_subcommands(ctx.plugins)}.get(path)
    focused = next((option for option in leaf if option.focused), None)
    pairs: list[tuple[str, str]] = []
    if sub and sub.suggest and focused and ctx.interaction.guild_id:
        pairs = await sub.suggest(ctx, focused.name, str(focused.value or ""))
    return AutocompleteResponse(
        ChoicesData([Choice(name[:100], value) for name, value in pairs[:MAX_CHOICES]])
    )


async def press_button(ctx: CommandContext) -> InteractionResponse | ModalResponse:
    """Answer a button press or form with the plugin owning its custom_id prefix."""
    data = ctx.interaction.data
    custom_id = data.custom_id if data else ""
    handler = ctx.plugins.button(custom_id.split(":")[0])
    if handler is None:
        kind = (
            "form" if ctx.interaction.type is InteractionType.MODAL_SUBMIT else "button"
        )
        return private_reply(f"That {kind} isn't one of ours.")
    return await handler(ctx)
