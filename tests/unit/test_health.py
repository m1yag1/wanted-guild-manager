import pytest
from litestar.status_codes import HTTP_200_OK
from litestar.testing import AsyncTestClient

from wgm.app import create_app


@pytest.mark.anyio
async def test_ping_returns_pong() -> None:
    async with AsyncTestClient(app=create_app()) as client:
        response = await client.get("/ping")

    assert response.status_code == HTTP_200_OK
    assert response.json() == {"message": "pong!"}
