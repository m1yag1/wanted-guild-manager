"""Fixtures for Discord requests: a signing key, signed bodies and payloads."""

from collections.abc import Callable
from pathlib import Path

import pytest
from nacl.signing import SigningKey

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
