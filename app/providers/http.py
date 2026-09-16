"""HTTP client helpers shared by provider adapters.

Adapters accept an ``httpx.Client`` so tests can inject a mocked transport.
"""

import httpx

from app.core.config import get_settings
from app.providers.errors import ProviderIntegrationError, ProviderTimeoutError


class ProviderHttpClient:
    """Thin wrapper around httpx that maps failures to safe provider errors."""

    def __init__(self, base_url: str, timeout: float | None = None):
        settings = get_settings()
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout if timeout is not None else settings.provider_http_timeout_seconds,
        )

    def close(self) -> None:
        self._client.close()

    def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                "PROVIDER_TIMEOUT", "The payment provider did not respond in time"
            ) from exc
        except httpx.HTTPError as exc:
            # httpx.ConnectError, transport errors, invalid responses, etc.
            raise ProviderIntegrationError(
                "PROVIDER_UNREACHABLE", "The payment provider could not be reached"
            ) from exc
        return response

    @staticmethod
    def close_all(clients: list["ProviderHttpClient"]) -> None:
        for client in clients:
            client.close()