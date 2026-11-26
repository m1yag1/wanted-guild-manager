from litestar.status_codes import HTTP_200_OK
from litestar.testing import TestClient

from wgm.app import app


def test_ping_returns_pong() -> None:
    with TestClient(app=app) as client:
        response = client.get("/ping")

    assert response.status_code == HTTP_200_OK
    assert response.json() == {"message": "pong!"}
