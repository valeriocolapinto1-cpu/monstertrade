from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app


def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_secrets_are_masked() -> None:
    settings = Settings(twelve_data_api_key="segreto-di-prova")  # type: ignore[arg-type]
    assert "segreto-di-prova" not in repr(settings)
    assert "segreto-di-prova" not in str(settings.model_dump())
