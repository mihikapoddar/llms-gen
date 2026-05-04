"""Optional LLMS_GEN_API_KEY on monitor-admin routes only (not jobs or POST register)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

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


def test_job_poll_public_when_api_key_set(monkeypatch):
    monkeypatch.setenv("LLMS_GEN_API_KEY", "secret")
    from llms_gen.config import get_settings
    from llms_gen.main import app

    get_settings.cache_clear()
    with TestClient(app) as client:
        r = client.get("/api/jobs/00000000-0000-4000-8000-000000000000")
    assert r.status_code == 404


def test_post_job_public_when_api_key_set(monkeypatch):
    monkeypatch.setenv("LLMS_GEN_API_KEY", "secret")
    from llms_gen.config import get_settings
    from llms_gen.main import app

    get_settings.cache_clear()
    with patch(
        "llms_gen.api.routes.jobs.run_job_in_background", new=AsyncMock()
    ):
        with TestClient(app) as client:
            r = client.post(
                "/api/jobs",
                json={"url": "https://example.com"},
            )
    assert r.status_code == 202


def test_post_monitored_public_when_api_key_set(monkeypatch):
    monkeypatch.setenv("LLMS_GEN_API_KEY", "secret")
    from llms_gen.config import get_settings
    from llms_gen.main import app

    get_settings.cache_clear()
    url = f"https://auth-test-{uuid.uuid4().hex}.example.com/"
    with TestClient(app) as client:
        r = client.post(
            "/api/monitored-sites",
            json={"url": url, "interval_hours": 24},
        )
    assert r.status_code == 201


def test_refresh_monitored_requires_api_key(monkeypatch):
    monkeypatch.setenv("LLMS_GEN_API_KEY", "secret")
    from llms_gen.config import get_settings
    from llms_gen.main import app

    get_settings.cache_clear()
    url = f"https://refresh-auth-{uuid.uuid4().hex}.example.com/"
    with TestClient(app) as client:
        create = client.post(
            "/api/monitored-sites",
            json={"url": url, "interval_hours": 24},
        )
        assert create.status_code == 201
        site_id = create.json()["id"]
        r = client.post(f"/api/monitored-sites/{site_id}/refresh")
    assert r.status_code == 401
