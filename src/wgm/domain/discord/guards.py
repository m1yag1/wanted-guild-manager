"""Guards for Discord routes."""

from typing import Any

from litestar import Request
from litestar.connection import ASGIConnection
from litestar.exceptions import NotAuthorizedException
from litestar.handlers.base import BaseRouteHandler

from wgm.domain.discord.signatures import is_valid_signature
from wgm.lib.settings import Settings

SIGNATURE_HEADER = "x-signature-ed25519"
TIMESTAMP_HEADER = "x-signature-timestamp"


async def require_discord_signature(
    connection: ASGIConnection[Any, Any, Any, Any], _: BaseRouteHandler
) -> None:
    """Reject any request that Discord did not sign.

    Raises:
        NotAuthorizedException: The signature is missing or does not match.
    """
    settings: Settings = connection.app.state.settings
    request: Request[Any, Any, Any] = Request(connection.scope, connection.receive)
    signature = connection.headers.get(SIGNATURE_HEADER, "")
    timestamp = connection.headers.get(TIMESTAMP_HEADER, "")
    body = await request.body()
    if not is_valid_signature(
        public_key=settings.discord.public_key,
        signature=signature,
        timestamp=timestamp,
        body=body,
    ):
        raise NotAuthorizedException("Invalid request signature")
