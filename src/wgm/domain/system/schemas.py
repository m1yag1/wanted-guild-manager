"""Response bodies for system routes."""

import msgspec


class PingResponse(msgspec.Struct):
    """Body of a successful health check."""

    message: str
