import pytest
from litestar import Litestar
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_401_UNAUTHORIZED,
)
from litestar.testing import AsyncTestClient

from tests.fixtures.discord import LoadPayload, Sign
from tests.fixtures.discord_api import FakeDiscordApi

URL = "/discord/interactions"


@pytest.mark.anyio
async def test_answers_ping_with_pong(
    app: Litestar, sign: Sign, discord_payload: LoadPayload
) -> None:
    body, headers = sign(discord_payload("ping"))

    async with AsyncTestClient(app=app) as client:
        response = await client.post(URL, content=body, headers=headers)

    assert response.status_code == HTTP_200_OK
    assert response.json() == {"type": 1}


@pytest.mark.anyio
async def test_rejects_unsigned_requests(
    app: Litestar, discord_payload: LoadPayload
) -> None:
    async with AsyncTestClient(app=app) as client:
        response = await client.post(
            URL,
            content=discord_payload("ping"),
            headers={"content-type": "application/json"},
        )

    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.anyio
async def test_rejects_a_body_changed_after_signing(
    app: Litestar, sign: Sign, discord_payload: LoadPayload
) -> None:
    _, headers = sign(discord_payload("ping"))

    async with AsyncTestClient(app=app) as client:
        response = await client.post(
            URL, content=discord_payload("application_command"), headers=headers
        )

    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.anyio
async def test_slash_commands_answer_thinking_then_edit_in_the_reply(
    app: Litestar,
    sign: Sign,
    discord_payload: LoadPayload,
    discord_api: FakeDiscordApi,
) -> None:
    body, headers = sign(discord_payload("application_command"))

    async with AsyncTestClient(app=app) as client:
        response = await client.post(URL, content=body, headers=headers)

    assert response.json() == {"type": 5, "data": {"flags": 64}}
    edit = discord_api.requests[-1]
    assert (edit.method, edit.path) == (
        "PATCH",
        "/webhooks/1310000000000000000/fake-interaction-token/messages/@original",
    )
    assert "`/wgm help`" in edit.body["content"]
    assert edit.body["flags"] == 64


@pytest.mark.anyio
async def test_forms_go_to_the_plugin_that_owns_them(
    app: Litestar, sign: Sign, discord_payload: LoadPayload
) -> None:
    body, headers = sign(discord_payload("modal_submit"))

    async with AsyncTestClient(app=app) as client:
        response = await client.post(URL, content=body, headers=headers)

    assert response.json()["data"]["content"] == "That form isn't one of ours."
