from fastapi.testclient import TestClient

from app.main import app


def test_app_version_is_available_without_cache():
    response = TestClient(app).get("/api/app-version")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate, max-age=0"
    assert response.json()["version"]
