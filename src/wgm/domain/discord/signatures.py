"""Verify that a request really comes from Discord.

Discord signs every interaction with Ed25519 over the timestamp header
followed by the raw body.
See https://discord.com/developers/docs/interactions/overview#setting-up-an-endpoint
"""

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey


def is_valid_signature(
    *, public_key: str, signature: str, timestamp: str, body: bytes
) -> bool:
    """Check a Discord request signature.

    Args:
        public_key: The application's hex-encoded public key.
        signature: The `X-Signature-Ed25519` header (hex).
        timestamp: The `X-Signature-Timestamp` header.
        body: The raw request body.

    Returns:
        True when the signature matches, False for any bad or malformed input.
    """
    try:
        VerifyKey(bytes.fromhex(public_key)).verify(
            timestamp.encode() + body, bytes.fromhex(signature)
        )
    except (BadSignatureError, ValueError):
        return False
    return True
