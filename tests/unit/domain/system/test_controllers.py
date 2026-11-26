import pytest
from litestar import Litestar
from litestar.status_codes import HTTP_200_OK
from litestar.testing import AsyncTestClient


@pytest.mark.anyio
async def test_ping_returns_pong(app: Litestar) -> None:
    async with AsyncTestClient(app=app) as client:
        response = await client.get("/ping")

    assert response.status_code == HTTP_200_OK
    assert response.json() == {"message": "pong!"}
