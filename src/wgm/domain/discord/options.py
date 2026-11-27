"""Building blocks for slash command options.

See https://discord.com/developers/docs/interactions/application-commands
"""

from typing import Any

SUB_COMMAND = 1
SUB_COMMAND_GROUP = 2
STRING = 3
INTEGER = 4
CHANNEL = 7
TEXT_CHANNEL = 0


def text(name: str, description: str, **extra: Any) -> dict[str, Any]:
    """A required text option."""
    return {
        "type": STRING,
        "name": name,
        "description": description,
        "required": True,
        **extra,
    }


def choice(name: str, description: str, values: tuple[str, ...]) -> dict[str, Any]:
    """A required option picked from a list."""
    return text(name, description, choices=[{"name": v, "value": v} for v in values])


def integer(
    name: str, description: str, *, required: bool, low: int, high: int
) -> dict[str, Any]:
    """A whole number between `low` and `high`."""
    return {
        "type": INTEGER,
        "name": name,
        "description": description,
        "required": required,
        "min_value": low,
        "max_value": high,
    }
