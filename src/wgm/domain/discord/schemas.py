"""Discord interaction payloads, limited to the fields we use.

See https://discord.com/developers/docs/interactions/receiving-and-responding
"""

from enum import IntEnum, IntFlag
from typing import Any

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
    DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE = 5
    """Shows "thinking..." until we edit the reply in."""
    UPDATE_MESSAGE = 7
    """Edit the message whose button was pressed."""
    APPLICATION_COMMAND_AUTOCOMPLETE_RESULT = 8
    """Suggestions for the option being typed."""


class MessageFlags(IntFlag):
    """Message flags we use."""

    EPHEMERAL = 64
    """Only the person who ran the command sees the reply."""


class InteractionOption(msgspec.Struct):
    """A chosen subcommand, group, or option value."""

    name: str
    type: int
    value: str | int | float | bool | None = None
    options: list["InteractionOption"] = []
    focused: bool = False
    """Set on the option being typed, when asking for suggestions."""


class InteractionData(msgspec.Struct):
    """What was used: a command (name, options) or a button (custom_id)."""

    name: str = ""
    options: list[InteractionOption] = []
    custom_id: str = ""


class User(msgspec.Struct):
    """A Discord user."""

    id: str
    username: str = ""
    global_name: str | None = None


class Member(msgspec.Struct):
    """The user as a member of the server the command ran in."""

    user: User
    roles: list[str] = []
    """Role IDs."""
    permissions: str = "0"
    """The member's computed permissions in the channel, as a bit string."""
    nick: str | None = None


class Message(msgspec.Struct):
    """The message a button belongs to."""

    id: str
    channel_id: str = ""


class Interaction(msgspec.Struct):
    """An incoming interaction. Unknown fields are ignored."""

    id: str
    application_id: str
    type: InteractionType
    token: str
    version: int
    data: InteractionData | None = None
    guild_id: str | None = None
    channel_id: str | None = None
    member: Member | None = None
    message: Message | None = None


class MessageData(msgspec.Struct, omit_defaults=True):
    """The message we reply with."""

    content: str = ""
    flags: MessageFlags = MessageFlags(0)
    components: list[dict[str, Any]] | None = None
    allowed_mentions: dict[str, list[str]] | None = None
    """Set to {"parse": []} so names in a post never ping anyone."""


class InteractionResponse(msgspec.Struct, omit_defaults=True):
    """Our answer to an interaction."""

    type: InteractionResponseType
    data: MessageData | None = None


class Choice(msgspec.Struct):
    """One suggestion: what the member sees, and the value sent if picked."""

    name: str
    value: str


class ChoicesData(msgspec.Struct):
    """Up to 25 suggestions."""

    choices: list[Choice]


class AutocompleteResponse(msgspec.Struct):
    """Our answer while a member types an option that has suggestions."""

    data: ChoicesData
    type: InteractionResponseType = (
        InteractionResponseType.APPLICATION_COMMAND_AUTOCOMPLETE_RESULT
    )
