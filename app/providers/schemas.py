"""Provider credential input schemas (ADR-017).

These are provider-specific, use ``SecretStr`` for every secret, and are the
*only* acceptable client-facing credential shapes. Secrets are never
serialised back through response schemas.
"""

from pydantic import BaseModel, ConfigDict, SecretStr, field_validator

from app.models.enums import PaymentEnvironment, PaymentProviderCode


class PaymentCredentialsIn(BaseModel):
    provider_code: PaymentProviderCode
    environment: PaymentEnvironment
    credentials: "ProviderCredentials"


class JengaCredentialInput(BaseModel):
    """Jenga (Finserve Africa) merchant credentials."""

    model_config = ConfigDict(extra="forbid")

    api_key: SecretStr
    merchant_code: SecretStr
    consumer_secret: SecretStr
    signing_private_key: SecretStr | None = None

    @field_validator("*")
    @classmethod
    def _reject_blank(cls, value, info):
        if isinstance(value, SecretStr) and not value.get_secret_value():
            raise ValueError(f"{info.field_name} must not be empty")
        return value


class DarajaCredentialInput(BaseModel):
    """Safaricom Daraja STK Push credentials (sandbox or production)."""

    model_config = ConfigDict(extra="forbid")

    consumer_key: SecretStr
    consumer_secret: SecretStr
    short_code: SecretStr
    passkey: SecretStr

    @field_validator("*")
    @classmethod
    def _reject_blank(cls, value, info):
        if isinstance(value, SecretStr) and not value.get_secret_value():
            raise ValueError(f"{info.field_name} must not be empty")
        return value


ProviderCredentials = JengaCredentialInput | DarajaCredentialInput