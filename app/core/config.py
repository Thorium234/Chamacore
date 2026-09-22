from base64 import b64encode
from decimal import Decimal
from functools import lru_cache
from hashlib import sha256

from pydantic_settings import BaseSettings, SettingsConfigDict

# Deterministic, clearly-labelled development-only credential master key. It
# is derived from a constant so local tests are reproducible. Production
# deployments MUST set CHAMACORE_CREDENTIAL_ENCRYPTION_KEY explicitly.
DEV_CREDENTIAL_MASTER = "chamacore-dev-only-credential-encryption-key"
DEV_CREDENTIAL_KEY_B64 = b64encode(
    sha256(DEV_CREDENTIAL_MASTER.encode()).digest()
).decode("ascii")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="CHAMACORE_", extra="ignore")

    app_name: str = "ChamaCore"
    # Development is the default; production deployments MUST set
    # CHAMACORE_DEBUG=false and a real CHAMACORE_JWT_SECRET_KEY.
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    # SQLite is used for development, PostgreSQL for production.
    database_url: str = "sqlite:///./chamacore.db"

    # JWT signing. The default secret is for local development only and
    # MUST be overridden in any deployed environment. Access tokens have a
    # short lifetime by default (120 minutes, production-readiness brief 3.1);
    # clients refresh them via POST /api/v1/auth/refresh.
    jwt_secret_key: str = "local-development-only-secret-change-me-in-prod"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 120
    refresh_token_expires_days: int = 30

    # Global share unit price in KES (ADR-005).
    share_unit_price: Decimal = Decimal("100")

    # V3 provider-credential encryption (ADR-017). The master key is a
    # Base64-encoded 32-byte value from the environment; in development a
    # deterministic dev key is substituted. Older key versions may be
    # supplied through CHAMACORE_CREDENTIAL_ENCRYPTION_KEYS as a JSON map
    # {"<version>": "<base64 key>"} so rotation never forces wholesale
    # re-entry of provider credentials.
    credential_encryption_key: str = ""
    credential_encryption_key_version: int = 1
    credential_encryption_keys: dict[str, str] = {}

    # Public base URL used to build provider callback URLs
    # (e.g. https://app.chamacore.example). Development default matches
    # the local uvicorn server.
    public_base_url: str = "http://localhost:8000"

    # Browser origins allowed to call the API from a frontend (CORS).
    # Comma-separated explicit origins ONLY — never "*" (allow_credentials
    # is enabled, so a wildcard origin would be rejected anyway). Server-to-
    # server callbacks (Daraja STK/C2B) are not subject to CORS.
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    # General API rate limits (report 2.4). The auth/register, auth/token and
    # member-link limits are strict by design; the general API limit guards the
    # rest of the router. All are single-process (in-memory) limiters.
    general_api_per_minute_limit: int = 300
    auth_register_per_minute_limit: int = 10
    auth_token_per_minute_limit: int = 30
    auth_member_link_per_minute_limit: int = 10

    # Webhook safety and provider behaviour limits (ADR-018).
    payment_webhook_max_body_bytes: int = 262144
    payment_event_raw_retention_days: int = 90
    provider_http_timeout_seconds: float = 15.0
    payment_attempt_max_retries: int = 2
    payment_initiate_daily_limit: int = 5000
    payment_validate_per_minute_limit: int = 5
    payment_webhook_per_minute_limit: int = 60

    # Prometheus /metrics protection (production-readiness brief 3.3).
    # In production (CHAMACORE_DEBUG=false) the endpoint is reachable only
    # with this shared secret via the X-Metrics-Token header; if it is left
    # empty the endpoint returns 404 so the scrape path is never public.
    # Local development keeps /metrics open when CHAMACORE_DEBUG=true.
    metrics_token: str = ""

    def model_post_init(self, __context) -> None:
        default_secret = "local-development-only-secret-change-me-in-prod"
        if not self.debug and self.jwt_secret_key == default_secret:
            raise ValueError(
                "CHAMACORE_JWT_SECRET_KEY must be set to a secure value "
                "when CHAMACORE_DEBUG is false (i.e. in production)"
            )
        if self.debug and not self.credential_encryption_key:
            # Local development: substitute a deterministic, clearly labelled
            # dev key so provider credentials can be encrypted out of the box.
            self.credential_encryption_key = DEV_CREDENTIAL_KEY_B64
        if not self.debug and (
            not self.credential_encryption_key
            or self.credential_encryption_key == DEV_CREDENTIAL_KEY_B64
        ):
            raise ValueError(
                "CHAMACORE_CREDENTIAL_ENCRYPTION_KEY must be set to a secure "
                "Base64-encoded 32-byte key when CHAMACORE_DEBUG is false "
                "(i.e. in production)"
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()