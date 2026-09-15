from decimal import Decimal
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    # MUST be overridden in any deployed environment.
    jwt_secret_key: str = "local-development-only-secret-change-me-in-prod"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 24

    # Global share unit price in KES (ADR-005).
    share_unit_price: Decimal = Decimal("100")

    def model_post_init(self, __context) -> None:
        default_secret = "local-development-only-secret-change-me-in-prod"
        if not self.debug and self.jwt_secret_key == default_secret:
            raise ValueError(
                "CHAMACORE_JWT_SECRET_KEY must be set to a secure value "
                "when CHAMACORE_DEBUG is false (i.e. in production)"
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()