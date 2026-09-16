"""CredentialCipher tests (ADR-017): roundtrip, authentication, rotation."""

import base64
import json
import uuid

import pytest

from app.core.config import Settings
from app.core.credential_cipher import CredentialCipher, CredentialCipherError
from app.models.enums import PaymentEnvironment, PaymentProviderCode


def _make_settings(key: str, *, version: int = 1, old_keys=None) -> Settings:
    return Settings(
        credential_encryption_key=key,
        credential_encryption_key_version=version,
        credential_encryption_keys=old_keys or {},
    )


def _new_key() -> str:
    return base64.b64encode(b"x" * 32).decode("ascii")


def _new_random_key() -> str:
    return base64.b64encode(uuid.uuid4().bytes * 2).decode("ascii")


def _aad(**overrides):
    base = {
        "chama_id": uuid.UUID("11111111-1111-1111-1111-111111111111"),
        "provider_code": PaymentProviderCode.JENGA,
        "environment": PaymentEnvironment.SANDBOX,
        "credential_version": 1,
        "connection_id": uuid.UUID("22222222-2222-2222-2222-222222222222"),
    }
    base.update(overrides)
    return base


class TestRoundTrip:
    def test_roundtrip_returns_identical_payload(self):
        cipher = CredentialCipher(_make_settings(_new_key()))
        payload = {"merchant_code": "M1001", "consumer_secret": "s3cr3t", "api_key": "k"}
        blob = cipher.seal(payload, **_aad())
        opened = cipher.open(blob, **_aad())
        assert opened == payload

    def test_envelope_never_contains_plaintext(self):
        cipher = CredentialCipher(_make_settings(_new_key()))
        payload = {"merchant_code": "M1001", "consumer_secret": "s3cr3t"}
        blob = cipher.seal(payload, **_aad())
        assert "s3cr3t" not in blob
        assert "M1001" not in blob

    def test_distinct_nonces_produce_distinct_blobs(self):
        cipher = CredentialCipher(_make_settings(_new_key()))
        payload = {"merchant_code": "M1001"}
        first = cipher.seal(payload, **_aad())
        second = cipher.seal(payload, **_aad())
        assert first != second
        assert cipher.open(first, **_aad()) == cipher.open(second, **_aad())


class TestAuthentication:
    def test_wrong_key_fails(self):
        cipher_a = CredentialCipher(_make_settings(_new_key()))
        blob = cipher_a.seal({"merchant_code": "M1001"}, **_aad())
        cipher_b = CredentialCipher(_make_settings(_new_random_key()))
        with pytest.raises(CredentialCipherError):
            cipher_b.open(blob, **_aad())

    def test_wrong_chama_fails(self):
        cipher = CredentialCipher(_make_settings(_new_key()))
        blob = cipher.seal({"merchant_code": "M1001"}, **_aad())
        with pytest.raises(CredentialCipherError):
            cipher.open(blob, **_aad(chama_id=uuid.UUID("99999999-9999-9999-9999-999999999999")))

    def test_wrong_connection_fails(self):
        cipher = CredentialCipher(_make_settings(_new_key()))
        blob = cipher.seal({"merchant_code": "M1001"}, **_aad())
        with pytest.raises(CredentialCipherError):
            cipher.open(blob, **_aad(connection_id=uuid.UUID("88888888-8888-8888-8888-888888888888")))

    def test_tampered_nonce_fails(self):
        cipher = CredentialCipher(_make_settings(_new_key()))
        blob = cipher.seal({"merchant_code": "M1001"}, **_aad())
        envelope = json.loads(blob)
        raw = bytearray(base64.b64decode(envelope["n"]))
        raw[0] ^= 0x01
        envelope["n"] = base64.b64encode(bytes(raw)).decode("ascii")
        blob = json.dumps(envelope)
        with pytest.raises(CredentialCipherError):
            cipher.open(blob, **_aad())

    def test_tampered_ciphertext_fails(self):
        cipher = CredentialCipher(_make_settings(_new_key()))
        blob = cipher.seal({"merchant_code": "M1001"}, **_aad())
        envelope = json.loads(blob)
        raw = bytearray(base64.b64decode(envelope["c"]))
        raw[-1] ^= 0x01
        envelope["c"] = base64.b64encode(bytes(raw)).decode("ascii")
        blob = json.dumps(envelope)
        with pytest.raises(CredentialCipherError):
            cipher.open(blob, **_aad())


class TestMalformed:
    def test_empty_blob_fails(self):
        cipher = CredentialCipher(_make_settings(_new_key()))
        with pytest.raises(CredentialCipherError):
            cipher.open("", **_aad())

    def test_non_json_blob_fails(self):
        cipher = CredentialCipher(_make_settings(_new_key()))
        with pytest.raises(CredentialCipherError):
            cipher.open("not-json", **_aad())

    def test_missing_version_key_fails_open(self):
        cipher = CredentialCipher(_make_settings(_new_key()))
        blob = cipher.seal({"merchant_code": "M1001"}, **_aad())
        envelope = json.loads(blob)
        del envelope["kv"]
        with pytest.raises(CredentialCipherError):
            cipher.open(json.dumps(envelope), **_aad())

    def test_invalid_master_key_fails_seal(self):
        cipher = CredentialCipher(_make_settings("not-base64!"))
        with pytest.raises(CredentialCipherError):
            cipher.seal({"merchant_code": "M1001"}, **_aad())


class TestRotation:
    def test_old_version_key_opens_after_rotation(self):
        key_v1 = _new_key()
        key_v2 = _new_random_key()
        old = CredentialCipher(_make_settings(key_v1, version=1))
        blob = old.seal({"merchant_code": "M1001"}, **_aad(credential_version=1))
        rotated = CredentialCipher(
            _make_settings(key_v2, version=2, old_keys={"1": key_v1})
        )
        assert rotated.open(blob, **_aad(credential_version=1)) == {"merchant_code": "M1001"}

    def test_missing_old_key_fails_open(self):
        key_v1 = _new_key()
        key_v2 = _new_random_key()
        old = CredentialCipher(_make_settings(key_v1, version=1))
        blob = old.seal({"merchant_code": "M1001"}, **_aad())
        rotated = CredentialCipher(_make_settings(key_v2, version=2, old_keys={}))
        with pytest.raises(CredentialCipherError):
            rotated.open(blob, **_aad())

    def test_replay_against_other_record_fails_after_version_change(self):
        cipher = CredentialCipher(_make_settings(_new_key()))
        blob = cipher.seal({"merchant_code": "M1001"}, **_aad(credential_version=1))
        with pytest.raises(CredentialCipherError):
            cipher.open(blob, **_aad(credential_version=2))