"""Structured logging, correlation IDs, /metrics, and general rate-limit tests."""

import io
import json
import logging

from app.api import deps
from app.core.ratelimit import RateLimiter


def test_request_id_header_echoed(client):
    r = client.get("/health", headers={"X-Request-ID": "corr-123"})
    assert r.status_code == 200
    assert r.headers["X-Request-ID"] == "corr-123"


def test_request_id_generated_when_absent(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers["X-Request-ID"]


def test_metrics_expose_http_metrics(client):
    client.get("/health")
    r = client.get("/metrics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert (
        'chamacore_http_requests_total{route="/health",method="GET",status="2xx"} 1'
        in r.text
    )
    assert "chamacore_http_request_duration_seconds_bucket" in r.text


def test_general_rate_limit_returns_429(client, monkeypatch):
    monkeypatch.setattr(deps, "_general_limiter", RateLimiter(3, 60.0))
    for _ in range(3):
        blocked = client.get("/api/v1/auth/me")
        assert blocked.status_code == 401
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 429
    assert r.json()["detail"]["code"] == "RATE_LIMITED"


def test_json_formatter_includes_request_id():
    from app.core.logging import (
        JsonFormatter,
        RequestIdFilter,
        reset_request_id,
        set_request_id,
    )

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())
    log = logging.getLogger("app.request")
    log.setLevel(logging.INFO)
    previous = log.handlers
    try:
        log.handlers = [handler]
        log.propagate = False
        token = set_request_id("req-123")
        try:
            log.info("hello")
        finally:
            reset_request_id(token)
    finally:
        log.handlers = previous
        log.propagate = True

    payload = json.loads(stream.getvalue().strip())
    assert payload["request_id"] == "req-123"
    assert payload["message"] == "hello"