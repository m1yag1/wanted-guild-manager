"""Discord interaction payloads, limited to the fields we use.

See https://discord.com/developers/docs/interactions/receiving-and-responding
"""

from enum import IntEnum

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


class Interaction(msgspec.Struct):
    """An incoming interaction. Unknown fields are ignored."""

    id: str
    application_id: str
    type: InteractionType
    token: str
    version: int


class InteractionResponse(msgspec.Struct, omit_defaults=True):
    """Our answer to an interaction."""

    type: InteractionResponseType
