"""Production-build surface tests (brief 3.2, 3.3, 3.5).

Covers the behaviour differences of a non-debug application:
- interactive docs and the OpenAPI schema are not exposed
- minimal security headers are present
- /metrics requires the configured token and 404s otherwise
"""

from types import SimpleNamespace

import app.main as main
from fastapi.testclient import TestClient


def _prod_client() -> TestClient:
    return TestClient(main._make_app(debug=False))


def test_docs_disabled_in_production():
    with _prod_client() as c:
        assert c.get("/docs").status_code == 404
        assert c.get("/redoc").status_code == 404
        assert c.get("/openapi.json").status_code == 404
        assert c.get("/health").status_code == 200


def test_docs_enabled_in_debug(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_production_sends_security_headers():
    with _prod_client() as c:
        r = c.get("/health")
        assert r.status_code == 200
        assert r.headers["X-Content-Type-Options"] == "nosniff"
        assert r.headers["Referrer-Policy"] == "no-referrer"
        assert r.headers["Strict-Transport-Security"] == "max-age=63072000; includeSubDomains"


def test_debug_app_omits_security_headers(client):
    r = client.get("/health")
    assert "Strict-Transport-Security" not in r.headers
    assert "X-Content-Type-Options" not in r.headers


def test_metrics_requires_token_in_production(monkeypatch):
    monkeypatch.setattr(main.settings, "debug", False)
    monkeypatch.setattr(main.settings, "metrics_token", "metrics-secret")
    with _prod_client() as c:
        assert c.get("/metrics").status_code == 404
        assert c.get("/metrics", headers={"X-Metrics-Token": "wrong"}).status_code == 404
        r = c.get("/metrics", headers={"X-Metrics-Token": "metrics-secret"})
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/plain")


def test_metrics_stays_closed_when_token_unset_in_production(monkeypatch):
    monkeypatch.setattr(main.settings, "debug", False)
    monkeypatch.setattr(main.settings, "metrics_token", "")
    with _prod_client() as c:
        assert c.get("/metrics").status_code == 404
        assert c.get("/metrics", headers={"X-Metrics-Token": "anything"}).status_code == 404


def test_metrics_open_in_debug(monkeypatch, client):
    monkeypatch.setattr(main.settings, "debug", True)
    monkeypatch.setattr(main.settings, "metrics_token", "x")
    r = client.get("/metrics")
    assert r.status_code == 200