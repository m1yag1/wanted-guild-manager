"""Discord interaction payloads, limited to the fields we use.

See https://discord.com/developers/docs/interactions/receiving-and-responding
"""

from enum import IntEnum, IntFlag

import msgspec


class InteractionType(IntEnum):
    """Kinds of interaction Discord sends."""

    PING = 1
    APPLICATION_COMMAND = 2
    MESSAGE_COMPONENT = 3
    APPLICATION_COMMAND_AUTOCOMPLETE = 4
    MODAL_SUBMIT = 5


class InteractionResponseType(IntEnum):
    """Kinds of answer we can send back."""

    PONG = 1
    CHANNEL_MESSAGE_WITH_SOURCE = 4


class MessageFlags(IntFlag):
    """Message flags we use."""

    EPHEMERAL = 64
    """Only the person who ran the command sees the reply."""


class InteractionOption(msgspec.Struct):
    """A chosen subcommand or option value."""

    name: str
    type: int
    options: list["InteractionOption"] = []


class InteractionData(msgspec.Struct):
    """What was used: a command (name, options) or a button (custom_id)."""

    name: str = ""
    options: list[InteractionOption] = []
    custom_id: str = ""


class Interaction(msgspec.Struct):
    """An incoming interaction. Unknown fields are ignored."""

    id: str
    application_id: str
    type: InteractionType
    token: str
    version: int
    data: InteractionData | None = None


class MessageData(msgspec.Struct, omit_defaults=True):
    """The message we reply with."""

    content: str
    flags: MessageFlags = MessageFlags(0)


class InteractionResponse(msgspec.Struct, omit_defaults=True):
    """Our answer to an interaction."""

    type: InteractionResponseType
    data: MessageData | None = None
