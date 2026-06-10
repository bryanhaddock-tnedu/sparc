import json

from fastapi.testclient import TestClient

from app import main


def test_app_version_is_available_without_cache():
    response = TestClient(main.app).get("/api/app-version")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate, max-age=0"
    assert response.json()["version"]


def test_app_version_uses_packaged_static_version_when_build_version_is_local(tmp_path, monkeypatch):
    version_file = tmp_path / "app-version.json"
    version_file.write_text(json.dumps({"version": "0.1.1"}), encoding="utf-8")

    monkeypatch.setattr(main, "STATIC_VERSION_FILE", version_file)
    monkeypatch.setattr(main.settings, "build_version", "local")

    response = TestClient(main.app).get("/api/app-version")

    assert response.status_code == 200
    assert response.json()["version"] == "0.1.1"
