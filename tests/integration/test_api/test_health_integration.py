from fastapi.testclient import TestClient
from app.main import app
from app.config.settings import settings


def test_health_endpoint_returns_service_metadata():
    """Ensure the health endpoint exposes service metadata via the FastAPI router."""
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "healthy"
    assert payload["service"] == settings.SERVICE_NAME
    assert payload["version"] == settings.SERVICE_VERSION
    assert "timestamp" in payload and payload["timestamp"]
