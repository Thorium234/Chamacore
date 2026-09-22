"""CORS (frontend cross-origin) contract tests (production readiness report).

Browser SPAs talk to the API from a different origin; the API whitelists
explicit frontend origins via ``CHAMACORE_CORS_ORIGINS`` and never a "*"
(allow_credentials is enabled). Daraja STK/C2B callbacks are server-to-server
and not covered by CORS.
"""

from tests.conftest import create_chama, register_and_login

ALLOWED = ["http://localhost:3000", "http://localhost:5173"]


def _cors_headers(r) -> dict[str, str]:
    return {k.lower(): v for k, v in r.headers.items()}


class TestCors:
    def test_known_origin_is_echoed_on_get(self, client):
        for origin in ALLOWED:
            r = client.get("/health", headers={"Origin": origin})
            assert r.status_code == 200
            headers = _cors_headers(r)
            assert headers["access-control-allow-origin"] == origin
            assert headers["access-control-allow-credentials"] == "true"

    def test_preflight_allows_known_origin(self, client):
        r = client.options(
            "/api/v1/auth/token",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        assert r.status_code in (200, 204)
        headers = _cors_headers(r)
        assert headers["access-control-allow-origin"] == "http://localhost:5173"
        assert "POST" in headers["access-control-allow-methods"]
        assert headers["access-control-allow-credentials"] == "true"
        assert headers["access-control-allow-origin"] != "*"

    def test_disallowed_origin_gets_no_cors_headers(self, client):
        r = client.get("/health", headers={"Origin": "https://evil.example"})
        assert r.status_code == 200
        assert "access-control-allow-origin" not in _cors_headers(r)

    def test_disallowed_origin_preflight_is_rejected(self, client):
        r = client.options(
            "/api/v1/auth/token",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert "access-control-allow-origin" not in _cors_headers(r)

    def test_authenticated_request_cross_origin(self, client):
        headers = register_and_login(client, "cors@e.com")
        r = client.get("/api/v1/auth/me", headers={**headers, "Origin": "http://localhost:3000"})
        assert r.status_code == 200
        assert _cors_headers(r)["access-control-allow-origin"] == "http://localhost:3000"

    def test_express_request_id_header_is_exposed(self, client):
        r = client.get(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "X-Request-ID": "corr-from-browser",
            },
        )
        headers = _cors_headers(r)
        assert headers["access-control-expose-headers"] == "X-Request-ID"
        assert headers["x-request-id"] == "corr-from-browser"

    def test_chama_create_api_cross_origin(self, client):
        headers = register_and_login(client, "cors-create@e.com")
        chama = create_chama(client, headers)
        r = client.get(
            f"/api/v1/chamas/{chama['id']}",
            headers={**headers, "Origin": "http://localhost:5173"},
        )
        assert r.status_code == 200
        assert _cors_headers(r)["access-control-allow-origin"] == "http://localhost:5173"