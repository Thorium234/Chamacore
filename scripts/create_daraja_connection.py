"""Create (and optionally validate) a Daraja payment connection via the API.

Sandbox bootstrap helper for the P2 finalization checklist: reads the same
``DARAJA_*`` variables documented in ``.env.example`` and creates a connection
for a Chama through the running ChamaCore API, so no manual copy-paste of
sealed-credential payloads is needed.

Writes nothing and stores nothing locally. Uses only the standard library.

Environment variables (see .env.example):

- ``CHAMACORE_BASE_URL``        base URL of the running API (default ``http://localhost:8000``)
- ``CHAMACORE_API_V1_PREFIX``   API prefix (default ``/api/v1``)
- ``CHAMACORE_EMAIL`` / ``CHAMACORE_PASSWORD``   chairperson/login credentials
- ``CHAMACORE_CHAMA_ID``        target Chama (or pass ``--chama-id``)
- ``DARAJA_CONSUMER_KEY`` / ``DARAJA_CONSUMER_SECRET``
- ``DARAJA_SHORT_CODE`` / ``DARAJA_PASSKEY``
- ``DARAJA_ENVIRONMENT``        ``sandbox`` (default) or ``production``

Usage::

    CHAMACORE_EMAIL=chair@example.com CHAMACORE_PASSWORD='***' \\
    CHAMACORE_CHAMA_ID=<uuid> . ./.env \\
    python scripts/create_daraja_connection.py [--validate]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"error: environment variable {name} is required", file=sys.stderr)
        sys.exit(2)
    return value


def _request_json(method: str, url: str, *, payload=None, headers=None, form: bool = False):
    data = None
    request_headers = dict(headers or {})
    if payload is not None:
        if form:
            data = urllib.parse.urlencode(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            data = json.dumps(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(
            f"error: {method} {url} returned {exc.code}\n{body[:2000]}",
            file=sys.stderr,
        )
        sys.exit(1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--chama-id",
        default=os.environ.get("CHAMACORE_CHAMA_ID", ""),
        help="target Chama UUID (or set CHAMACORE_CHAMA_ID)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="ask Daraja to validate the new connection's credentials",
    )
    args = parser.parse_args(argv)

    email = _require_env("CHAMACORE_EMAIL")
    password = _require_env("CHAMACORE_PASSWORD")
    chama_id = args.chama_id.strip()
    if not chama_id:
        print("error: --chama-id (or CHAMACORE_CHAMA_ID) is required", file=sys.stderr)
        return 2

    base_url = os.environ.get("CHAMACORE_BASE_URL", "http://localhost:8000").rstrip("/")
    prefix = os.environ.get("CHAMACORE_API_V1_PREFIX", "/api/v1").strip("/")

    environment = os.environ.get("DARAJA_ENVIRONMENT", "sandbox").strip().upper()
    if environment not in ("SANDBOX", "PRODUCTION"):
        print("error: DARAJA_ENVIRONMENT must be sandbox or production", file=sys.stderr)
        return 2
    credentials = {
        "consumer_key": _require_env("DARAJA_CONSUMER_KEY"),
        "consumer_secret": _require_env("DARAJA_CONSUMER_SECRET"),
        "short_code": _require_env("DARAJA_SHORT_CODE"),
        "passkey": _require_env("DARAJA_PASSKEY"),
    }

    token = _request_json(
        "POST",
        f"{base_url}/{prefix}/auth/token",
        form=True,
        payload={
            "grant_type": "password",
            "username": email,
            "password": password,
            "scope": "",
        },
    ).get("access_token")
    if not token:
        print("error: auth token endpoint returned no access_token", file=sys.stderr)
        return 1
    auth = {"Authorization": f"Bearer {token}"}

    connection = _request_json(
        "POST",
        f"{base_url}/{prefix}/chamas/{chama_id}/payment-connections",
        payload={
            "provider_code": "DARAJA",
            "environment": environment,
            "credentials": credentials,
        },
        headers=auth,
    )
    connection_id = connection.get("id")
    print(f"created payment connection {connection_id} ({environment})")

    if args.validate:
        validated = _request_json(
            "POST",
            f"{base_url}/{prefix}/chamas/{chama_id}/payment-connections/"
            f"{connection_id}/validate",
            headers=auth,
        )
        print(json.dumps(validated, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())