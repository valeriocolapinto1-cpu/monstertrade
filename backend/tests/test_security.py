from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings


@pytest.fixture
def make_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[object]:
    def build(**env: str) -> TestClient:
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        get_settings.cache_clear()
        from app.main import create_app

        return TestClient(create_app())

    yield build
    get_settings.cache_clear()


def test_production_without_secret_refuses_everything(make_client) -> None:  # type: ignore[no-untyped-def]
    client = make_client(ENVIRONMENT="production")
    assert client.get("/health").status_code == 200
    assert client.get("/api/today").status_code == 503
    assert client.get("/docs").status_code == 404


def test_shared_secret_required(make_client) -> None:  # type: ignore[no-untyped-def]
    secret = "-".join(["segreto", "condiviso", "di", "prova"])
    client = make_client(ENVIRONMENT="production", API_SHARED_SECRET=secret)
    assert client.get("/api/broker/portfolio").status_code == 401
    assert client.get("/api/signals", headers={"X-API-Key": "sbagliato"}).status_code == 401
    ok = client.get("/api/broker/portfolio", headers={"X-API-Key": secret})
    assert ok.status_code == 200
    assert ok.json() == {"configured": False}


def test_no_write_methods_exposed(make_client) -> None:  # type: ignore[no-untyped-def]
    client = make_client(ENVIRONMENT="development")
    for path in ("/api/today", "/api/broker/portfolio", "/api/journal"):
        assert client.post(path).status_code == 405
        assert client.delete(path).status_code == 405
