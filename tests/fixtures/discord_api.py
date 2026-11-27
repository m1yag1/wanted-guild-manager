"""A small local stand-in for Discord's REST API, served over real HTTP."""

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest
from attrs import define, field


@define
class Request:
    """One request the fake API received."""

    method: str
    path: str
    authorization: str
    body: Any


@define
class FakeDiscordApi:
    """Records requests; answers from `responses` keyed by "METHOD path".

    Without a matching response it echoes the request body with status 200.
    """

    url: str = ""
    requests: list[Request] = field(factory=list)
    responses: dict[str, tuple[int, Any]] = field(factory=dict)


@pytest.fixture
def discord_api() -> Iterator[FakeDiscordApi]:
    """A fake Discord API on a random local port, at `discord_api.url`."""
    api = FakeDiscordApi()

    class Handler(BaseHTTPRequestHandler):
        def _handle(self) -> None:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else None
            api.requests.append(
                Request(
                    self.command,
                    self.path,
                    self.headers.get("Authorization", ""),
                    body,
                )
            )
            status, reply = api.responses.get(
                f"{self.command} {self.path}", (200, body or {})
            )
            payload = json.dumps(reply).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        do_GET = do_PUT = do_PATCH = _handle

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            """Keep test output quiet."""

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    api.url = f"http://127.0.0.1:{server.server_port}"
    yield api
    server.shutdown()
    server.server_close()
