import pytest
from litestar import Litestar
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
)
from litestar.testing import AsyncTestClient

from tests.fixtures.discord import LoadPayload, Sign

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
async def test_answers_wgm_help_privately(
    app: Litestar, sign: Sign, discord_payload: LoadPayload
) -> None:
    body, headers = sign(discord_payload("application_command"))

    async with AsyncTestClient(app=app) as client:
        response = await client.post(URL, content=body, headers=headers)

    assert response.status_code == HTTP_200_OK
    reply = response.json()
    assert reply["type"] == 4
    assert reply["data"]["flags"] == 64
    assert "`/wgm help`" in reply["data"]["content"]


@pytest.mark.anyio
async def test_unknown_subcommands_get_the_help_text(
    app: Litestar, sign: Sign, discord_payload: LoadPayload
) -> None:
    body, headers = sign(discord_payload("unknown_subcommand"))

    async with AsyncTestClient(app=app) as client:
        response = await client.post(URL, content=body, headers=headers)

    assert response.json()["data"]["content"].startswith("Unknown command.")


@pytest.mark.anyio
async def test_reports_interactions_it_does_not_handle_yet(
    app: Litestar, sign: Sign, discord_payload: LoadPayload
) -> None:
    body, headers = sign(discord_payload("message_component"))

    async with AsyncTestClient(app=app) as client:
        response = await client.post(URL, content=body, headers=headers)

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert "MESSAGE_COMPONENT" in response.json()["detail"]
