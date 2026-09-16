"""Authenticated encryption for provider credentials (ADR-017).

Credentials are sealed with AES-256-GCM using a random 12-byte nonce per
record. The associated data (AAD) binds the ciphertext to its owning Chama,
provider, environment, and credential version so a blob cannot be replayed
against another record.

The master key comes from ``CHAMACORE_CREDENTIAL_ENCRYPTION_KEY`` (a
Base64-encoded 32-byte value). Older key versions are provided through
``CHAMACORE_CREDENTIAL_ENCRYPTION_KEYS``, a JSON map of version to key, so a
key rotation does not force all providers to be re-entered at once: previously
sealed blobs remain decryptable through their recorded key version and are
re-sealed lazily when the connection is next updated.
"""

import base64
import json
import os
import uuid
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings
from app.models.enums import PaymentEnvironment, PaymentProviderCode

AAD_VERSION = 1
CIPHER_VERSION = 1
NONCE_BYTES = 12


class CredentialCipherError(Exception):
    """Raised when a credential blob cannot be sealed or opened.

    The message never contains key material, ciphertext, or provider secrets.
    """


class CredentialCipher:
    """Seals and opens provider credential payloads with AES-256-GCM."""

    def __init__(self, settings=None):
        self._settings = settings or get_settings()

    def _current_key(self) -> bytes:
        key = self._settings.credential_encryption_key
        try:
            decoded = base64.b64decode(key, validate=True)
        except (ValueError, TypeError) as exc:
            raise CredentialCipherError("credential master key is not valid Base64") from exc
        if len(decoded) != 32:
            raise CredentialCipherError("credential master key must decode to 32 bytes")
        return decoded

    def _key_for_version(self, key_version: int) -> bytes:
        if key_version == self._settings.credential_encryption_key_version:
            return self._current_key()
        raw = self._settings.credential_encryption_keys.get(str(key_version))
        if raw is None:
            raise CredentialCipherError(
                f"no decryption key available for credential key version {key_version}"
            )
        try:
            decoded = base64.b64decode(raw, validate=True)
        except (ValueError, TypeError) as exc:
            raise CredentialCipherError(
                f"credential key version {key_version} is not valid Base64"
            ) from exc
        if len(decoded) != 32:
            raise CredentialCipherError(
                f"credential key version {key_version} must decode to 32 bytes"
            )
        return decoded

    @staticmethod
    def build_aad(
        *,
        chama_id: uuid.UUID,
        provider_code: PaymentProviderCode,
        environment: PaymentEnvironment,
        credential_version: int,
        connection_id: uuid.UUID,
    ) -> bytes:
        """Build canonical associated data (ADR-017)."""
        parts = [
            "chamacore-v1",
            str(connection_id),
            str(chama_id),
            provider_code.value,
            environment.value,
            str(credential_version),
        ]
        return "|".join(parts).encode("utf-8")

    def seal(
        self,
        payload: dict[str, Any],
        *,
        chama_id: uuid.UUID,
        provider_code: PaymentProviderCode,
        environment: PaymentEnvironment,
        credential_version: int,
        connection_id: uuid.UUID,
    ) -> str:
        """Encrypt a canonical JSON payload into a versioned envelope string."""
        key = self._current_key()
        nonce = os.urandom(NONCE_BYTES)
        aad = self.build_aad(
            chama_id=chama_id,
            provider_code=provider_code,
            environment=environment,
            credential_version=credential_version,
            connection_id=connection_id,
        )
        plaintext = json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad)
        envelope = {
            "cv": CIPHER_VERSION,
            "kv": self._settings.credential_encryption_key_version,
            "n": base64.b64encode(nonce).decode("ascii"),
            "c": base64.b64encode(ciphertext).decode("ascii"),
        }
        return json.dumps(envelope, sort_keys=True, separators=(",", ":"))

    def open(
        self,
        blob: str,
        *,
        chama_id: uuid.UUID,
        provider_code: PaymentProviderCode,
        environment: PaymentEnvironment,
        credential_version: int,
        connection_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Decrypt a sealed envelope and return the canonical credential map.

        Raises :class:`CredentialCipherError` on any malformed or
        unauthenticated envelope. The plaintext is intentionally not exposed
        in the error message.
        """
        try:
            envelope = json.loads(blob)
            key_version = int(envelope["kv"])
            nonce = base64.b64decode(envelope["n"], validate=True)
            ciphertext = base64.b64decode(envelope["c"], validate=True)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise CredentialCipherError("credential envelope is malformed") from exc

        if len(nonce) != NONCE_BYTES:
            raise CredentialCipherError("credential envelope has an invalid nonce")

        key = self._key_for_version(key_version)
        aad = self.build_aad(
            chama_id=chama_id,
            provider_code=provider_code,
            environment=environment,
            credential_version=credential_version,
            connection_id=connection_id,
        )
        try:
            plaintext = AESGCM(key).decrypt(nonce, ciphertext, aad)
        except (InvalidTag, ValueError) as exc:
            raise CredentialCipherError(
                "credential envelope failed authentication; the encryption key "
                "or associated data may have changed"
            ) from exc
        try:
            parsed = json.loads(plaintext.decode("utf-8"))
        except (ValueError, json.JSONDecodeError) as exc:
            raise CredentialCipherError("decrypted credential payload is malformed") from exc
        if not isinstance(parsed, dict):
            raise CredentialCipherError("decrypted credential payload is not an object")
        return parsed