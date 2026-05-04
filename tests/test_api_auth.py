"""Optional LLMS_GEN_API_KEY gate on /api routes."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_monitored_list_without_api_key_ok(monkeypatch):
    monkeypatch.delenv("LLMS_GEN_API_KEY", raising=False)
    from llms_gen.config import get_settings
    from llms_gen.main import app

    get_settings.cache_clear()
    with TestClient(app) as client:
        r = client.get("/api/monitored-sites")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_monitored_list_401_when_key_set_missing_header(monkeypatch):
    monkeypatch.setenv("LLMS_GEN_API_KEY", "only-operators")
    from llms_gen.config import get_settings
    from llms_gen.main import app

    get_settings.cache_clear()
    with TestClient(app) as client:
        r = client.get("/api/monitored-sites")
    assert r.status_code == 401


def test_monitored_list_ok_with_header(monkeypatch):
    monkeypatch.setenv("LLMS_GEN_API_KEY", "only-operators")
    from llms_gen.config import get_settings
    from llms_gen.main import app

    get_settings.cache_clear()
    with TestClient(app) as client:
        r = client.get(
            "/api/monitored-sites", headers={"X-LLMS-GEN-API-Key": "only-operators"}
        )
    assert r.status_code == 200


def test_monitored_list_ok_with_bearer(monkeypatch):
    monkeypatch.setenv("LLMS_GEN_API_KEY", "secret-token")
    from llms_gen.config import get_settings
    from llms_gen.main import app

    get_settings.cache_clear()
    with TestClient(app) as client:
        r = client.get(
            "/api/monitored-sites",
            headers={"Authorization": "Bearer secret-token"},
        )
    assert r.status_code == 200


def test_health_never_requires_api_key(monkeypatch):
    monkeypatch.setenv("LLMS_GEN_API_KEY", "locked-down")
    from llms_gen.config import get_settings
    from llms_gen.main import app

    get_settings.cache_clear()
    with TestClient(app) as client:
        r = client.get("/health")
    assert r.status_code == 200
