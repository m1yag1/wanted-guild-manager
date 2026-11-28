"""Fixtures for Discord requests: a signing key, signed bodies and payloads."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from nacl.signing import SigningKey

from wgm.domain.events.roster import post_text

GUILD_ID = "1290000000000000000"
ADMIN_ROLE_ID = "900"
MANAGE_SERVER = str(1 << 5)

SignedRequest = tuple[bytes, dict[str, str]]
Sign = Callable[[bytes], SignedRequest]
LoadPayload = Callable[[str], bytes]


@pytest.fixture
def signing_key() -> SigningKey:
    """A throwaway key standing in for Discord's."""
    return SigningKey.generate()


@pytest.fixture
def discord_payload() -> LoadPayload:
    """Load a Discord interaction payload from `data/discord/<name>.json`."""
    folder = Path(__file__).parent / "data" / "discord"

    def load(name: str) -> bytes:
        return (folder / f"{name}.json").read_bytes()

    return load


@pytest.fixture
def sign(signing_key: SigningKey) -> Sign:
    """Sign a body the way Discord does and return it with its headers."""

    def sign_body(body: bytes) -> SignedRequest:
        timestamp = "1764170000"
        signature = signing_key.sign(timestamp.encode() + body).signature.hex()
        return body, {
            "content-type": "application/json",
            "x-signature-ed25519": signature,
            "x-signature-timestamp": timestamp,
        }

    return sign_body


MakeCommand = Callable[..., bytes]


@pytest.fixture
def wgm_command(discord_payload: LoadPayload) -> MakeCommand:
    """A /wgm interaction body for a subcommand path, such as `event create`.

    Keyword arguments become option values; `roles`, `permissions` and
    `in_server` shape the member who runs it.
    """

    def make(
        path: str,
        *,
        roles: tuple[str, ...] = (),
        permissions: str = "0",
        in_server: bool = True,
        nicks: dict[str, str] | None = None,
        **values: str | int,
    ) -> bytes:
        payload = json.loads(discord_payload("application_command"))
        options: list[dict[str, Any]] = [
            {"name": name, "type": 4 if isinstance(value, int) else 3, "value": value}
            for name, value in values.items()
        ]
        for name in reversed(path.split()):
            kind = 1 if not options or options[0]["type"] in (3, 4) else 2
            options = [{"name": name, "type": kind, "options": options}]
        payload["data"]["options"] = options
        if nicks:
            payload["data"]["resolved"] = {
                "users": {
                    uid: {"username": nick.lower()} for uid, nick in nicks.items()
                },
                "members": {uid: {"nick": nick} for uid, nick in nicks.items()},
            }
        payload["member"]["roles"] = list(roles)
        payload["member"]["permissions"] = permissions
        if not in_server:
            for key in ("guild_id", "member"):
                payload.pop(key)
            payload["user"] = {"id": "53908232506183680", "username": "mason"}
        return json.dumps(payload).encode()

    return make


MakeButton = Callable[..., bytes]


@pytest.fixture
def wgm_button(discord_payload: LoadPayload) -> MakeButton:
    """A button-press interaction body for a `custom_id`.

    `user_id` and `nick` describe who pressed it; `message_id` is the post.
    `values` makes it a dropdown pick instead.
    """

    def make(
        custom_id: str,
        *,
        user_id: str = "53908232506183680",
        nick: str | None = "Kael",
        message_id: str = "5550001",
        values: list[str] | None = None,
    ) -> bytes:
        payload = json.loads(discord_payload("message_component"))
        payload["data"]["custom_id"] = custom_id
        if values is not None:
            payload["data"]["component_type"] = 3  # a dropdown
            payload["data"]["values"] = values
        payload["member"]["user"]["id"] = user_id
        payload["member"]["nick"] = nick
        payload["message"] = {"id": message_id, "channel_id": "1290000000000000001"}
        return json.dumps(payload).encode()

    return make


MakeForm = Callable[..., bytes]


@pytest.fixture
def wgm_form(discord_payload: LoadPayload) -> MakeForm:
    """A submitted form (modal) body for a `custom_id`, with its reason field."""

    def make(custom_id: str, *, reason: str = "Working late") -> bytes:
        payload = json.loads(discord_payload("modal_submit"))
        payload["data"]["custom_id"] = custom_id
        payload["data"]["components"][0]["components"][0]["value"] = reason
        return json.dumps(payload).encode()

    return make


def post_buttons(message: dict[str, Any]) -> list[dict[str, Any]]:
    """The sign-up buttons inside an event post (a message or reply body)."""
    found: list[dict[str, Any]] = []

    def walk(components: list[dict[str, Any]]) -> None:
        for component in components:
            if component.get("type") == 2:  # noqa: PLR2004
                found.append(component)
            walk(component.get("components", []))

    walk(message.get("components") or [])
    return found


def post_words(message: dict[str, Any]) -> str:
    """All the text in an event post (a message or reply body)."""
    return post_text(message.get("components") or [])
