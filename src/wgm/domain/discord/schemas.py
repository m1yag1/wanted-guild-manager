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
    MODAL = 9
    """Open a small form."""


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


class FormField(msgspec.Struct):
    """A text field in a submitted form, or the row holding it."""

    type: int
    custom_id: str = ""
    value: str = ""
    components: list["FormField"] = []


class ResolvedUser(msgspec.Struct):
    """A user picked in a user option."""

    username: str = ""
    global_name: str | None = None


class ResolvedMember(msgspec.Struct):
    """A picked user's membership in the server."""

    nick: str | None = None


class Resolved(msgspec.Struct):
    """Details of users picked in options, by user ID."""

    users: dict[str, ResolvedUser] = {}
    members: dict[str, ResolvedMember] = {}

    def name(self, user_id: str) -> str:
        """Server nickname, else display name, else username."""
        user = self.users.get(user_id, ResolvedUser())
        nick = self.members.get(user_id, ResolvedMember()).nick
        return nick or user.global_name or user.username or user_id


class InteractionData(msgspec.Struct):
    """What was used: a command (name, options), a button or a form (custom_id)."""

    name: str = ""
    options: list[InteractionOption] = []
    custom_id: str = ""
    components: list[FormField] = []
    """A submitted form's rows of fields."""
    resolved: Resolved = msgspec.field(default_factory=Resolved)
    values: list[str] = []
    """What was picked in a dropdown."""

    def field(self, custom_id: str) -> str:
        """The text typed in a submitted form's field, or ""."""
        for row in self.components:
            for item in row.components:
                if item.custom_id == custom_id:
                    return item.value
        return ""


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


class ModalData(msgspec.Struct):
    """A form: its id, title and rows of text fields."""

    custom_id: str
    title: str
    components: list[dict[str, Any]]


class ModalResponse(msgspec.Struct):
    """Our answer when a press should open a form."""

    data: ModalData
    type: InteractionResponseType = InteractionResponseType.MODAL
