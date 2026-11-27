"""The /wgm slash command: its definition and how each subcommand answers.

The definition is what `inv discord.register-commands` sends to Discord.
See https://discord.com/developers/docs/interactions/application-commands
"""

from typing import Any

from wgm.domain.discord.schemas import (
    InteractionData,
    InteractionResponse,
    InteractionResponseType,
    MessageData,
    MessageFlags,
)

SUB_COMMAND = 1

HELP = {
    "help": "Show the commands you can use",
}

WGM_COMMAND: dict[str, Any] = {
    "name": "wgm",
    "type": 1,  # chat input (slash command)
    "description": "Wanted Guild event sign ups",
    "options": [
        {"type": SUB_COMMAND, "name": name, "description": description}
        for name, description in HELP.items()
    ],
}

COMMANDS = [WGM_COMMAND]


def private_reply(content: str) -> InteractionResponse:
    """A reply only the person who ran the command can see."""
    return InteractionResponse(
        type=InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
        data=MessageData(content=content, flags=MessageFlags.EPHEMERAL),
    )


def help_text() -> str:
    """The list of /wgm commands."""
    lines = [f"`/wgm {name}`: {description}" for name, description in HELP.items()]
    return "**Wanted Guild Manager**\n" + "\n".join(lines)


def run_command(data: InteractionData) -> InteractionResponse:
    """Answer a /wgm slash command."""
    subcommand = data.options[0].name if data.options else ""
    if data.name == "wgm" and subcommand == "help":
        return private_reply(help_text())
    return private_reply(f"Unknown command. {help_text()}")
