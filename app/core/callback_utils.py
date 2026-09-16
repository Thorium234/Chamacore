"""Per-connection callback token derivation and canonical hash helpers.

The callback token is a deterministic HMAC derived from the credential master
key and connection identity. It is never stored; it can be regenerated for
each payment attempt so provider callback URLs carry a capability that only
the owner of the master key can produce. Secrets still never enter logs.
"""

import hashlib
import hmac
import json
import uuid

from app.core.config import get_settings
from app.models.enums import PaymentEnvironment, PaymentProviderCode

CALLBACK_NONCE_PREFIX = b"chamacore-callback-token-v1"


def connection_callback_token(
    *,
    connection_id: uuid.UUID,
    provider_code: PaymentProviderCode,
    environment: PaymentEnvironment,
) -> str:
    """Derive the callback capability token for a connection."""
    settings = get_settings()
    message = "|".join(
        [
            "chamacore-v1",
            str(connection_id),
            provider_code.value,
            environment.value,
        ]
    ).encode("utf-8")
    digest = hmac.new(
        settings.credential_encryption_key.encode("ascii"),
        CALLBACK_NONCE_PREFIX + message,
        hashlib.sha256,
    ).digest()
    return digest.hex()[:32]


def constant_time_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def payload_hash(raw_payload: bytes) -> str:
    return hashlib.sha256(raw_payload).hexdigest()


def canonical_payload_hash(*, membership_id: uuid.UUID, amount: str, currency: str, purpose: str) -> str:
    """Hash of a client idempotency payload.

    Currency is upper-cased and the amount is passed as a canonical decimal
    string so an identical business request always hashes identically.
    """
    canonical = json.dumps(
        {
            "membership_id": str(membership_id),
            "amount": f"{amount}",
            "currency": currency.upper(),
            "purpose": purpose,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()